#!/mnt/data/openclaw/paddleocr-venv/bin/python3
"""
贾维斯 OCR 便捷入口 — PP-OCRv6 文字识别
===========================================
适用机器：通用（当前 Mark1 / 公司 Linux 已验证）
系统 / OS：Linux（依赖 PaddleOCR venv）
用途：一行命令对图片做 OCR，输出结构化文本结果

用法：
  python3 scripts/jarvis-ocr.py --input image.png
  python3 scripts/jarvis-ocr.py --input image.png --lang en
  python3 scripts/jarvis-ocr.py --input image.png --json        # JSON 输出
  python3 scripts/jarvis-ocr.py --input image.png --benchmark    # 测速模式
  python3 scripts/jarvis-ocr.py --list-models                    # 列出可用规格

依赖：
  venv: /mnt/data/openclaw/paddleocr-venv
  PaddlePaddle 3.2.2（3.3.x 有 CPU OneDNN bug #77340）
  PaddleOCR 3.7.0
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

# ── 模型规格映射 ──────────────────────────────────────────
MODEL_SPECS = {
    "tiny":   {"det": "PP-OCRv6_tiny_det",   "rec": "PP-OCRv6_tiny_rec"},
    "small":  {"det": "PP-OCRv6_small_det",  "rec": "PP-OCRv6_small_rec"},
    "medium": {"det": "PP-OCRv6_medium_det", "rec": "PP-OCRv6_medium_rec"},
}


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="贾维斯 OCR — PP-OCRv6 文字识别便捷入口"
    )
    p.add_argument("--input", "-i", help="输入图片路径")
    p.add_argument("--lang", default="ch", help="识别语言 (ch / en / korean / japan / ...)")
    p.add_argument(
        "--model", default="medium", choices=list(MODEL_SPECS),
        help="模型规格 (tiny / small / medium)，默认 medium"
    )
    p.add_argument("--json", action="store_true", help="JSON 格式输出")
    p.add_argument("--benchmark", action="store_true", help="测速模式（重复 3 次取平均）")
    p.add_argument("--list-models", action="store_true", help="列出可用模型规格")
    p.add_argument("--no-doc-preprocess", action="store_true", help="禁用文档预处理（方向校正/展平）")
    return p.parse_args()


def list_models():
    print("PP-OCRv6 可用规格：")
    print(f"{'规格':<10} {'参数量':<10} {'ONNX大小':<12} {'适用场景'}")
    print("-" * 55)
    for spec, params, size_mb, scene in [
        ("tiny",   "1.5M",  "~6 MB",   "浏览器、超轻边缘"),
        ("small",  "7.7M",  "~30 MB",  "树莓派、低配 VPS"),
        ("medium", "34.5M", "~140 MB", "服务器、高精度"),
    ]:
        marker = " ← 默认" if spec == "medium" else ""
        print(f"  {spec:<8} {params:<10} {size_mb:<12} {scene}{marker}")


def run_ocr(
    image_path: str,
    lang: str = "ch",
    model_size: str = "medium",
    disable_doc_preprocess: bool = False,
) -> tuple[list[dict], float]:
    """
    执行 OCR 识别。
    返回 (results, elapsed_seconds)
    results: [{"text": str, "confidence": float}, ...]
    """
    from paddleocr import PaddleOCR  # noqa: E402

    specs = MODEL_SPECS[model_size]

    ocr_kwargs = {
        "lang": lang,
        "text_detection_model_name": specs["det"],
        "text_recognition_model_name": specs["rec"],
    }

    if disable_doc_preprocess:
        ocr_kwargs.update({
            "use_doc_orientation_classify": False,
            "use_doc_unwarping": False,
            "use_textline_orientation": False,
        })

    ocr = PaddleOCR(**ocr_kwargs)

    t0 = time.time()
    result = ocr.predict(image_path)
    elapsed = time.time() - t0

    lines: list[dict] = []
    for page in result:
        texts = page.get("rec_texts", [])
        scores = page.get("rec_scores", [])
        for text, score in zip(texts, scores):
            lines.append({"text": text, "confidence": round(float(score), 4)})

    return lines, elapsed


def format_output(results: list[dict], elapsed: float, as_json: bool = False):
    """格式化输出"""
    if as_json:
        print(json.dumps({
            "elapsed_s": round(elapsed, 2),
            "lines": results,
        }, ensure_ascii=False, indent=2))
    else:
        for item in results:
            print(f"  [{item['confidence']:.2%}] {item['text']}")
        print(f"\n⏱  {elapsed:.2f}s | {len(results)} 行文字")


def main():
    args = parse_args()

    if args.list_models:
        list_models()
        return

    if not args.input:
        print("❌ 请指定 --input 图片路径", file=sys.stderr)
        sys.exit(1)

    image_path = Path(args.input)
    if not image_path.exists():
        print(f"❌ 文件不存在: {image_path}", file=sys.stderr)
        sys.exit(1)

    # ── 识别 ──
    if args.benchmark:
        runs = 3
        total = 0.0
        for i in range(runs):
            results, elapsed = run_ocr(
                str(image_path), args.lang, args.model, args.no_doc_preprocess
            )
            total += elapsed
            print(f"[跑 {i+1}/{runs}] {elapsed:.2f}s  {len(results)} 行", file=sys.stderr)
        avg = total / runs
        print(f"\n📊 平均: {avg:.2f}s（{runs} 次）", file=sys.stderr)
        format_output(results, avg, args.json)
    else:
        results, elapsed = run_ocr(
            str(image_path), args.lang, args.model, args.no_doc_preprocess
        )
        format_output(results, elapsed, args.json)


if __name__ == "__main__":
    main()
