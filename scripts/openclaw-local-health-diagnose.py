#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import shutil
import socket
import ssl
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

WORKSPACE = Path.home() / ".openclaw" / "workspace"
CONFIG_PATH = Path.home() / ".openclaw" / "openclaw.json"
STATE_DIR = Path(os.environ.get("XDG_STATE_HOME", str(Path.home() / ".local" / "state"))) / "openclaw" / "local-health"
REPORT_PATH = STATE_DIR / "last-report.json"
SUMMARY_PATH = STATE_DIR / "last-summary.txt"
TRANSITION_PATH = STATE_DIR / "transition-state.json"
LOG_PATH = STATE_DIR / "health-diagnostic.log"
FALLBACK_INTERFACE = {
    "reserved": True,
    "enabled": False,
    "backend": None,
    "endpoint": None,
    "command": None,
    "notes": "Reserved for future local fallback model handoff when primary routes are unavailable.",
}
DEFAULT_GENERIC_PROBES = [
    ("github-api", "https://api.github.com"),
    ("baidu-home", "https://www.baidu.com"),
]
REQUEST_TIMEOUT_SECONDS = 5.0
OPENCLAW_STATUS_TIMEOUT_SECONDS = 8.0


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as fh:
        data = json.load(fh)
    return data if isinstance(data, dict) else {}


def save_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(content, encoding="utf-8")
    tmp.replace(path)


def save_json(path: Path, payload: dict[str, Any]) -> None:
    save_text(path, json.dumps(payload, ensure_ascii=False, indent=2) + "\n")


def append_log(line: str) -> None:
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with LOG_PATH.open("a", encoding="utf-8") as fh:
        fh.write(line + "\n")


def run_openclaw_status_json() -> tuple[dict[str, Any] | None, str | None]:
    try:
        result = subprocess.run(
            ["openclaw", "status", "--json"],
            cwd=str(WORKSPACE),
            capture_output=True,
            text=True,
            timeout=OPENCLAW_STATUS_TIMEOUT_SECONDS,
            check=False,
        )
    except Exception as exc:
        return None, f"status_exec_failed: {exc}"

    if result.returncode != 0:
        stderr = (result.stderr or result.stdout or "").strip()
        return None, f"status_command_failed: {stderr[:300]}"

    try:
        return json.loads(result.stdout), None
    except json.JSONDecodeError as exc:
        return None, f"status_json_invalid: {exc}"


def tcp_probe(host: str, port: int, timeout: float = REQUEST_TIMEOUT_SECONDS) -> tuple[bool, str, float | None]:
    started = time.monotonic()
    try:
        with socket.create_connection((host, port), timeout=timeout):
            latency_ms = round((time.monotonic() - started) * 1000, 1)
            return True, "tcp_ok", latency_ms
    except socket.timeout:
        return False, "tcp_timeout", None
    except OSError as exc:
        return False, f"tcp_error:{exc.__class__.__name__}", None


def http_probe(name: str, url: str, timeout: float = REQUEST_TIMEOUT_SECONDS) -> dict[str, Any]:
    parsed = urllib.parse.urlparse(url)
    host = parsed.hostname or ""
    scheme = parsed.scheme or "https"
    port = parsed.port or (443 if scheme == "https" else 80)
    probe: dict[str, Any] = {
        "name": name,
        "url": url,
        "host": host,
        "ok": False,
        "category": "unknown",
        "detail": "uninitialized",
        "latencyMs": None,
    }
    if not host:
        probe.update({"category": "invalid", "detail": "missing-host"})
        return probe

    started = time.monotonic()
    tcp_ok, tcp_detail, tcp_latency = tcp_probe(host, port, timeout=timeout)
    probe["tcpLatencyMs"] = tcp_latency
    if not tcp_ok:
        probe.update({"category": "transport", "detail": tcp_detail})
        return probe

    request = urllib.request.Request(url, headers={"User-Agent": "OpenClaw-LocalHealth/1.0"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as resp:
            latency_ms = round((time.monotonic() - started) * 1000, 1)
            probe.update({
                "ok": True,
                "category": "http",
                "detail": f"http_{getattr(resp, 'status', 'unknown')}",
                "latencyMs": latency_ms,
                "httpStatus": getattr(resp, "status", None),
            })
            return probe
    except urllib.error.HTTPError as exc:
        latency_ms = round((time.monotonic() - started) * 1000, 1)
        probe.update({
            "ok": True,
            "category": "http",
            "detail": f"http_{exc.code}",
            "latencyMs": latency_ms,
            "httpStatus": exc.code,
        })
        return probe
    except ssl.SSLError as exc:
        probe.update({"category": "tls", "detail": f"tls_error:{exc.__class__.__name__}"})
        return probe
    except urllib.error.URLError as exc:
        reason = getattr(exc, "reason", exc)
        detail = getattr(reason, "strerror", None) or getattr(reason, "reason", None) or str(reason)
        probe.update({"category": "http", "detail": f"url_error:{detail}"[:240]})
        return probe
    except Exception as exc:
        probe.update({"category": "http", "detail": f"unexpected:{exc.__class__.__name__}"})
        return probe


def active_provider_ids(config: dict[str, Any]) -> set[str]:
    active: set[str] = set()
    primary_model = config.get("agents", {}).get("defaults", {}).get("model", {}).get("primary")
    if isinstance(primary_model, str) and "/" in primary_model:
        active.add(primary_model.split("/", 1)[0])
    image_model = config.get("agents", {}).get("defaults", {}).get("imageModel", {}).get("primary")
    if isinstance(image_model, str) and "/" in image_model:
        active.add(image_model.split("/", 1)[0])
    return active


def collect_provider_probes(config: dict[str, Any]) -> list[dict[str, Any]]:
    providers = config.get("models", {}).get("providers", {})
    active_ids = active_provider_ids(config)
    items: list[dict[str, Any]] = []
    for provider_id, provider_cfg in providers.items():
        if not isinstance(provider_cfg, dict):
            continue
        base_url = provider_cfg.get("baseUrl")
        if not isinstance(base_url, str) or not base_url.strip():
            continue
        probe = http_probe(f"provider:{provider_id}", base_url.strip())
        probe["providerId"] = provider_id
        probe["isPrimary"] = provider_id in active_ids
        items.append(probe)
    return items


def collect_generic_probes() -> list[dict[str, Any]]:
    return [http_probe(name, url) for name, url in DEFAULT_GENERIC_PROBES]


def derive_summary(status_payload: dict[str, Any] | None, status_error: str | None, generic_probes: list[dict[str, Any]], provider_probes: list[dict[str, Any]]) -> tuple[str, str, list[str]]:
    reasons: list[str] = []
    severity = "ok"
    summary = "本地健康检查正常"

    if status_error:
        reasons.append("status_command_failed")
        severity = "warn"
        summary = "OpenClaw 状态命令异常，已退回基础探测"

    gateway_reachable = bool(status_payload and status_payload.get("gateway", {}).get("reachable"))
    gateway_service_state = status_payload.get("gatewayService", {}).get("runtime", {}).get("status") if status_payload else None
    if status_payload and not gateway_reachable:
        reasons.append("gateway_unreachable")
        severity = "critical"
        summary = "Gateway 不可达"
    if status_payload and gateway_service_state not in (None, "running"):
        reasons.append("gateway_service_not_running")
        severity = "critical"
        summary = "Gateway service 未处于运行状态"

    generic_ok = any(item.get("ok") for item in generic_probes)
    if generic_probes and not generic_ok:
        reasons.append("external_network_unreachable")
        if severity != "critical":
            severity = "critical"
            summary = "外网探测全部失败，疑似本机外联异常"

    primary_provider_probes = [item for item in provider_probes if item.get("isPrimary")]
    provider_ok_count = sum(1 for item in primary_provider_probes if item.get("ok"))
    if primary_provider_probes and provider_ok_count == 0:
        reasons.append("primary_provider_routes_unreachable")
        if severity == "ok":
            severity = "warn"
            summary = "主线模型提供商路由全部不可达"
    elif primary_provider_probes and provider_ok_count < len(primary_provider_probes):
        reasons.append("primary_provider_routes_partially_unreachable")
        if severity == "ok":
            severity = "warn"
            summary = "主线模型提供商路由部分不可达"

    optional_provider_failures = [item for item in provider_probes if not item.get("isPrimary") and not item.get("ok")]
    if optional_provider_failures:
        reasons.append("optional_provider_routes_unreachable")

    if not reasons:
        reasons.append("healthy")
    return severity, summary, reasons


def build_human_summary(report: dict[str, Any]) -> str:
    lines = [
        f"[{report['checkedAt']}] {report['severity'].upper()} - {report['summary']}",
        f"host={report['host']} gateway={report['gateway']['status']} service={report['gateway']['serviceStatus']}",
        f"reasons={', '.join(report['reasons'])}",
    ]
    generic_bits = []
    for item in report.get("genericProbes", []):
        generic_bits.append(f"{item['name']}={'ok' if item['ok'] else 'fail'}({item['detail']})")
    if generic_bits:
        lines.append("generic=" + "; ".join(generic_bits))
    provider_bits = []
    for item in report.get("providerProbes", []):
        marker = "*" if item.get("isPrimary") else ""
        provider_bits.append(f"{item['name']}{marker}={'ok' if item['ok'] else 'fail'}({item['detail']})")
    if provider_bits:
        lines.append("providers=" + "; ".join(provider_bits))
    return "\n".join(lines)


def maybe_notify(previous: dict[str, Any], current: dict[str, Any], enabled: bool) -> None:
    if not enabled:
        return
    prev_severity = previous.get("severity")
    prev_summary = previous.get("summary")
    if prev_severity == current.get("severity") and prev_summary == current.get("summary"):
        return
    if not shutil.which("notify-send"):
        return
    if not (os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY") or os.environ.get("DBUS_SESSION_BUS_ADDRESS")):
        return
    title = f"OpenClaw 健康诊断：{current['severity'].upper()}"
    body = current["summary"]
    subprocess.run(["notify-send", title, body], check=False)


def main() -> int:
    parser = argparse.ArgumentParser(description="Local OpenClaw health diagnosis without relying on model replies")
    parser.add_argument("--notify-on-change", action="store_true", help="Best-effort desktop notification when summary changes")
    parser.add_argument("--print-json", action="store_true", help="Print JSON report")
    parser.add_argument("--print-human", action="store_true", help="Print human-readable summary")
    args = parser.parse_args()

    STATE_DIR.mkdir(parents=True, exist_ok=True)
    config = load_json(CONFIG_PATH)
    status_payload, status_error = run_openclaw_status_json()
    generic_probes = collect_generic_probes()
    provider_probes = collect_provider_probes(config)
    severity, summary, reasons = derive_summary(status_payload, status_error, generic_probes, provider_probes)

    gateway_runtime = status_payload.get("gatewayService", {}).get("runtime", {}) if status_payload else {}
    gateway_info = status_payload.get("gateway", {}) if status_payload else {}
    host = gateway_info.get("self", {}).get("host") or socket.gethostname()
    report = {
        "checkedAt": now_iso(),
        "host": host,
        "severity": severity,
        "summary": summary,
        "reasons": reasons,
        "statusError": status_error,
        "gateway": {
            "status": "reachable" if gateway_info.get("reachable") else "unreachable",
            "latencyMs": gateway_info.get("connectLatencyMs"),
            "serviceStatus": gateway_runtime.get("status") or "unknown",
            "serviceState": gateway_runtime.get("state") or "unknown",
            "serviceSubState": gateway_runtime.get("subState") or "unknown",
            "pid": gateway_runtime.get("pid"),
        },
        "genericProbes": generic_probes,
        "providerProbes": provider_probes,
        "fallback": FALLBACK_INTERFACE,
    }

    previous = load_json(TRANSITION_PATH)
    save_json(REPORT_PATH, report)
    save_text(SUMMARY_PATH, build_human_summary(report) + "\n")
    save_json(TRANSITION_PATH, {"severity": severity, "summary": summary, "checkedAt": report["checkedAt"]})

    if previous.get("severity") != severity or previous.get("summary") != summary:
        append_log(f"[{report['checkedAt']}] {severity.upper()} {summary} reasons={','.join(reasons)}")
    maybe_notify(previous, report, args.notify_on_change)

    if args.print_json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    elif args.print_human or not args.print_json:
        print(build_human_summary(report))

    if severity == "critical":
        return 2
    if severity == "warn":
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
