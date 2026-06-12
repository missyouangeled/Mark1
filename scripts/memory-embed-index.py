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


def compute_per_file_hashes(files: list[Path]) -> dict[str, str]:
    """计算每个文件的独立哈希（用于增量更新：只重建变化的文件）"""
    result = {}
    for fp in sorted(files):
        rel = str(fp.relative_to(MEMORY_DIR))
        result[rel] = hashlib.sha256(fp.read_bytes()).hexdigest()
    return result


def _embed_via_sidecar(texts: list[str], batch_size: int = 100) -> np.ndarray:
    """通过 embed-sidecar HTTP 接口做向量化（分批发送，不加载第二个模型副本）。"""
    import urllib.request
    SIDECAR_URL = "http://127.0.0.1:18792"

    all_embeddings = []
    for i in range(0, len(texts), batch_size):
        batch = texts[i:i + batch_size]
        try:
            req = urllib.request.Request(
                f"{SIDECAR_URL}/encode",
                data=json.dumps({"texts": batch}).encode(),
                headers={"Content-Type": "application/json"},
            )
            resp = urllib.request.urlopen(req, timeout=120)
            data = json.loads(resp.read().decode())
            if data.get("ok"):
                all_embeddings.append(np.array(data["embeddings"], dtype=np.float32))
            else:
                raise RuntimeError(f"sidecar encode failed: {data.get('error')}")
        except Exception as e:
            raise RuntimeError(f"sidecar unavailable: {e}")
    return np.vstack(all_embeddings) if len(all_embeddings) > 1 else all_embeddings[0]


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

    # 全量重建
    return _rebuild_full(md_files, current_hash)


def build_incremental() -> dict:
    """增量索引：只重建变化的文件，保留未变文件的数据。
    
    — 用于 lifecycle-maintainer 每 5 分钟自动调用，
      每次只处理新增/修改的文件，不重新做 5379 段。
    """
    md_files = sorted(MEMORY_DIR.rglob("*.md"))
    if not md_files:
        return {"ok": False, "error": "没有找到 memory 文件"}

    # 如果没有现有索引 → 全量重建
    if not EMBEDDINGS_FILE.exists() or not SEGMENTS_FILE.exists() or not MANIFEST_FILE.exists():
        return _rebuild_full(md_files, compute_file_hash(md_files))

    try:
        manifest = json.loads(MANIFEST_FILE.read_text())
        segments_data = json.loads(SEGMENTS_FILE.read_text())
        existing_segments: list[dict] = segments_data.get("segments", [])
        existing_embeddings = np.load(str(EMBEDDINGS_FILE))
    except Exception:
        return _rebuild_full(md_files, compute_file_hash(md_files))

    # 逐文件 hash 对比：找出变化的文件
    current_hashes = compute_per_file_hashes(md_files)
    old_per_file = manifest.get("per_file_hash", {})

    changed_files = set()
    new_files = set()
    for rel, h in current_hashes.items():
        if rel not in old_per_file:
            new_files.add(rel)
        elif old_per_file[rel] != h:
            changed_files.add(rel)

    # 找出删除的文件
    removed_files = set(old_per_file) - set(current_hashes)

    all_changed = changed_files | new_files | removed_files
    if not all_changed:
        return {
            "ok": True,
            "rebuilt": False,
            "reason": "增量检查：无文件变化",
            "segments": manifest.get("n_segments", 0),
            "files_checked": len(md_files),
        }

    print(f"增量更新: 新增 {len(new_files)}, 修改 {len(changed_files)}, 删除 {len(removed_files)}", flush=True)
    t0 = time.time()

    # 删除已移除/修改的文件的旧段落和向量
    affected = changed_files | removed_files
    keep_indices = [
        i for i, s in enumerate(existing_segments)
        if s["file"] not in affected
    ]
    old_segments_kept = [existing_segments[i] for i in keep_indices]
    old_embeddings_kept = existing_embeddings[keep_indices] if len(keep_indices) > 0 else np.empty((0, existing_embeddings.shape[1]), dtype=np.float32)

    # 对新文件/修改文件重新切分 + 向量化
    rebuild_files = changed_files | new_files
    new_segments = []
    for fp in md_files:
        rel = str(fp.relative_to(MEMORY_DIR))
        if rel not in rebuild_files:
            continue
        try:
            text = fp.read_text(encoding="utf-8")
        except Exception:
            continue
        segs = segment_markdown(text, rel)
        new_segments.extend(segs)

    all_segments = old_segments_kept + new_segments
    if not all_segments:
        return {"ok": False, "error": "增量后无有效段落"}

    new_embeddings = np.empty((0, existing_embeddings.shape[1]), dtype=np.float32)
    if new_segments:
        new_texts = [s["content"] for s in new_segments]
        print(f"通过 sidecar 向量化 {len(new_segments)} 个新段落...", flush=True)
        new_embeddings = _embed_via_sidecar(new_texts)
        new_embeddings = np.asarray(new_embeddings, dtype=np.float32)

    merged_embeddings = np.vstack([old_embeddings_kept, new_embeddings]) if len(old_embeddings_kept) > 0 else new_embeddings

    # 保存
    np.save(str(EMBEDDINGS_FILE), merged_embeddings)
    segments_data = {
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "n_segments": len(all_segments),
        "dim": int(merged_embeddings.shape[1]),
        "segments": all_segments,
    }
    SEGMENTS_FILE.write_text(json.dumps(segments_data, ensure_ascii=False, indent=2))

    new_manifest = {
        "content_hash": compute_file_hash(md_files),
        "per_file_hash": current_hashes,
        "n_segments": len(all_segments),
        "dim": int(merged_embeddings.shape[1]),
        "model": "paraphrase-multilingual-MiniLM-L12-v2",
        "files_indexed": len(md_files),
        "last_built": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "build_time_s": round(time.time() - t0, 1),
        "incremental": True,
        "changed": len(changed_files),
        "new": len(new_files),
        "removed": len(removed_files),
        "segments_changed": len(new_segments),
        "segments_kept": len(old_segments_kept),
    }
    MANIFEST_FILE.write_text(json.dumps(new_manifest, ensure_ascii=False, indent=2))

    elapsed = time.time() - t0
    print(f"增量索引完成: {len(all_segments)} 段 ({len(old_segments_kept)} 保留 + {len(new_segments)} 新), 耗时 {elapsed:.1f}s", flush=True)

    return {
        "ok": True,
        "rebuilt": True,
        "incremental": True,
        "n_segments": len(all_segments),
        "segments_kept": len(old_segments_kept),
        "segments_changed": len(new_segments),
        "build_time_s": round(elapsed, 1),
    }


def _rebuild_full(md_files: list[Path], current_hash: str | None = None) -> dict:
    """全量重建索引"""
    if current_hash is None:
        current_hash = compute_file_hash(md_files)

    t0 = time.time()

    # 加载模型
    print("加载模型...", flush=True)
    os.environ.setdefault("HF_HOME", "/mnt/data/openclaw/huggingface")
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"
    from sentence_transformers import SentenceTransformer
    model = SentenceTransformer(MODEL_PATH, device="cpu")

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
    parser.add_argument("--incremental-view", action="store_true",
                        help="增量索引模式（lifecycle-maintainer 调用）：逐文件 hash 对比，只重建变化的文件")
    parser.add_argument("--json", action="store_true", default=True)
    args = parser.parse_args()

    if args.incremental_view:
        result = build_incremental()
        print(json.dumps(result, ensure_ascii=False))
        return 0 if result.get("ok") else 1

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
