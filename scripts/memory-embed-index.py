#!/usr/bin/env python3
"""
memory-embed-index.py — 记忆文件向量索引构建

遍历 memory/ 所有 .md 文件 → 段落切分 → sentence embedding → 保存为 NumPy 索引

用法：
  python3 scripts/memory-embed-index.py              # 增量索引（跳过无变化时）
  python3 scripts/memory-embed-index.py --force      # 强制重建
  python3 scripts/memory-embed-index.py --check      # 仅检查是否需要重建
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import time
from pathlib import Path

import numpy as np

WORKSPACE = Path(__file__).resolve().parent.parent
MEMORY_DIR = WORKSPACE / "memory"
INDEX_DIR = Path(os.environ.get("MEMORY_INDEX_DIR", "/mnt/data/openclaw/scratch/memory-embed-index"))
INDEX_DIR.mkdir(parents=True, exist_ok=True)

EMBEDDINGS_FILE = INDEX_DIR / "embeddings.npy"
SEGMENTS_FILE = INDEX_DIR / "segments.json"
MANIFEST_FILE = INDEX_DIR / "manifest.json"

VENV_PYTHON = os.path.expanduser("~/.local/share/openclaw-embed-venv311/bin/python3")
MODEL_PATH = "/mnt/data/openclaw/huggingface/hub/models--sentence-transformers--paraphrase-multilingual-MiniLM-L12-v2/snapshots/main"


def segment_markdown(text: str, filename: str) -> list[dict]:
    """将 Markdown 按段落切分，保留来源信息。
    
    切分规则：
    - 以空行为分隔符
    - 跳过纯标题行（#...）和纯分隔线
    - 跳过太短的段落（< 10 字符）
    - 每段关联文件名 + 行号范围
    """
    lines = text.split("\n")
    segments = []
    current = []
    start_line = 0

    def flush():
        nonlocal current, start_line
        if not current:
            return
        content = "\n".join(current).strip()
        # 跳过空行/标题/分隔线/太短
        if content and not re.match(r'^#{1,6}\s', content) and not re.match(r'^[-*_]{3,}$', content) and len(content) >= 10:
            segments.append({
                "file": filename,
                "line": start_line + 1,
                "content": content,
            })
        current = []
        start_line = 0

    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped == "":
            flush()
        else:
            if not current:
                start_line = i
            current.append(line)

    flush()
    return segments


def compute_file_hash(files: list[Path]) -> str:
    """计算所有 memory 文件的内容哈希（用于增量更新判断）"""
    h = hashlib.sha256()
    for fp in sorted(files):
        h.update(fp.read_bytes())
    return h.hexdigest()


def load_model():
    """延迟加载模型（只在需要重建时）"""
    os.environ.setdefault("HF_HOME", "/mnt/data/openclaw/huggingface")
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"

    from sentence_transformers import SentenceTransformer
    return SentenceTransformer(MODEL_PATH, device="cpu")


def build_index(force: bool = False) -> dict:
    """构建/增量更新向量索引"""
    # 收集所有 memory 文件
    md_files = sorted(MEMORY_DIR.rglob("*.md"))
    if not md_files:
        return {"ok": False, "error": "没有找到 memory 文件"}

    # 增量检查
    current_hash = compute_file_hash(md_files)
    if not force and MANIFEST_FILE.exists():
        try:
            manifest = json.loads(MANIFEST_FILE.read_text())
            if manifest.get("content_hash") == current_hash:
                return {
                    "ok": True,
                    "rebuilt": False,
                    "reason": "内容无变化，跳过重建",
                    "segments": manifest.get("n_segments", 0),
                }
        except Exception:
            pass

    t0 = time.time()

    # 加载模型
    print("加载模型...", flush=True)
    model = load_model()

    # 切分段落
    all_segments = []
    for fp in md_files:
        rel = str(fp.relative_to(MEMORY_DIR))
        try:
            text = fp.read_text(encoding="utf-8")
        except Exception:
            continue
        segs = segment_markdown(text, rel)
        all_segments.extend(segs)

    if not all_segments:
        return {"ok": False, "error": "无有效段落"}

    print(f"段落数: {len(all_segments)}", flush=True)

    # 生成向量
    texts = [s["content"] for s in all_segments]
    print("生成向量...", flush=True)
    embeddings = model.encode(texts, show_progress_bar=True, batch_size=32)
    embeddings = np.asarray(embeddings, dtype=np.float32)

    # 保存
    np.save(str(EMBEDDINGS_FILE), embeddings)

    segments_data = {
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "n_segments": len(all_segments),
        "dim": int(embeddings.shape[1]),
        "segments": all_segments,
    }
    SEGMENTS_FILE.write_text(json.dumps(segments_data, ensure_ascii=False, indent=2))

    manifest = {
        "content_hash": current_hash,
        "n_segments": len(all_segments),
        "dim": int(embeddings.shape[1]),
        "model": "paraphrase-multilingual-MiniLM-L12-v2",
        "files_indexed": len(md_files),
        "last_built": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "build_time_s": round(time.time() - t0, 1),
    }
    MANIFEST_FILE.write_text(json.dumps(manifest, ensure_ascii=False, indent=2))

    elapsed = time.time() - t0
    print(f"索引构建完成: {len(all_segments)} 段, {embeddings.shape[1]} 维, 耗时 {elapsed:.1f}s", flush=True)

    return {
        "ok": True,
        "rebuilt": True,
        "n_segments": len(all_segments),
        "dim": int(embeddings.shape[1]),
        "build_time_s": round(elapsed, 1),
    }


def main():
    parser = argparse.ArgumentParser(description="记忆向量索引构建")
    parser.add_argument("--force", action="store_true", help="强制重建索引")
    parser.add_argument("--check", action="store_true", help="仅检查是否需要重建")
    parser.add_argument("--json", action="store_true", default=True)
    args = parser.parse_args()

    if args.check:
        md_files = sorted(MEMORY_DIR.rglob("*.md"))
        if not md_files:
            print(json.dumps({"ok": True, "needs_rebuild": False, "reason": "无 memory 文件"}))
            return 0

        current_hash = compute_file_hash(md_files)
        if MANIFEST_FILE.exists():
            try:
                manifest = json.loads(MANIFEST_FILE.read_text())
                if manifest.get("content_hash") == current_hash:
                    print(json.dumps({"ok": True, "needs_rebuild": False, "segments": manifest.get("n_segments")}))
                    return 0
            except Exception:
                pass

        print(json.dumps({"ok": True, "needs_rebuild": True, "files": len(md_files)}))
        return 0

    result = build_index(force=args.force)
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
