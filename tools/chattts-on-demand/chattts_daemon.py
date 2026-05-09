#!/usr/bin/env python3
"""
ChatTTS on-demand daemon.
Loads the model once, keeps it warm, and serves TTS requests via Unix socket.

Architecture:
  - Single-threaded, serial request processing (ChatTTS is not thread-safe for GPU)
  - Accepts requests on a Unix domain socket (JSON-line protocol)
  - After IDLE_TIMEOUT seconds of no requests, exits gracefully
  - Unix socket path: ~/.openclaw/workspace/tmp/.chattts-daemon.sock

Usage (via chattts-daemon.sh, not directly):
  Request:  {"text": "...", "out": "/path/to/output.wav", "preset": "default", "tempo": 1.15}
  Response: {"ok": true, "path": "/path/to/output.wav"}
             {"ok": false, "error": "..."}

Design constraints:
  - NOT a persistent service; auto-exits on idle timeout.
  - CPU-only (CUDA not available on this machine).
  - Single request at a time; subsequent requests queue up.
  - Memory footprint: ~1.5-2GB while loaded (ChatTTS model in memory).
"""

import argparse
import asyncio
import json
import logging
import os
import signal
import sys
import tempfile
import time
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")

# ── Paths ──────────────────────────────────────────────────────────────────
WORKSPACE = Path.home() / ".openclaw" / "workspace"
SOCKET_DIR = WORKSPACE / "tmp"
SOCKET_PATH = SOCKET_DIR / ".chattts-daemon.sock"
LOCK_FILE = SOCKET_DIR / ".chattts-daemon.lock"
PID_FILE = SOCKET_DIR / ".chattts-daemon.pid"

VENV_PYTHON = Path.home() / ".local/share/openclaw-voice-venv311/bin/python3"
SITE_PKGS = Path.home() / ".local/share/openclaw-voice-venv311/lib/python3.11/site-packages"
SKILL_SCRIPT = WORKSPACE / "skills" / "chattts-stable" / "scripts" / "chattts_stable.py"
ASSET_DIR = WORKSPACE / "tmp" / "voice-replies" / "chattts-hybrid"
ASSETS = WORKSPACE / "skills" / "chattts-stable" / "assets"
PRESETS_FILE = ASSETS / "presets.json"

# Ensure socket dir exists
SOCKET_DIR.mkdir(parents=True, exist_ok=True)

# ── Runtime globals (set after fork) ───────────────────────────────────────
chat = None          # ChatTTS instance
device = None        # torch device
config = None        # preset config
last_request_time = 0.0
current_preset_name = "default"
current_spk_emb = None

# ── Logging ──────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="[chattts-daemon] %(asctime)s %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("chattts-daemon")


# ── Patch ChatTTS runtime (same as chattts_stable.py) ──────────────────
def patch_chattts_runtime() -> None:
    import torch
    import ChatTTS.utils.dl as dl_mod
    import ChatTTS.model.dvae as dvae_mod
    import ChatTTS.model.tokenizer as tokenizer_mod

    def always_pass(*args, **kwargs):
        return True
    dl_mod.check_all_assets = always_pass
    dl_mod.check_model = always_pass
    dl_mod.check_folder = always_pass

    orig_dvae_load = dvae_mod.DVAE.load_state_dict
    def patched_dvae_load(self, state_dict, strict=True, assign=False):
        return orig_dvae_load(self, state_dict, strict=False, assign=assign)
    dvae_mod.DVAE.load_state_dict = patched_dvae_load

    orig_decoder_load = dvae_mod.DVAEDecoder.load_state_dict
    def patched_decoder_load(self, state_dict, strict=True, assign=False):
        return orig_decoder_load(self, state_dict, strict=False, assign=assign)
    dvae_mod.DVAEDecoder.load_state_dict = patched_decoder_load

    orig_encode = tokenizer_mod.Tokenizer.encode

    def patched_encode(self, text, num_vq, prompt=None, device='cpu'):
        import torch as _torch
        input_ids_lst = []
        attention_mask_lst = []
        max_input_ids_len = -1
        max_attention_mask_len = -1
        prompt_size = 0
        if prompt is not None:
            assert prompt.size(0) == num_vq, 'prompt dim 0 must equal to num_vq'
            prompt_size = prompt.size(1)
        for t in text:
            x = self._tokenizer(t, return_tensors='pt', add_special_tokens=False, padding=True)
            input_ids_lst.append(x['input_ids'].squeeze_(0))
            attention_mask_lst.append(x['attention_mask'].squeeze_(0))
            ids_sz = input_ids_lst[-1].size(0)
            if ids_sz > max_input_ids_len:
                max_input_ids_len = ids_sz
            attn_sz = attention_mask_lst[-1].size(0)
            if attn_sz > max_attention_mask_len:
                max_attention_mask_len = attn_sz
        if prompt is not None:
            max_input_ids_len += prompt_size
            max_attention_mask_len += prompt_size
        input_ids = _torch.zeros(len(input_ids_lst), max_input_ids_len, device=device, dtype=input_ids_lst[0].dtype)
        for i in range(len(input_ids_lst)):
            input_ids.narrow(0, i, 1).narrow(1, max_input_ids_len - prompt_size - input_ids_lst[i].size(0), input_ids_lst[i].size(0)).copy_(input_ids_lst[i])
        attention_mask = _torch.zeros(len(attention_mask_lst), max_attention_mask_len, device=device, dtype=attention_mask_lst[0].dtype)
        for i in range(len(attention_mask_lst)):
            attn = attention_mask.narrow(0, i, 1)
            attn.narrow(1, max_attention_mask_len - prompt_size - attention_mask_lst[i].size(0), attention_mask_lst[i].size(0)).copy_(attention_mask_lst[i])
            if prompt_size > 0:
                attn.narrow(1, max_attention_mask_len - prompt_size, prompt_size).fill_(1)
        text_mask = attention_mask.bool()
        new_input_ids = input_ids.unsqueeze_(-1).expand(-1, -1, num_vq).clone()
        del input_ids
        if prompt_size > 0:
            text_mask.narrow(1, max_input_ids_len - prompt_size, prompt_size).fill_(0)
            prompt_t = prompt.t().unsqueeze_(0).expand(new_input_ids.size(0), -1, -1)
            new_input_ids.narrow(1, max_input_ids_len - prompt_size, prompt_size).copy_(prompt_t)
            del prompt_t
        return new_input_ids, attention_mask, text_mask

    tokenizer_mod.Tokenizer.encode = patched_encode


# ── Model loading (one-shot) ──────────────────────────────────────────────
def load_model() -> bool:
    global chat, device

    log.info("Loading ChatTTS model (cold start)...")
    t0 = time.time()

    patch_chattts_runtime()
    import ChatTTS
    import torch

    device = torch.device("cpu")
    chat = ChatTTS.Chat()
    chat.logger.setLevel(logging.WARNING)

    result = chat.load(
        source="custom",
        custom_path=str(ASSET_DIR),
        device=device,
        compile=False,
        use_flash_attn=False,
    )
    elapsed = time.time() - t0
    if result:
        log.info(f"Model loaded in {elapsed:.1f}s")
    else:
        log.error(f"Model load FAILED after {elapsed:.1f}s")
    return result


# ── Load preset config ────────────────────────────────────────────────────
def load_preset_config() -> dict:
    if PRESETS_FILE.exists():
        with open(PRESETS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"presets": {}, "defaultPreset": "default", "defaultTempo": 1.0}


def resolve_spk_emb(preset_name: str) -> str | None:
    """Resolve speaker embedding for a given preset name."""
    if not config:
        return None
    presets = config.get("presets", {})
    preset = presets.get(preset_name)
    if not preset:
        return None
    spk_file = preset.get("spkEmbFile")
    if spk_file:
        path = ASSETS / spk_file
        if path.exists():
            return path.read_text(encoding="utf-8").strip()
    return None


# ── Synthesize (uses pre-loaded chat) ─────────────────────────────────────
def synthesize(text: str, out_path: str, preset: str = "default",
               tempo: float = 1.0, temperature: float = 0.3,
               top_p: float = 0.7, top_k: int = 20,
               max_new_token: int = 384) -> str:
    global last_request_time, current_preset_name, current_spk_emb

    import subprocess as _subprocess
    import numpy as np
    import soundfile as sf

    last_request_time = time.time()

    # Update speaker embedding if preset changed
    if preset != current_preset_name:
        current_preset_name = preset
        current_spk_emb = resolve_spk_emb(preset)
        if current_spk_emb:
            log.info(f"Switched to preset '{preset}' with custom spk_emb")
        else:
            log.info(f"Switched to preset '{preset}' (model-default)")

    log.info(f"Synthesizing: {text[:60]}{'...' if len(text) > 60 else ''}")

    t0 = time.time()
    params = chat.InferCodeParams(
        temperature=temperature,
        top_P=top_p,
        top_K=top_k,
        max_new_token=max_new_token,
        spk_emb=current_spk_emb or None,
    )
    wavs = chat.infer(
        [text],
        skip_refine_text=True,
        use_decoder=True,
        do_text_normalization=False,
        do_homophone_replacement=False,
        params_infer_code=params,
    )
    infer_time = time.time() - t0
    log.info(f"Inference done in {infer_time:.1f}s")

    # Save wav
    wav = wavs[0] if isinstance(wavs, list) else wavs
    if isinstance(wav, np.ndarray) and wav.ndim > 1:
        wav = wav[0]

    final_path = Path(out_path)
    final_path.parent.mkdir(parents=True, exist_ok=True)

    # Write raw audio to a UNIQUE temp WAV (avoids ffmpeg src==dst conflict)
    import tempfile as _tf
    raw_wav = _tf.NamedTemporaryFile(suffix=".chattts-raw.wav", delete=False)
    raw_wav_path = Path(raw_wav.name)
    raw_wav.close()
    sf.write(str(raw_wav_path), wav, 24000)

    ffmpeg = _find_ffmpeg()

    def _convert_with_ffmpeg(src, dst, atempo=None):
        cmd = [ffmpeg, "-y", "-i", str(src)]
        if atempo:
            cmd += ["-af", _build_atempo_filter(atempo)]
        if dst.suffix == ".mp3":
            cmd += ["-acodec", "libmp3lame", "-b:a", "160k"]
        cmd.append(str(dst))
        _subprocess.run(cmd, check=True, stdout=_subprocess.DEVNULL, stderr=_subprocess.DEVNULL)

    try:
        if abs(tempo - 1.0) >= 1e-6 and ffmpeg:
            _convert_with_ffmpeg(raw_wav_path, final_path, atempo=tempo)
        elif final_path.suffix == ".mp3":
            if ffmpeg:
                _convert_with_ffmpeg(raw_wav_path, final_path)
            else:
                final_path = final_path.with_suffix(".wav")
                raw_wav_path.rename(final_path)
        else:
            raw_wav_path.rename(final_path)
    finally:
        # Clean up temp file if still on disk (e.g. ffmpeg left it behind)
        if raw_wav_path.exists():
            raw_wav_path.unlink(missing_ok=True)

    total_time = time.time() - t0
    log.info(f"Output saved to {final_path} (total {total_time:.1f}s)")
    return str(final_path)


def _find_ffmpeg() -> str | None:
    import shutil
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg:
        return ffmpeg
    candidates = [
        Path("/usr/bin/ffmpeg"),
        Path("/usr/local/bin/ffmpeg"),
        Path.home() / ".local/share/openclaw-audio-tools/node_modules/@ffmpeg-installer/linux-x64/ffmpeg",
        Path.home() / ".local/share/openclaw-voice-venv311/ffmpeg",
    ]
    for c in candidates:
        if c.exists():
            return str(c)
    return None


def _build_atempo_filter(tempo: float) -> str:
    if tempo <= 0:
        return "atempo=1.0"
    factors = []
    remaining = tempo
    while remaining > 2.0:
        factors.append(2.0)
        remaining /= 2.0
    while remaining < 0.5:
        factors.append(0.5)
        remaining /= 0.5
    factors.append(remaining)
    return ",".join(f"atempo={f:.6f}" for f in factors)


# ── Unix socket server ──────────────────────────────────────────────────
async def handle_client(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
    """Handle one client: read a JSON line, process, write JSON line response."""
    global last_request_time

    try:
        data = await asyncio.wait_for(reader.readline(), timeout=30.0)
        if not data:
            writer.close()
            return

        request = json.loads(data.decode("utf-8").strip())
        text = request.get("text", "")
        out_path = request.get("out", "")
        preset = request.get("preset", config.get("defaultPreset", "default"))
        tempo = float(request.get("tempo", config.get("defaultTempo", 1.0)))
        temperature = float(request.get("temperature", 0.3))
        top_p = float(request.get("top_p", 0.7))
        top_k = int(request.get("top_k", 20))
        max_new_token = int(request.get("max_new_token", 384))

        if not text:
            response = {"ok": False, "error": "Missing 'text' field"}
            writer.write((json.dumps(response, ensure_ascii=False) + "\n").encode("utf-8"))
            await writer.drain()
            writer.close()
            return

        if not out_path:
            # Generate temp path
            ts = time.strftime("%Y%m%d-%H%M%S")
            out_path = str(WORKSPACE / "tmp/voice-replies" / f"chattts-ondemand-{ts}.mp3")

        try:
            final_path = synthesize(
                text=text, out_path=out_path,
                preset=preset, tempo=tempo,
                temperature=temperature, top_p=top_p,
                top_k=top_k, max_new_token=max_new_token,
            )
            response = {"ok": True, "path": final_path}
        except Exception as e:
            log.exception("Synthesis failed")
            response = {"ok": False, "error": str(e)}

        writer.write((json.dumps(response, ensure_ascii=False) + "\n").encode("utf-8"))
        await writer.drain()

    except asyncio.TimeoutError:
        response = {"ok": False, "error": "Timeout reading request"}
        try:
            writer.write((json.dumps(response, ensure_ascii=False) + "\n").encode("utf-8"))
            await writer.drain()
        except Exception:
            pass
    except json.JSONDecodeError:
        response = {"ok": False, "error": "Invalid JSON"}
        try:
            writer.write((json.dumps(response, ensure_ascii=False) + "\n").encode("utf-8"))
            await writer.drain()
        except Exception:
            pass
    except Exception as e:
        log.exception("Client handler error")
        try:
            response = {"ok": False, "error": str(e)}
            writer.write((json.dumps(response, ensure_ascii=False) + "\n").encode("utf-8"))
            await writer.drain()
        except Exception:
            pass
    finally:
        try:
            writer.close()
        except Exception:
            pass


async def idle_timeout_watcher(idle_timeout: float, server: asyncio.AbstractServer) -> None:
    """Monitor idle time; exit after idle_timeout seconds without requests."""
    global last_request_time
    last_request_time = time.time()  # initialized on first request

    # Check every 10s (responsive enough for 300s timeout; set lower for testing)
    while True:
        await asyncio.sleep(10)
        elapsed = time.time() - last_request_time
        if elapsed >= idle_timeout:
            log.info(f"Idle for {elapsed:.0f}s ({idle_timeout}s timeout). Exiting.")
            server.close()
            _cleanup_all_artifacts()
            # Force exit (the asyncio event loop will stop)
            os._exit(0)


def cleanup_stale_socket() -> None:
    """Remove stale socket and lock files."""
    if SOCKET_PATH.exists():
        log.info("Removing stale socket file")
        SOCKET_PATH.unlink(missing_ok=True)
    if LOCK_FILE.exists():
        log.info("Removing stale lock file")
        LOCK_FILE.unlink(missing_ok=True)


def _cleanup_all_artifacts() -> None:
    """Remove all daemon artifacts: socket, lock, and PID files."""
    log.info("Cleaning up all daemon artifacts")
    for p in [SOCKET_PATH, LOCK_FILE, PID_FILE]:
        try:
            if p.exists():
                p.unlink(missing_ok=True)
        except Exception:
            pass


async def main_async(idle_timeout: int) -> None:
    global config
    config = load_preset_config()
    cleanup_stale_socket()

    if not load_model():
        log.error("Failed to load ChatTTS model. Exiting.")
        sys.exit(1)

    log.info(f"Starting Unix socket server at {SOCKET_PATH}")
    log.info(f"Idle timeout: {idle_timeout}s")
    log.info(f"Default preset: {config.get('defaultPreset', 'default')}")
    log.info(f"Default tempo: {config.get('defaultTempo', 1.0)}")

    server = await asyncio.start_unix_server(handle_client, path=str(SOCKET_PATH))
    os.chmod(str(SOCKET_PATH), 0o666)  # Allow any user to connect

    # Start idle timeout watcher
    asyncio.create_task(idle_timeout_watcher(idle_timeout, server))

    log.info("Daemon ready. Waiting for requests...")
    try:
        async with server:
            await server.serve_forever()
    except asyncio.CancelledError:
        pass
    except Exception as e:
        log.error(f"Server error: {e}")
    finally:
        _cleanup_all_artifacts()


def main() -> None:
    ap = argparse.ArgumentParser(description="ChatTTS on-demand daemon")
    ap.add_argument("--idle-timeout", type=int, default=300,
                    help="Seconds of idle before auto-exit (default: 300)")
    args = ap.parse_args()

    try:
        asyncio.run(main_async(args.idle_timeout))
    except KeyboardInterrupt:
        log.info("Received SIGINT, shutting down")
        _cleanup_all_artifacts()


if __name__ == "__main__":
    main()
