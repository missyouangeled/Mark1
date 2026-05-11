#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import json
import mimetypes
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import requests

WORKSPACE = Path.home() / ".openclaw" / "workspace"
AUTH_PROFILES = Path.home() / ".openclaw" / "agents" / "main" / "agent" / "auth-profiles.json"
DEFAULT_OUT_DIR = WORKSPACE / "tmp" / "nvidia-image-test"

RATIO_SIZES = {
    "1:1": (1024, 1024),
    "16:9": (1344, 768),
    "9:16": (768, 1344),
    "4:5": (896, 1152),
    "5:4": (1152, 896),
    "3:2": (832, 1216),
    "2:3": (1216, 832),
}

MODELS = {
    "flux-dev": {
        "endpoint": "https://ai.api.nvidia.com/v1/genai/black-forest-labs/flux.1-dev",
        "default_steps": 28,
        "supports_ratio": True,
        "supports_cfg_scale": True,
        "supports_image_modes": False,
        "default_cfg_scale": 3.5,
    },
    "flux-schnell": {
        "endpoint": "https://ai.api.nvidia.com/v1/genai/black-forest-labs/flux.1-schnell",
        "default_steps": 4,
        "supports_ratio": False,
        "supports_cfg_scale": False,
        "supports_image_modes": False,
        "default_cfg_scale": None,
    },
    "flux-klein": {
        "endpoint": "https://ai.api.nvidia.com/v1/genai/black-forest-labs/flux.2-klein-4b",
        "default_steps": 4,
        "supports_ratio": False,
        "supports_cfg_scale": False,
        "supports_image_modes": False,
        "default_cfg_scale": None,
    },
}


def load_api_key() -> str:
    env_key = os.environ.get("NVIDIA_API_KEY", "").strip()
    if env_key:
        return env_key
    if not AUTH_PROFILES.exists():
        raise SystemExit(f"未找到认证文件: {AUTH_PROFILES}")
    data = json.loads(AUTH_PROFILES.read_text(encoding="utf-8"))
    profiles = data.get("profiles", {})
    profile = profiles.get("nvidia:default", {})
    key = (profile.get("key") or "").strip()
    if not key:
        raise SystemExit("未找到可用的 nvidia:default API key")
    return key


def is_url(value: str) -> bool:
    parsed = urlparse(value)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)



def image_to_api_value(image: str) -> str:
    if is_url(image):
        return image
    path = Path(image).expanduser()
    if not path.exists():
        raise SystemExit(f"输入图片不存在: {path}")
    mime, _ = mimetypes.guess_type(path.name)
    if not mime:
        mime = "application/octet-stream"
    b64 = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{b64}"



def choose_output_path(out: str | None, model: str) -> Path:
    if out:
        path = Path(out).expanduser()
        path.parent.mkdir(parents=True, exist_ok=True)
        return path
    DEFAULT_OUT_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    return DEFAULT_OUT_DIR / f"{model}-{ts}.jpg"



def normalize_seed(value: int | None) -> int:
    if value is None:
        return int(datetime.now().timestamp()) % 4294967295
    if value < 0 or value >= 4294967296:
        raise SystemExit("seed 必须在 0 <= seed < 4294967296 之间")
    return value



def build_payload(args: argparse.Namespace, model_cfg: dict[str, Any]) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "prompt": args.prompt,
        "seed": normalize_seed(args.seed),
        "steps": args.steps if args.steps is not None else model_cfg["default_steps"],
    }

    if model_cfg["supports_ratio"]:
        width, height = RATIO_SIZES[args.ratio]
        payload["width"] = width
        payload["height"] = height

    if model_cfg["supports_cfg_scale"] and args.cfg_scale is not None:
        payload["cfg_scale"] = args.cfg_scale
    elif model_cfg["supports_cfg_scale"] and args.mode != "base":
        payload["cfg_scale"] = model_cfg["default_cfg_scale"]

    if model_cfg["supports_image_modes"]:
        payload["mode"] = args.mode
        if args.mode != "base":
            if not args.image:
                raise SystemExit("使用 canny/depth 模式时必须提供 --image")
            payload["image"] = image_to_api_value(args.image)
        elif args.image:
            raise SystemExit("mode=base 时不要同时传 --image；如需图生图请使用 --mode canny 或 --mode depth")
    else:
        if args.mode != "base":
            if args.model == "flux-dev":
                raise SystemExit(
                    "当前接入的 NVIDIA Build hosted 路线还不支持本地图片直传图生图："
                    "实测返回 `Expected: example_id, got: base64`。"
                    "self-hosted Visual GenAI NIM 文档支持 image/base64，但这台机器当前走的 hosted 接口未打通。"
                )
            raise SystemExit(f"模型 {args.model} 不支持模式 {args.mode}")
        if args.image:
            if args.model == "flux-dev":
                raise SystemExit(
                    "当前接入的 NVIDIA Build hosted 路线还不支持本地图片直传图生图："
                    "实测返回 `Expected: example_id, got: base64`。"
                    "self-hosted Visual GenAI NIM 文档支持 image/base64，但这台机器当前走的 hosted 接口未打通。"
                )
            raise SystemExit(f"模型 {args.model} 当前未接入图生图输入")

    return payload



def invoke(endpoint: str, api_key: str, payload: dict[str, Any]) -> dict[str, Any]:
    resp = requests.post(
        endpoint,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=300,
    )
    if resp.status_code != 200:
        raise SystemExit(f"NVIDIA Build 调用失败 ({resp.status_code}): {resp.text[:1200]}")
    return resp.json()



def save_result(out_path: Path, response: dict[str, Any], meta_path: Path, payload: dict[str, Any], endpoint: str) -> None:
    artifacts = response.get("artifacts") or []
    if not artifacts:
        raise SystemExit("返回里没有 artifacts")
    art = artifacts[0]
    image_b64 = art.get("base64") or art.get("b64_json")
    if not image_b64:
        raise SystemExit("返回里没有图片 base64 字段")
    out_path.write_bytes(base64.b64decode(image_b64))
    meta = {
        "endpoint": endpoint,
        "payload": payload,
        "response_meta": {
            "finish_reason": art.get("finishReason") or art.get("finish_reason"),
            "seed": art.get("seed"),
        },
        "output": str(out_path),
    }
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")



def make_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description="NVIDIA Build 文生图最小入口（当前 hosted 图生图未打通）")
    ap.add_argument("--model", choices=sorted(MODELS.keys()), default="flux-dev", help="模型别名")
    ap.add_argument("--prompt", required=True, help="生成提示词")
    ap.add_argument("--image", help="图生图输入；支持本地路径或 http(s) URL")
    ap.add_argument("--mode", choices=["base", "canny", "depth"], default="base", help="flux-dev 的生成模式")
    ap.add_argument("--ratio", choices=sorted(RATIO_SIZES.keys()), default="1:1", help="输出比例（仅 flux-dev 生效）")
    ap.add_argument("--steps", type=int, help="采样步数")
    ap.add_argument("--seed", type=int, help="随机种子，必须 < 4294967296")
    ap.add_argument("--cfg-scale", type=float, help="引导强度（仅 flux-dev 使用）")
    ap.add_argument("--out", help="输出图片路径")
    ap.add_argument("--print-payload", action="store_true", help="仅打印最终 payload，不发请求")
    return ap



def main() -> int:
    parser = make_parser()
    args = parser.parse_args()
    model_cfg = MODELS[args.model]
    payload = build_payload(args, model_cfg)

    if args.print_payload:
        print(json.dumps({"endpoint": model_cfg["endpoint"], "payload": payload}, ensure_ascii=False, indent=2))
        return 0

    out_path = choose_output_path(args.out, args.model)
    meta_path = out_path.with_suffix(out_path.suffix + ".json")
    api_key = load_api_key()
    response = invoke(model_cfg["endpoint"], api_key, payload)
    save_result(out_path, response, meta_path, payload, model_cfg["endpoint"])

    print(json.dumps({
        "ok": True,
        "model": args.model,
        "output": str(out_path),
        "metadata": str(meta_path),
        "seed": payload["seed"],
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
