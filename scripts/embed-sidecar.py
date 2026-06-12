#!/usr/bin/env python3
"""
embed-sidecar.py — 本地向量模型常驻 HTTP 服务

启动时加载 paraphrase-multilingual-MiniLM-L12-v2 到内存，
之后通过 HTTP POST /search 接收查询文本，返回语义搜索结果。

用法：
  直接运行：python3 ~/.local/share/openclaw-embed-venv311/bin/python3 scripts/embed-sidecar.py
  systemd：systemctl --user start openclaw-embed-sidecar

接口：
  GET  /healthz           → {"ok": true}
  GET  /stats             → {"model": "...", "uptime": ..., "queries": ...}
  POST /search            → body: {"query": "..."}  → {"ok": true, "results": [...], "confidence": 0.78}
  POST /search/batch      → body: {"queries": ["...", "..."]}  → {"ok": true, "results": [[...], [...]]}

默认端口：18792
"""
from __future__ import annotations

import argparse
import json
import os
import signal
import sys
import threading
import time
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import numpy as np

os.environ.setdefault("HF_HOME", "/mnt/data/openclaw/huggingface")
os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TRANSFORMERS_OFFLINE"] = "1"

MODEL_PATH = "/mnt/data/openclaw/huggingface/hub/models--sentence-transformers--paraphrase-multilingual-MiniLM-L12-v2/snapshots/main"
INDEX_DIR = Path(os.environ.get("MEMORY_INDEX_DIR", "/mnt/data/openclaw/scratch/memory-embed-index"))
DEFAULT_PORT = 18792
CONFIDENCE_THRESHOLD = 0.60

# 全局状态
_model = None
_embeddings = None
_segments = None
_lock = threading.Lock()
_started_at: float = 0.0
_total_queries: int = 0
_total_errors: int = 0


def load_resources():
    """加载模型 + 索引到内存（启动时调用一次）"""
    global _model, _embeddings, _segments, _started_at

    from sentence_transformers import SentenceTransformer

    t0 = time.time()
    sys.stderr.write("[embed-sidecar] loading model...\n")
    _model = SentenceTransformer(MODEL_PATH, device="cpu")
    sys.stderr.write(f"[embed-sidecar] model loaded in {time.time()-t0:.1f}s\n")

    if INDEX_DIR.exists():
        emb_file = INDEX_DIR / "embeddings.npy"
        seg_file = INDEX_DIR / "segments.json"
        if emb_file.exists() and seg_file.exists():
            t1 = time.time()
            _embeddings = np.load(str(emb_file))
            _segments = json.loads(seg_file.read_text())["segments"]
            sys.stderr.write(f"[embed-sidecar] index loaded: {len(_segments)} segments, {time.time()-t1:.1f}s\n")
    else:
        sys.stderr.write("[embed-sidecar] no index found, search will return empty\n")

    _started_at = time.time()
    sys.stderr.write(f"[embed-sidecar] ready (total startup: {time.time()-t0:.1f}s)\n")


def do_search(query: str, top_k: int = 5) -> dict:
    """执行语义搜索"""
    global _total_queries, _total_errors

    if _model is None:
        _total_errors += 1
        return {"ok": False, "error": "model not loaded"}

    try:
        t0 = time.time()
        query_vec = _model.encode([query], show_progress_bar=False)[0]
        query_vec = np.asarray(query_vec, dtype=np.float32)

        if _embeddings is not None and _segments is not None:
            # 余弦相似度
            query_norm = query_vec / (np.linalg.norm(query_vec) + 1e-10)
            emb_norms = _embeddings / (np.linalg.norm(_embeddings, axis=1, keepdims=True) + 1e-10)
            similarities = np.dot(emb_norms, query_norm)
            top_indices = np.argsort(similarities)[::-1][:top_k * 2]  # 取 2x 用于去重

            seen = set()
            results = []
            for idx in top_indices:
                score = float(similarities[idx])
                seg = _segments[idx]
                # 去重：同一 content hash 只保留最高分数的一条
                content_hash = hash(seg["content"])
                if content_hash in seen:
                    continue
                seen.add(content_hash)
                results.append({
                    "file": seg["file"],
                    "line": seg["line"],
                    "content": seg["content"][:500],
                    "score": round(score, 4),
                })
                if len(results) >= top_k:
                    break

            best_score = results[0]["score"] if results else 0.0
            _total_queries += 1

            return {
                "ok": True,
                "query": query,
                "results": results,
                "top_score": round(best_score, 4),
                "confidence": round(best_score, 4),
                "short_circuit": best_score >= CONFIDENCE_THRESHOLD,
                "timing_ms": round((time.time() - t0) * 1000),
            }
        else:
            return {"ok": True, "query": query, "results": [], "confidence": 0.0, "short_circuit": False}
    except Exception as e:
        _total_errors += 1
        return {"ok": False, "error": str(e)}


class EmbedHandler(BaseHTTPRequestHandler):
    server_version = "embed-sidecar/1.0"

    def log_message(self, fmt, *args):
        pass  # 静默访问日志

    def _json(self, code: int, data: dict):
        payload = json.dumps(data, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self):
        if self.path == "/healthz":
            self._json(200, {"ok": True, "model_loaded": _model is not None})
        elif self.path == "/stats":
            uptime = time.time() - _started_at if _started_at > 0 else 0
            self._json(200, {
                "ok": True,
                "model": "paraphrase-multilingual-MiniLM-L12-v2",
                "model_loaded": _model is not None,
                "index_segments": len(_segments) if _segments else 0,
                "uptime_seconds": round(uptime, 1),
                "total_queries": _total_queries,
                "total_errors": _total_errors,
            })
        else:
            self._json(404, {"ok": False, "error": "not found"})

    def do_POST(self):
        content_len = int(self.headers.get("Content-Length", 0))
        if content_len == 0:
            self._json(400, {"ok": False, "error": "empty body"})
            return
        if content_len > 65536:
            self._json(413, {"ok": False, "error": "body too large"})
            return

        try:
            body = json.loads(self.rfile.read(content_len))
        except json.JSONDecodeError:
            self._json(400, {"ok": False, "error": "invalid JSON"})
            return

        if self.path == "/search":
            query = body.get("query", "").strip()
            if not query:
                self._json(400, {"ok": False, "error": "missing 'query'"})
                return
            top_k = int(body.get("top", 5))
            result = do_search(query, top_k=top_k)
            self._json(200, result)

        elif self.path == "/search/batch":
            queries = body.get("queries", [])
            if not queries or not isinstance(queries, list):
                self._json(400, {"ok": False, "error": "missing 'queries' array"})
                return
            results = [do_search(q) for q in queries[:20]]
            self._json(200, {"ok": True, "results": results})

        else:
            self._json(404, {"ok": False, "error": "not found"})


def main():
    parser = argparse.ArgumentParser(description="embed-sidecar")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    args = parser.parse_args()

    # 预热
    t0 = time.time()
    load_resources()

    server = ThreadingHTTPServer((args.host, args.port), EmbedHandler)
    server.daemon_threads = True
    server.allow_reuse_address = True

    def _shutdown(sig, frame):
        sys.stderr.write(f"\n[embed-sidecar] shutting down ({_total_queries} queries, {_total_errors} errors)\n")
        server.shutdown()
    server.server_close()

    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    sys.stderr.write(f"[embed-sidecar] listening on {args.host}:{args.port}\n")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.shutdown()
    server.server_close()


if __name__ == "__main__":
    main()
