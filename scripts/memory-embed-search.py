#!/usr/bin/env python3
"""
memory-embed-search.py — 本地向量语义搜索

使用预构建的 sentence embedding 索引，做余弦相似度语义搜索。

用法：
  python3 scripts/memory-embed-search.py "查询文本"
  python3 scripts/memory-embed-search.py --top 5 "查询文本"
  python3 scripts/memory-embed-search.py --json "查询文本"
  python3 scripts/memory-embed-search.py --check  # 检查索引是否存在
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

import numpy as np

INDEX_DIR = Path(os.environ.get("MEMORY_INDEX_DIR", "/mnt/data/openclaw/scratch/memory-embed-index"))
EMBEDDINGS_FILE = INDEX_DIR / "embeddings.npy"
SEGMENTS_FILE = INDEX_DIR / "segments.json"
MANIFEST_FILE = INDEX_DIR / "manifest.json"

VENV_PYTHON = os.path.expanduser("~/.local/share/openclaw-embed-venv311/bin/python3")
MODEL_PATH = "/mnt/data/openclaw/huggingface/hub/models--sentence-transformers--paraphrase-multilingual-MiniLM-L12-v2/snapshots/main"

CONFIDENCE_THRESHOLD = 0.60  # 余弦相似度 ≥ 此值视为置信结果


def check_index() -> dict:
    """检查索引状态"""
    if not EMBEDDINGS_FILE.exists() or not SEGMENTS_FILE.exists():
        return {"ok": False, "error": "索引不存在，请先运行 memory-embed-index.py"}
    try:
        manifest = json.loads(MANIFEST_FILE.read_text()) if MANIFEST_FILE.exists() else {}
    except Exception:
        manifest = {}
    return {
        "ok": True,
        "n_segments": manifest.get("n_segments", "?"),
        "dim": manifest.get("dim", "?"),
        "last_built": manifest.get("last_built", "?"),
    }


def load_model():
    """延迟加载模型"""
    os.environ.setdefault("HF_HOME", "/mnt/data/openclaw/huggingface")
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"

    from sentence_transformers import SentenceTransformer
    return SentenceTransformer(MODEL_PATH, device="cpu")


def search(query: str, top_k: int = 5) -> dict:
    """执行语义搜索"""
    t0 = time.time()

    status = check_index()
    if not status["ok"]:
        return status

    # 加载索引
    load_start = time.time()
    embeddings = np.load(str(EMBEDDINGS_FILE))
    segments_data = json.loads(SEGMENTS_FILE.read_text())
    segments = segments_data["segments"]
    load_time = time.time() - load_start

    # 加载模型 + 编码查询
    encode_start = time.time()
    model = load_model()
    query_vec = model.encode([query], show_progress_bar=False)[0]
    query_vec = np.asarray(query_vec, dtype=np.float32)
    encode_time = time.time() - encode_start

    # 余弦相似度
    sim_start = time.time()
    # 归一化
    query_norm = query_vec / (np.linalg.norm(query_vec) + 1e-10)
    emb_norms = embeddings / (np.linalg.norm(embeddings, axis=1, keepdims=True) + 1e-10)
    similarities = np.dot(emb_norms, query_norm)
    sim_time = time.time() - sim_start

    # 取 top-K
    top_indices = np.argsort(similarities)[::-1][:top_k]

    results = []
    for idx in top_indices:
        score = float(similarities[idx])
        seg = segments[idx]
        results.append({
            "file": seg["file"],
            "line": seg["line"],
            "content": seg["content"][:500],
            "score": round(score, 4),
        })

    best_score = results[0]["score"] if results else 0.0
    total_time = time.time() - t0

    return {
        "ok": True,
        "query": query,
        "results": results,
        "top_score": round(best_score, 4),
        "confidence": round(best_score, 4),
        "short_circuit": best_score >= CONFIDENCE_THRESHOLD,
        "timing": {
            "total_ms": round(total_time * 1000),
            "load_ms": round(load_time * 1000),
            "encode_ms": round(encode_time * 1000),
            "sim_ms": round(sim_time * 1000),
        },
    }


def main():
    parser = argparse.ArgumentParser(description="本地向量语义搜索")
    parser.add_argument("query", nargs="+", help="搜索文本")
    parser.add_argument("--top", type=int, default=5, help="返回 top-K 结果")
    parser.add_argument("--check", action="store_true", help="检查索引状态")
    parser.add_argument("--json", action="store_true", default=True)
    args = parser.parse_args()

    if args.check:
        status = check_index()
        print(json.dumps(status, ensure_ascii=False))
        return 0 if status["ok"] else 1

    query = " ".join(args.query).strip()
    if not query:
        print(json.dumps({"ok": False, "error": "empty query"}, ensure_ascii=False))
        return 1

    result = search(query, top_k=args.top)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("short_circuit") else 1


if __name__ == "__main__":
    sys.exit(main())
