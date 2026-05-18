#!/usr/bin/env python3
# 适用机器：通用（当前按公司 Linux 的 Control UI 直连需求做最小验证）
# 系统 / OS：通用
# 用途：为 infos-handle 提供最小本地 HTTP/SSE sidecar，给 Control UI 等消费方优先直连统一请求层。

from __future__ import annotations

import argparse
import json
import socketserver
import sys
import time
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from openclaw_infos_handle_contract import invoke_handle_query, invoke_handle_request

WORKSPACE = Path(__file__).resolve().parents[1]
INFOS_HANDLE_SCRIPT = WORKSPACE / "scripts" / "openclaw-infos-handle.py"
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 18790
DEFAULT_SSE_KIND = "snapshot.summary"
DEFAULT_SSE_INTERVAL_MS = 15000
DEFAULT_OUTPUT_ROOT = WORKSPACE / "tmp" / "infos-handle" / "outputs"
DEFAULT_BROKER_ROOT = Path.home() / ".local" / "state" / "openclaw" / "broker"
DEFAULT_SNAPSHOT_PATH = DEFAULT_BROKER_ROOT / "views" / "snapshot.json"
DEFAULT_EVENTS_PATH = DEFAULT_BROKER_ROOT / "events.jsonl"


class SidecarServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(
        self,
        server_address: tuple[str, int],
        handler_class: type[BaseHTTPRequestHandler],
        *,
        snapshot_path: Path,
        events_path: Path,
        output_root: Path,
        python_executable: str,
    ) -> None:
        super().__init__(server_address, handler_class)
        self.snapshot_path = snapshot_path
        self.events_path = events_path
        self.output_root = output_root
        self.python_executable = python_executable


class SidecarHandler(BaseHTTPRequestHandler):
    server: SidecarServer
    protocol_version = "HTTP/1.1"

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A003
        sys.stderr.write(f"[infos-handle-sidecar] {self.address_string()} - {format % args}\n")

    def do_OPTIONS(self) -> None:  # noqa: N802
        self.send_response(HTTPStatus.NO_CONTENT)
        self._send_common_headers(content_type="text/plain; charset=utf-8", content_length=0)
        self.end_headers()

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path == "/healthz":
            self._write_json(
                {
                    "ok": True,
                    "service": "infos-handle-sidecar",
                    "snapshotPath": str(self.server.snapshot_path),
                    "eventsPath": str(self.server.events_path),
                    "outputRoot": str(self.server.output_root),
                }
            )
            return
        if parsed.path.startswith("/v1/query/"):
            self._handle_query(parsed)
            return
        if parsed.path == "/v1/events/stream":
            self._handle_sse(parsed)
            return
        self._write_json({"ok": False, "error": f"unknown path: {parsed.path}"}, status=HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path != "/v1/handle":
            self._write_json({"ok": False, "error": f"unknown path: {parsed.path}"}, status=HTTPStatus.NOT_FOUND)
            return
        try:
            content_length = int(self.headers.get("Content-Length") or "0")
        except ValueError:
            content_length = 0
        raw_body = self.rfile.read(content_length) if content_length > 0 else b""
        try:
            payload = json.loads(raw_body.decode("utf-8") or "{}")
        except json.JSONDecodeError as exc:
            self._write_json({"ok": False, "error": f"invalid json body: {exc}"}, status=HTTPStatus.BAD_REQUEST)
            return
        if not isinstance(payload, dict):
            self._write_json({"ok": False, "error": "request body must be a JSON object"}, status=HTTPStatus.BAD_REQUEST)
            return
        payload.setdefault("snapshotPath", str(self.server.snapshot_path))
        payload.setdefault("eventsPath", str(self.server.events_path))
        payload.setdefault("outputRoot", str(self.server.output_root))
        try:
            response = invoke_handle_request(
                INFOS_HANDLE_SCRIPT,
                payload,
                python_executable=self.server.python_executable,
            )
        except RuntimeError as exc:
            self._write_json({"ok": False, "error": str(exc)}, status=HTTPStatus.BAD_GATEWAY)
            return
        status = HTTPStatus.OK if response.get("ok") else HTTPStatus.BAD_GATEWAY
        self._write_json(response, status=status)

    def _handle_query(self, parsed) -> None:
        kind = parsed.path.removeprefix("/v1/query/").strip("/")
        if not kind:
            self._write_json({"ok": False, "error": "missing query kind"}, status=HTTPStatus.BAD_REQUEST)
            return
        params = parse_qs(parsed.query, keep_blank_values=False)
        output_format = self._first_text(params.get("format")) or "json"
        if output_format not in {"text", "json"}:
            self._write_json({"ok": False, "error": "query endpoint currently only supports format=text|json"}, status=HTTPStatus.BAD_REQUEST)
            return
        limit = self._parse_int(self._first_text(params.get("limit")))
        try:
            snapshot = invoke_handle_query(
                INFOS_HANDLE_SCRIPT,
                kind=kind,
                output_format=output_format,
                limit=limit,
                source_name=self._first_text(params.get("sourceName"), params.get("source_name")),
                panel_name=self._first_text(params.get("panelName"), params.get("panel_name")),
                snapshot_path=str(self.server.snapshot_path),
                events_path=str(self.server.events_path),
                python_executable=self.server.python_executable,
            )
        except RuntimeError as exc:
            self._write_json({"ok": False, "error": str(exc), "kind": kind}, status=HTTPStatus.BAD_GATEWAY)
            return
        if output_format == "text":
            self._write_text(str(snapshot.get("text") or ""), content_type="text/plain; charset=utf-8")
            return
        self._write_json(snapshot)

    def _handle_sse(self, parsed) -> None:
        params = parse_qs(parsed.query, keep_blank_values=False)
        kind = self._first_text(params.get("kind")) or DEFAULT_SSE_KIND
        interval_ms = max(1000, self._parse_int(self._first_text(params.get("intervalMs")), DEFAULT_SSE_INTERVAL_MS) or DEFAULT_SSE_INTERVAL_MS)
        self.send_response(HTTPStatus.OK)
        self._send_common_headers(content_type="text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
        self.send_header("Connection", "keep-alive")
        self.end_headers()
        self.close_connection = False
        event_id = 0
        try:
            while True:
                event_id += 1
                payload = self._build_sse_payload(kind)
                body = json.dumps(payload, ensure_ascii=False)
                chunk = f"id: {event_id}\nevent: snapshot\ndata: {body}\n\n".encode("utf-8")
                self.wfile.write(chunk)
                self.wfile.flush()
                time.sleep(interval_ms / 1000)
        except (BrokenPipeError, ConnectionResetError, OSError):
            return
        except RuntimeError as exc:
            try:
                body = json.dumps({"ok": False, "error": str(exc), "kind": kind}, ensure_ascii=False)
                self.wfile.write(f"event: error\ndata: {body}\n\n".encode("utf-8"))
                self.wfile.flush()
            except Exception:
                return

    def _build_sse_payload(self, kind: str) -> dict[str, Any]:
        return invoke_handle_query(
            INFOS_HANDLE_SCRIPT,
            kind=kind,
            output_format="json",
            snapshot_path=str(self.server.snapshot_path),
            events_path=str(self.server.events_path),
            python_executable=self.server.python_executable,
        )

    def _write_json(self, payload: dict[str, Any], *, status: HTTPStatus = HTTPStatus.OK) -> None:
        content = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(status)
        self._send_common_headers(content_type="application/json; charset=utf-8", content_length=len(content))
        self.end_headers()
        self.wfile.write(content)

    def _write_text(self, payload: str, *, status: HTTPStatus = HTTPStatus.OK, content_type: str = "text/plain; charset=utf-8") -> None:
        content = payload.encode("utf-8")
        self.send_response(status)
        self._send_common_headers(content_type=content_type, content_length=len(content))
        self.end_headers()
        self.wfile.write(content)

    def _send_common_headers(self, *, content_type: str, content_length: int | None = None) -> None:
        self.send_header("Content-Type", content_type)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Methods", "GET,POST,OPTIONS")
        self.send_header("Cache-Control", "no-store")
        if content_length is not None:
            self.send_header("Content-Length", str(content_length))

    @staticmethod
    def _first_text(*value_lists: list[str] | None) -> str | None:
        for values in value_lists:
            if not values:
                continue
            for value in values:
                if isinstance(value, str) and value.strip():
                    return value.strip()
        return None

    @staticmethod
    def _parse_int(raw: str | None, default: int | None = None) -> int | None:
        if raw is None:
            return default
        try:
            return int(raw)
        except ValueError:
            return default


def main() -> int:
    parser = argparse.ArgumentParser(description="Minimal infos-handle HTTP/SSE sidecar")
    parser.add_argument("--host", default=DEFAULT_HOST, help="Bind host (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help="Bind port")
    parser.add_argument("--snapshot-path", default=str(DEFAULT_SNAPSHOT_PATH), help="Broker snapshot.json path")
    parser.add_argument("--events-path", default=str(DEFAULT_EVENTS_PATH), help="Broker events.jsonl path")
    parser.add_argument("--output-root", default=str(DEFAULT_OUTPUT_ROOT), help="Directory for infos-handle preview artifacts")
    args = parser.parse_args()

    server = SidecarServer(
        (args.host, args.port),
        SidecarHandler,
        snapshot_path=Path(args.snapshot_path).expanduser().resolve(),
        events_path=Path(args.events_path).expanduser().resolve(),
        output_root=Path(args.output_root).expanduser().resolve(),
        python_executable=sys.executable,
    )
    print(json.dumps({
        "ok": True,
        "service": "infos-handle-sidecar",
        "host": args.host,
        "port": args.port,
        "snapshotPath": str(server.snapshot_path),
        "eventsPath": str(server.events_path),
        "outputRoot": str(server.output_root),
    }, ensure_ascii=False))
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        return 0
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
