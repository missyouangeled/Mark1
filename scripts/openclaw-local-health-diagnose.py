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
from html import escape
from pathlib import Path
from typing import Any

WORKSPACE = Path.home() / ".openclaw" / "workspace"
CONFIG_PATH = Path.home() / ".openclaw" / "openclaw.json"
STATE_DIR = Path(os.environ.get("XDG_STATE_HOME", str(Path.home() / ".local" / "state"))) / "openclaw" / "local-health"
REPORT_PATH = STATE_DIR / "last-report.json"
SUMMARY_PATH = STATE_DIR / "last-summary.txt"
TRANSITION_PATH = STATE_DIR / "transition-state.json"
LOG_PATH = STATE_DIR / "health-diagnostic.log"
CANVAS_DOC_DIR = Path.home() / ".openclaw" / "canvas" / "documents" / "local-health-status"
CANVAS_DOC_PATH = CANVAS_DOC_DIR / "index.html"
CANVAS_STATUS_JSON_PATH = CANVAS_DOC_DIR / "status.json"
HOST_THERMAL_BRIDGE_FILENAME = "host-thermal-bridge.json"
HOST_THERMAL_BRIDGE_PATH = STATE_DIR / HOST_THERMAL_BRIDGE_FILENAME
DEFAULT_CONTROL_UI_DIST_ROOT = Path.home() / ".npm-global" / "lib" / "node_modules" / "openclaw" / "dist" / "control-ui"
PUBLIC_STATUS_HTML_NAME = "jarvis-local-health-status.html"
PUBLIC_STATUS_JSON_NAME = "jarvis-local-health-status.json"
SUPERVISOR_STATE_DIR = Path(os.environ.get("XDG_STATE_HOME", str(Path.home() / ".local" / "state"))) / "openclaw" / "supervisor"
SUPERVISOR_STATUS_PATH = SUPERVISOR_STATE_DIR / "supervisor-status.json"
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
OPENCLAW_STATUS_TIMEOUT_SECONDS = 15.0
LOG_ROTATE_MAX_BYTES = 2 * 1024 * 1024
LOG_ROTATE_KEEP_BYTES = 1 * 1024 * 1024
CANVAS_STALE_WARN_MINUTES = 12
CANVAS_STALE_BAD_MINUTES = 20
THERMAL_WARN_C = 85.0
THERMAL_CRITICAL_C = 95.0
HOST_THERMAL_BRIDGE_WARN_MINUTES = 10
HOST_THERMAL_BRIDGE_BAD_MINUTES = 20
LOAD_WARN_RATIO = 1.2
LOAD_CRITICAL_RATIO = 1.8
MEM_AVAILABLE_WARN_RATIO = 0.12
MEM_AVAILABLE_CRITICAL_RATIO = 0.06
SWAP_FREE_WARN_RATIO = 0.15
ISSUE_PRIORITY = {
    "gateway_service_not_running": 10,
    "gateway_unreachable": 20,
    "external_network_unreachable": 30,
    "thermal_critical": 35,
    "thermal_bridge_unavailable": 38,
    "primary_provider_routes_unreachable": 40,
    "thermal_warn": 45,
    "thermal_bridge_stale": 46,
    "resource_pressure_critical": 48,
    "primary_provider_routes_partially_unreachable": 50,
    "resource_pressure_warn": 55,
    "status_command_failed": 60,
}
SEVERITY_PRIORITY = {"ok": 0, "warn": 1, "critical": 2}


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as fh:
        data = json.load(fh)
    return data if isinstance(data, dict) else {}


def load_supervisor_status() -> dict[str, Any]:
    payload = load_json(SUPERVISOR_STATUS_PATH)
    if not payload:
        return {
            "status": "unavailable",
            "summary": "监工状态未接入",
            "detail": f"尚未生成监工状态文件：{SUPERVISOR_STATUS_PATH}",
            "checkedAt": None,
            "hasActiveTask": False,
            "activeTaskCount": 0,
            "focusTask": None,
            "recentTerminalTask": None,
            "service": {
                "state": "unavailable",
                "policyMode": "unknown",
                "taskActive": False,
                "desiredState": "unknown",
                "updatedAt": None,
                "updatedBy": None,
                "host": None,
                "reason": None,
            },
            "sourcePath": str(SUPERVISOR_STATUS_PATH),
        }

    service = payload.get("service") if isinstance(payload.get("service"), dict) else {}
    focus_task = payload.get("focusTask") if isinstance(payload.get("focusTask"), dict) else None
    recent_terminal_task = payload.get("recentTerminalTask") if isinstance(payload.get("recentTerminalTask"), dict) else None
    return {
        "status": str(payload.get("status") or "unknown"),
        "summary": str(payload.get("summary") or "监工状态未知"),
        "detail": str(payload.get("detail") or ""),
        "checkedAt": payload.get("checkedAt"),
        "hasActiveTask": bool(payload.get("hasActiveTask")),
        "activeTaskCount": int(payload.get("activeTaskCount") or 0),
        "focusTask": focus_task,
        "recentTerminalTask": recent_terminal_task,
        "service": {
            "state": str(service.get("state") or "unknown"),
            "policyMode": str(service.get("policyMode") or "unknown"),
            "taskActive": bool(service.get("taskActive")),
            "desiredState": str(service.get("desiredState") or "unknown"),
            "updatedAt": service.get("updatedAt"),
            "updatedBy": service.get("updatedBy"),
            "host": service.get("host"),
            "reason": service.get("reason"),
        },
        "sourcePath": str(payload.get("paths", {}).get("statusFile") or SUPERVISOR_STATUS_PATH),
    }


def save_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(content, encoding="utf-8")
    tmp.replace(path)


def save_json(path: Path, payload: dict[str, Any]) -> None:
    save_text(path, json.dumps(payload, ensure_ascii=False, indent=2) + "\n")


def append_log(line: str) -> None:
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    if LOG_PATH.exists() and LOG_PATH.stat().st_size > LOG_ROTATE_MAX_BYTES:
        try:
            raw = LOG_PATH.read_bytes()
            tail = raw[-LOG_ROTATE_KEEP_BYTES:]
            newline_index = tail.find(b"\n")
            if newline_index != -1:
                tail = tail[newline_index + 1 :]
            LOG_PATH.write_bytes(b"[log-rotated]\n" + tail)
        except Exception:
            pass
    with LOG_PATH.open("a", encoding="utf-8") as fh:
        fh.write(line + "\n")


def resolve_control_ui_dist_root() -> Path | None:
    env_override = os.environ.get("OPENCLAW_PACKAGE_ROOT")
    if env_override:
        candidate = Path(env_override).expanduser().resolve()
        if candidate.name == "control-ui" and candidate.exists():
            return candidate
        dist_root = candidate / "dist" / "control-ui"
        if dist_root.exists():
            return dist_root

    if DEFAULT_CONTROL_UI_DIST_ROOT.exists():
        return DEFAULT_CONTROL_UI_DIST_ROOT

    try:
        npm_root = subprocess.run(
            ["npm", "root", "-g"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        candidate = Path(npm_root) / "openclaw" / "dist" / "control-ui"
        if candidate.exists():
            return candidate.resolve()
    except Exception:
        pass

    return None


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


def normalize_temp_c(raw: str | int | float | None) -> float | None:
    if raw is None:
        return None
    try:
        value = float(str(raw).strip())
    except (TypeError, ValueError):
        return None
    if abs(value) >= 1000:
        value = value / 1000.0
    if value < 1 or value > 130:
        return None
    return round(value, 1)



def preferred_host_thermal_bridge_path() -> Path:
    env_path = os.environ.get("OPENCLAW_HOST_THERMAL_JSON")
    if env_path:
        return Path(env_path).expanduser()
    env_dir = os.environ.get("OPENCLAW_HOST_THERMAL_DIR")
    if env_dir:
        return Path(env_dir).expanduser() / HOST_THERMAL_BRIDGE_FILENAME
    return HOST_THERMAL_BRIDGE_PATH



def iter_host_thermal_bridge_candidates() -> list[Path]:
    candidates: list[Path] = [preferred_host_thermal_bridge_path(), HOST_THERMAL_BRIDGE_PATH]

    explicit_shared_paths = [
        Path('/mnt/hgfs') / HOST_THERMAL_BRIDGE_FILENAME,
        Path('/mnt/hgfs/OpenClawBridge') / HOST_THERMAL_BRIDGE_FILENAME,
        Path('/mnt/hgfs/openclaw-bridge') / HOST_THERMAL_BRIDGE_FILENAME,
        Path('/mnt/hgfs/openclaw-local-health') / HOST_THERMAL_BRIDGE_FILENAME,
        Path('/mnt/hgfs/OpenClawLocalHealth') / HOST_THERMAL_BRIDGE_FILENAME,
    ]
    candidates.extend(explicit_shared_paths)

    for pattern in (
        f'/mnt/hgfs/*/{HOST_THERMAL_BRIDGE_FILENAME}',
        f'/media/*/*/{HOST_THERMAL_BRIDGE_FILENAME}',
        f'/run/media/*/*/{HOST_THERMAL_BRIDGE_FILENAME}',
    ):
        candidates.extend(Path('/').glob(pattern.lstrip('/')))

    deduped: list[Path] = []
    seen: set[str] = set()
    for path in candidates:
        try:
            normalized = str(path.expanduser())
        except Exception:
            continue
        if normalized in seen:
            continue
        seen.add(normalized)
        deduped.append(Path(normalized))
    return deduped



def resolve_host_thermal_bridge_path() -> tuple[Path | None, str | None]:
    preferred = preferred_host_thermal_bridge_path()
    preferred_str = str(preferred.expanduser())
    for path in iter_host_thermal_bridge_candidates():
        candidate = path.expanduser()
        if candidate.exists() and candidate.is_file():
            source = 'file' if str(candidate) in {preferred_str, str(HOST_THERMAL_BRIDGE_PATH)} else 'file-auto'
            return candidate, source
    return None, None



def load_host_thermal_bridge() -> dict[str, Any] | None:
    bridge_path, bridge_source = resolve_host_thermal_bridge_path()
    if bridge_path is None:
        return None
    try:
        payload = json.loads(bridge_path.read_text(encoding='utf-8'))
    except Exception:
        return {
            "status": "unavailable",
            "summary": "宿主机温度桥接损坏",
            "detail": f"宿主机温度桥接文件不是合法 JSON：{bridge_path}",
            "maxTempC": None,
            "hottest": None,
            "probes": [],
            "bridgePath": str(bridge_path),
            "bridgeSource": bridge_source or "file",
        }

    if not isinstance(payload, dict):
        return None

    probes: list[dict[str, Any]] = []
    for item in payload.get("probes", []):
        if not isinstance(item, dict):
            continue
        temp_c = normalize_temp_c(item.get("tempC"))
        if temp_c is None:
            continue
        probes.append({
            "source": "host-bridge",
            "label": str(item.get("label") or item.get("name") or "host-sensor"),
            "tempC": temp_c,
        })

    host_temp = normalize_temp_c(payload.get("tempC"))
    if host_temp is not None:
        probes.append({
            "source": "host-bridge",
            "label": str(payload.get("label") or payload.get("source") or "host-cpu"),
            "tempC": host_temp,
        })

    probes.sort(key=lambda item: float(item.get('tempC') or 0), reverse=True)
    hottest = probes[0] if probes else None
    max_temp = float(hottest.get('tempC')) if hottest else None

    status = str(payload.get("status") or "").strip().lower()
    if status not in {"ok", "warn", "critical"}:
        if max_temp is not None and max_temp >= THERMAL_CRITICAL_C:
            status = "critical"
        elif max_temp is not None and max_temp >= THERMAL_WARN_C:
            status = "warn"
        else:
            status = "ok" if probes else "unavailable"

    summary = str(payload.get("summary") or "").strip()
    if not summary:
        if status == "critical":
            summary = "宿主机 CPU 温度过高"
        elif status == "warn":
            summary = "宿主机 CPU 温度偏高"
        elif status == "ok":
            summary = "宿主机温度正常"
        else:
            summary = "宿主机温度不可读"

    detail = str(payload.get("detail") or "").strip()
    if not detail:
        if hottest and max_temp is not None:
            detail = f"最高 {max_temp:.1f}°C（{hottest.get('label') or 'host-sensor'}）"
        else:
            detail = f"宿主机温度桥接文件存在，但未提供可用温度：{bridge_path}"

    updated_at = payload.get("updatedAt")
    age_minutes: float | None = None
    if isinstance(updated_at, str) and updated_at.strip():
        try:
            updated_dt = datetime.fromisoformat(updated_at.replace('Z', '+00:00'))
            if updated_dt.tzinfo is None:
                updated_dt = updated_dt.replace(tzinfo=timezone.utc)
            age_minutes = max(0.0, (datetime.now(timezone.utc) - updated_dt.astimezone(timezone.utc)).total_seconds() / 60.0)
        except ValueError:
            age_minutes = None
    if age_minutes is None:
        try:
            age_minutes = max(0.0, (time.time() - bridge_path.stat().st_mtime) / 60.0)
        except OSError:
            age_minutes = None

    if age_minutes is not None and age_minutes >= HOST_THERMAL_BRIDGE_BAD_MINUTES:
        status = "unavailable"
        summary = "宿主机温度桥接过期"
        detail = f"宿主机温度桥接已超过 {HOST_THERMAL_BRIDGE_BAD_MINUTES} 分钟未更新（当前约 {age_minutes:.0f} 分钟）：{bridge_path}"
    elif age_minutes is not None and age_minutes >= HOST_THERMAL_BRIDGE_WARN_MINUTES:
        if status == "ok":
            status = "warn"
            summary = "宿主机温度桥接可能过期"
        detail = f"{detail}；桥接文件约 {age_minutes:.0f} 分钟未更新"

    return {
        "status": status,
        "summary": summary,
        "detail": detail,
        "maxTempC": max_temp,
        "hottest": hottest,
        "probes": probes,
        "bridgePath": str(bridge_path),
        "bridgeSource": bridge_source or "file",
        "sourceHint": str(payload.get("source") or "host-bridge"),
        "updatedAt": updated_at,
        "bridgeAgeMinutes": round(age_minutes, 1) if age_minutes is not None else None,
    }



def collect_thermal_status() -> dict[str, Any]:
    bridge = load_host_thermal_bridge()
    if bridge is not None:
        return bridge

    probes: list[dict[str, Any]] = []
    seen_labels: set[str] = set()

    thermal_root = Path('/sys/class/thermal')
    if thermal_root.exists():
        for zone in sorted(thermal_root.glob('thermal_zone*')):
            temp_path = zone / 'temp'
            if not temp_path.exists():
                continue
            label = ((zone / 'type').read_text(encoding='utf-8', errors='ignore').strip() if (zone / 'type').exists() else zone.name) or zone.name
            temp_c = normalize_temp_c(temp_path.read_text(encoding='utf-8', errors='ignore'))
            key = f"thermal:{label}"
            if temp_c is None or key in seen_labels:
                continue
            seen_labels.add(key)
            probes.append({"source": "thermal_zone", "label": label, "tempC": temp_c})

    hwmon_root = Path('/sys/class/hwmon')
    if hwmon_root.exists():
        for hwmon in sorted(hwmon_root.glob('hwmon*')):
            chip = (hwmon / 'name').read_text(encoding='utf-8', errors='ignore').strip() if (hwmon / 'name').exists() else hwmon.name
            for temp_input in sorted(hwmon.glob('temp*_input')):
                temp_c = normalize_temp_c(temp_input.read_text(encoding='utf-8', errors='ignore'))
                if temp_c is None:
                    continue
                label_path = temp_input.with_name(temp_input.name.replace('_input', '_label'))
                sensor_label = label_path.read_text(encoding='utf-8', errors='ignore').strip() if label_path.exists() else temp_input.stem.replace('_input', '')
                label = f"{chip}:{sensor_label}"
                key = f"hwmon:{label}"
                if key in seen_labels:
                    continue
                seen_labels.add(key)
                probes.append({"source": "hwmon", "label": label, "tempC": temp_c})

    probes.sort(key=lambda item: float(item.get('tempC') or 0), reverse=True)
    hottest = probes[0] if probes else None
    max_temp = float(hottest.get('tempC')) if hottest else None

    if not probes:
        return {
            "status": "unavailable",
            "summary": "温度不可读",
            "detail": "当前机器未暴露可读温度传感器（当前环境像是 VMware 虚拟机）。",
            "maxTempC": None,
            "hottest": None,
            "probes": [],
            "bridgePath": str(HOST_THERMAL_BRIDGE_PATH),
            "bridgeSource": None,
        }

    if max_temp is not None and max_temp >= THERMAL_CRITICAL_C:
        status = "critical"
        summary = "CPU 温度过高"
    elif max_temp is not None and max_temp >= THERMAL_WARN_C:
        status = "warn"
        summary = "CPU 温度偏高"
    else:
        status = "ok"
        summary = "温度正常"

    detail = f"最高 {max_temp:.1f}°C（{hottest.get('label') or 'unknown'}）" if hottest and max_temp is not None else "未读到温度"
    return {
        "status": status,
        "summary": summary,
        "detail": detail,
        "maxTempC": max_temp,
        "hottest": hottest,
        "probes": probes,
        "bridgePath": str(HOST_THERMAL_BRIDGE_PATH),
        "bridgeSource": None,
    }


def collect_system_pressure() -> dict[str, Any]:
    cpu_count = os.cpu_count() or 1
    load1, load5, load15 = os.getloadavg()
    load_ratio = round(load1 / cpu_count, 2) if cpu_count else None

    meminfo: dict[str, int] = {}
    try:
        for line in Path('/proc/meminfo').read_text(encoding='utf-8', errors='ignore').splitlines():
            if ':' not in line:
                continue
            key, rest = line.split(':', 1)
            value = rest.strip().split()[0]
            meminfo[key] = int(value)
    except Exception:
        meminfo = {}

    mem_total_kb = meminfo.get('MemTotal', 0)
    mem_available_kb = meminfo.get('MemAvailable', 0)
    swap_total_kb = meminfo.get('SwapTotal', 0)
    swap_free_kb = meminfo.get('SwapFree', 0)

    mem_available_ratio = (mem_available_kb / mem_total_kb) if mem_total_kb else None
    swap_free_ratio = (swap_free_kb / swap_total_kb) if swap_total_kb else None

    status = 'ok'
    summary = '负载正常'
    reasons: list[str] = []

    if load_ratio is not None and load_ratio >= LOAD_CRITICAL_RATIO:
        status = 'critical'
        summary = 'CPU 负载过高'
        reasons.append('cpu-load')
    elif load_ratio is not None and load_ratio >= LOAD_WARN_RATIO:
        status = 'warn'
        summary = 'CPU 负载偏高'
        reasons.append('cpu-load')

    if mem_available_ratio is not None and mem_available_ratio <= MEM_AVAILABLE_CRITICAL_RATIO:
        status = 'critical'
        summary = '内存压力过高'
        reasons.append('memory')
    elif mem_available_ratio is not None and mem_available_ratio <= MEM_AVAILABLE_WARN_RATIO and status == 'ok':
        status = 'warn'
        summary = '内存压力偏高'
        reasons.append('memory')

    if swap_total_kb > 0 and swap_free_ratio is not None and swap_free_ratio <= SWAP_FREE_WARN_RATIO and status == 'ok':
        status = 'warn'
        summary = 'Swap 余量偏低'
        reasons.append('swap')

    detail_parts = [f"load1={load1:.2f}/{cpu_count}c"]
    if mem_total_kb:
        detail_parts.append(f"MemAvailable={mem_available_kb // 1024}MB/{mem_total_kb // 1024}MB")
    if swap_total_kb:
        detail_parts.append(f"SwapFree={swap_free_kb // 1024}MB/{swap_total_kb // 1024}MB")

    return {
        'status': status,
        'summary': summary,
        'detail': '；'.join(detail_parts),
        'cpuCount': cpu_count,
        'load1': round(load1, 2),
        'load5': round(load5, 2),
        'load15': round(load15, 2),
        'loadRatio': load_ratio,
        'memTotalKb': mem_total_kb,
        'memAvailableKb': mem_available_kb,
        'memAvailableRatio': round(mem_available_ratio, 3) if mem_available_ratio is not None else None,
        'swapTotalKb': swap_total_kb,
        'swapFreeKb': swap_free_kb,
        'swapFreeRatio': round(swap_free_ratio, 3) if swap_free_ratio is not None else None,
        'reasons': reasons,
    }



def add_issue(issues: list[dict[str, Any]], code: str, label: str, detail: str, scope: str, severity: str) -> None:
    issues.append({
        "code": code,
        "label": label,
        "detail": detail,
        "scope": scope,
        "severity": severity,
    })



def join_probe_names(items: list[dict[str, Any]]) -> str:
    names: list[str] = []
    for item in items:
        provider_id = item.get("providerId")
        if isinstance(provider_id, str) and provider_id:
            names.append(provider_id)
        else:
            names.append(str(item.get("name") or "unknown"))
    return ", ".join(names)



def unique_issue_labels(issues: list[dict[str, Any]]) -> list[str]:
    labels: list[str] = []
    seen: set[str] = set()
    for issue in issues:
        label = str(issue.get("label") or "").strip()
        if not label or label in seen:
            continue
        seen.add(label)
        labels.append(label)
    return labels



def pick_primary_issue(issues: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not issues:
        return None
    return min(issues, key=lambda item: ISSUE_PRIORITY.get(str(item.get("code") or ""), 999))



def derive_summary(
    status_payload: dict[str, Any] | None,
    status_error: str | None,
    generic_probes: list[dict[str, Any]],
    provider_probes: list[dict[str, Any]],
    thermal_status: dict[str, Any],
    system_pressure: dict[str, Any],
) -> tuple[str, str, list[str], str, list[dict[str, Any]]]:
    issues: list[dict[str, Any]] = []
    extra_reasons: list[str] = []

    if status_error:
        add_issue(
            issues,
            code="status_command_failed",
            label="Gateway 状态读取异常",
            detail=status_error,
            scope="gateway",
            severity="warn",
        )

    gateway_reachable = bool(status_payload and status_payload.get("gateway", {}).get("reachable"))
    gateway_service_state = status_payload.get("gatewayService", {}).get("runtime", {}).get("status") if status_payload else None
    if status_payload and not gateway_reachable:
        add_issue(
            issues,
            code="gateway_unreachable",
            label="Gateway 不可达",
            detail="openclaw status 返回 gateway.reachable=false",
            scope="gateway",
            severity="critical",
        )
    if status_payload and gateway_service_state not in (None, "running"):
        add_issue(
            issues,
            code="gateway_service_not_running",
            label="Gateway 服务未运行",
            detail=f"gateway runtime.status={gateway_service_state}",
            scope="gateway",
            severity="critical",
        )

    generic_ok = any(item.get("ok") for item in generic_probes)
    if generic_probes and not generic_ok:
        add_issue(
            issues,
            code="external_network_unreachable",
            label="本机网络不通",
            detail=f"外网探测全部失败: {join_probe_names([item for item in generic_probes if not item.get('ok')])}",
            scope="network",
            severity="critical",
        )

    primary_provider_probes = [item for item in provider_probes if item.get("isPrimary")]
    provider_ok_count = sum(1 for item in primary_provider_probes if item.get("ok"))
    if primary_provider_probes and provider_ok_count == 0:
        add_issue(
            issues,
            code="primary_provider_routes_unreachable",
            label="AI 模型路由不通",
            detail=f"主线 provider 全部失败: {join_probe_names(primary_provider_probes)}",
            scope="model",
            severity="warn",
        )
    elif primary_provider_probes and provider_ok_count < len(primary_provider_probes):
        add_issue(
            issues,
            code="primary_provider_routes_partially_unreachable",
            label="AI 模型路由部分异常",
            detail=f"主线 provider 部分失败: {join_probe_names([item for item in primary_provider_probes if not item.get('ok')])}",
            scope="model",
            severity="warn",
        )

    optional_provider_failures = [item for item in provider_probes if not item.get("isPrimary") and not item.get("ok")]
    if optional_provider_failures:
        extra_reasons.append("optional_provider_routes_unreachable")

    thermal_summary_text = str(thermal_status.get("summary") or "")
    thermal_detail_text = str(thermal_status.get("detail") or "")
    thermal_is_bridge = "桥接" in thermal_summary_text or "桥接" in thermal_detail_text

    if thermal_status.get("status") == "critical":
        add_issue(
            issues,
            code="thermal_critical",
            label="CPU 温度过高",
            detail=thermal_detail_text or "温度过高",
            scope="thermal",
            severity="critical",
        )
    elif thermal_status.get("status") == "warn":
        add_issue(
            issues,
            code="thermal_bridge_stale" if thermal_is_bridge else "thermal_warn",
            label=thermal_summary_text or ("宿主机温度桥接可能过期" if thermal_is_bridge else "CPU 温度偏高"),
            detail=thermal_detail_text or ("桥接可能过期" if thermal_is_bridge else "温度偏高"),
            scope="thermal",
            severity="warn",
        )
    elif thermal_status.get("status") == "unavailable" and thermal_is_bridge:
        add_issue(
            issues,
            code="thermal_bridge_unavailable",
            label=thermal_summary_text or "宿主机温度桥接异常",
            detail=thermal_detail_text or "宿主机温度桥接不可用",
            scope="thermal",
            severity="warn",
        )

    if system_pressure.get("status") == "critical":
        add_issue(
            issues,
            code="resource_pressure_critical",
            label=str(system_pressure.get("summary") or "系统负载过高"),
            detail=str(system_pressure.get("detail") or "系统资源压力过高"),
            scope="resource",
            severity="critical",
        )
    elif system_pressure.get("status") == "warn":
        add_issue(
            issues,
            code="resource_pressure_warn",
            label=str(system_pressure.get("summary") or "系统负载偏高"),
            detail=str(system_pressure.get("detail") or "系统资源压力偏高"),
            scope="resource",
            severity="warn",
        )

    if not issues:
        return "ok", "本地健康检查正常", ["healthy", *extra_reasons], "正常", []

    primary_issue = pick_primary_issue(issues)
    severity = max((str(item.get("severity") or "ok") for item in issues), key=lambda value: SEVERITY_PRIORITY.get(value, 0))
    summary = str(primary_issue.get("label") or "本地健康检查异常") if primary_issue else "本地健康检查异常"
    reasons = [str(item.get("code") or "unknown_issue") for item in issues] + extra_reasons
    issue_overview = "；".join(unique_issue_labels(issues))
    return severity, summary, reasons, issue_overview, issues



def build_human_summary(report: dict[str, Any]) -> str:
    lines = [
        f"[{report['checkedAt']}] {report['severity'].upper()} - {report['summary']}",
    ]
    if report.get("severity") != "ok":
        lines.append(f"问题概述={report.get('issueOverview') or report['summary']}")
    lines.append(f"host={report['host']} gateway={report['gateway']['status']} service={report['gateway']['serviceStatus']}")
    thermal = report.get("thermal", {})
    lines.append(f"thermal={thermal.get('summary', '未知')} detail={thermal.get('detail', 'n/a')}")
    lines.append(f"reasons={', '.join(report['reasons'])}")
    if report.get("statusError"):
        lines.append(f"statusError={report['statusError']}")
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



def build_failure_log_entry(report: dict[str, Any]) -> str:
    lines = [
        f"[{report['checkedAt']}] severity={report['severity'].upper()} summary={report['summary']}",
        f"issueOverview={report.get('issueOverview') or report['summary']}",
        f"reasons={','.join(report.get('reasons', []))}",
    ]
    if report.get("statusError"):
        lines.append(f"statusError={report['statusError']}")

    gateway = report.get("gateway", {})
    lines.append(
        "gateway="
        f"status={gateway.get('status')} serviceStatus={gateway.get('serviceStatus')} "
        f"serviceState={gateway.get('serviceState')} serviceSubState={gateway.get('serviceSubState')} "
        f"latencyMs={gateway.get('latencyMs')} pid={gateway.get('pid')}"
    )
    thermal = report.get("thermal", {})
    lines.append(
        "thermal="
        f"status={thermal.get('status')} summary={thermal.get('summary')} detail={thermal.get('detail')} maxTempC={thermal.get('maxTempC')}"
    )

    issues = report.get("issues", [])
    if issues:
        lines.append("issues:")
        for issue in issues:
            lines.append(
                f"  - scope={issue.get('scope')} severity={issue.get('severity')} "
                f"code={issue.get('code')} label={issue.get('label')} detail={issue.get('detail')}"
            )

    failed_generic = [item for item in report.get("genericProbes", []) if not item.get("ok")]
    if failed_generic:
        lines.append("genericProbeFailures:")
        for item in failed_generic:
            lines.append(
                f"  - name={item.get('name')} url={item.get('url')} host={item.get('host')} "
                f"category={item.get('category')} detail={item.get('detail')} "
                f"tcpLatencyMs={item.get('tcpLatencyMs')} latencyMs={item.get('latencyMs')}"
            )

    failed_providers = [item for item in report.get("providerProbes", []) if not item.get("ok")]
    if failed_providers:
        lines.append("providerProbeFailures:")
        for item in failed_providers:
            lines.append(
                f"  - providerId={item.get('providerId')} primary={item.get('isPrimary')} url={item.get('url')} "
                f"host={item.get('host')} category={item.get('category')} detail={item.get('detail')} "
                f"tcpLatencyMs={item.get('tcpLatencyMs')} latencyMs={item.get('latencyMs')}"
            )

    lines.append("---")
    return "\n".join(lines)



def first_issue_for_scope(report: dict[str, Any], scope: str) -> dict[str, Any] | None:
    issues = [item for item in report.get("issues", []) if item.get("scope") == scope]
    if not issues:
        return None
    return min(issues, key=lambda item: ISSUE_PRIORITY.get(str(item.get("code") or ""), 999))



def summarize_scope_card(report: dict[str, Any], scope: str) -> tuple[str, str, str]:
    issue = first_issue_for_scope(report, scope)
    if scope == "gateway":
        if issue:
            tone = "bad" if issue.get("severity") == "critical" else "warn"
            return str(issue.get("label") or "异常"), str(issue.get("detail") or ""), tone
        gateway = report.get("gateway", {})
        detail = f"可达 / service={gateway.get('serviceStatus') or 'unknown'}"
        return "正常", detail, "ok"

    if scope == "network":
        if issue:
            tone = "bad" if issue.get("severity") == "critical" else "warn"
            return str(issue.get("label") or "异常"), str(issue.get("detail") or ""), tone
        ok_count = sum(1 for item in report.get("genericProbes", []) if item.get("ok"))
        total = len(report.get("genericProbes", []))
        detail = f"外网探测通过 {ok_count}/{total}" if total else "未配置外网探测"
        return "正常", detail, "ok"

    if scope == "model":
        if issue:
            tone = "bad" if issue.get("severity") == "critical" else "warn"
            return str(issue.get("label") or "异常"), str(issue.get("detail") or ""), tone
        primary_probes = [item for item in report.get("providerProbes", []) if item.get("isPrimary")]
        optional_failures = [item for item in report.get("providerProbes", []) if not item.get("isPrimary") and not item.get("ok")]
        if primary_probes:
            detail = f"主线 provider 正常 {sum(1 for item in primary_probes if item.get('ok'))}/{len(primary_probes)}"
        else:
            detail = "未识别到主线 provider"
        if optional_failures:
            detail += f"；非主线异常 {join_probe_names(optional_failures)}"
        return "正常", detail, "ok"

    if scope == "thermal":
        if issue:
            tone = "bad" if issue.get("severity") == "critical" else "warn"
            return str(issue.get("label") or "异常"), str(issue.get("detail") or ""), tone
        thermal = report.get("thermal", {})
        thermal_status = str(thermal.get("status") or "unknown")
        if thermal_status == "unavailable":
            return str(thermal.get("summary") or "温度不可读"), str(thermal.get("detail") or "当前机器未暴露温度传感器"), "na"
        return str(thermal.get("summary") or "温度正常"), str(thermal.get("detail") or ""), "ok"

    if scope == "resource":
        if issue:
            tone = "bad" if issue.get("severity") == "critical" else "warn"
            return str(issue.get("label") or "异常"), str(issue.get("detail") or ""), tone
        resource = report.get("resource", {})
        return str(resource.get("summary") or "负载正常"), str(resource.get("detail") or ""), "ok"

    if scope == "supervisor":
        supervisor = report.get("supervisor", {})
        service = supervisor.get("service", {}) if isinstance(supervisor.get("service"), dict) else {}
        service_state = str(service.get("state") or "unknown")
        status = str(supervisor.get("status") or "unknown")
        detail = str(supervisor.get("detail") or supervisor.get("summary") or "")
        if service_state == "disabled":
            return "已关闭", detail or "监工服务当前未启用", "na"
        if service_state == "armed" and status == "idle":
            return "待命中", detail or "监工服务已开启，但当前无后台任务", "ok"
        if status == "running":
            return "运行中", detail or "后台任务正在运行", "ok"
        if status == "stalled":
            return "可能卡住", detail or "至少一个后台任务超过静默阈值", "warn"
        if status == "failed":
            return "异常结束", detail or "最近一个后台任务异常结束", "bad"
        if status == "done":
            return "刚完成", detail or "最近一个后台任务刚完成", "ok"
        if status == "idle":
            return "空闲", detail or "当前没有后台任务", "ok"
        if status == "unavailable":
            return str(supervisor.get("summary") or "未接入"), detail or "尚未读取到监工状态文件", "na"
        return str(supervisor.get("summary") or "未知"), detail, "na"

    return "正常", "", "ok"



def build_probe_lines(report: dict[str, Any]) -> tuple[list[str], list[str]]:
    failed_generic = [item for item in report.get("genericProbes", []) if not item.get("ok")]
    failed_providers = [item for item in report.get("providerProbes", []) if not item.get("ok")]
    generic_lines = [
        f"{item.get('name')}: {item.get('detail')}"
        for item in failed_generic
    ]
    provider_lines = [
        f"{item.get('providerId') or item.get('name')}: {item.get('detail')}"
        for item in failed_providers
    ]
    return generic_lines, provider_lines



def dedupe_preserve_order(items: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        text = item.strip()
        if not text or text in seen:
            continue
        seen.add(text)
        result.append(text)
    return result



def build_self_help_actions(report: dict[str, Any]) -> list[str]:
    codes = {str(item.get("code") or "") for item in report.get("issues", [])}
    actions: list[str] = []

    if "gateway_service_not_running" in codes or "gateway_unreachable" in codes:
        actions.extend([
            "先执行 `openclaw gateway restart`，优先恢复本机网关。",
            "若 Control UI 仍卡住，再刷新当前页面。",
        ])

    if "status_command_failed" in codes:
        actions.extend([
            "若只是 Gateway 状态读取异常，优先执行 `openclaw gateway restart`。",
            "如果页面表现异常但网络正常，也可先刷新页面，再重开浏览器。",
        ])

    if "external_network_unreachable" in codes:
        actions.extend([
            "先检查当前机器是否断网、代理/VPN 是否异常。",
            "可直接在浏览器访问 `https://api.github.com` 或 `https://www.baidu.com` 做连通性判断。",
        ])

    if "primary_provider_routes_unreachable" in codes or "primary_provider_routes_partially_unreachable" in codes:
        actions.extend([
            "如果 Gateway 和网络都正常，但 AI 模型不通，优先检查 provider 的 API Key、baseUrl 和上游服务状态。",
            "可稍后重试，或临时切换到另一条可用 provider / 网络出口。",
        ])

    if "thermal_critical" in codes or "thermal_warn" in codes:
        actions.extend([
            "如果 CPU 温度偏高，优先降低当前负载，关闭高占用程序或暂停大任务。",
            "天气热且没有空调时，尽量改善散热；必要时让机器空闲降温后再继续。",
        ])

    if "resource_pressure_critical" in codes or "resource_pressure_warn" in codes:
        actions.extend([
            "如果 CPU 负载或内存压力偏高，优先关闭高占用程序、减少并行任务。",
            "内存紧张时先关浏览器无关标签页；若 swap 也快吃满，建议重开浏览器或让机器空闲一会儿。",
        ])

    thermal = report.get("thermal", {})
    if thermal.get("bridgePath") and ("桥接" in str(thermal.get("summary") or "") or "桥接" in str(thermal.get("detail") or "")):
        actions.append("若宿主机温度桥接已过期/损坏，优先检查 Windows 计划任务是否仍在更新 host-thermal-bridge.json，以及 VMware 共享文件夹是否还挂着。")
    elif str(thermal.get("status") or "") == "unavailable":
        actions.append("当前环境暂时读不到 CPU 温度；若要监控真实温度，通常需要在宿主机/实体机上读取传感器。")

    supervisor = report.get("supervisor", {})
    supervisor_status = str(supervisor.get("status") or "")
    supervisor_service = supervisor.get("service", {}) if isinstance(supervisor.get("service"), dict) else {}
    if supervisor_status == "stalled":
        actions.extend([
            "监工显示后台任务可能卡住时，先看当前关注任务的 label 和静默时长，再决定继续等还是人工介入。",
            "若确认只是长步骤正常等待，可继续观察；若明显异常，优先检查对应后台任务日志或直接重跑该任务。",
        ])
    elif supervisor_status == "failed":
        actions.extend([
            "若监工显示后台任务异常结束，优先检查最近结束任务的错误摘要，再决定是否重试。",
            "如果只是这轮工作不再需要后台协作，也可以直接先关监工服务，避免继续误报。",
        ])
    elif str(supervisor_service.get("state") or "") == "unavailable":
        actions.append("若你准备使用监工能力，但这里显示未接入，先运行一次 `python3 scripts/openclaw-supervisor-status.py --print-human` 生成状态文件。")

    if not codes and supervisor_status not in {"stalled", "failed"}:
        actions.extend([
            "如果页面卡住但这里显示正常，优先刷新当前页面。",
            "刷新后仍无效时，重开浏览器；这通常更像前端/浏览器层卡死，而不是 Gateway、网络或 AI 模型故障。",
        ])

    return dedupe_preserve_order(actions)[:4]



def build_canvas_html(report: dict[str, Any]) -> str:
    severity = str(report.get("severity") or "ok")
    summary = str(report.get("summary") or "本地健康检查正常")
    issue_overview = str(report.get("issueOverview") or summary)
    severity_label = {"ok": "正常", "warn": "告警", "critical": "严重异常"}.get(severity, severity.upper())
    severity_class = {"ok": "ok", "warn": "warn", "critical": "bad"}.get(severity, "warn")
    gateway_title, gateway_detail, gateway_tone = summarize_scope_card(report, "gateway")
    network_title, network_detail, network_tone = summarize_scope_card(report, "network")
    model_title, model_detail, model_tone = summarize_scope_card(report, "model")
    thermal_title, thermal_detail, thermal_tone = summarize_scope_card(report, "thermal")
    resource_title, resource_detail, resource_tone = summarize_scope_card(report, "resource")
    supervisor_title, supervisor_detail, supervisor_tone = summarize_scope_card(report, "supervisor")
    generic_lines, provider_lines = build_probe_lines(report)
    issues = report.get("issues", [])
    self_help_actions = [str(item) for item in report.get("selfHelpActions", [])]
    supervisor = report.get("supervisor", {})
    supervisor_service = supervisor.get("service", {}) if isinstance(supervisor.get("service"), dict) else {}
    supervisor_focus = supervisor.get("focusTask") if isinstance(supervisor.get("focusTask"), dict) else None
    supervisor_recent = supervisor.get("recentTerminalTask") if isinstance(supervisor.get("recentTerminalTask"), dict) else None
    supervisor_lines = [
        f"服务状态：{supervisor_service.get('state') or '-'}（策略：{supervisor_service.get('policyMode') or '-'} / 有效意图：{supervisor_service.get('desiredState') or '-'}）",
        f"任务激活：{supervisor_service.get('taskActive')}",
        f"监工状态：{supervisor.get('status') or '-'}",
        f"说明：{supervisor.get('detail') or supervisor.get('summary') or '-'}",
    ]
    if supervisor_focus:
        supervisor_lines.append(
            f"当前关注：{supervisor_focus.get('label') or supervisor_focus.get('taskId') or '-'}；静默 {supervisor_focus.get('silentSeconds') if supervisor_focus.get('silentSeconds') is not None else '-'} 秒"
        )
    if supervisor_recent:
        supervisor_lines.append(
            f"最近结束：{supervisor_recent.get('status') or '-'} / {supervisor_recent.get('label') or supervisor_recent.get('taskId') or '-'}"
        )
    if supervisor.get("checkedAt"):
        supervisor_lines.append(f"监工更新时间：{supervisor.get('checkedAt')}")
    issue_items = "".join(
        f"<li><strong>{escape(str(item.get('label') or '异常'))}</strong><span>{escape(str(item.get('detail') or ''))}</span></li>"
        for item in issues
    ) or "<li><strong>无异常</strong><span>当前检查项未发现主线问题</span></li>"
    self_help_items = "".join(f"<li>{escape(line)}</li>" for line in self_help_actions) or "<li>暂无建议</li>"
    generic_items = "".join(f"<li>{escape(line)}</li>" for line in generic_lines) or "<li>无</li>"
    provider_items = "".join(f"<li>{escape(line)}</li>" for line in provider_lines) or "<li>无</li>"
    supervisor_items = "".join(f"<li>{escape(line)}</li>" for line in supervisor_lines) or "<li>暂无监工状态</li>"
    status_error = report.get("statusError")
    status_error_html = (
        f"<div class='subline'><span class='label'>状态命令：</span>{escape(str(status_error))}</div>"
        if status_error else ""
    )
    checked_at = escape(str(report.get('checkedAt') or ''))
    return f"""<!doctype html>
<html lang=\"zh-CN\">
<head>
  <meta charset=\"utf-8\" />
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
  <meta http-equiv=\"refresh\" content=\"30\" />
  <title>本地健康监督</title>
  <style>
    :root {{ color-scheme: dark; }}
    * {{ box-sizing: border-box; }}
    body {{ margin: 0; background: #0b1017; color: #eaf1fb; font: 14px/1.5 -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }}
    .wrap {{ max-width: 980px; margin: 0 auto; padding: 18px; }}
    .card {{ background: linear-gradient(180deg, #111926, #0d141e); border: 1px solid #223248; border-radius: 18px; padding: 18px; box-shadow: 0 12px 40px rgba(0,0,0,.28); }}
    .top {{ display: flex; justify-content: space-between; align-items: flex-start; gap: 14px; flex-wrap: wrap; }}
    .title {{ font-size: 22px; font-weight: 700; margin: 0; }}
    .muted {{ color: #9db0c7; font-size: 12px; }}
    .badge {{ padding: 7px 12px; border-radius: 999px; font-weight: 700; font-size: 12px; border: 1px solid transparent; }}
    .badge.ok {{ background: rgba(34,197,94,.14); color: #8ef0ad; border-color: rgba(34,197,94,.28); }}
    .badge.warn {{ background: rgba(245,158,11,.14); color: #ffd089; border-color: rgba(245,158,11,.28); }}
    .badge.bad {{ background: rgba(239,68,68,.14); color: #ff9d9d; border-color: rgba(239,68,68,.28); }}
    .hero {{ margin-top: 16px; padding: 16px; border-radius: 16px; background: rgba(255,255,255,.03); border: 1px solid rgba(255,255,255,.06); }}
    .hero-title {{ font-size: 28px; font-weight: 800; margin: 0 0 8px; }}
    .hero-sub {{ color: #aac0d8; }}
    .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 12px; margin-top: 16px; }}
    .mini {{ border-radius: 14px; padding: 14px; border: 1px solid rgba(255,255,255,.07); background: rgba(255,255,255,.025); }}
    .mini .k {{ font-size: 12px; color: #89a1ba; margin-bottom: 6px; }}
    .mini .v {{ font-size: 18px; font-weight: 700; margin-bottom: 6px; }}
    .mini .d {{ font-size: 12px; color: #b8c7d8; }}
    .mini.ok .v {{ color: #8ef0ad; }}
    .mini.warn .v {{ color: #ffd089; }}
    .mini.bad .v {{ color: #ff9d9d; }}
    .mini.na .v {{ color: #c7d4e5; }}
    .section {{ margin-top: 16px; }}
    .section h2 {{ font-size: 14px; margin: 0 0 8px; color: #dce7f5; }}
    .list {{ margin: 0; padding-left: 18px; color: #c7d4e5; }}
    .list li {{ margin: 6px 0; }}
    .list strong {{ color: #eef5ff; display: inline-block; min-width: 92px; }}
    .subline {{ margin-top: 8px; font-size: 12px; color: #aac0d8; }}
    .label {{ color: #88a0ba; }}
    .freshness.ok {{ color: #8ef0ad; }}
    .freshness.warn {{ color: #ffd089; }}
    .freshness.bad {{ color: #ff9d9d; }}
    @media (max-width: 760px) {{ .grid {{ grid-template-columns: 1fr; }} .hero-title {{ font-size: 24px; }} }}
  </style>
</head>
<body data-checked-at=\"{checked_at}\" data-stale-warn-minutes=\"{CANVAS_STALE_WARN_MINUTES}\" data-stale-bad-minutes=\"{CANVAS_STALE_BAD_MINUTES}\">
  <div class=\"wrap\">
    <div class=\"card\">
      <div class=\"top\">
        <div>
          <h1 class=\"title\">本地健康监督</h1>
          <div class=\"muted\">每 30 秒自动刷新页面；诊断任务默认约每 5 分钟更新一次</div>
        </div>
        <div class=\"badge {severity_class}\">{escape(severity_label)}</div>
      </div>

      <div class=\"hero\">
        <div class=\"hero-title\">{escape(summary)}</div>
        <div class=\"hero-sub\">一句话概述：{escape(issue_overview)}</div>
        <div class=\"subline\"><span class=\"label\">更新时间：</span>{escape(str(report.get('checkedAt') or '-'))}</div>
        <div id=\"freshness\" class=\"subline freshness ok\">数据新鲜度：刚更新</div>
        <div class=\"subline\"><span class=\"label\">主机：</span>{escape(str(report.get('host') or '-'))}</div>
        {status_error_html}
      </div>

      <div class=\"grid\">
        <div class=\"mini {gateway_tone}\"><div class=\"k\">Gateway</div><div class=\"v\">{escape(gateway_title)}</div><div class=\"d\">{escape(gateway_detail)}</div></div>
        <div class=\"mini {network_tone}\"><div class=\"k\">网络</div><div class=\"v\">{escape(network_title)}</div><div class=\"d\">{escape(network_detail)}</div></div>
        <div class=\"mini {model_tone}\"><div class=\"k\">AI 模型</div><div class=\"v\">{escape(model_title)}</div><div class=\"d\">{escape(model_detail)}</div></div>
        <div class=\"mini {thermal_tone}\"><div class=\"k\">温度</div><div class=\"v\">{escape(thermal_title)}</div><div class=\"d\">{escape(thermal_detail)}</div></div>
        <div class=\"mini {resource_tone}\"><div class=\"k\">负载 / 内存</div><div class=\"v\">{escape(resource_title)}</div><div class=\"d\">{escape(resource_detail)}</div></div>
        <div class=\"mini {supervisor_tone}\"><div class=\"k\">监工</div><div class=\"v\">{escape(supervisor_title)}</div><div class=\"d\">{escape(supervisor_detail)}</div></div>
      </div>

      <div class=\"section\">
        <h2>监工状态</h2>
        <ul class=\"list\">{supervisor_items}</ul>
      </div>

      <div class=\"section\">
        <h2>当前问题</h2>
        <ul class=\"list\">{issue_items}</ul>
      </div>

      <div class=\"section\">
        <h2>本地自救建议</h2>
        <ul class=\"list\">{self_help_items}</ul>
      </div>

      <div class=\"section\">
        <h2>外网失败探针</h2>
        <ul class=\"list\">{generic_items}</ul>
      </div>

      <div class=\"section\">
        <h2>Provider 失败探针</h2>
        <ul class=\"list\">{provider_items}</ul>
      </div>
    </div>
  </div>
  <script>
    (() => {{
      const root = document.body;
      const checkedAtRaw = root.dataset.checkedAt || '';
      const warnMinutes = Number(root.dataset.staleWarnMinutes || '12');
      const badMinutes = Number(root.dataset.staleBadMinutes || '20');
      const el = document.getElementById('freshness');
      if (!el || !checkedAtRaw) return;
      const checkedAt = new Date(checkedAtRaw);
      if (Number.isNaN(checkedAt.getTime())) {{
        el.textContent = '数据新鲜度：时间解析失败';
        el.className = 'subline freshness warn';
        return;
      }}
      const render = () => {{
        const diffMs = Date.now() - checkedAt.getTime();
        const diffMinutes = Math.max(0, Math.floor(diffMs / 60000));
        if (diffMinutes >= badMinutes) {{
          el.textContent = `数据新鲜度：可能已失效（${{diffMinutes}} 分钟前）`;
          el.className = 'subline freshness bad';
          return;
        }}
        if (diffMinutes >= warnMinutes) {{
          el.textContent = `数据新鲜度：可能过期（${{diffMinutes}} 分钟前）`;
          el.className = 'subline freshness warn';
          return;
        }}
        el.textContent = diffMinutes <= 1 ? '数据新鲜度：刚更新' : `数据新鲜度：${{diffMinutes}} 分钟前`;
        el.className = 'subline freshness ok';
      }};
      render();
      setInterval(render, 30000);
    }})();
  </script>
</body>
</html>
"""



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



def maybe_send_frontstage(previous: dict[str, Any], current: dict[str, Any], enabled: bool) -> None:
    if not enabled:
        return
    prev_severity = str(previous.get("severity") or "")
    prev_summary = str(previous.get("summary") or "")
    severity = str(current.get("severity") or "ok")
    summary = str(current.get("summary") or "本地健康状态未知")
    if prev_severity == severity and prev_summary == summary:
        return

    if severity == "ok":
        if prev_severity and prev_severity != "ok":
            event_key = f"recovered|{prev_severity}|{current.get('checkedAt')}"
            message = "[本地健康] 当前已恢复正常。"
        else:
            return
    else:
        prefix = "[本地健康] 检测到严重异常：" if severity == "critical" else "[本地健康] 当前有告警："
        event_key = f"{severity}|{summary}|{current.get('checkedAt')}"
        message = f"{prefix}{summary}"

    helper_path = Path(__file__).with_name("openclaw-infos-handle.py")
    cmd = [
        sys.executable,
        str(helper_path),
        "notify-frontstage",
        "--source",
        "local-health",
        "--event-key",
        event_key,
        "--session-key",
        "agent:main:main",
        "--message",
        message,
        "--data-json",
        json.dumps({"severity": severity, "summary": summary, "checkedAt": current.get("checkedAt")}, ensure_ascii=False),
    ]
    subprocess.run(cmd, capture_output=True, text=True, check=False)



def main() -> int:
    parser = argparse.ArgumentParser(description="Local OpenClaw health diagnosis without relying on model replies")
    parser.add_argument("--notify-on-change", action="store_true", help="Best-effort desktop notification when summary changes")
    parser.add_argument("--notify-frontstage", action="store_true", help="Send frontstage updates on health warn/critical transitions and recovery")
    parser.add_argument("--print-json", action="store_true", help="Print JSON report")
    parser.add_argument("--print-human", action="store_true", help="Print human-readable summary")
    args = parser.parse_args()

    STATE_DIR.mkdir(parents=True, exist_ok=True)
    config = load_json(CONFIG_PATH)
    status_payload, status_error = run_openclaw_status_json()
    generic_probes = collect_generic_probes()
    provider_probes = collect_provider_probes(config)
    thermal_status = collect_thermal_status()
    system_pressure = collect_system_pressure()
    supervisor_status = load_supervisor_status()
    severity, summary, reasons, issue_overview, issues = derive_summary(status_payload, status_error, generic_probes, provider_probes, thermal_status, system_pressure)

    gateway_runtime = status_payload.get("gatewayService", {}).get("runtime", {}) if status_payload else {}
    gateway_info = status_payload.get("gateway", {}) if status_payload else {}
    host = gateway_info.get("self", {}).get("host") or socket.gethostname()
    report = {
        "checkedAt": now_iso(),
        "host": host,
        "severity": severity,
        "summary": summary,
        "issueOverview": issue_overview,
        "issues": issues,
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
        "thermal": thermal_status,
        "resource": system_pressure,
        "supervisor": supervisor_status,
        "fallback": FALLBACK_INTERFACE,
    }
    report["selfHelpActions"] = build_self_help_actions(report)

    previous = load_json(TRANSITION_PATH)
    public_status_payload = {
        "checkedAt": report["checkedAt"],
        "host": report["host"],
        "severity": report["severity"],
        "summary": report["summary"],
        "issueOverview": report["issueOverview"],
        "issues": report["issues"],
        "selfHelpActions": report["selfHelpActions"],
        "gateway": report["gateway"],
        "thermal": report["thermal"],
        "resource": report["resource"],
        "supervisor": report["supervisor"],
    }

    save_json(REPORT_PATH, report)
    save_text(SUMMARY_PATH, build_human_summary(report) + "\n")
    save_text(CANVAS_DOC_PATH, build_canvas_html(report))
    save_json(CANVAS_STATUS_JSON_PATH, public_status_payload)

    control_ui_dist_root = resolve_control_ui_dist_root()
    if control_ui_dist_root:
        save_text(control_ui_dist_root / PUBLIC_STATUS_HTML_NAME, build_canvas_html(report))
        save_json(control_ui_dist_root / PUBLIC_STATUS_JSON_NAME, public_status_payload)

    save_json(TRANSITION_PATH, {"severity": severity, "summary": summary, "checkedAt": report["checkedAt"]})

    if severity != "ok":
        append_log(build_failure_log_entry(report))
    elif previous.get("severity") and previous.get("severity") != "ok":
        append_log(
            f"[{report['checkedAt']}] RECOVERED summary={report['summary']} previousSeverity={previous.get('severity')} previousSummary={previous.get('summary')}"
        )
    maybe_notify(previous, report, args.notify_on_change)
    maybe_send_frontstage(previous, report, args.notify_frontstage)

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
