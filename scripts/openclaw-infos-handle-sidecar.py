#!/usr/bin/env python3
# 适用机器：通用（当前按公司 Linux 的 Control UI 直连需求做验证）
# 系统 / OS：通用
# 用途：为 infos-handle 提供稳固的本地 HTTP/SSE sidecar，给 Control UI 等消费方优先直连统一请求层。

from __future__ import annotations

import argparse
import json
import mimetypes
import os
import signal
import socketserver
import subprocess
import sys
import threading
import time
from contextlib import contextmanager
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, quote, unquote, urlparse

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
ARTIFACT_ROUTE_PREFIX = "/v1/artifacts"
ARTIFACT_TRUE_VALUES = {"1", "true", "yes", "on"}
ARTIFACT_SUFFIX_PREFERENCE = {
    "image": [".svg", ".png", ".webp", ".jpg", ".jpeg", ".gif"],
    "audio": [".mp3", ".wav", ".m4a", ".ogg", ".flac"],
}
HANDLE_TIMEOUT_SECONDS = int(os.environ.get("INFOS_HANDLE_SIDECAR_HANDLE_TIMEOUT_S", "45"))
SSE_QUERY_TIMEOUT_SECONDS = int(os.environ.get("INFOS_HANDLE_SIDECAR_SSE_QUERY_TIMEOUT_S", "20"))
MAX_ACTIVE_REQUESTS = int(os.environ.get("INFOS_HANDLE_SIDECAR_MAX_ACTIVE", "32"))
REQUEST_BODY_LIMIT_BYTES = 256 * 1024
GATEWAY_CONFIG_PATH = Path.home() / ".openclaw" / "openclaw.json"
NO_AUTH_PATHS = {"/healthz"}


def _load_gateway_auth_config() -> dict[str, Any]:
    """Read Gateway auth config from openclaw.json. Returns empty dict on failure."""
    try:
        if not GATEWAY_CONFIG_PATH.exists():
            return {}
        with open(GATEWAY_CONFIG_PATH, "r", encoding="utf-8") as fh:
            # Use json5-style relaxed parsing; fall back to plain json
            raw = fh.read()
            try:
                import json5
                config = json5.loads(raw)
            except ImportError:
                config = json.loads(raw)
    except Exception:
        return {}
    if not isinstance(config, dict):
        return {}
    auth = config.get("gateway", {}).get("auth") if isinstance(config.get("gateway"), dict) else None
    return auth if isinstance(auth, dict) else {}


def _check_auth(handler: BaseHTTPRequestHandler, parsed_path: str) -> bool:
    """Validate Bearer token against Gateway auth config. Returns True if authorized."""
    # No auth for healthz and artifact routes (artifacts use opaque refs)
    if parsed_path in NO_AUTH_PATHS or parsed_path.startswith(f"{ARTIFACT_ROUTE_PREFIX}/"):
        return True
    # Localhost is always allowed (backward compat for local consumers like Control UI)
    client_host = handler.client_address[0] if handler.client_address else ""
    if client_host in ("127.0.0.1", "::1", "localhost"):
        return True
    auth_config = _load_gateway_auth_config()
    mode = str(auth_config.get("mode") or "")
    if mode == "none":
        return True
    if mode not in ("token", "password"):
        return False
    expected = str(auth_config.get("token") or auth_config.get("password") or "")
    if not expected:
        return False
    auth_header = handler.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return False
    provided = auth_header[7:].strip()
    return _constant_time_compare(provided, expected)


def _constant_time_compare(a: str, b: str) -> bool:
    if len(a) != len(b):
        return False
    result = 0
    for x, y in zip(a, b):
        result |= ord(x) ^ ord(y)
    return result == 0


def build_artifact_href(artifact_ref: str) -> str:
    return f"{ARTIFACT_ROUTE_PREFIX}/{quote(artifact_ref, safe='')}"



def enrich_artifact_hrefs(payload: Any) -> None:
    if isinstance(payload, dict):
        artifact = payload.get("artifact") if isinstance(payload.get("artifact"), dict) else None
        artifact_ref = None
        if artifact:
            ref_value = artifact.get("ref")
            if isinstance(ref_value, str) and ref_value.strip():
                artifact_ref = ref_value.strip()
        if artifact_ref is None:
            ref_value = payload.get("artifactRef")
            if isinstance(ref_value, str) and ref_value.strip():
                artifact_ref = ref_value.strip()
        if artifact_ref:
            href = build_artifact_href(artifact_ref)
            payload.setdefault("artifactHref", href)
            if artifact:
                artifact.setdefault("href", href)
        for value in payload.values():
            enrich_artifact_hrefs(value)
    elif isinstance(payload, list):
        for item in payload:
            enrich_artifact_hrefs(item)



def resolve_artifact_path(output_root: Path, artifact_ref: str) -> tuple[Path, str]:
    normalized_ref = str(artifact_ref or "").strip()
    parts = normalized_ref.split(":", 2)
    if len(parts) != 3 or parts[0] != "infos-handle":
        raise ValueError(f"unsupported artifact ref: {artifact_ref}")
    format_name = parts[1].strip()
    stem = parts[2].strip()
    if format_name not in ARTIFACT_SUFFIX_PREFERENCE:
        raise FileNotFoundError(f"unsupported artifact format: {format_name}")
    if not stem or any(char not in "abcdefghijklmnopqrstuvwxyz0123456789-_." for char in stem.lower()):
        raise ValueError(f"invalid artifact stem: {stem}")
    artifact_dir = (output_root / format_name).resolve()
    if not artifact_dir.exists():
        raise FileNotFoundError(f"artifact directory missing: {artifact_dir}")

    preferred_suffixes = ARTIFACT_SUFFIX_PREFERENCE.get(format_name) or []
    suffix_rank = {suffix: index for index, suffix in enumerate(preferred_suffixes)}
    candidates: list[Path] = []
    for candidate in artifact_dir.glob(f"{stem}.*"):
        resolved = candidate.resolve()
        try:
            resolved.relative_to(artifact_dir)
        except ValueError:
            continue
        if resolved.is_file():
            candidates.append(resolved)
    if not candidates:
        raise FileNotFoundError(f"artifact not found: {artifact_ref}")
    candidates.sort(key=lambda item: (suffix_rank.get(item.suffix.lower(), 999), item.name))
    return candidates[0], format_name



def guess_artifact_media_type(path: Path, format_name: str) -> str:
    guessed, _ = mimetypes.guess_type(path.name)
    if guessed:
        return guessed
    return {
        "image": "image/svg+xml",
        "audio": "audio/mpeg",
    }.get(format_name, "application/octet-stream")


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
        self._sse_connections: int = 0
        self._active_requests: int = 0
        self._lock: threading.Lock = threading.Lock()
        self._started_at: float = time.time()
        self._total_requests: int = 0
        self._total_errors: int = 0

    def validate_startup(self) -> None:
        if not INFOS_HANDLE_SCRIPT.exists():
            raise FileNotFoundError(f"infos-handle script not found: {INFOS_HANDLE_SCRIPT}")
        self.output_root.mkdir(parents=True, exist_ok=True)
        sys.stderr.write(
            f"[infos-handle-sidecar] startup ok snapshot={self.snapshot_path} events={self.events_path} "
            f"output_root={self.output_root} handle_timeout={HANDLE_TIMEOUT_SECONDS}s "
            f"sse_query_timeout={SSE_QUERY_TIMEOUT_SECONDS}s max_active={MAX_ACTIVE_REQUESTS}\n"
        )

    @contextmanager
    def acquire_request_slot(self):
        with self._lock:
            if self._active_requests >= MAX_ACTIVE_REQUESTS:
                raise RuntimeError(
                    f"too many active requests ({self._active_requests}/{MAX_ACTIVE_REQUESTS}); try again shortly"
                )
            self._active_requests += 1
            self._total_requests += 1
        try:
            yield
        finally:
            with self._lock:
                self._active_requests = max(0, self._active_requests - 1)

    def record_error(self) -> None:
        with self._lock:
            self._total_errors += 1

    def server_stats(self) -> dict[str, Any]:
        with self._lock:
            return {
                "startedAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(self._started_at)),
                "uptimeSeconds": round(time.time() - self._started_at, 1),
                "sseConnections": self._sse_connections,
                "activeRequests": self._active_requests,
                "totalRequests": self._total_requests,
                "totalErrors": self._total_errors,
                "maxActiveRequests": MAX_ACTIVE_REQUESTS,
            }


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
        if not _check_auth(self, parsed.path):
            self._write_json({"ok": False, "error": "unauthorized"}, status=HTTPStatus.UNAUTHORIZED)
            return
        if parsed.path == "/healthz":
            self._write_json(
                {
                    "ok": True,
                    "service": "infos-handle-sidecar",
                    "snapshotPath": str(self.server.snapshot_path),
                    "eventsPath": str(self.server.events_path),
                    "outputRoot": str(self.server.output_root),
                    "artifactRoutePrefix": ARTIFACT_ROUTE_PREFIX,
                    "sseConnections": self.server._sse_connections,
                }
            )
            return
        if parsed.path.startswith("/v1/query/"):
            self._handle_query(parsed)
            return
        if parsed.path == ARTIFACT_ROUTE_PREFIX or parsed.path.startswith(f"{ARTIFACT_ROUTE_PREFIX}/"):
            self._handle_artifact(parsed)
            return
        if parsed.path == "/v1/events/stream":
            self._handle_sse(parsed)
            return
        self._write_json({"ok": False, "error": f"unknown path: {parsed.path}"}, status=HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        if not _check_auth(self, parsed.path):
            self._write_json({"ok": False, "error": "unauthorized"}, status=HTTPStatus.UNAUTHORIZED)
            return
        if parsed.path != "/v1/handle":
            self._write_json({"ok": False, "error": f"unknown path: {parsed.path}"}, status=HTTPStatus.NOT_FOUND)
            return
        try:
            with self.server.acquire_request_slot():
                self._do_handle(parsed)
        except RuntimeError as exc:
            self.server.record_error()
            self._write_json({"ok": False, "error": str(exc)}, status=HTTPStatus.SERVICE_UNAVAILABLE)

    def _do_handle(self, parsed) -> None:
        try:
            content_length = int(self.headers.get("Content-Length") or "0")
        except ValueError:
            content_length = 0
        if content_length > REQUEST_BODY_LIMIT_BYTES:
            self._write_json(
                {"ok": False, "error": "request body too large", "maxBytes": REQUEST_BODY_LIMIT_BYTES},
                status=HTTPStatus.REQUEST_ENTITY_TOO_LARGE,
            )
            return
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
        request_id = payload.get("requestId", "-")
        try:
            response = self._invoke_handle_with_timeout(payload)
        except subprocess.TimeoutExpired as exc:
            self.server.record_error()
            sys.stderr.write(
                f"[infos-handle-sidecar] handle timeout requestId={request_id} timeout={exc.timeout}s\n"
            )
            self._write_json(
                {
                    "ok": False,
                    "error": f"handle request timed out after {HANDLE_TIMEOUT_SECONDS}s",
                    "requestId": request_id,
                },
                status=HTTPStatus.GATEWAY_TIMEOUT,
            )
            return
        except RuntimeError as exc:
            self.server.record_error()
            self._write_json({"ok": False, "error": str(exc), "requestId": request_id}, status=HTTPStatus.BAD_GATEWAY)
            return
        enrich_artifact_hrefs(response)
        status = HTTPStatus.OK if response.get("ok") else HTTPStatus.BAD_GATEWAY
        self._write_json(response, status=status)

    def _invoke_handle_with_timeout(self, payload: dict[str, Any]) -> dict[str, Any]:
        return invoke_handle_request(
            INFOS_HANDLE_SCRIPT,
            payload,
            python_executable=self.server.python_executable,
            run=lambda cmd, **kwargs: subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=False,
                timeout=HANDLE_TIMEOUT_SECONDS,
                **{k: v for k, v in kwargs.items() if k == "input"},
            ),
        )

    def _handle_query(self, parsed) -> None:
        kind = parsed.path.removeprefix("/v1/query/").strip("/")
        if not kind:
            self._write_json({"ok": False, "error": "missing query kind"}, status=HTTPStatus.BAD_REQUEST)
            return
        params = parse_qs(parsed.query, keep_blank_values=False)
        output_format = self._first_text(params.get("format")) or "json"
        if output_format in {"image", "audio"}:
            self._handle_query_via_post(kind, output_format, params)
            return
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
        except Exception as exc:
            self._write_json({"ok": False, "error": str(exc), "kind": kind}, status=HTTPStatus.BAD_GATEWAY)
            return
        if output_format == "text":
            self._write_text(str(snapshot.get("text") or ""), content_type="text/plain; charset=utf-8")
            return
        self._write_json(snapshot)

    def _handle_query_via_post(self, kind: str, output_format: str, params: dict[str, list[str]]) -> None:
        limit = self._parse_int(self._first_text(params.get("limit")))
        payload: dict[str, Any] = {
            "kind": kind,
            "format": output_format,
            "snapshotPath": str(self.server.snapshot_path),
            "eventsPath": str(self.server.events_path),
            "outputRoot": str(self.server.output_root),
        }
        if limit is not None:
            payload["limit"] = limit
        source_name = self._first_text(params.get("sourceName"), params.get("source_name"))
        if source_name:
            payload["sourceName"] = source_name
        panel_name = self._first_text(params.get("panelName"), params.get("panel_name"))
        if panel_name:
            payload["panelName"] = panel_name
        try:
            response = invoke_handle_request(
                INFOS_HANDLE_SCRIPT,
                payload,
                python_executable=self.server.python_executable,
            )
        except Exception as exc:
            self._write_json({"ok": False, "error": str(exc), "kind": kind, "format": output_format}, status=HTTPStatus.BAD_GATEWAY)
            return
        enrich_artifact_hrefs(response)
        status = HTTPStatus.OK if response.get("ok") else HTTPStatus.BAD_GATEWAY
        self._write_json(response, status=status)

    def _handle_artifact(self, parsed) -> None:
        params = parse_qs(parsed.query, keep_blank_values=False)
        ref_from_path = parsed.path.removeprefix(ARTIFACT_ROUTE_PREFIX).strip("/")
        artifact_ref = unquote(ref_from_path) if ref_from_path else self._first_text(params.get("ref"))
        if not artifact_ref:
            self._write_json({"ok": False, "error": "missing artifact ref"}, status=HTTPStatus.BAD_REQUEST)
            return
        try:
            artifact_path, format_name = resolve_artifact_path(self.server.output_root, artifact_ref)
        except ValueError as exc:
            self._write_json({"ok": False, "error": str(exc), "artifactRef": artifact_ref}, status=HTTPStatus.BAD_REQUEST)
            return
        except FileNotFoundError as exc:
            self._write_json({"ok": False, "error": str(exc), "artifactRef": artifact_ref}, status=HTTPStatus.NOT_FOUND)
            return
        try:
            content = artifact_path.read_bytes()
        except OSError as exc:
            self._write_json({"ok": False, "error": f"unable to read artifact: {exc}", "artifactRef": artifact_ref}, status=HTTPStatus.BAD_GATEWAY)
            return

        download_flag = (self._first_text(params.get("download"), params.get("attachment")) or "").strip().lower() in ARTIFACT_TRUE_VALUES
        disposition = "attachment" if download_flag else "inline"
        self.send_response(HTTPStatus.OK)
        self._send_common_headers(content_type=guess_artifact_media_type(artifact_path, format_name), content_length=len(content))
        self.send_header("Content-Disposition", f'{disposition}; filename="{artifact_path.name}"')
        self.send_header("X-Infos-Handle-Artifact-Ref", artifact_ref)
        self.send_header("X-Infos-Handle-Artifact-Format", format_name)
        self.end_headers()
        self.wfile.write(content)

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
        with self.server._lock:
            self.server._sse_connections += 1
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
        finally:
            with self.server._lock:
                self.server._sse_connections = max(0, self.server._sse_connections - 1)

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
        "artifactRoutePrefix": ARTIFACT_ROUTE_PREFIX,
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
