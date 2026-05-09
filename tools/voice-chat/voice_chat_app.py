#!/usr/bin/env python3
"""
适用机器：公司（Linux）
系统 / OS：Linux
用途：浏览器录音 -> NVIDIA ASR -> OpenClaw agent -> ChatTTS stable 的本地语音对话 MVP。

说明：
- 这是一条“按下录音、松开后几秒内回你”的半双工链路，不是 full duplex 实时打断式通话。
- 默认使用独立 voice session，避免把当前文字主会话刷满测试消息。
- ASR 依赖本机 NVIDIA audio bridge（默认 http://127.0.0.1:18890）。
- TTS 依赖已封装好的 ChatTTS stable 入口。
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import time
import urllib.error
import urllib.request
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse

BASE_DIR = Path(__file__).resolve().parent
WORKSPACE_DIR = BASE_DIR.parent.parent
TMP_DIR = WORKSPACE_DIR / "tmp" / "voice-chat"
OUTPUT_DIR = TMP_DIR / "outputs"
STATE_PATH = TMP_DIR / "voice-session.json"
INDEX_PATH = BASE_DIR / "index.html"
PRESETS_PATH = WORKSPACE_DIR / "skills" / "chattts-stable" / "assets" / "presets.json"
CHATTTTS_WRAPPER = WORKSPACE_DIR / "tools" / "voice-reply" / "chattts-stable.sh"
OPENCLAW_BIN = shutil.which("openclaw") or "openclaw"
NVIDIA_BRIDGE_URL = os.environ.get("OPENCLAW_NVIDIA_AUDIO_BRIDGE_URL", "http://127.0.0.1:18890").rstrip("/")
VOICE_SESSION_KEY = os.environ.get("OPENCLAW_VOICE_SESSION_KEY", "agent:main:voice-chat")
VOICE_SESSION_LABEL = os.environ.get("OPENCLAW_VOICE_SESSION_LABEL", "实时语音对话")
DEFAULT_HOST = os.environ.get("OPENCLAW_VOICE_CHAT_HOST", "127.0.0.1")
DEFAULT_PORT = int(os.environ.get("OPENCLAW_VOICE_CHAT_PORT", "18891"))
DEFAULT_LANGUAGE = os.environ.get("OPENCLAW_VOICE_CHAT_LANGUAGE", "zh-CN")
DEFAULT_TTS_MAX_NEW_TOKEN = int(os.environ.get("OPENCLAW_VOICE_CHAT_TTS_MAX_NEW_TOKEN", "384"))
DEFAULT_ASR_MODEL = os.environ.get("OPENCLAW_VOICE_CHAT_ASR_MODEL", "nvidia/whisper-large-v3")
AGENT_TIMEOUT_SECONDS = int(os.environ.get("OPENCLAW_VOICE_CHAT_AGENT_TIMEOUT", "300"))
AGENT_MAX_TOKENS = int(os.environ.get("OPENCLAW_VOICE_CHAT_AGENT_MAX_TOKENS", "120"))
ASR_TIMEOUT_SECONDS = int(os.environ.get("OPENCLAW_VOICE_CHAT_ASR_TIMEOUT", "180"))
SESSION_CREATE_TIMEOUT_SECONDS = int(os.environ.get("OPENCLAW_VOICE_CHAT_SESSION_TIMEOUT", "60"))
KEEP_AUDIO_FILES = int(os.environ.get("OPENCLAW_VOICE_CHAT_KEEP_AUDIO_FILES", "24"))

TMP_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="OpenClaw Voice Chat MVP", version="0.1.0")


ANSI_RE = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")


def load_presets() -> dict[str, Any]:
    return json.loads(PRESETS_PATH.read_text(encoding="utf-8"))


def default_preset_name() -> str:
    return str(load_presets().get("defaultPreset") or "default")


def default_tempo() -> float:
    try:
        return float(load_presets().get("defaultTempo") or 1.15)
    except Exception:
        return 1.15


def strip_ansi(text: str) -> str:
    return ANSI_RE.sub("", text or "")


def try_parse_json(raw: str) -> Any:
    raw = strip_ansi((raw or "").strip())
    if not raw:
        return None
    try:
        return json.loads(raw)
    except Exception:
        pass
    start = raw.find("{")
    end = raw.rfind("}")
    if start != -1 and end != -1 and end > start:
        candidate = raw[start:end + 1]
        try:
            return json.loads(candidate)
        except Exception:
            return None
    return None


def run_command(cmd: list[str], timeout: int) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            cmd,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout,
            encoding="utf-8",
            errors="replace",
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=500, detail=f"命令不存在：{cmd[0]}") from exc
    except subprocess.TimeoutExpired as exc:
        raise HTTPException(status_code=504, detail=f"命令执行超时：{' '.join(cmd)}") from exc


def load_state() -> dict[str, Any] | None:
    if not STATE_PATH.exists():
        return None
    try:
        return json.loads(STATE_PATH.read_text(encoding="utf-8"))
    except Exception:
        return None



def save_state(payload: dict[str, Any]) -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")



def delete_state() -> None:
    if STATE_PATH.exists():
        STATE_PATH.unlink()



def create_voice_session() -> dict[str, Any]:
    payload = json.dumps({
        "key": VOICE_SESSION_KEY,
        "label": VOICE_SESSION_LABEL,
        "task": "你是语音助手，请用极简短的中文回复，每句不超过20字，总共不超过50字。只说最核心的内容，不用客套话、不用解释、不用列举。直接说。",
    }, ensure_ascii=False)
    proc = run_command(
        [OPENCLAW_BIN, "gateway", "call", "sessions.create", "--json", "--params", payload],
        timeout=SESSION_CREATE_TIMEOUT_SECONDS,
    )
    if proc.returncode != 0:
        detail = strip_ansi(proc.stderr or proc.stdout or "sessions.create 失败").strip()
        raise HTTPException(status_code=502, detail=f"创建语音会话失败：{detail}")
    data = try_parse_json(proc.stdout)
    if not isinstance(data, dict):
        raise HTTPException(status_code=502, detail=f"sessions.create 返回无法解析：{proc.stdout[:500]}")
    session_id = data.get("sessionId") or data.get("id") or data.get("session_id")
    if not session_id:
        raise HTTPException(status_code=502, detail=f"sessions.create 未返回 sessionId：{json.dumps(data, ensure_ascii=False)[:500]}")
    state = {
        "sessionId": session_id,
        "key": data.get("key") or VOICE_SESSION_KEY,
        "label": data.get("label") or VOICE_SESSION_LABEL,
        "createdAt": datetime.now().isoformat(timespec="seconds"),
    }
    save_state(state)
    return state



def ensure_voice_session(force_recreate: bool = False) -> dict[str, Any]:
    if not force_recreate:
        state = load_state()
        if isinstance(state, dict) and state.get("sessionId"):
            return state
    return create_voice_session()



def extract_text_from_content(content: Any) -> str:
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, dict):
        if isinstance(content.get("text"), str) and content.get("text", "").strip():
            return content["text"].strip()
        for key in ("content", "message", "assistant", "response", "reply", "result", "final"):
            if key in content:
                text = extract_text_from_content(content[key])
                if text:
                    return text
        return ""
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, dict):
                if item.get("type") in {"text", "output_text", "message_text", "assistant_text"} and isinstance(item.get("text"), str):
                    text = item["text"].strip()
                    if text:
                        parts.append(text)
                        continue
                nested = extract_text_from_content(item)
                if nested:
                    parts.append(nested)
            elif isinstance(item, str):
                text = item.strip()
                if text:
                    parts.append(text)
        return "\n".join(part for part in parts if part).strip()
    return ""



def extract_agent_text(payload: Any) -> str:
    if isinstance(payload, str):
        return payload.strip()
    if isinstance(payload, list):
        for item in reversed(payload):
            text = extract_agent_text(item)
            if text:
                return text
        return ""
    if not isinstance(payload, dict):
        return ""

    for key in (
        "finalAssistantVisibleText",
        "finalAssistantRawText",
        "assistantVisibleText",
        "assistantRawText",
        "assistantText",
    ):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()

    for key in ("result", "response", "payload", "data"):
        if key in payload:
            text = extract_agent_text(payload[key])
            if text:
                return text

    messages = payload.get("messages")
    if isinstance(messages, list):
        for item in reversed(messages):
            if isinstance(item, dict) and item.get("role") == "assistant":
                text = extract_text_from_content(item.get("content") or item)
                if text:
                    return text

    for key in ("assistant", "reply", "final", "message", "content", "text"):
        if key in payload:
            text = extract_text_from_content(payload[key])
            if text:
                return text

    for value in payload.values():
        text = extract_agent_text(value)
        if text:
            return text
    return ""



def ask_openclaw(text: str, *, recreate_once: bool = True) -> dict[str, Any]:
    state = ensure_voice_session()
    cmd = [
        OPENCLAW_BIN,
        "agent",
        "--session-id",
        str(state["sessionId"]),
        "--message",
        text,
        "--json",
    ]
    proc = run_command(cmd, timeout=AGENT_TIMEOUT_SECONDS)
    if proc.returncode != 0:
        detail = strip_ansi(proc.stderr or proc.stdout or "openclaw agent 失败").strip()
        if recreate_once and ("session" in detail.lower() or "not found" in detail.lower()):
            delete_state()
            ensure_voice_session(force_recreate=True)
            return ask_openclaw(text, recreate_once=False)
        raise HTTPException(status_code=502, detail=f"OpenClaw agent 调用失败：{detail}")

    data = try_parse_json(proc.stdout)
    reply_text = extract_agent_text(data) if data is not None else ""
    if not reply_text:
        raw = strip_ansi(proc.stdout).strip()
        if raw and not raw.startswith("{"):
            reply_text = raw
    if not reply_text:
        raise HTTPException(status_code=502, detail=f"未能从 OpenClaw agent 输出中提取回复文本：{proc.stdout[:500]}")
    return {
        "session": state,
        "replyText": reply_text,
        "raw": data if data is not None else strip_ansi(proc.stdout).strip(),
    }



def encode_multipart_form(fields: dict[str, str], files: list[tuple[str, str, bytes, str]]) -> tuple[bytes, str]:
    boundary = f"----OpenClawVoice{uuid.uuid4().hex}"
    body = bytearray()
    for name, value in fields.items():
        body.extend(f"--{boundary}\r\n".encode())
        body.extend(f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode())
        body.extend(str(value).encode("utf-8"))
        body.extend(b"\r\n")
    for field_name, filename, content, content_type in files:
        body.extend(f"--{boundary}\r\n".encode())
        body.extend(f'Content-Disposition: form-data; name="{field_name}"; filename="{filename}"\r\n'.encode())
        body.extend(f"Content-Type: {content_type}\r\n\r\n".encode())
        body.extend(content)
        body.extend(b"\r\n")
    body.extend(f"--{boundary}--\r\n".encode())
    return bytes(body), boundary



def transcribe_audio(filename: str, audio_bytes: bytes, *, language: str, model: str) -> dict[str, Any]:
    content_type = "audio/webm"
    suffix = Path(filename or "audio.webm").suffix.lower()
    if suffix == ".wav":
        content_type = "audio/wav"
    elif suffix == ".mp3":
        content_type = "audio/mpeg"
    elif suffix in {".m4a", ".mp4"}:
        content_type = "audio/mp4"
    elif suffix in {".ogg", ".opus"}:
        content_type = "audio/ogg"

    fields = {
        "model": model,
        "language": language,
        "response_format": "verbose_json",
    }
    body, boundary = encode_multipart_form(
        fields,
        [("file", filename or "audio.webm", audio_bytes, content_type)],
    )
    req = urllib.request.Request(
        f"{NVIDIA_BRIDGE_URL}/v1/audio/transcriptions",
        data=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=ASR_TIMEOUT_SECONDS) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise HTTPException(status_code=502, detail=f"NVIDIA ASR bridge 返回错误：{detail}") from exc
    except urllib.error.URLError as exc:
        raise HTTPException(status_code=502, detail=f"无法连接 NVIDIA ASR bridge：{exc}") from exc

    payload = try_parse_json(raw)
    if not isinstance(payload, dict):
        raise HTTPException(status_code=502, detail=f"ASR 返回无法解析：{raw[:500]}")
    text = str(payload.get("text") or "").strip()
    if not text:
        raise HTTPException(status_code=422, detail=f"ASR 未识别出文本：{json.dumps(payload, ensure_ascii=False)[:500]}")
    return payload



def clean_voice_text(text: str) -> str:
    """Clean agent reply text for better TTS output.

    Removes markdown symbols, parentheses notations, repetitive structures,
    and keeps text concise and natural for voice rendering.
    """
    t = text.strip()
    # Remove markdown: **bold**, *italic*, `code`, ```, [links](), images, headings, lists
    t = re.sub(r"(\*\*|__)(.*?)\1", r"\2", t)
    t = re.sub(r"(\*|_)(.*?)\1", r"\2", t)
    t = re.sub(r"```[\s\S]*?```", "", t)
    t = re.sub(r"`([^`]+)`", r"\1", t)
    t = re.sub(r"\[([^]]+)\]\([^)]+\)", r"\1", t)
    t = re.sub(r"^#{1,6}\s+", "", t, flags=re.MULTILINE)
    t = re.sub(r"^[-*+]\s+", "", t, flags=re.MULTILINE)
    t = re.sub(r"^\d+\.\s+", "", t, flags=re.MULTILINE)
    # Remove parenthetical stage directions like （笑）、（无奈）、（叹气）
    t = re.sub(r"[（\(][^）\)]*[）\)]", "", t)
    # Remove common AI filler phrases (at start and standalone)
    t = re.sub(r"^(嗯[，,]|好的[，,]|好[的，]?|没问题[，,]|当然[，,]|明白[，,]|知道了[，,]|没错[，,]|对[的，]?)+", "", t)
    t = re.sub(r"(，嗯|。嗯)[，,]", "，", t)
    # Replace ... and — with natural sentence breaks
    t = t.replace("…", "。").replace("...", "。").replace("——", "，")
    # Remove excessive punctuation sequences
    t = re.sub(r"[！!？?。，,]{2,}", lambda m: m.group(0)[0], t)
    # Collapse multiple whitespace / newlines
    t = re.sub(r"\n{2,}", "\n", t)
    t = re.sub(r"\s{2,}", " ", t)
    t = t.strip()
    # Truncate very long replies to ~120 chars for voice (keeps TTS under ~8s)
    if len(t) > 120:
        # Try to break at sentence boundary
        break_at = t.rfind("。", 0, 120)
        if break_at > 30:
            t = t[:break_at + 1]
        else:
            break_at = t.rfind("，", 0, 120)
            if break_at > 30:
                t = t[:break_at + 1] + "。"
            else:
                t = t[:117] + "。"
    return t


def cleanup_outputs() -> None:
    files = sorted(OUTPUT_DIR.glob("*.mp3"), key=lambda p: p.stat().st_mtime, reverse=True)
    for stale in files[KEEP_AUDIO_FILES:]:
        try:
            stale.unlink()
        except Exception:
            pass



def synthesize_reply(text: str, *, preset: str, tempo: float, max_new_token: int | None = None) -> Path:
    text = clean_voice_text(text)
    cleanup_outputs()
    output_path = OUTPUT_DIR / f"voice-chat-reply-{datetime.now().strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:8]}.mp3"
    cmd = [
        "bash",
        str(CHATTTTS_WRAPPER),
        "--preset",
        preset,
        "--tempo",
        str(tempo),
        "--max-new-token",
        str(max_new_token if max_new_token is not None else DEFAULT_TTS_MAX_NEW_TOKEN),
        "--text",
        text,
        "--out",
        str(output_path),
    ]
    proc = run_command(cmd, timeout=AGENT_TIMEOUT_SECONDS)
    if proc.returncode != 0 or not output_path.exists():
        detail = strip_ansi(proc.stderr or proc.stdout or "ChatTTS stable 渲染失败").strip()
        raise HTTPException(status_code=502, detail=f"ChatTTS stable 渲染失败：{detail}")
    return output_path



def presets_for_api() -> list[dict[str, Any]]:
    cfg = load_presets()
    items = []
    for name, meta in (cfg.get("presets") or {}).items():
        items.append({
            "name": name,
            "label": meta.get("label") or name,
            "mode": meta.get("mode") or "spk-emb",
            "aliases": meta.get("aliases") or [],
            "default": name == cfg.get("defaultPreset"),
        })
    return items



def probe_bridge() -> dict[str, Any]:
    req = urllib.request.Request(f"{NVIDIA_BRIDGE_URL}/health", method="GET")
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": str(exc)}
    payload = try_parse_json(raw)
    if isinstance(payload, dict):
        return payload
    return {"ok": False, "raw": raw[:200]}


@app.get("/", response_class=HTMLResponse)
def index() -> str:
    return INDEX_PATH.read_text(encoding="utf-8")


@app.get("/api/health")
def health() -> dict[str, Any]:
    return {
        "ok": True,
        "service": "openclaw-voice-chat-mvp",
        "bridge": probe_bridge(),
        "session": load_state(),
        "presets": presets_for_api(),
        "defaultPreset": default_preset_name(),
        "defaultTempo": default_tempo(),
        "outputCount": len(list(OUTPUT_DIR.glob("*.mp3"))),
    }


@app.get("/api/presets")
def presets() -> dict[str, Any]:
    return {
        "defaultPreset": default_preset_name(),
        "defaultTempo": default_tempo(),
        "presets": presets_for_api(),
    }


@app.post("/api/session/reset")
def reset_session() -> dict[str, Any]:
    delete_state()
    state = ensure_voice_session(force_recreate=True)
    return {"ok": True, "session": state}


@app.post("/api/text-turn")
def text_turn(
    text: str = Form(...),
    preset: str | None = Form(None),
    tempo: float | None = Form(None),
) -> JSONResponse:
    clean_text = (text or "").strip()
    if not clean_text:
        raise HTTPException(status_code=400, detail="文本不能为空。")
    chosen_preset = (preset or default_preset_name()).strip()
    chosen_tempo = float(tempo if tempo is not None else default_tempo())

    t0 = time.perf_counter()
    agent = ask_openclaw(clean_text)
    t1 = time.perf_counter()
    audio_path = synthesize_reply(agent["replyText"], preset=chosen_preset, tempo=chosen_tempo)
    t2 = time.perf_counter()

    return JSONResponse({
        "ok": True,
        "mode": "text-turn",
        "transcript": clean_text,
        "replyText": agent["replyText"],
        "audioUrl": f"/audio/{audio_path.name}",
        "session": agent["session"],
        "latencyMs": {
            "agent": round((t1 - t0) * 1000),
            "tts": round((t2 - t1) * 1000),
            "total": round((t2 - t0) * 1000),
        },
    })


@app.post("/api/turn")
async def audio_turn(
    file: UploadFile = File(...),
    preset: str | None = Form(None),
    tempo: float | None = Form(None),
    language: str = Form(DEFAULT_LANGUAGE),
    model: str = Form(DEFAULT_ASR_MODEL),
) -> JSONResponse:
    audio_bytes = await file.read()
    if not audio_bytes:
        raise HTTPException(status_code=400, detail="上传音频为空。")
    chosen_preset = (preset or default_preset_name()).strip()
    chosen_tempo = float(tempo if tempo is not None else default_tempo())

    t0 = time.perf_counter()
    asr_payload = transcribe_audio(file.filename or "audio.webm", audio_bytes, language=language, model=model)
    transcript = str(asr_payload.get("text") or "").strip()
    t1 = time.perf_counter()
    agent = ask_openclaw(transcript)
    t2 = time.perf_counter()
    audio_path = synthesize_reply(agent["replyText"], preset=chosen_preset, tempo=chosen_tempo)
    t3 = time.perf_counter()

    return JSONResponse({
        "ok": True,
        "mode": "audio-turn",
        "transcript": transcript,
        "replyText": agent["replyText"],
        "audioUrl": f"/audio/{audio_path.name}",
        "session": agent["session"],
        "asr": {
            "modelUsed": asr_payload.get("model") or asr_payload.get("model_used") or model,
            "language": asr_payload.get("language") or language,
            "sampleRateHz": asr_payload.get("sample_rate_hz"),
        },
        "latencyMs": {
            "asr": round((t1 - t0) * 1000),
            "agent": round((t2 - t1) * 1000),
            "tts": round((t3 - t2) * 1000),
            "total": round((t3 - t0) * 1000),
        },
    })


@app.get("/audio/{name}")
def audio_file(name: str) -> FileResponse:
    safe_name = Path(name).name
    path = OUTPUT_DIR / safe_name
    if not path.exists() or path.is_dir():
        raise HTTPException(status_code=404, detail="音频不存在。")
    return FileResponse(path, media_type="audio/mpeg", filename=path.name)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "voice_chat_app:app",
        host=DEFAULT_HOST,
        port=DEFAULT_PORT,
        reload=False,
    )
