#!/usr/bin/env python3
# 适用机器：通用（当前已在公司（Linux）验证）
# 系统 / OS：Linux / macOS / Windows（部分 systemd 检查在 Windows 上会自动跳过）
# 用途：检测 OpenClaw 当前版本是否发生变化；若已升级，则主动按“升级后自检清单”做一轮最小核对，并输出可读摘要。

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any

from openclaw_infos_handle_contract import invoke_handle_query

WORKSPACE = Path(__file__).resolve().parents[1]
CHECKLIST_PATH = WORKSPACE / "docs" / "通用-OpenClaw-升级后自检清单.md"
STATE_DIR = Path(os.environ.get("XDG_STATE_HOME", str(Path.home() / ".local" / "state"))) / "openclaw" / "post-upgrade-self-check"
STATE_PATH = STATE_DIR / "state.json"
REPORT_PATH = STATE_DIR / "last-report.json"
DEFAULT_PACKAGE_JSON = Path.home() / ".npm-global" / "lib" / "node_modules" / "openclaw" / "package.json"
BRANDING_CONF = Path.home() / ".config" / "systemd" / "user" / "openclaw-gateway.service.d" / "branding.conf"
CONTROL_UI_DIST = Path.home() / ".npm-global" / "lib" / "node_modules" / "openclaw" / "dist" / "control-ui"
CONTROL_UI_OVERRIDE = CONTROL_UI_DIST / "jarvis-branding-override.js"
INFOS_HANDLE_SCRIPT = WORKSPACE / "scripts" / "openclaw-infos-handle.py"
INFOS_HANDLE_TEST = WORKSPACE / "scripts" / "test-openclaw-infos-handle.py"
INFOS_HANDLE_CALLERS_TEST = WORKSPACE / "scripts" / "test-infos-handle-frontstage-callers.py"
FRONTSTAGE_APPLY_SCRIPT = WORKSPACE / "scripts" / "apply-openclaw-frontstage-broker-data.py"
UNIFIED_PROXY_APPLY_SCRIPT = WORKSPACE / "scripts" / "apply-openclaw-infos-handle-gateway-proxy.py"
SIDECAR_USER_SERVICE = "openclaw-infos-handle-sidecar.service"
UNIFIED_PROXY_USER_SERVICE = "openclaw-unified-proxy.service"
DEFAULT_ONLINE_MESSAGE = "贾维斯已上线，我在。要开始干活的话，直接喊我。"

SHANGHAI_TZ = timezone(timedelta(hours=8))


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")



def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}



def save_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")



def run(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=WORKSPACE, capture_output=True, text=True, check=False)



def detect_package_json() -> Path | None:
    env_override = os.environ.get("OPENCLAW_PACKAGE_ROOT")
    if env_override:
        candidate = Path(env_override).expanduser().resolve() / "package.json"
        if candidate.exists():
            return candidate
    if DEFAULT_PACKAGE_JSON.exists():
        return DEFAULT_PACKAGE_JSON
    npm_root = run(["npm", "root", "-g"]).stdout.strip()
    if npm_root:
        candidate = Path(npm_root).expanduser().resolve() / "openclaw" / "package.json"
        if candidate.exists():
            return candidate
    return None



def current_openclaw_version() -> tuple[str | None, str | None]:
    package_json = detect_package_json()
    if not package_json:
        return None, None
    try:
        data = json.loads(package_json.read_text(encoding="utf-8"))
    except Exception:
        return None, str(package_json)
    version = data.get("version") if isinstance(data, dict) else None
    return version if isinstance(version, str) else None, str(package_json)



def make_check(name: str, ok: bool, detail: str, *, required: bool = True) -> dict[str, Any]:
    return {
        "name": name,
        "ok": ok,
        "required": required,
        "detail": detail,
    }



def check_branding_execstartpre() -> dict[str, Any]:
    if not BRANDING_CONF.exists():
        return make_check("branding_execstartpre", False, f"缺少文件：{BRANDING_CONF}")
    text = BRANDING_CONF.read_text(encoding="utf-8", errors="ignore")
    needle = f"ExecStartPre=-/usr/bin/python3 {WORKSPACE / 'scripts' / 'apply-openclaw-control-ui-branding.py'}"
    return make_check(
        "branding_execstartpre",
        needle in text,
        "已挂到 gateway 启动前自动重打" if needle in text else "branding.conf 存在，但未找到自动重打入口",
    )



def check_live_control_ui_markers() -> dict[str, Any]:
    assets_dir = CONTROL_UI_DIST / "assets"
    asset_candidates = sorted(assets_dir.glob("index-*.js")) if assets_dir.exists() else []
    asset_path = asset_candidates[-1] if asset_candidates else None
    if asset_path is None or not CONTROL_UI_OVERRIDE.exists():
        return make_check("live_control_ui_markers", False, "live Control UI 资产或 override 缺失")
    asset_text = asset_path.read_text(encoding="utf-8", errors="ignore")
    override_text = CONTROL_UI_OVERRIDE.read_text(encoding="utf-8", errors="ignore")
    ok = (
        "JarvisProjectYieldedHistoryReply" in asset_text
        and "JarvisShouldShowPendingReadingIndicator" in asset_text
        and '"snapshotJsonHref": "/jarvis-frontstage-snapshot.json"' in override_text
    )
    detail = (
        f"关键前端补丁标记齐全：{asset_path.name}"
        if ok
        else f"关键前端补丁标记不完整：{asset_path.name}"
    )
    return make_check("live_control_ui_markers", ok, detail)



def run_cmd_check(name: str, cmd: list[str], success_substring: str | None = None, *, required: bool = True) -> dict[str, Any]:
    result = run(cmd)
    output = ((result.stdout or "") + (result.stderr or "")).strip()
    ok = result.returncode == 0 and (success_substring is None or success_substring in output)
    if ok and success_substring:
        detail = success_substring
    else:
        detail = output.splitlines()[-1] if output else f"exit={result.returncode}"
    return make_check(name, ok, detail, required=required)



def check_infos_handle_contract_entry() -> dict[str, Any]:
    request_id = "post-upgrade-self-check:contract.catalog"
    try:
        snapshot = invoke_handle_query(
            INFOS_HANDLE_SCRIPT,
            kind="contract.catalog",
            output_format="json",
            request_id=request_id,
            python_executable=sys.executable,
            run=subprocess.run,
        )
    except RuntimeError as exc:
        return make_check("infos_handle_contract_entry", False, str(exc))

    result = snapshot.get("result") if isinstance(snapshot.get("result"), dict) else {}
    request_catalog = result.get("requestCatalog") if isinstance(result.get("requestCatalog"), dict) else {}
    actions = request_catalog.get("actions") if isinstance(request_catalog.get("actions"), dict) else {}
    handle_catalog = actions.get("handle") if isinstance(actions.get("handle"), dict) else {}
    helper_functions = handle_catalog.get("clientHelperFunctions") if isinstance(handle_catalog.get("clientHelperFunctions"), list) else []
    ok = (
        snapshot.get("ok")
        and snapshot.get("requestId") == request_id
        and snapshot.get("kind") == "contract.catalog"
        and snapshot.get("requestInputMode") == "request_file"
        and snapshot.get("responseOutputMode") == "stdout"
        and handle_catalog.get("preferredRequestInputMode") == "request_file"
        and handle_catalog.get("clientHelperModule") == "openclaw_infos_handle_contract.py"
        and "invoke_handle_query" in helper_functions
        and "extract_handle_response_snapshot" in helper_functions
    )
    detail = (
        f"requestId={snapshot.get('requestId') or '-'} "
        f"input={snapshot.get('requestInputMode') or '-'} "
        f"kind={snapshot.get('kind') or '-'} "
        f"helper={handle_catalog.get('clientHelperModule') or '-'}"
    )
    return make_check("infos_handle_contract_entry", bool(ok), detail)



def check_infos_handle_snapshot_summary_entry() -> dict[str, Any]:
    request_id = "post-upgrade-self-check:snapshot.summary"
    try:
        snapshot = invoke_handle_query(
            INFOS_HANDLE_SCRIPT,
            kind="snapshot.summary",
            output_format="json",
            request_id=request_id,
            python_executable=sys.executable,
            run=subprocess.run,
        )
    except RuntimeError as exc:
        return make_check("infos_handle_snapshot_summary_entry", False, str(exc))

    result = snapshot.get("result") if isinstance(snapshot.get("result"), dict) else {}
    ok = (
        snapshot.get("ok")
        and snapshot.get("requestId") == request_id
        and snapshot.get("kind") == "snapshot.summary"
        and snapshot.get("format") == "json"
        and snapshot.get("requestInputMode") == "request_file"
        and snapshot.get("responseOutputMode") == "stdout"
        and isinstance(result.get("summary"), str)
        and bool(str(result.get("summary") or "").strip())
    )
    detail = (
        f"requestId={snapshot.get('requestId') or '-'} "
        f"kind={snapshot.get('kind') or '-'} "
        f"severity={result.get('severity') or '-'} "
        f"summary={result.get('summary') or '-'}"
    )
    return make_check("infos_handle_snapshot_summary_entry", bool(ok), detail)



def check_infos_handle_sources_latest_entry() -> dict[str, Any]:
    request_id = "post-upgrade-self-check:sources.latest"
    try:
        snapshot = invoke_handle_query(
            INFOS_HANDLE_SCRIPT,
            kind="sources.latest",
            output_format="json",
            request_id=request_id,
            python_executable=sys.executable,
            run=subprocess.run,
        )
    except RuntimeError as exc:
        return make_check("infos_handle_sources_latest_entry", False, str(exc))

    result = snapshot.get("result") if isinstance(snapshot.get("result"), dict) else {}
    source_items = result.get("sourceItems") if isinstance(result.get("sourceItems"), list) else None
    available_sources = result.get("availableSources") if isinstance(result.get("availableSources"), list) else None
    ok = (
        snapshot.get("ok")
        and snapshot.get("requestId") == request_id
        and snapshot.get("kind") == "sources.latest"
        and snapshot.get("format") == "json"
        and snapshot.get("requestInputMode") == "request_file"
        and snapshot.get("responseOutputMode") == "stdout"
        and isinstance(result.get("count"), int)
        and source_items is not None
        and available_sources is not None
    )
    detail = (
        f"requestId={snapshot.get('requestId') or '-'} "
        f"kind={snapshot.get('kind') or '-'} "
        f"count={result.get('count') if isinstance(result.get('count'), int) else '-'} "
        f"sources={len(source_items) if isinstance(source_items, list) else '-'}"
    )
    return make_check("infos_handle_sources_latest_entry", bool(ok), detail)



def systemd_unit_state(unit: str) -> tuple[bool, dict[str, str]]:
    if sys.platform.startswith("win"):
        return False, {}
    result = run(["systemctl", "--user", "show", unit, "-p", "LoadState", "-p", "UnitFileState", "-p", "ActiveState", "-p", "SubState"])
    output = (result.stdout or "") + (result.stderr or "")
    lines = [line.strip() for line in output.splitlines() if line.strip()]
    data: dict[str, str] = {}
    for line in lines:
        if "=" in line:
            k, v = line.split("=", 1)
            data[k] = v
    exists = result.returncode == 0 and data.get("LoadState") not in {None, "not-found", "masked"}
    return exists, data


def check_timer(unit: str) -> dict[str, Any]:
    if sys.platform.startswith("win"):
        return make_check(unit, True, "Windows 环境跳过 systemd 检查", required=False)
    exists, data = systemd_unit_state(unit)
    ok = (
        exists
        and data.get("UnitFileState") == "enabled"
        and data.get("ActiveState") == "active"
        and data.get("SubState") in {"waiting", "running", "elapsed"}
    )
    return make_check(unit, ok, json.dumps(data, ensure_ascii=False))


def check_user_service(unit: str, *, required_if_present: bool = True) -> dict[str, Any]:
    if sys.platform.startswith("win"):
        return make_check(unit, True, "Windows 环境跳过 systemd 检查", required=False)
    exists, data = systemd_unit_state(unit)
    if not exists:
        return make_check(unit, True, f"未安装：{unit}", required=False)
    ok = data.get("ActiveState") == "active" and data.get("SubState") in {"running", "listening", "waiting", "elapsed"}
    return make_check(unit, ok, json.dumps(data, ensure_ascii=False), required=required_if_present)


def check_lifecycle_maintainer() -> dict[str, Any]:
    """检查生命周期维护器 timer 和输出文件（替代旧 daily-transcript-aggregator）"""
    timer_ok = True
    timer_detail = ""
    if not sys.platform.startswith("win"):
        exists, data = systemd_unit_state("openclaw-lifecycle-maintainer.timer")
        timer_ok = (
            exists
            and data.get("UnitFileState") == "enabled"
            and data.get("ActiveState") == "active"
            and data.get("SubState") in {"waiting", "running", "elapsed"}
        )
        timer_detail = json.dumps(data, ensure_ascii=False)
    # 检查今天的 transcript 文件是否存在
    today = datetime.now(SHANGHAI_TZ).strftime("%Y-%m-%d")
    transcript_file = WORKSPACE / "memory" / "daily" / f"{today}-transcript.md"
    file_ok = transcript_file.exists() and transcript_file.stat().st_size > 0
    ok = timer_ok and file_ok
    detail = f"timer={timer_ok}, file={'OK' if file_ok else 'MISSING/EMPTY'}"
    if timer_detail:
        detail += f" | timer_state={timer_detail}"
    return make_check("lifecycle-maintainer", ok, detail)


def check_infos_handle_sidecar_live() -> dict[str, Any]:
    cmd = [
        sys.executable,
        str(FRONTSTAGE_APPLY_SCRIPT),
        "--verify-control-ui-infos-handle-sidecar",
    ]
    result = run(cmd)
    output = ((result.stdout or "") + (result.stderr or "")).strip()
    if result.returncode != 0:
        detail = output.splitlines()[-1] if output else f"exit={result.returncode}"
        return make_check("infos_handle_sidecar_live", False, detail)
    ok = False
    detail = "missing controlUiInfosHandleSidecar payload"
    for block in output.split("\n{\n"):
        text = block if block.startswith("{") else "{\n" + block
        try:
            payload = json.loads(text)
        except Exception:
            continue
        sidecar = payload.get("controlUiInfosHandleSidecar") if isinstance(payload.get("controlUiInfosHandleSidecar"), dict) else None
        if not sidecar:
            continue
        ok = sidecar.get("ok") is True
        detail = (
            f"summaryKind={sidecar.get('summaryKind') or '-'} "
            f"severity={sidecar.get('summarySeverity') or '-'} "
            f"sseReady={sidecar.get('sseReady')}"
        )
        break
    return make_check("infos_handle_sidecar_live", ok, detail)


def check_infos_handle_unified_proxy_verify() -> dict[str, Any]:
    if not UNIFIED_PROXY_APPLY_SCRIPT.exists():
        return make_check("infos_handle_unified_proxy_verify", True, "缺少 apply 脚本，跳过", required=False)
    result = run([sys.executable, str(UNIFIED_PROXY_APPLY_SCRIPT), "--verify", "--print-json"])
    output = ((result.stdout or "") + (result.stderr or "")).strip()
    if result.returncode != 0:
        detail = output.splitlines()[-1] if output else f"exit={result.returncode}"
        return make_check("infos_handle_unified_proxy_verify", False, detail)
    try:
        payload = json.loads(result.stdout)
    except Exception:
        detail = output.splitlines()[-1] if output else "invalid json"
        return make_check("infos_handle_unified_proxy_verify", False, detail)
    verify = payload.get("verify") if isinstance(payload.get("verify"), dict) else {}
    ok = bool(verify.get("ok")) and verify.get("localHealthzOk") is True and verify.get("localSummaryCode") == 200
    remote_no_auth = verify.get("remoteNoAuthCode")
    remote_with_auth = verify.get("remoteWithAuthCode")
    if verify.get("lanIp"):
        ok = ok and remote_no_auth == 401 and remote_with_auth == 200
    detail = (
        f"mode={verify.get('mode') or payload.get('mode') or '-'} "
        f"port={verify.get('port') or '-'} "
        f"local={verify.get('localSummaryCode') or '-'} "
        f"remoteNoAuth={remote_no_auth if remote_no_auth is not None else '-'} "
        f"remoteWithAuth={remote_with_auth if remote_with_auth is not None else '-'}"
    )
    return make_check("infos_handle_unified_proxy_verify", ok, detail)



def build_report(force: bool = False) -> dict[str, Any]:
    previous_state = load_json(STATE_PATH)
    version, package_json_path = current_openclaw_version()
    previous_version = previous_state.get("lastVerifiedVersion") if isinstance(previous_state.get("lastVerifiedVersion"), str) else None
    version_changed = bool(version) and version != previous_version
    should_verify = force or version_changed or previous_version is None

    checks: list[dict[str, Any]] = []
    if should_verify:
        checks.append(make_check("checklist_exists", CHECKLIST_PATH.exists(), f"清单：{CHECKLIST_PATH}"))
        checks.append(check_branding_execstartpre())
        checks.append(check_live_control_ui_markers())
        checks.append(run_cmd_check(
            "broker_snapshot_dock_verify",
            [sys.executable, str(FRONTSTAGE_APPLY_SCRIPT), "--verify-control-ui-snapshot-dock"],
            '"snapshotFirstReady": true',
        ))
        checks.append(check_infos_handle_contract_entry())
        checks.append(check_infos_handle_snapshot_summary_entry())
        checks.append(check_infos_handle_sources_latest_entry())
        checks.append(check_infos_handle_sidecar_live())
        checks.append(check_user_service(SIDECAR_USER_SERVICE))
        checks.append(check_user_service(UNIFIED_PROXY_USER_SERVICE))
        checks.append(check_infos_handle_unified_proxy_verify())
        checks.append(run_cmd_check(
            "broker_test",
            [sys.executable, str(WORKSPACE / "scripts" / "test-frontstage-broker.py")],
            "ALL PASS",
        ))
        checks.append(run_cmd_check(
            "infos_handle_test",
            [sys.executable, str(INFOS_HANDLE_TEST)],
            "ALL PASS",
        ))
        checks.append(run_cmd_check(
            "infos_handle_callers_test",
            [sys.executable, str(INFOS_HANDLE_CALLERS_TEST)],
            "ALL PASS",
        ))
        checks.append(run_cmd_check(
            "frontstage_guardian_test",
            [sys.executable, str(WORKSPACE / "scripts" / "openclaw-frontstage-guardian.py"), "--print-human"],
            "OK",
        ))
        checks.append(run_cmd_check(
            "task_scheduler_test",
            [sys.executable, str(WORKSPACE / "scripts" / "openclaw-task-scheduler.py"), "--print-human"],
            "idle",
        ))
        checks.append(check_timer("openclaw-frontstage-guardian.timer"))
        checks.append(check_timer("openclaw-health-collector.timer"))
        checks.append(check_timer("openclaw-task-scheduler.timer"))
        checks.append(check_lifecycle_maintainer())
        checks.append(check_timer("openclaw-resume-watch.timer"))
    ok = all(item.get("ok") for item in checks if item.get("required", True)) if checks else True

    summary = "未检测到版本变化，本轮跳过升级后自检。"
    boot_message = DEFAULT_ONLINE_MESSAGE
    if should_verify and ok:
        summary = f"已完成 OpenClaw {version or 'unknown'} 升级后自检：关键补丁、broker、infos-handle、sidecar 与统一入口都正常。"
        boot_message = f"贾维斯已上线，我在。刚核对过 OpenClaw {version or '当前版本'} 升级后自检清单：关键补丁、broker、infos-handle、sidecar 和统一入口都正常。"
    elif should_verify and not ok:
        failed = [item["name"] for item in checks if item.get("required", True) and not item.get("ok")]
        summary = f"OpenClaw {version or 'unknown'} 升级后自检未全部通过：{', '.join(failed)}"
        boot_message = f"贾维斯已上线，我在。检测到 OpenClaw 已更新，但升级后自检没全过：{', '.join(failed)}。先别慌，喊我我来修。"

    report = {
        "checkedAt": now_iso(),
        "checklistPath": str(CHECKLIST_PATH),
        "packageJson": package_json_path,
        "currentVersion": version,
        "previousVersion": previous_version,
        "versionChanged": version_changed,
        "shouldVerify": should_verify,
        "ok": ok,
        "summary": summary,
        "bootMessage": boot_message,
        "checks": checks,
    }
    save_json(REPORT_PATH, report)
    if should_verify and ok and version:
        save_json(STATE_PATH, {
            "lastCheckedAt": report["checkedAt"],
            "lastVerifiedVersion": version,
            "lastChecklistPath": str(CHECKLIST_PATH),
            "lastReportPath": str(REPORT_PATH),
        })
    elif should_verify:
        save_json(STATE_PATH, {
            "lastCheckedAt": report["checkedAt"],
            "lastVerifiedVersion": previous_version,
            "lastChecklistPath": str(CHECKLIST_PATH),
            "lastReportPath": str(REPORT_PATH),
            "lastFailedVersion": version,
        })
    return report



def main() -> int:
    parser = argparse.ArgumentParser(description="Run the post-upgrade OpenClaw self-check checklist")
    parser.add_argument("--force", action="store_true", help="Run the self-check even when the version did not change")
    parser.add_argument("--strict", action="store_true", help="Return non-zero when required checks fail")
    parser.add_argument("--print-json", action="store_true", help="Print JSON report")
    parser.add_argument("--print-human", action="store_true", help="Print human-readable summary")
    parser.add_argument("--print-boot-json", action="store_true", help="Print JSON suitable for BOOT.md handling")
    args = parser.parse_args()

    report = build_report(force=args.force)

    if args.print_json or args.print_boot_json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    elif args.print_human or True:
        print(report["summary"])
        if report.get("shouldVerify"):
            for item in report.get("checks", []):
                marker = "PASS" if item.get("ok") else ("SKIP" if not item.get("required", True) else "FAIL")
                print(f"- {marker} {item.get('name')}: {item.get('detail')}")
        else:
            print(f"- checklist: {report.get('checklistPath')}")

    return 1 if args.strict and report.get("shouldVerify") and not report.get("ok") else 0


if __name__ == "__main__":
    raise SystemExit(main())
