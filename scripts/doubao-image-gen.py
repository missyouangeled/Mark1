#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""豆包 Seedream 图生 —— HTTP 直调兜底脚本
用途：OpenClaw 当前版本的 image_generate 工具不支持 volcengine-agent 作为图生 provider
     （内置适配器表只认 openai/fal/google/minimax/xai/litellm/openrouter/deepinfra/comfy），
     所以图生走这个脚本。
用法：python3 scripts/doubao-image-gen.py "提示词" [输出文件名]
"""
import json
import sys
import time
import urllib.request
from pathlib import Path

CONFIG = Path.home() / ".openclaw" / "openclaw.json"
ENDPOINT = "https://ark.cn-beijing.volces.com/api/plan/v3/images/generations"
MODEL = "doubao-seedream-5.0-lite"
OUTDIR = Path.home() / ".openclaw" / "workspace" / "media" / "images"


def get_key() -> str:
    cfg = json.loads(CONFIG.read_text(encoding="utf-8"))
    return cfg["models"]["providers"]["volcengine-agent"]["apiKey"]


def generate(prompt: str, name: str | None = None) -> Path:
    payload = json.dumps({
        "model": MODEL,
        "prompt": prompt,
        "size": "1920x1920",
        "watermark": False,          # 必须 false，否则带「AI生成」水印
        "response_format": "url",
    }).encode("utf-8")

    req = urllib.request.Request(
        ENDPOINT,
        data=payload,
        headers={
            "Authorization": f"Bearer {get_key()}",
            "Content-Type": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=150) as resp:
        data = json.loads(resp.read().decode("utf-8"))

    url = data["data"][0]["url"]
    OUTDIR.mkdir(parents=True, exist_ok=True)
    out = OUTDIR / (name or f"seedream_{int(time.time())}.jpeg")
    with urllib.request.urlopen(url, timeout=90) as img:
        out.write_bytes(img.read())
    return out


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: doubao-image-gen.py \"提示词\" [文件名]", file=sys.stderr)
        sys.exit(1)
    path = generate(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None)
    print(f"OK {path} {path.stat().st_size}")
