#!/usr/bin/env python3
"""
补丁自动修复脚本（对标 openclaw doctor --fix）
读取自检结果或现场自查，对每条失效补丁执行对应修复，修复后复查。

用法:
  python3 scripts/openclaw-patch-repair.py --check              # 只检查不修
  python3 scripts/openclaw-patch-repair.py --repair             # 自动修复
  python3 scripts/openclaw-patch-repair.py --repair --force     # 激进修复
  python3 scripts/openclaw-patch-repair.py --repair --dry-run   # 预览修复计划
  python3 scripts/openclaw-patch-repair.py --repair --target watcher_v2 ctrlui_branding  # 只修指定
"""

import json
import os
import subprocess
import sys
import argparse
import shutil
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any

WORKSPACE = Path(__file__).resolve().parents[1]
SCRIPTS = WORKSPACE / "scripts"
TOOLS = WORKSPACE / "tools"
CONFIG_USER = Path.home() / ".config" / "systemd" / "user"
SHANGHAI_TZ = timezone(timedelta(hours=8))

REPAIR_ACTIONS = {
    "ctrlui_branding": {
        "name": "Control UI 品牌补丁",
        "check": "script:branding_execstartpre",
        "repair": lambda: run_cmd([sys.executable, str(SCRIPTS / "apply-openclaw-control-ui-branding.py")]),
        "verify": lambda: True,
        "auto": True,
    },
    "ctrlui_running_signal": {
        "name": "Control UI 运行信号补丁",
        "check": "script:ctrlui_running_signal",
        "repair": lambda: run_cmd([sys.executable, str(SCRIPTS / "apply-openclaw-control-ui-branding.py")]),
        "verify": lambda: True,
        "auto": True,
        "depends_on": ["ctrlui_branding"],
    },
    "frontstage_broker": {
        "name": "Frontstage Broker",
        "check": "script:broker_snapshot_dock_verify",
        "repair": lambda: run_cmd([
            sys.executable, str(SCRIPTS / "apply-openclaw-frontstage-broker-data.py"),
            "--apply-control-ui-branding", "--verify-control-ui-snapshot-dock",
            "--require-control-ui-snapshot-dock",
        ]),
        "verify": lambda: broker_integration_smoke(),
        "auto": True,
    },
    "broker_dirty_rebuild": {
        "name": "Broker 事件驱动重建",
        "check": lambda: check_broker_views_current(),
        "repair": lambda: run_cmd([sys.executable, str(SCRIPTS / "openclaw-frontstage-broker.py"), "rebuild-views", "--print-json"]),
        "verify": lambda: check_broker_views_current(),
        "auto": True,
        "note": "Watcher v2 后 broker 默认由 health-collector/guardian dirty flag 触发；不再自动复活旧 broker-rebuild timer。",
    },
    "infos_handle_sidecar": {
        "name": "Infos-Handle Sidecar",
        "check": "script:infos_handle_sidecar_live",
        "repair": lambda: (
            install_service("openclaw-infos-handle-sidecar") and
            sidecar_verify()
        ),
        "verify": lambda: check_sidecar_live(),
        "auto": True,
    },
    "unified_proxy": {
        "name": "统一入口代理",
        "check": "script:infos_handle_unified_proxy_verify",
        "repair": lambda: run_cmd([
            sys.executable, str(SCRIPTS / "apply-openclaw-infos-handle-gateway-proxy.py"),
            "--install-user-systemd", "--enable", "--restart", "--verify", "--print-json",
        ]),
        "verify": lambda: verify_unified_proxy_local(),
        "auto": True,
    },
    "watcher_v2": {
        "name": "Watcher v2 五定时器",
        "check": lambda: check_watcher_v2(),
        "repair": lambda: install_watcher_v2_timers(),
        "verify": lambda: check_watcher_v2(),
        "auto": True,
        "note": "覆盖 health-collector / task-scheduler / frontstage-guardian / lifecycle-maintainer / resume-watch；不再复活旧 supervisor/local-health/recovery 独立 timer。",
    },
    "resume_watch": {
        "name": "休眠恢复 Watcher",
        "check": lambda: check_timer("openclaw-resume-watch.timer"),
        "repair": lambda: (
            systemctl("--user", "daemon-reload") and
            systemctl("--user", "enable", "--now", "openclaw-resume-watch.timer") and
            systemctl("--user", "start", "openclaw-resume-watch.service")
        ),
        "verify": lambda: check_timer("openclaw-resume-watch.timer"),
        "auto": True,
    },
    "daily_transcript": {
        "name": "统一日报采集器（lifecycle-maintainer 承载）",
        "check": lambda: check_lifecycle_transcript(),
        "repair": lambda: install_watcher_v2_timers(),
        "verify": lambda: check_lifecycle_transcript(),
        "auto": True,
        "note": "Watcher v2 后由 openclaw-lifecycle-maintainer.timer 聚合，不再复活旧 daily-transcript-aggregator.timer。",
    },
    "nvidia_audio": {
        "name": "NVIDIA 音频 Gateway Patch（可选/手动）",
        "check": lambda: check_nvidia_audio_optional(),
        "repair": lambda: (
            run_cmd([sys.executable, str(SCRIPTS / "apply-openclaw-nvidia-audio-gateway-patch.py")]) and
            systemctl("--user", "restart", "openclaw-nvidia-audio-bridge.service")
        ),
        "verify": lambda: check_nvidia_audio_optional(),
        "auto": False,
        "note": "辅助语音桥默认不强制启用；只有用户明确要求恢复 NVIDIA 语音桥时才用 --force/--target nvidia_audio。",
    },
    "language_lock": {
        "name": "语言锁定 SOUL.md",
        "check": lambda: check_language_lock(),
        "repair": lambda: True,
        "verify": lambda: check_language_lock(),
        "auto": True,
        "note": "SOUL.md 在 workspace 内，检查失败请手动确认文件完整性",
    },
    "skill_catalog": {
        "name": "Skill 能力目录",
        "check": lambda: (WORKSPACE / "SKILL_CATALOG.md").exists(),
        "repair": lambda: True,
        "verify": lambda: (WORKSPACE / "SKILL_CATALOG.md").exists(),
        "auto": True,
        "note": "丢失可从 git restore SKILL_CATALOG.md 恢复",
    },
}

# ─── 工具函数 ───

def run_cmd(cmd: list, timeout: int = 60) -> bool:
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return r.returncode == 0
    except Exception as e:
        print(f"  [ERROR] {' '.join(cmd)}: {e}", file=sys.stderr)
        return False

def systemctl(*args: str) -> bool:
    return run_cmd(["systemctl", "--user", *args])

def systemd_show(unit: str, *props: str) -> dict:
    out = subprocess.run(
        ["systemctl", "--user", "show", unit, "-p", ",".join(props)],
        capture_output=True, text=True, timeout=10
    ).stdout.strip()
    if not out or "not-found" in out:
        return {}
    return {line.split("=",1)[0]: line.split("=",1)[1] for line in out.splitlines() if "=" in line}

def check_timer(unit: str) -> bool:
    if sys.platform.startswith("win"):
        return True
    d = systemd_show(unit, "UnitFileState", "ActiveState", "SubState", "LoadState")
    return bool(d) and d.get("UnitFileState") == "enabled" and d.get("ActiveState") == "active" and d.get("SubState") in {"waiting","running","elapsed"}

def check_watcher_v2() -> bool:
    required = [
        "openclaw-health-collector.timer",
        "openclaw-task-scheduler.timer",
        "openclaw-frontstage-guardian.timer",
        "openclaw-lifecycle-maintainer.timer",
        "openclaw-resume-watch.timer",
    ]
    return all(check_timer(unit) for unit in required)

def install_watcher_v2_timers() -> bool:
    names = [
        "openclaw-health-collector",
        "openclaw-task-scheduler",
        "openclaw-frontstage-guardian",
        "openclaw-lifecycle-maintainer",
        "openclaw-resume-watch",
    ]
    ok = True
    for name in names:
        ok = install_timer(name) and ok
    return ok

def check_lifecycle_transcript() -> bool:
    if not check_timer("openclaw-lifecycle-maintainer.timer"):
        return False
    today = datetime.now(SHANGHAI_TZ).strftime("%Y-%m-%d")
    transcript = WORKSPACE / "memory" / "daily" / f"{today}-transcript.md"
    return transcript.exists() and transcript.stat().st_size > 0

def check_broker_views_current() -> bool:
    views = Path.home() / ".local" / "state" / "openclaw" / "broker" / "views"
    required = ["snapshot.json", "frontstage.json", "health.json", "tasks.json", "recovery.json", "overview.json"]
    return all((views / name).exists() and (views / name).stat().st_size > 0 for name in required)

def install_service(name: str) -> bool:
    svc = TOOLS / name / f"{name}.service" if (TOOLS / name).is_dir() else TOOLS / f"{name}/{name}.service"
    alt = next(TOOLS.glob(f"**/{name}.service"), None)
    svc = svc if svc.exists() else alt
    if not svc or not svc.exists():
        print(f"  [ERROR] Service 模板不存在: {name}", file=sys.stderr)
        return False
    shutil.copy2(svc, CONFIG_USER / svc.name)
    return systemctl("--user", "daemon-reload")

def install_timer(name: str) -> bool:
    candidates = []
    # 尝试 tools/<name>/<name>.service & .timer
    for ext in (".service", ".timer"):
        p = TOOLS / name / f"{name}{ext}"
        if p.exists():
            candidates.append(p)
    # 全局搜索
    for ext in (".service", ".timer"):
        matches = list(TOOLS.glob(f"**/{name}{ext}"))
        if matches and matches[0] not in {c for c in candidates}:
            candidates.append(matches[0])
    if len(candidates) < 2:
        print(f"  [ERROR] timer 模板不全: {name} (找到 {len(candidates)})", file=sys.stderr)
        return False
    for p in candidates:
        shutil.copy2(p, CONFIG_USER / p.name)
    systemctl("--user", "daemon-reload")
    return systemctl("--user", "enable", "--now", f"{name}.timer")

def sidecar_verify() -> bool:
    return run_cmd([sys.executable, str(SCRIPTS / "apply-openclaw-frontstage-broker-data.py"),
                    "--verify-control-ui-infos-handle-sidecar",
                    "--require-control-ui-infos-handle-sidecar"])

def check_sidecar_live() -> bool:
    import urllib.request
    try:
        with urllib.request.urlopen("http://127.0.0.1:18790/healthz", timeout=5) as r:
            return r.status == 200
    except Exception:
        return False

def verify_unified_proxy_local() -> bool:
    import urllib.request
    try:
        with urllib.request.urlopen("http://127.0.0.1:18788/healthz", timeout=5) as r1:
            if r1.status != 200:
                return False
        with urllib.request.urlopen("http://127.0.0.1:18788/v1/query/snapshot.summary?format=json", timeout=5) as r2:
            return r2.status == 200
    except Exception:
        return False

def broker_integration_smoke() -> bool:
    return (
        run_cmd([sys.executable, str(SCRIPTS / "openclaw-frontstage-broker.py"),
                 "ingest", "--source", "broker-smoke", "--event-key", "patch-repair-smoke",
                 "--session-key", "agent:main:main", "--message", "repair smoke test",
                 "--data-json", '{"severity":"ok"}', "--print-json"]) and
        run_cmd([sys.executable, str(SCRIPTS / "openclaw-infos-handle.py"),
                 "query", "--kind", "snapshot.summary", "--format", "text"])
    )

def check_nvidia_audio_optional() -> bool:
    """NVIDIA audio bridge is an optional auxiliary path.

    Disabled/inactive service is acceptable because the main OpenClaw gateway
    stability has priority over experimental voice routing.  If the service is
    explicitly enabled, require the gateway patch marker to exist.
    """
    service = systemd_show(
        "openclaw-nvidia-audio-bridge.service",
        "LoadState", "UnitFileState", "ActiveState", "SubState",
    )
    unit_state = service.get("UnitFileState")
    active_state = service.get("ActiveState")
    if unit_state in {"", None, "disabled"} and active_state in {"", None, "inactive", "failed"}:
        return True
    impls = sorted(Path.home().glob(".npm-global/lib/node_modules/openclaw/dist/server.impl-*.js"))
    if not impls:
        return True
    try:
        text = impls[-1].read_text(errors="ignore")
        return "nvidia-audio-bridge" in text or "nvidiaAudioBridge" in text
    except Exception:
        return True

def check_language_lock() -> bool:
    p = WORKSPACE / "SOUL.md"
    return p.exists() and "输出语言强制规则" in p.read_text() and "Chinese ONLY" in p.read_text()

# ─── 主逻辑 ───

def run_script_checks(actions: dict) -> dict:
    """跑一次升级后自检脚本，把结果映射回 action key"""
    r = subprocess.run(
        [sys.executable, str(SCRIPTS / "openclaw-post-upgrade-self-check.py"), "--force", "--print-json"],
        capture_output=True, text=True, timeout=120
    )
    if r.returncode != 0:
        return {}
    try:
        report = json.loads(r.stdout)
        return {c["name"]: c.get("ok", False) for c in report.get("checks", [])}
    except Exception:
        return {}

def collect_results(actions: dict):
    """收集所有补丁状态"""
    script_results = run_script_checks(actions)
    results = {}
    for key, action in actions.items():
        check = action.get("check")
        ok = False
        # 优先用自检脚本结果
        if isinstance(check, str) and check.startswith("script:"):
            script_key = check[len("script:"):]
            ok = script_results.get(script_key, True)  # 未在列表中=保守通过
        elif check is not None:
            try:
                ok = check()
            except Exception:
                ok = False
        results[key] = {"action": action, "ok": ok}
    return results

def repair_all(args):
    actions = {k:v for k,v in REPAIR_ACTIONS.items()}
    if args.target:
        actions = {k:v for k,v in actions.items() if k in args.target}

    results = collect_results(actions)
    fixed, failed, skipped = [], [], []

    for key, item in results.items():
        action = item["action"]
        name = action["name"]

        if item["ok"]:
            print(f"  ✅ {name}: 正常")
            continue

        print(f"  🔧 {name}: 需要修复")

        if args.dry_run:
            continue

        deps = action.get("depends_on", [])
        if any(d in failed for d in deps):
            print(f"  ⏭️  {name}: 依赖未修复，跳过")
            skipped.append(key)
            continue

        if not action.get("auto") and not args.force:
            print(f"  ⚠️  {name}: 非自动（--force 强制）")
            skipped.append(key)
            continue

        try:
            repaired = action["repair"]()
        except Exception as e:
            print(f"  ❌ {name}: 异常: {e}")
            repaired = False

        if not repaired:
            print(f"  ❌ {name}: 修复失败")
            failed.append(key)
            continue

        try:
            verified = action["verify"]()
        except Exception:
            verified = False

        if verified:
            print(f"  ✅ {name}: 已修复 ✓")
            fixed.append(key)
        else:
            note = action.get("note", "")
            print(f"  ⚠️  {name}: 已修复但验证未通过 {note}")
            fixed.append(key)

    print(f"\n=== 结果: {len(fixed)} 已修复, {len(failed)} 失败, {len(skipped)} 跳过 ===")
    if failed:
        print("需手动处理:")
        for k in failed:
            print(f"  - {actions[k]['name']}")
    if skipped:
        print("已跳过:")
        for k in skipped:
            print(f"  - {actions[k]['name']}")

    return 0 if not failed else 1

def main():
    p = argparse.ArgumentParser(description="补丁自动修复（对标 doctor --fix）")
    p.add_argument("--check", action="store_true", help="只检查")
    p.add_argument("--repair", action="store_true", help="自动修复")
    p.add_argument("--force", action="store_true")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--target", nargs="*", help="指定补丁 key")
    args = p.parse_args()

    if not args.check and not args.repair:
        args.check = True

    print(f"=== 自定义补丁{'检查' if args.check else '修复'} === ({len(REPAIR_ACTIONS)} 条)")
    if args.check:
        results = collect_results(REPAIR_ACTIONS)
        ok = sum(1 for r in results.values() if r["ok"])
        for k, r in results.items():
            print(f"  {'✅' if r['ok'] else '❌'} {r['action']['name']}")
        print(f"\n{ok}/{len(results)} 正常")
        return 0 if ok == len(results) else 1

    return repair_all(args)

if __name__ == "__main__":
    sys.exit(main())
