#!/usr/bin/env python3
# 适用机器：通用（当前已在公司（Linux）验证）
# 系统 / OS：Linux / macOS / Windows（取决于本机 Python 与 OpenClaw 路径）
# 用途：为当前机器重建并验证 frontstage broker 的 sidecar 数据层产物，适合作为升级后重装与最小回归入口。

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[1]
BROKER_SCRIPT = WORKSPACE / "scripts" / "openclaw-frontstage-broker.py"
BROKER_TEST = WORKSPACE / "scripts" / "test-frontstage-broker.py"
INFOS_HANDLE_SCRIPT = WORKSPACE / "scripts" / "openclaw-infos-handle.py"
INFOS_HANDLE_TEST = WORKSPACE / "scripts" / "test-openclaw-infos-handle.py"
BROKER_REBUILD_SERVICE = WORKSPACE / "tools" / "openclaw-frontstage-broker" / "openclaw-frontstage-broker-rebuild.service"
BROKER_REBUILD_TIMER = WORKSPACE / "tools" / "openclaw-frontstage-broker" / "openclaw-frontstage-broker-rebuild.timer"
BRANDING_SCRIPT = WORKSPACE / "scripts" / "apply-openclaw-control-ui-branding.py"
DEFAULT_PACKAGE_ROOT = Path.home() / ".npm-global" / "lib" / "node_modules" / "openclaw"
OVERRIDE_SCRIPT_NAME = "jarvis-branding-override.js"
USER_SYSTEMD_DIR = Path.home() / ".config" / "systemd" / "user"


def run(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=WORKSPACE, capture_output=True, text=True, check=False)


def resolve_control_ui_dist_root() -> Path | None:
    env_override = os.environ.get("OPENCLAW_PACKAGE_ROOT")
    if env_override:
        candidate = Path(env_override).expanduser().resolve() / "dist" / "control-ui"
        if candidate.exists():
            return candidate

    candidate = DEFAULT_PACKAGE_ROOT / "dist" / "control-ui"
    if candidate.exists():
        return candidate

    try:
        npm_root = subprocess.run(
            ["npm", "root", "-g"],
            cwd=WORKSPACE,
            capture_output=True,
            text=True,
            check=False,
        ).stdout.strip()
    except Exception:
        npm_root = ""
    if npm_root:
        candidate = Path(npm_root).expanduser().resolve() / "openclaw" / "dist" / "control-ui"
        if candidate.exists():
            return candidate
    return None


def inspect_control_ui_snapshot_dock() -> dict[str, object]:
    dist_root = resolve_control_ui_dist_root()
    payload: dict[str, object] = {
        "available": bool(dist_root),
        "distRoot": str(dist_root) if dist_root else None,
        "overrideScript": None,
        "snapshotJsonHref": None,
        "legacyStatusJsonHref": None,
        "statusJsonHref": None,
        "effectiveJsonHref": None,
        "statusPageHref": None,
        "snapshotFirst": False,
        "legacyStatusAliasMarked": False,
        "usesNormalizeFrontstageSnapshot": False,
    }
    if not dist_root:
        return payload

    override_script = dist_root / OVERRIDE_SCRIPT_NAME
    payload["overrideScript"] = str(override_script)
    if not override_script.exists():
        return payload

    script_text = override_script.read_text(encoding="utf-8")
    snapshot_json_match = re.search(r'"snapshotJsonHref":\s*"([^"]+)"', script_text)
    legacy_status_json_match = re.search(r'"legacyStatusJsonHref":\s*"([^"]+)"', script_text)
    status_json_match = re.search(r'"statusJsonHref":\s*"([^"]+)"', script_text)
    status_page_match = re.search(r'"href":\s*"([^"]+/jarvis-frontstage-status\.html|/jarvis-frontstage-status\.html)"', script_text)
    snapshot_json_href = snapshot_json_match.group(1) if snapshot_json_match else None
    legacy_status_json_href = legacy_status_json_match.group(1) if legacy_status_json_match else None
    status_json_href = status_json_match.group(1) if status_json_match else None
    status_page_href = status_page_match.group(1) if status_page_match else None
    effective_json_href = snapshot_json_href or status_json_href
    payload["snapshotJsonHref"] = snapshot_json_href
    payload["legacyStatusJsonHref"] = legacy_status_json_href
    payload["statusJsonHref"] = status_json_href
    payload["effectiveJsonHref"] = effective_json_href
    payload["statusPageHref"] = status_page_href
    payload["snapshotFirst"] = effective_json_href == "/jarvis-frontstage-snapshot.json"
    payload["legacyStatusAliasMarked"] = legacy_status_json_href == "/jarvis-frontstage-status.json" or (
        bool(snapshot_json_href) and status_json_href == "/jarvis-frontstage-status.json"
    )
    payload["usesNormalizeFrontstageSnapshot"] = "function normalizeFrontstageSnapshot" in script_text
    return payload



def inspect_live_frontstage_publication() -> dict[str, object]:
    dist_root = resolve_control_ui_dist_root()
    payload: dict[str, object] = {
        "available": bool(dist_root),
        "distRoot": str(dist_root) if dist_root else None,
        "snapshotJsonPath": None,
        "legacyStatusJsonPath": None,
        "snapshotJsonExists": False,
        "legacyStatusJsonExists": False,
        "snapshotContractPrimaryView": None,
        "snapshotContractPrimaryPublishedJsonKey": None,
        "legacyStatusAliasMarked": False,
        "legacyStatusMatchesSnapshot": False,
        "snapshotFirstReady": False,
    }
    if not dist_root:
        return payload

    snapshot_path = dist_root / "jarvis-frontstage-snapshot.json"
    legacy_status_path = dist_root / "jarvis-frontstage-status.json"
    payload["snapshotJsonPath"] = str(snapshot_path)
    payload["legacyStatusJsonPath"] = str(legacy_status_path)
    payload["snapshotJsonExists"] = snapshot_path.exists()
    payload["legacyStatusJsonExists"] = legacy_status_path.exists()

    snapshot_payload = None
    legacy_status_payload = None
    if snapshot_path.exists():
        try:
            snapshot_payload = json.loads(snapshot_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            snapshot_payload = None
    if legacy_status_path.exists():
        try:
            legacy_status_payload = json.loads(legacy_status_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            legacy_status_payload = None

    snapshot_contract = snapshot_payload.get("snapshotContract") if isinstance(snapshot_payload, dict) and isinstance(snapshot_payload.get("snapshotContract"), dict) else {}
    published_catalog = snapshot_contract.get("publishedJsonCatalog") if isinstance(snapshot_contract.get("publishedJsonCatalog"), dict) else {}
    legacy_status_contract = published_catalog.get("frontstageStatusJson") if isinstance(published_catalog.get("frontstageStatusJson"), dict) else {}
    payload["snapshotContractPrimaryView"] = snapshot_contract.get("primaryView")
    payload["snapshotContractPrimaryPublishedJsonKey"] = snapshot_contract.get("primaryPublishedJsonKey")
    payload["legacyStatusAliasMarked"] = (
        legacy_status_contract.get("role") == "legacy_alias"
        and legacy_status_contract.get("canonicalPublishedJsonKey") == "frontstageSnapshotJson"
    )
    payload["legacyStatusMatchesSnapshot"] = isinstance(snapshot_payload, dict) and isinstance(legacy_status_payload, dict) and snapshot_payload == legacy_status_payload
    payload["snapshotFirstReady"] = (
        payload["snapshotJsonExists"]
        and payload["legacyStatusJsonExists"]
        and payload["snapshotContractPrimaryView"] == "snapshot"
        and payload["snapshotContractPrimaryPublishedJsonKey"] == "frontstageSnapshotJson"
        and payload["legacyStatusAliasMarked"]
        and payload["legacyStatusMatchesSnapshot"]
    )
    return payload


def install_user_systemd() -> dict[str, str]:
    if sys.platform.startswith("win"):
        raise RuntimeError("user systemd install is not supported on Windows")
    if shutil.which("systemctl") is None:
        raise RuntimeError("systemctl not found")
    USER_SYSTEMD_DIR.mkdir(parents=True, exist_ok=True)
    shutil.copy2(BROKER_REBUILD_SERVICE, USER_SYSTEMD_DIR / BROKER_REBUILD_SERVICE.name)
    shutil.copy2(BROKER_REBUILD_TIMER, USER_SYSTEMD_DIR / BROKER_REBUILD_TIMER.name)
    for cmd in [
        ["systemctl", "--user", "daemon-reload"],
        ["systemctl", "--user", "enable", "--now", BROKER_REBUILD_TIMER.name],
        ["systemctl", "--user", "start", BROKER_REBUILD_SERVICE.name],
    ]:
        result = run(cmd)
        if result.returncode != 0:
            raise RuntimeError((result.stderr or result.stdout or f"command failed: {' '.join(cmd)}").strip())
    return {
        "service": str(USER_SYSTEMD_DIR / BROKER_REBUILD_SERVICE.name),
        "timer": str(USER_SYSTEMD_DIR / BROKER_REBUILD_TIMER.name),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Apply and verify frontstage broker data layer")
    parser.add_argument("--install-user-systemd", action="store_true", help="Also install and enable broker rebuild user systemd units on Linux")
    parser.add_argument("--apply-control-ui-branding", action="store_true", help="Also re-apply the current Control UI branding patch before snapshot-first verification")
    parser.add_argument("--verify-control-ui-snapshot-dock", action="store_true", help="Inspect the live Control UI override script plus live public JSON, and report whether snapshot is first while status.json is only a legacy alias")
    parser.add_argument("--require-control-ui-snapshot-dock", action="store_true", help="Fail if the live Control UI snapshot-first chain is not ready")
    args = parser.parse_args()

    steps = [
        [sys.executable, "-m", "py_compile", str(BROKER_SCRIPT), str(BROKER_TEST), str(INFOS_HANDLE_SCRIPT), str(INFOS_HANDLE_TEST), str(BRANDING_SCRIPT)],
        [sys.executable, str(BROKER_TEST)],
        [sys.executable, str(INFOS_HANDLE_TEST)],
    ]
    if args.apply_control_ui_branding:
        steps.append([sys.executable, str(BRANDING_SCRIPT)])
    steps.append(
        [
            sys.executable,
            str(BROKER_SCRIPT),
            "rebuild-views",
            "--print-json",
        ]
    )

    rebuild_payload = None
    installed_units = None
    dock_snapshot_check = None
    frontstage_publication_check = None
    for cmd in steps:
        result = run(cmd)
        if result.returncode != 0:
            sys.stderr.write(result.stderr or result.stdout or f"command failed: {' '.join(cmd)}\n")
            return result.returncode
        if cmd[1:3] != ["-m", "py_compile"]:
            output = (result.stdout or "").strip()
            if output.startswith("{"):
                try:
                    rebuild_payload = json.loads(output)
                except json.JSONDecodeError:
                    pass
            else:
                print(output)

    if args.install_user_systemd:
        try:
            installed_units = install_user_systemd()
        except RuntimeError as exc:
            sys.stderr.write(f"install-user-systemd failed: {exc}\n")
            return 1

    if args.verify_control_ui_snapshot_dock or args.require_control_ui_snapshot_dock or args.apply_control_ui_branding:
        dock_snapshot_check = inspect_control_ui_snapshot_dock()
        frontstage_publication_check = inspect_live_frontstage_publication()
        if args.require_control_ui_snapshot_dock and not (
            bool(dock_snapshot_check.get("snapshotFirst")) and bool(frontstage_publication_check.get("snapshotFirstReady"))
        ):
            sys.stderr.write(
                json.dumps(
                    {
                        "controlUiSnapshotDock": dock_snapshot_check,
                        "frontstagePublication": frontstage_publication_check,
                    },
                    ensure_ascii=False,
                    indent=2,
                )
                + "\n"
            )
            return 1

    print("Applied frontstage broker data layer.")
    if isinstance(rebuild_payload, dict):
        print(json.dumps(rebuild_payload, ensure_ascii=False, indent=2))
    if dock_snapshot_check is not None:
        print(json.dumps({"controlUiSnapshotDock": dock_snapshot_check}, ensure_ascii=False, indent=2))
    if frontstage_publication_check is not None:
        print(json.dumps({"frontstagePublication": frontstage_publication_check}, ensure_ascii=False, indent=2))
    if installed_units:
        print(json.dumps({"installedUserSystemd": installed_units}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
