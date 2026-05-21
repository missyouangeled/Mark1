#!/usr/bin/env python3
"""
OpenClaw Data Chat — 轻量 HTTP 代理 + 聊天界面
┌─────────┐    :8899    ┌──────────────┐    :18790    ┌──────────────────┐
│ 浏览器   │ ◄────────► │ data-chat.py │ ◄────────► │ infos-handle     │
│          │  聊天界面    │ (proxy)      │            │ sidecar          │
└─────────┘             └──────┬───────┘            └──────────────────┘
                               │ 直接读 broker 文件
                               ▼
                        ~/.local/state/openclaw/broker/

用法:
  python3 scripts/openclaw-data-chat.py [--port PORT] [--host HOST]
  默认: http://0.0.0.0:8899
"""

import http.server
import http.client
import json
import os
import re
import sys
import urllib.request
import urllib.error
from pathlib import Path
from urllib.parse import urlparse
from socketserver import ThreadingMixIn

class ThreadingHTTPServer(ThreadingMixIn, http.server.HTTPServer):
    """Multi-threaded HTTP server so SSE doesn't block other requests."""
    daemon_threads = True

WORKSPACE = Path(__file__).resolve().parent.parent
HTML_PATH = WORKSPACE / "tools" / "openclaw-data-chat" / "index.html"
BROKER_DIR = Path.home() / ".local" / "state" / "openclaw" / "broker"
SIDECAR_URL = "http://127.0.0.1:18790"
GATEWAY_URL = "http://127.0.0.1:18789"
GATEWAY_TOKEN = "d488a7bb89c5fd8a69d4fe23c53c109017c0a5b8ca2d0a8f"

class ProxyHandler(http.server.BaseHTTPRequestHandler):
    """Serves the chat UI & proxies /api/* to infos-handle sidecar."""

    def log_message(self, fmt, *args):
        # concise log
        sys.stderr.write(f"[data-chat] {self.client_address[0]} - {fmt%args}\n")

    # ── helpers ──────────────────────────────────────────────

    def _serve_file(self, rel_path):
        """Serve a static file from workspace (safe paths only)."""
        safe_dirs = ['tmp', 'media', 'avatars', 'assets']
        rel = rel_path.lstrip('/')
        # only allow access to safe subdirectories
        parts = rel.split('/')
        if not parts or parts[0] not in safe_dirs:
            return None
        fp = WORKSPACE / rel
        fp = fp.resolve()
        if not str(fp).startswith(str(WORKSPACE.resolve())):
            return None
        if not fp.is_file():
            return None
        # determine content type
        ext = fp.suffix.lower()
        ct_map = {
            '.png':'image/png','.jpg':'image/jpeg','.jpeg':'image/jpeg',
            '.gif':'image/gif','.webp':'image/webp','.svg':'image/svg+xml',
            '.mp3':'audio/mpeg','.wav':'audio/wav','.ogg':'audio/ogg','.m4a':'audio/mp4',
            '.mp4':'video/mp4','.webm':'video/webm',
            '.json':'application/json','.txt':'text/plain','.html':'text/html',
        }
        ct = ct_map.get(ext, 'application/octet-stream')
        try:
            with open(fp, 'rb') as f:
                data = f.read()
            self.send_response(200)
            self.send_header('Content-Type', ct)
            self.send_header('Content-Length', str(len(data)))
            self.send_header('Cache-Control', 'public, max-age=300')
            self._cors()
            self.end_headers()
            self.wfile.write(data)
        except Exception as e:
            self._send_json(500, {'error':'serve_failed','detail':str(e)})
        return True

    def _send_html(self, code, body):
        self.send_response(code)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self._cors()
        self.end_headers()
        self.wfile.write(body.encode("utf-8"))

    def _send_json(self, code, obj):
        body = json.dumps(obj, ensure_ascii=False, indent=2)
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self._cors()
        self.end_headers()
        self.wfile.write(body.encode("utf-8"))

    def _send_text(self, code, text):
        self.send_response(code)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self._cors()
        self.end_headers()
        self.wfile.write(text.encode("utf-8"))

    def _cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")

    def _proxy_to_sidecar(self, path, stream=False):
        """Forward request to infos-handle sidecar.
        If stream=True, use chunked transfer for SSE/streaming endpoints."""
        url = SIDECAR_URL + path
        if stream:
            self._proxy_stream(url)
            return
        try:
            req = urllib.request.Request(url)
            # forward auth if present
            auth = self.headers.get("Authorization")
            if auth:
                req.add_header("Authorization", auth)
            # forward client IP
            xff = self.headers.get("X-Forwarded-For") or self.client_address[0]
            req.add_header("X-Forwarded-For", xff)
            req.add_header("X-Real-IP", self.client_address[0])

            with urllib.request.urlopen(req, timeout=15) as resp:
                body = resp.read()
                ct = resp.headers.get("Content-Type", "application/json")
                self.send_response(resp.status)
                self.send_header("Content-Type", ct)
                self._cors()
                self.end_headers()
                self.wfile.write(body)
        except urllib.error.HTTPError as e:
            body = e.read()
            self.send_response(e.code)
            self.send_header("Content-Type", "application/json")
            self._cors()
            self.end_headers()
            self.wfile.write(body)
        except Exception as e:
            self._send_json(502, {"error": "sidecar_unreachable", "detail": str(e)})

    def _proxy_stream(self, url):
        """Stream proxy for SSE / long-lived responses."""
        parsed = urlparse(url)
        try:
            conn = http.client.HTTPConnection(parsed.hostname, parsed.port, timeout=30)
            path_qs = parsed.path + ("?" + parsed.query if parsed.query else "")
            headers = {}
            auth = self.headers.get("Authorization")
            if auth:
                headers["Authorization"] = auth
            xff = self.headers.get("X-Forwarded-For") or self.client_address[0]
            headers["X-Forwarded-For"] = xff
            headers["X-Real-IP"] = self.client_address[0]

            conn.request("GET", path_qs, headers=headers)
            resp = conn.getresponse()

            ct = resp.getheader("Content-Type", "text/event-stream")
            self.send_response(resp.status)
            self.send_header("Content-Type", ct)
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Connection", "keep-alive")
            self._cors()
            self.end_headers()

            # stream chunks
            while True:
                chunk = resp.read(4096)
                if not chunk:
                    break
                self.wfile.write(chunk)
                self.wfile.flush()
            conn.close()
        except Exception as e:
            self._send_json(502, {"error": "stream_proxy_error", "detail": str(e)})

    def _inject_media_paths(self, content):
        """If the response doesn't contain MEDIA:, scan for recently generated
        media files and append their MEDIA: paths to the response."""
        if "MEDIA:" in content:
            return content  # already has it

        import time
        now = time.time()
        injected = []

        # scan common media output dirs for files created in the last 120s
        scan_dirs = [
            WORKSPACE / "tmp" / "nvidia-image-test",
            WORKSPACE / "tmp" / "voice-replies",
        ]
        for scan_dir in scan_dirs:
            if not scan_dir.exists():
                continue
            for f in sorted(scan_dir.iterdir(), key=lambda x: x.stat().st_mtime, reverse=True):
                if not f.is_file():
                    continue
                mtime = f.stat().st_mtime
                if now - mtime > 120:
                    continue  # too old
                rel = str(f.resolve().relative_to(WORKSPACE.resolve()))
                ext = f.suffix.lower()
                if ext in ('.jpg', '.jpeg', '.png', '.gif', '.webp', '.svg',
                           '.mp3', '.wav', '.ogg', '.m4a', '.mp4', '.webm'):
                    injected.append(f"MEDIA:{rel}")
                    break  # only take the most recent per dir

        if injected:
            content = content.rstrip() + "\n\n" + "\n".join(injected)
        return content

    def _proxy_chat(self, body):
        """Proxy chat completion to Gateway OpenAI endpoint."""
        try:
            parsed = urlparse(GATEWAY_URL)
            conn = http.client.HTTPConnection(parsed.hostname, parsed.port, timeout=180)
            headers = {
                "Content-Type": "application/json",
                "Authorization": "Bearer " + GATEWAY_TOKEN,
            }
            # forward model override from request
            req_model = self.headers.get("X-OpenClaw-Model", "")
            if req_model:
                headers["X-OpenClaw-Model"] = req_model
            conn.request("POST", "/v1/chat/completions", body=body, headers=headers)
            resp = conn.getresponse()
            rbody = resp.read()
            ct = resp.getheader("Content-Type", "application/json")

            # post-process: inject MEDIA paths if model forgot them
            try:
                data = json.loads(rbody)
                if data.get("choices"):
                    for choice in data["choices"]:
                        msg = choice.get("message", {})
                        if msg.get("content"):
                            msg["content"] = self._inject_media_paths(msg["content"])
                rbody = json.dumps(data, ensure_ascii=False).encode("utf-8")
            except (json.JSONDecodeError, UnicodeDecodeError):
                pass  # couldn't parse, send raw

            self.send_response(resp.status)
            self.send_header("Content-Type", ct)
            self._cors()
            self.end_headers()
            self.wfile.write(rbody)
            conn.close()
        except Exception as e:
            self._send_json(502, {"error": "gateway_unreachable", "detail": str(e)})

    # ── broker helpers ───────────────────────────────────────

    def _broker_events(self, n=20):
        ef = BROKER_DIR / "events.jsonl"
        if not ef.exists():
            return []
        lines = []
        with open(ef, "r") as f:
            for line in f:
                line = line.strip()
                if line:
                    lines.append(line)
        recent = lines[-n:]
        events = []
        for line in recent:
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                events.append({"raw": line[:200]})
        return events

    def _broker_views(self):
        vd = BROKER_DIR / "views"
        if not vd.exists():
            return {"error": "views dir not found", "path": str(vd)}
        views = {}
        for f in sorted(vd.iterdir()):
            if f.suffix == ".json":
                try:
                    with open(f) as fh:
                        data = json.load(fh)
                    # summary: include top-level keys + file size
                    summary = {
                        "file": f.name,
                        "size": f.stat().st_size,
                        "keys": list(data.keys())[:20] if isinstance(data, dict) else f"[{type(data).__name__}]"
                    }
                    views[f.stem] = summary
                except Exception as e:
                    views[f.stem] = {"error": str(e)}
        return views

    def _broker_view_detail(self, name):
        vf = BROKER_DIR / "views" / f"{name}.json"
        if not vf.exists():
            return {"error": "view not found", "name": name, "available": [f.stem for f in sorted((BROKER_DIR/"views").glob("*.json"))]}
        try:
            with open(vf) as f:
                return json.load(f)
        except Exception as e:
            return {"error": str(e)}

    # ── routing ───────────────────────────────────────────────

    def do_OPTIONS(self):
        self.send_response(204)
        self._cors()
        self.end_headers()

    def do_GET(self):
        path = self.path.split("?")[0]

        # ── media static files ──
        if path.startswith("/media/"):
            self._serve_file(path[7:])
            return
        if path == "/" or path == "/index.html":
            if HTML_PATH.exists():
                with open(HTML_PATH, "r") as f:
                    html = f.read()
                self._send_html(200, html)
            else:
                self._send_html(500, f"<h1>HTML not found</h1><p>{HTML_PATH}</p>")
            return

        # ── broker special routes ──
        if path == "/api/broker/events":
            qs = self.path.split("?")[-1] if "?" in self.path else ""
            n = 20
            for p in qs.split("&"):
                if p.startswith("n="):
                    try: n = int(p[2:])
                    except: pass
            events = self._broker_events(n)
            self._send_json(200, {"count": len(events), "events": events})
            return

        if path == "/api/broker/views":
            views = self._broker_views()
            self._send_json(200, views)
            return

        m = re.match(r"^/api/broker/views/([\w\-\.]+)$", path)
        if m:
            detail = self._broker_view_detail(m.group(1))
            self._send_json(200, detail)
            return

        # ── proxy to sidecar ──
        if path.startswith("/api/"):
            proxy_path = path[4:]  # strip /api prefix
            if not proxy_path.startswith("/"):
                proxy_path = "/" + proxy_path
            # preserve query string
            if "?" in self.path:
                proxy_path += "?" + self.path.split("?", 1)[1]
            # auto-detect SSE / stream endpoints
            is_stream = "/events/stream" in proxy_path
            self._proxy_to_sidecar(proxy_path, stream=is_stream)
            return

        # ── 404 ──
        self._send_json(404, {"error": "not_found", "path": path})

    def do_POST(self):
        # read body
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length) if length else b""

        path = self.path.split("?")[0]

        # ── chat completions ──
        if path == "/api/chat/completions":
            self._proxy_chat(body)
            return

        if path.startswith("/api/"):
            proxy_path = path[4:]
            if not proxy_path.startswith("/"):
                proxy_path = "/" + proxy_path
            if "?" in self.path:
                proxy_path += "?" + self.path.split("?", 1)[1]

            url = SIDECAR_URL + proxy_path
            try:
                req = urllib.request.Request(url, data=body, method="POST")
                ct = self.headers.get("Content-Type", "")
                if ct:
                    req.add_header("Content-Type", ct)
                auth = self.headers.get("Authorization")
                if auth:
                    req.add_header("Authorization", auth)
                xff = self.headers.get("X-Forwarded-For") or self.client_address[0]
                req.add_header("X-Forwarded-For", xff)
                req.add_header("X-Real-IP", self.client_address[0])

                with urllib.request.urlopen(req, timeout=15) as resp:
                    rbody = resp.read()
                    rct = resp.headers.get("Content-Type", "application/json")
                    self.send_response(resp.status)
                    self.send_header("Content-Type", rct)
                    self._cors()
                    self.end_headers()
                    self.wfile.write(rbody)
            except urllib.error.HTTPError as e:
                rbody = e.read()
                self.send_response(e.code)
                self.send_header("Content-Type", "application/json")
                self._cors()
                self.end_headers()
                self.wfile.write(rbody)
            except Exception as e:
                self._send_json(502, {"error": "sidecar_unreachable", "detail": str(e)})
            return

        self._send_json(404, {"error": "not_found", "path": path})


def main():
    import argparse
    ap = argparse.ArgumentParser(description="OpenClaw Data Chat")
    ap.add_argument("--port", type=int, default=8899)
    ap.add_argument("--host", default="0.0.0.0")
    args = ap.parse_args()

    if not HTML_PATH.exists():
        print(f"[data-chat] ⚠ HTML 未找到: {HTML_PATH}")
        print("[data-chat] 请确保 tools/openclaw-data-chat/index.html 存在")
        sys.exit(1)

    addr = (args.host, args.port)
    server = ThreadingHTTPServer(addr, ProxyHandler)
    print(f"[data-chat] 🚀 启动 → http://{args.host}:{args.port}")
    print(f"[data-chat] 📡 代理 → {SIDECAR_URL}")
    print(f"[data-chat] 📂 broker → {BROKER_DIR}")
    print(f"[data-chat] 🌐 前端 → {HTML_PATH}")
    print(f"[data-chat] 按 Ctrl+C 停止")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[data-chat] 已停止")
        server.server_close()


if __name__ == "__main__":
    main()
