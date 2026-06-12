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


def _handle_client(conn, handler_cls):
    """在独立线程中处理单个 HTTP 连接（原生 socket）"""
    try:
        rfile = conn.makefile('rb', buffering=0)
        wfile = conn.makefile('wb', buffering=0)

        # 解析请求行
        request_line = rfile.readline().decode('utf-8', errors='replace').strip()
        if not request_line:
            conn.close()
            return

        parts = request_line.split()
        if len(parts) < 2:
            conn.sendall(b'HTTP/1.1 400 Bad Request\r\n\r\n')
            conn.close()
            return

        method, path = parts[0].upper(), parts[1]

        # 读 headers
        headers = {}
        while True:
            line = rfile.readline().decode('utf-8', errors='replace').strip()
            if not line:
                break
            if ':' in line:
                k, v = line.split(':', 1)
                headers[k.strip().lower()] = v.strip()

        content_len = int(headers.get('content-length', 0))
        body = rfile.read(content_len) if content_len > 0 else b''

        # 创建 handler 实例并处理
        handler = handler_cls(method, path, headers, body)
        status_code, resp_headers, resp_body = handler.handle()

        # 发送响应
        status_text = {200: 'OK', 400: 'Bad Request', 404: 'Not Found', 413: 'Payload Too Large',
                       500: 'Internal Server Error', 503: 'Service Unavailable'}.get(status_code, 'Error')
        resp = f'HTTP/1.1 {status_code} {status_text}\r\n'
        for k, v in resp_headers.items():
            resp += f'{k}: {v}\r\n'
        resp += '\r\n'
        wfile.write(resp.encode())
        wfile.write(resp_body)
        wfile.flush()
    except Exception:
        pass
    finally:
        try:
            conn.close()
        except Exception:
            pass


class SimpleEmbedHandler:
    """原生 HTTP handler（不依赖 BaseHTTPRequestHandler/selectors）"""
    def __init__(self, method, path, headers, body):
        self.method = method
        self.path = path
        self.headers = headers
        self.body = body

    def handle(self):
        if self.method == 'GET':
            return self._get()
        elif self.method == 'POST':
            return self._post()
        return 405, {}, b'{"ok":false,"error":"method not allowed"}'

    def _json_resp(self, data, code=200):
        body = json.dumps(data, ensure_ascii=False).encode()
        return code, {'Content-Type': 'application/json; charset=utf-8', 'Content-Length': str(len(body))}, body

    def _get(self):
        if self.path == '/healthz':
            return self._json_resp({'ok': True, 'model_loaded': _model is not None})
        if self.path == '/stats':
            uptime = time.time() - _started_at if _started_at > 0 else 0
            return self._json_resp({
                'ok': True, 'model': 'paraphrase-multilingual-MiniLM-L12-v2',
                'model_loaded': _model is not None,
                'index_segments': len(_segments) if _segments else 0,
                'uptime_seconds': round(uptime, 1),
                'total_queries': _total_queries, 'total_errors': _total_errors,
            })
        return self._json_resp({'ok': False, 'error': 'not found'}, 404)

    def _post(self):
        try:
            data = json.loads(self.body)
        except json.JSONDecodeError:
            return self._json_resp({'ok': False, 'error': 'invalid JSON'}, 400)

        if self.path == '/search':
            query = data.get('query', '').strip()
            if not query:
                return self._json_resp({'ok': False, 'error': "missing 'query'"}, 400)
            top_k = int(data.get('top', 5))
            return self._json_resp(do_search(query, top_k=top_k))

        if self.path == '/encode':
            texts = data.get('texts', [])
            if not texts or not isinstance(texts, list):
                return self._json_resp({'ok': False, 'error': "missing 'texts' array"}, 400)
            if len(texts) > 200:
                return self._json_resp({'ok': False, 'error': 'max 500 texts per request'}, 413)
            if _model is None:
                return self._json_resp({'ok': False, 'error': 'model not loaded'}, 503)
            try:
                vecs = _model.encode(texts, show_progress_bar=False, batch_size=32)
                return self._json_resp({'ok': True, 'embeddings': vecs.tolist(),
                                        'dim': int(vecs.shape[1]), 'count': len(texts)})
            except Exception as e:
                return self._json_resp({'ok': False, 'error': str(e)}, 500)

        if self.path == '/search/batch':
            queries = data.get('queries', [])
            if not queries or not isinstance(queries, list):
                return self._json_resp({'ok': False, 'error': "missing 'queries' array"}, 400)
            results = [do_search(q) for q in queries[:20]]
            return self._json_resp({'ok': True, 'results': results})

        return self._json_resp({'ok': False, 'error': 'not found'}, 404)


def main():
    parser = argparse.ArgumentParser(description="embed-sidecar")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    args = parser.parse_args()

    load_resources()

    import socket
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind((args.host, args.port))
    sock.listen(128)
    sock.settimeout(1.0)

    sys.stderr.write(f"[embed-sidecar] listening on {args.host}:{args.port}\n")

    running = True
    def _stop(sig, frame):
        nonlocal running
        running = False
        sys.stderr.write(f"\n[embed-sidecar] shutting down ({_total_queries} queries, {_total_errors} errors)\n")
    signal.signal(signal.SIGINT, _stop)
    signal.signal(signal.SIGTERM, _stop)

    while running:
        try:
            conn, addr = sock.accept()
            threading.Thread(target=_handle_client, args=(conn, SimpleEmbedHandler), daemon=True).start()
        except socket.timeout:
            continue
        except KeyboardInterrupt:
            break
        except Exception as e:
            sys.stderr.write(f"[embed-sidecar] accept error: {e}\n")
            time.sleep(0.5)

    sock.close()


if __name__ == "__main__":
    main()
