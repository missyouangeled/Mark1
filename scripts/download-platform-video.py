#!/usr/bin/env python3
# 适用机器：通用（当前已在公司（Linux）验证）
# 系统 / OS：通用（依赖 agent-browser / ffprobe / Python requests）
# 用途：从公开视频页提取真实媒体地址并下载。目前先支持抖音公开视频页 URL。
from __future__ import annotations

import argparse
import json
import os
import random
import re
import shlex
import shutil
import subprocess
import sys
import uuid
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

import requests

WORKSPACE = Path(__file__).resolve().parents[1]
DEFAULT_OUTDIR = WORKSPACE / "tmp" / "video-downloads"
DEFAULT_ESTIMATE = "200M"
DEFAULT_PICK = "first"
DOUYIN_VIDEO_RE = re.compile(r"https?://www\.douyin\.com/video/(\d+)")
DOUYIN_USER_RE = re.compile(r"https?://www\.douyin\.com/user/([A-Za-z0-9._-]+)")
GENERIC_URL_RE = re.compile(r"https?://[^\s\"'<>]+")


def die(message: str, code: int = 1) -> None:
    print(f"error: {message}", file=sys.stderr)
    raise SystemExit(code)


def run(cmd: list[str], *, check: bool = True, capture: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        check=check,
        text=True,
        capture_output=capture,
    )


def ensure_tool(name: str) -> None:
    if shutil.which(name):
        return
    die(f"缺少依赖工具：{name}")


def preflight(estimate: str, purpose: str) -> None:
    script = WORKSPACE / "scripts" / "storage-preflight.sh"
    if not script.exists():
        return
    result = run(["bash", str(script), estimate, purpose], check=False)
    if result.stdout:
        print(result.stdout.rstrip())
    if result.returncode != 0:
        if result.stderr:
            print(result.stderr.rstrip(), file=sys.stderr)
        die("空间预检失败，已停止下载。")


def parse_jsonish(raw: str):
    text = raw.strip()
    if not text:
        return None
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        die(f"无法解析 JSON 输出：{exc}\n原始输出：{text[:500]}")
    if isinstance(data, str):
        try:
            return json.loads(data)
        except json.JSONDecodeError:
            return data
    return data


def browser_eval(session: str, expr: str) -> object:
    result = run(["agent-browser", "--session", session, "eval", expr], check=False)
    if result.returncode != 0:
        stderr = (result.stderr or "").strip()
        if "No usable sandbox" in stderr:
            die("agent-browser 启动失败：当前环境需要 --no-sandbox。请先执行 `agent-browser close --all`，再带 `--browser-args \"--no-sandbox\"` 重试。")
        die(f"agent-browser eval 失败：{stderr or result.stdout}")
    return parse_jsonish(result.stdout)


def browser_open(session: str, url: str, browser_args: str | None) -> None:
    cmd = ["agent-browser"]
    if browser_args:
        cmd += ["--args", browser_args]
    cmd += ["--session", session, "open", url]
    result = run(cmd, check=False)
    if result.returncode != 0:
        stderr = (result.stderr or "").strip()
        stdout = (result.stdout or "").strip()
        if "No usable sandbox" in stderr or "No usable sandbox" in stdout:
            die("agent-browser 启动失败：当前环境需要 --no-sandbox。请先执行 `agent-browser close --all`，再带 `--browser-args \"--no-sandbox\"` 重试。")
        die(f"打开页面失败：{stderr or stdout}")


def browser_wait(session: str, ms: int) -> None:
    result = run(["agent-browser", "--session", session, "wait", str(ms)], check=False)
    if result.returncode != 0:
        die(f"等待页面加载失败：{(result.stderr or result.stdout).strip()}")


def browser_close(session: str) -> None:
    run(["agent-browser", "--session", session, "close"], check=False)


def try_detect_platform(url: str) -> tuple[str, str] | None:
    video = DOUYIN_VIDEO_RE.search(url)
    if video:
        return "douyin", video.group(1)
    user = DOUYIN_USER_RE.search(url)
    if user:
        return "douyin_user", user.group(1)
    return None


def detect_platform(url: str) -> tuple[str, str]:
    detected = try_detect_platform(url)
    if detected:
        return detected
    die("当前脚本只支持抖音公开视频页 URL 或作者主页 URL，例如 https://www.douyin.com/video/<id> / https://www.douyin.com/user/<sec_user_id>")


def normalize_url(url: str) -> str:
    return url.rstrip('),.!?;]}>\"\'')


def extract_supported_urls(text: str) -> list[str]:
    found: list[str] = []
    for match in GENERIC_URL_RE.findall(text or ""):
        url = normalize_url(match)
        if try_detect_platform(url):
            found.append(url)
    deduped: list[str] = []
    seen: set[str] = set()
    for url in found:
        if url not in seen:
            seen.add(url)
            deduped.append(url)
    return deduped


def collect_inputs(raw_inputs: list[str], input_file: str | None) -> list[str]:
    chunks = list(raw_inputs)
    if input_file:
        path = Path(input_file)
        if not path.exists():
            die(f"输入文件不存在：{path}")
        chunks.append(path.read_text(encoding="utf-8", errors="ignore"))

    collected: list[str] = []
    for item in chunks:
        item = item.strip()
        if not item:
            continue
        direct = normalize_url(item)
        if " " not in direct and "\n" not in direct and try_detect_platform(direct):
            collected.append(direct)
            continue
        extracted = extract_supported_urls(item)
        if extracted:
            collected.extend(extracted)

    deduped: list[str] = []
    seen: set[str] = set()
    for url in collected:
        if url not in seen:
            seen.add(url)
            deduped.append(url)
    if not deduped:
        die("没有从输入里提取到任何受支持的视频页 / 作者主页 URL。")
    return deduped


def choose_candidate(urls: list[str], pick: str) -> str:
    if not urls:
        die("没有可选的视频候选 URL")

    pick = (pick or DEFAULT_PICK).strip()
    if pick == "first":
        return urls[0]
    if pick == "last":
        return urls[-1]
    if pick == "random":
        return random.choice(urls)
    if pick.startswith("index:"):
        raw = pick.split(":", 1)[1].strip()
        if not raw.isdigit():
            die(f"非法的 pick 参数：{pick}（index:N 里的 N 必须是正整数）")
        idx = int(raw)
        if idx < 1 or idx > len(urls):
            die(f"pick={pick} 超出候选范围（当前共 {len(urls)} 条）")
        return urls[idx - 1]
    if pick.startswith("video:"):
        target = pick.split(":", 1)[1].strip()
        for url in urls:
            _, video_id = detect_platform(url)
            if video_id == target:
                return url
        die(f"没有在候选里找到 video:{target}")

    die(f"不支持的 pick 参数：{pick}（可用：first / last / random / index:N / video:<id>）")


def describe_candidates(urls: list[str]) -> list[dict]:
    described: list[dict] = []
    for idx, url in enumerate(urls, start=1):
        platform, item_id = detect_platform(url)
        described.append(
            {
                "index": idx,
                "platform": platform,
                "id": item_id,
                "url": url,
            }
        )
    return described


def write_candidate_urls(path: str | None, urls: list[str]) -> None:
    if not path:
        return
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("\n".join(urls) + ("\n" if urls else ""), encoding="utf-8")


def write_json_file(path: str | None, payload: dict) -> None:
    if not path:
        return
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def build_download_command(*, pick: str, candidates_out: str | None, input_file: str | None, browser_args: str | None, urls: list[str]) -> str:
    cmd = ["python3", "scripts/download-platform-video.py"]
    if candidates_out:
        cmd += ["dummy", "--input-file", candidates_out]
    elif input_file:
        cmd += ["dummy", "--input-file", input_file]
    else:
        cmd += urls
    cmd += [f"--pick={pick}"]
    if browser_args:
        cmd += [f"--browser-args={browser_args}"]
    return " ".join(shlex.quote(part) for part in cmd)


def build_candidate_report(*, pick: str, selected: str, selected_from: list[str], candidates: list[str], source: dict | None = None, candidates_out: str | None = None, next_download_command: str | None = None) -> dict:
    report = {
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "pick": pick,
        "selected": selected,
        "selected_from": selected_from,
        "candidates_out": candidates_out,
        "next_download_command": next_download_command,
        "candidates": describe_candidates(candidates),
    }
    if source:
        report["source"] = source
    return report


def extract_douyin_user_candidates(session: str) -> dict:
    payload = browser_eval(
        session,
        "JSON.stringify((()=>{"
        "const body=(document.body&&document.body.innerText)||'';"
        "const title=(document.title||'').replace(/的抖音 - 抖音$/,'').trim();"
        "const links=Array.from(document.querySelectorAll('a[href]')).map(a=>a.href).filter(Boolean);"
        "const videos=[];"
        "for(const href of links){ if(href.includes('/video/') && !videos.includes(href)) videos.push(href); }"
        "return {title,hasServiceError:body.includes('服务异常'), bodySample:body.slice(0,2000), candidates:videos};"
        "})())",
    )
    if not isinstance(payload, dict):
        die(f"作者主页提取结果异常：{payload!r}")
    candidates = [u for u in (payload.get('candidates') or []) if isinstance(u, str)]
    return {
        "title": payload.get("title") or "douyin-user",
        "has_service_error": bool(payload.get("hasServiceError")),
        "body_sample": payload.get("bodySample") or "",
        "candidates": candidates,
    }


def extract_douyin_video(session: str) -> dict:
    payload = browser_eval(
        session,
        "JSON.stringify((()=>{"
        "const title=(document.title||'').replace(/ - 抖音$/,'').trim();"
        "const videos=Array.from(document.querySelectorAll('video')).map(v=>({currentSrc:v.currentSrc||'',duration:v.duration||0})).filter(v=>v.currentSrc);"
        "const best=videos.find(v=>v.currentSrc.startsWith('https://'))||videos[0]||null;"
        "return {title,url:location.href,video:best,all:videos};"
        "})())",
    )
    if not isinstance(payload, dict):
        die(f"页面提取结果异常：{payload!r}")
    video = payload.get("video") or {}
    media_url = video.get("currentSrc") if isinstance(video, dict) else None
    if not media_url or not str(media_url).startswith("https://"):
        die("没有从页面里取到真实视频地址。当前页面可能不是公开视频页，或平台策略已变化。")
    return {
        "title": payload.get("title") or "douyin-video",
        "page_url": payload.get("url") or "",
        "media_url": media_url,
        "page_duration": video.get("duration") or 0,
    }


def sanitize_filename(name: str) -> str:
    cleaned = re.sub(r"[\\/:*?\"<>|]+", "_", name).strip()
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned[:120] or "video"


def ffprobe_json(path: Path) -> dict | None:
    if not shutil.which("ffprobe"):
        return None
    result = run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration,size",
            "-of",
            "json",
            str(path),
        ],
        check=False,
    )
    if result.returncode != 0:
        return None
    return parse_jsonish(result.stdout)


def download_file(url: str, out: Path) -> int:
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Referer": "https://www.douyin.com/",
    }
    with requests.get(url, stream=True, timeout=60, headers=headers) as resp:
        resp.raise_for_status()
        with open(out, "wb") as fh:
            for chunk in resp.iter_content(chunk_size=1024 * 1024):
                if chunk:
                    fh.write(chunk)
    return out.stat().st_size


def main() -> None:
    parser = argparse.ArgumentParser(description="从公开视频页提取真实媒体地址并下载。当前支持抖音公开视频页。")
    parser.add_argument("inputs", nargs="+", help="一个或多个输入；可直接传抖音视频页 URL、作者主页 URL，或包含这些 URL 的混合文本")
    parser.add_argument("--input-file", help="从文本文件中读取混合输入，自动提取支持的 URL")
    parser.add_argument("--pick", default=DEFAULT_PICK, help="当传入多个候选 URL 时，选择规则：first / last / random / index:N / video:<id>；默认 first")
    parser.add_argument("--list-only", action="store_true", help="仅输出解析到的候选 URL 列表，不下载")
    parser.add_argument("--candidates-out", help="把候选 URL 一行一个写入文本文件，便于后续复用")
    parser.add_argument("--report-out", help="把结构化 JSON 结果写入文件，便于 agent 后续接力")
    parser.add_argument("-o", "--output", help="输出文件路径；默认按标题自动生成到 tmp/video-downloads/")
    parser.add_argument("--outdir", help="输出目录；默认 tmp/video-downloads/")
    parser.add_argument("--session", help="agent-browser 会话名；默认自动生成")
    parser.add_argument("--browser-args", help="传给 agent-browser 的浏览器参数，例如 --no-sandbox")
    parser.add_argument("--wait-ms", type=int, default=3000, help="页面打开后的等待毫秒数，默认 3000")
    parser.add_argument("--estimate", default=DEFAULT_ESTIMATE, help=f"下载前空间预检大小，默认 {DEFAULT_ESTIMATE}")
    parser.add_argument("--keep-session", action="store_true", help="下载完成后不自动关闭 agent-browser 会话")
    args = parser.parse_args()

    ensure_tool("agent-browser")
    ensure_tool("python3")

    collected_urls = collect_inputs(args.inputs, args.input_file)
    selected_input = choose_candidate(collected_urls, args.pick)
    input_platform, input_id = detect_platform(selected_input)

    if args.list_only and input_platform != "douyin_user":
        report = build_candidate_report(
            pick=args.pick,
            selected=selected_input,
            selected_from=collected_urls,
            candidates=collected_urls,
            candidates_out=args.candidates_out,
            next_download_command=build_download_command(
                pick=args.pick,
                candidates_out=args.candidates_out,
                input_file=args.input_file,
                browser_args=args.browser_args,
                urls=collected_urls,
            ),
        )
        write_candidate_urls(args.candidates_out, collected_urls)
        write_json_file(args.report_out, report)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return

    session = args.session or f"video-dl-{uuid.uuid4().hex[:8]}"
    resolved_candidates: list[str] | None = None
    try:
        if input_platform == "douyin_user":
            browser_open(session, selected_input, args.browser_args)
            browser_wait(session, args.wait_ms)
            user_info = extract_douyin_user_candidates(session)
            resolved_candidates = user_info["candidates"]
            if user_info["has_service_error"]:
                die("作者主页作品流当前返回‘服务异常’，为避免误把热点/推荐视频当成作者作品，脚本已停止自动选取。请改用公开视频页 URL 或先从外搜拿到候选视频页再传给脚本。")
            if not resolved_candidates:
                die("作者主页里没有解析到任何视频候选 URL。")
            if args.list_only:
                selected_url = choose_candidate(resolved_candidates, args.pick)
                report = build_candidate_report(
                    pick=args.pick,
                    selected=selected_url,
                    selected_from=collected_urls,
                    candidates=resolved_candidates,
                    source={
                        "platform": input_platform,
                        "page_url": selected_input,
                        "title": user_info["title"],
                    },
                    candidates_out=args.candidates_out,
                    next_download_command=build_download_command(
                        pick=args.pick,
                        candidates_out=args.candidates_out,
                        input_file=args.input_file,
                        browser_args=args.browser_args,
                        urls=resolved_candidates,
                    ),
                )
                write_candidate_urls(args.candidates_out, resolved_candidates)
                write_json_file(args.report_out, report)
                print(json.dumps(report, ensure_ascii=False, indent=2))
                return
            selected_url = choose_candidate(resolved_candidates, args.pick)
            platform, video_id = detect_platform(selected_url)
            browser_open(session, selected_url, args.browser_args)
            browser_wait(session, args.wait_ms)
        else:
            selected_url = selected_input
            platform, video_id = detect_platform(selected_url)
            browser_open(session, selected_url, args.browser_args)
            browser_wait(session, args.wait_ms)

        preflight(args.estimate, f"{platform}-video-download")
        if platform == "douyin":
            info = extract_douyin_video(session)
        else:
            die(f"未支持的平台：{platform}")
    finally:
        if not args.keep_session:
            browser_close(session)

    outdir = Path(args.outdir) if args.outdir else DEFAULT_OUTDIR
    outdir.mkdir(parents=True, exist_ok=True)
    if args.output:
        out = Path(args.output)
    else:
        name = sanitize_filename(info["title"])
        out = outdir / f"{name}-{video_id}.mp4"

    size = download_file(info["media_url"], out)
    probe = ffprobe_json(out)

    result = {
        "platform": platform,
        "video_id": video_id,
        "title": info["title"],
        "selected_from": collected_urls,
        "pick": args.pick,
        "resolved_candidates": resolved_candidates,
        "page_url": info["page_url"],
        "media_url": info["media_url"],
        "output": str(out),
        "bytes": size,
        "ffprobe": probe,
        "replay_download_command": build_download_command(
            pick=args.pick,
            candidates_out=args.candidates_out,
            input_file=args.input_file,
            browser_args=args.browser_args,
            urls=collected_urls,
        ),
    }
    write_json_file(args.report_out, result)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
