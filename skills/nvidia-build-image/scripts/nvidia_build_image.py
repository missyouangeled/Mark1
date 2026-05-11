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
from urllib.parse import urlparse

import requests

WORKSPACE = Path.home() / ".openclaw" / "workspace"
AUTH_PROFILES = Path.home() / ".openclaw" / "agents" / "main" / "agent" / "auth-profiles.json"
DEFAULT_OUT_DIR = WORKSPACE / "tmp" / "nvidia-image-test"
DEFAULT_NIM_BASE_URL = os.environ.get("NVIDIA_IMAGE_NIM_BASE_URL") or os.environ.get("NIM_BASE_URL") or "http://127.0.0.1:8000"
DEFAULT_NIM_API_KEY = os.environ.get("NVIDIA_IMAGE_NIM_API_KEY") or os.environ.get("NIM_API_KEY") or ""

RATIO_SIZES = {
    "1:1": (1024, 1024),
    "16:9": (1344, 768),
    "9:16": (768, 1344),
    "4:5": (896, 1152),
    "5:4": (1152, 896),
    "3:2": (832, 1216),
    "2:3": (1216, 832),
}

BUILD_HOSTED_MODELS = {
    "flux-dev": {
        "endpoint": "https://ai.api.nvidia.com/v1/genai/black-forest-labs/flux.1-dev",
        "default_steps": 28,
        "supports_ratio": True,
        "supports_cfg_scale": True,
    },
    "flux-schnell": {
        "endpoint": "https://ai.api.nvidia.com/v1/genai/black-forest-labs/flux.1-schnell",
        "default_steps": 4,
        "supports_ratio": False,
        "supports_cfg_scale": False,
    },
    "flux-klein": {
        "endpoint": "https://ai.api.nvidia.com/v1/genai/black-forest-labs/flux.2-klein-4b",
        "default_steps": 4,
        "supports_ratio": False,
        "supports_cfg_scale": False,
    },
}

NIM_HTTP_MODELS = {
    "flux-dev": {
        "path": "/v1/infer",
        "default_steps": 28,
        "supports_image_modes": True,
        "requires_image": False,
    },
    "flux-schnell": {
        "path": "/v1/infer",
        "default_steps": 4,
        "supports_image_modes": False,
        "requires_image": False,
    },
    "flux-kontext": {
        "path": "/v1/infer",
        "default_steps": 30,
        "supports_image_modes": False,
        "requires_image": True,
    },
}

ALL_MODELS = sorted(set(BUILD_HOSTED_MODELS) | set(NIM_HTTP_MODELS))


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


def choose_output_path(out: str | None, backend: str, model: str) -> Path:
    if out:
        path = Path(out).expanduser()
        path.parent.mkdir(parents=True, exist_ok=True)
        return path
    DEFAULT_OUT_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    return DEFAULT_OUT_DIR / f"{backend}-{model}-{ts}.jpg"


def normalize_seed(value: int | None) -> int:
    if value is None:
        return int(datetime.now().timestamp()) % 4294967295
    if value < 0 or value >= 4294967296:
        raise SystemExit("seed 必须在 0 <= seed < 4294967296 之间")
    return value


def normalize_base_url(value: str) -> str:
    return value.rstrip("/")


def build_hosted_payload(args: argparse.Namespace, model_cfg: dict) -> dict:
    if args.mode != "base" or args.image:
        if args.model == "flux-dev":
            raise SystemExit(
                "当前接入的 NVIDIA Build hosted 路线还不支持本地图片直传图生图："
                "实测返回 `Expected: example_id, got: base64`。"
                "若后续要继续补这条能力，请切到 `--backend nim-http` 并接 self-hosted Visual GenAI NIM。"
            )
        raise SystemExit(f"后端 {args.backend} 下的模型 {args.model} 当前只支持纯文生图")

    payload = {
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

    return payload


def build_nim_payload(args: argparse.Namespace, model_cfg: dict) -> dict:
    if args.ratio != "1:1":
        raise SystemExit("当前 `nim-http` 后端还没把 ratio/size 参数接进正式入口；先保持默认 1:1。")
    if args.cfg_scale is not None:
        raise SystemExit("当前 `nim-http` 后端还没把 cfg_scale 接进正式入口；先不要传。")

    payload = {
        "prompt": args.prompt,
        "seed": normalize_seed(args.seed),
        "steps": args.steps if args.steps is not None else model_cfg["default_steps"],
    }

    if model_cfg.get("requires_image"):
        if not args.image:
            raise SystemExit(f"模型 {args.model} 在 `nim-http` 后端下必须提供 --image")
        if args.mode != "base":
            raise SystemExit(f"模型 {args.model} 在 `nim-http` 后端下不使用 canny/depth 模式")
        payload["image"] = image_to_api_value(args.image)
        return payload

    if model_cfg.get("supports_image_modes"):
        payload["mode"] = args.mode
        if args.mode != "base":
            if not args.image:
                raise SystemExit("使用 canny/depth 模式时必须提供 --image")
            payload["image"] = image_to_api_value(args.image)
            payload["preprocess_image"] = True
        elif args.image:
            raise SystemExit("mode=base 时不要同时传 --image；如需图像引导请使用 --mode canny 或 --mode depth")
        return payload

    if args.mode != "base":
        raise SystemExit(f"模型 {args.model} 在 `nim-http` 后端下不支持模式 {args.mode}")
    if args.image:
        raise SystemExit(f"模型 {args.model} 在 `nim-http` 后端下当前不接收 --image")
    return payload


def resolve_request(args: argparse.Namespace) -> tuple[dict, str, dict]:
    if args.backend == "build-hosted":
        if args.model not in BUILD_HOSTED_MODELS:
            raise SystemExit(f"后端 {args.backend} 当前不支持模型 {args.model}")
        model_cfg = BUILD_HOSTED_MODELS[args.model]
        payload = build_hosted_payload(args, model_cfg)
        return model_cfg, model_cfg["endpoint"], payload

    if args.backend == "nim-http":
        if args.model not in NIM_HTTP_MODELS:
            raise SystemExit(f"后端 {args.backend} 当前不支持模型 {args.model}")
        model_cfg = NIM_HTTP_MODELS[args.model]
        payload = build_nim_payload(args, model_cfg)
        endpoint = normalize_base_url(args.base_url) + model_cfg["path"]
        return model_cfg, endpoint, payload

    raise SystemExit(f"未知 backend: {args.backend}")


def invoke_build_hosted(endpoint: str, payload: dict) -> dict:
    api_key = load_api_key()
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


def invoke_nim_http(endpoint: str, payload: dict, nim_api_key: str | None) -> dict:
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
    }
    key = (nim_api_key or "").strip()
    if key:
        headers["Authorization"] = f"Bearer {key}"
    resp = requests.post(endpoint, headers=headers, json=payload, timeout=300)
    if resp.status_code != 200:
        raise SystemExit(
            f"self-hosted NIM 调用失败 ({resp.status_code}): {resp.text[:1200]}\n"
            "请先确认目标 NIM 服务已启动，并且当前模型容器与所选 model/backend 匹配。"
        )
    return resp.json()


def save_result(
    out_path: Path,
    response: dict,
    meta_path: Path,
    payload: dict,
    endpoint: str,
    backend: str,
    model: str,
) -> None:
    artifacts = response.get("artifacts") or []
    if not artifacts:
        raise SystemExit("返回里没有 artifacts")
    art = artifacts[0]
    image_b64 = art.get("base64") or art.get("b64_json")
    if not image_b64:
        raise SystemExit("返回里没有图片 base64 字段")
    out_path.write_bytes(base64.b64decode(image_b64))
    meta = {
        "backend": backend,
        "model": model,
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
    ap = argparse.ArgumentParser(description="NVIDIA 图像技能入口：默认 Build hosted，预留 self-hosted NIM backend")
    ap.add_argument("--backend", choices=["build-hosted", "nim-http"], default="build-hosted", help="图像后端")
    ap.add_argument("--model", choices=ALL_MODELS, default="flux-dev", help="模型别名（不同 backend 可用集不同）")
    ap.add_argument("--prompt", required=True, help="生成提示词")
    ap.add_argument("--image", help="输入图片；支持本地路径或 http(s) URL")
    ap.add_argument("--mode", choices=["base", "canny", "depth"], default="base", help="flux-dev 在 nim-http 下支持的模式")
    ap.add_argument("--ratio", choices=sorted(RATIO_SIZES.keys()), default="1:1", help="输出比例（当前仅 build-hosted 的 flux-dev 接入）")
    ap.add_argument("--steps", type=int, help="采样步数")
    ap.add_argument("--seed", type=int, help="随机种子，必须 < 4294967296")
    ap.add_argument("--cfg-scale", type=float, help="引导强度（当前仅 build-hosted 的 flux-dev 接入）")
    ap.add_argument("--base-url", default=DEFAULT_NIM_BASE_URL, help="nim-http 后端的服务根地址")
    ap.add_argument("--nim-api-key", default=DEFAULT_NIM_API_KEY, help="nim-http 后端的可选 Bearer token")
    ap.add_argument("--out", help="输出图片路径")
    ap.add_argument("--print-payload", action="store_true", help="仅打印最终 endpoint/payload，不发请求")
    return ap


def main() -> int:
    parser = make_parser()
    args = parser.parse_args()
    _, endpoint, payload = resolve_request(args)

    if args.print_payload:
        print(
            json.dumps(
                {
                    "backend": args.backend,
                    "model": args.model,
                    "endpoint": endpoint,
                    "payload": payload,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0

    out_path = choose_output_path(args.out, args.backend, args.model)
    meta_path = out_path.with_suffix(out_path.suffix + ".json")

    if args.backend == "build-hosted":
        response = invoke_build_hosted(endpoint, payload)
    elif args.backend == "nim-http":
        response = invoke_nim_http(endpoint, payload, args.nim_api_key)
    else:
        raise SystemExit(f"未知 backend: {args.backend}")

    save_result(out_path, response, meta_path, payload, endpoint, args.backend, args.model)

    print(
        json.dumps(
            {
                "ok": True,
                "backend": args.backend,
                "model": args.model,
                "output": str(out_path),
                "metadata": str(meta_path),
                "seed": payload["seed"],
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
