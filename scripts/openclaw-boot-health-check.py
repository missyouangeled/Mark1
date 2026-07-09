#!/usr/bin/env python3
"""
boot-health-check.py — 开机后自动体检 + 自愈
运行时机: 系统启动后，Gateway 就绪后触发
"""

from __future__ import annotations

import json
import hashlib
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

SERVICES = {
    "gateway": "openclaw-gateway.service",
    "infos-handle-sidecar": "openclaw-infos-handle-sidecar.service",
    "unified-proxy": "openclaw-unified-proxy.service",
}

TIMERS = {
    "frontstage-guardian": "openclaw-frontstage-guardian.timer",
    "health-collector": "openclaw-health-collector.timer",
    "task-scheduler": "openclaw-task-scheduler.timer",
    "lifecycle-maintainer": "openclaw-lifecycle-maintainer.timer",
    "resume-watch": "openclaw-resume-watch.timer",
}

STATE_DIR = Path.home() / ".local/state/openclaw/boot-health"
STATE_FILE = STATE_DIR / "last-check.json"
INJECT_STATE_FILE = STATE_DIR / "last-startup-inject.json"
SCRIPT_DIR = Path(__file__).resolve().parent
SH = timezone(timedelta(hours=8))
STARTUP_INJECT_COOLDOWN_SECONDS = 30 * 60


def run(cmd: list[str], timeout: int = 5) -> tuple[int, str, str]:
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return r.returncode, r.stdout.strip(), r.stderr.strip()
    except subprocess.TimeoutExpired:
        return 124, "", "timeout"
    except Exception as e:
        return 1, "", str(e)


def now_sh() -> datetime:
    return datetime.now(SH)


def parse_iso(text: str | None) -> datetime | None:
    if not text:
        return None
    try:
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        return datetime.fromisoformat(text).astimezone(SH)
    except Exception:
        return None


def load_json(path: Path):
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def save_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def compute_message_digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def compute_boot_event_key(ok: bool, issues: list[str], boot_message: str) -> str:
    fingerprint_source = json.dumps(
        {
            "ok": bool(ok),
            "issues": list(issues),
            "bootMessage": boot_message,
        },
        ensure_ascii=False,
        sort_keys=True,
    )
    digest = compute_message_digest(fingerprint_source)[:16]
    return f"boot-health|{digest}"


def should_skip_startup_inject(message: str) -> tuple[bool, dict]:
    state = load_json(INJECT_STATE_FILE)
    digest = compute_message_digest(message)
    now = now_sh()
    info = {
        "digest": digest,
        "checkedAt": now.isoformat(),
        "cooldownSeconds": STARTUP_INJECT_COOLDOWN_SECONDS,
    }
    if not isinstance(state, dict):
        return False, info

    last_at = parse_iso(state.get("lastInjectedAt"))
    last_digest = state.get("messageDigest")
    if last_at is None or last_digest != digest:
        return False, info

    age = (now - last_at).total_seconds()
    info["lastInjectedAt"] = last_at.isoformat()
    info["ageSeconds"] = round(age, 3)
    if 0 <= age < STARTUP_INJECT_COOLDOWN_SECONDS:
        return True, info
    return False, info


def check_service(name: str, unit: str) -> dict:
    """检查并自动拉起 systemd 用户服务。"""
    rc, out, err = run(["systemctl", "--user", "is-active", unit])
    if rc == 0:
        return {"name": name, "status": "running", "action": "none"}

    # 尝试拉起
    rc2, _, err2 = run(["systemctl", "--user", "start", unit], timeout=10)
    time.sleep(1)
    rc3, _, _ = run(["systemctl", "--user", "is-active", unit])
    if rc3 == 0:
        return {"name": name, "status": "recovered", "action": "started"}
    return {"name": name, "status": "failed", "action": "start-failed", "error": err2}


def check_timer(name: str, unit: str) -> dict:
    rc, out, err = run(["systemctl", "--user", "is-active", unit])
    if rc == 0:
        return {"name": name, "status": "active", "action": "none"}
    rc2, _, err2 = run(["systemctl", "--user", "start", unit], timeout=10)
    time.sleep(1)
    rc3, _, _ = run(["systemctl", "--user", "is-active", unit])
    if rc3 == 0:
        return {"name": name, "status": "recovered", "action": "started"}
    return {"name": name, "status": "inactive", "action": "start-failed", "error": err2}


def check_disk() -> dict:
    rc, out, err = run(["df", "-h", "/"])
    if rc != 0:
        return {"path": "/", "status": "error", "error": err}
    lines = out.strip().split("\n")
    if len(lines) < 2:
        return {"path": "/", "status": "unknown"}
    parts = lines[1].split()
    pct = int(parts[4].replace("%", ""))
    return {
        "path": "/",
        "used_pct": pct,
        "status": "critical" if pct >= 95 else "warning" if pct >= 85 else "ok",
        "available": parts[3],
    }


def check_memory() -> dict:
    rc, out, err = run(["free", "-m"])
    if rc != 0:
        return {"status": "error"}
    lines = out.strip().split("\n")
    if len(lines) < 2:
        return {"status": "unknown"}
    parts = lines[1].split()
    total = int(parts[1])
    available = int(parts[6])
    pct = int((total - available) / total * 100)
    return {
        "total_mb": total,
        "available_mb": available,
        "used_pct": pct,
        "status": "critical" if pct >= 95 else "warning" if pct >= 90 else "ok",
    }


def check_gateway_port() -> dict:
    """快速验证 Gateway 端口可达。"""
    import socket
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(3)
        s.connect(("127.0.0.1", 18789))
        s.close()
        return {"port": 18789, "status": "reachable"}
    except Exception as e:
        return {"port": 18789, "status": "unreachable", "error": str(e)}


def check_gateway_startup_errors() -> dict:
    """检查 Gateway 启动过程中是否有 config invalid 等严重错误。
    2026-06-22: gateway 7 连败后才通过 doctor --fix 启动成功，
    但 systemctl is-active 返回 active，boot health 误报 OK。"""
    try:
        rc, out, err = run(
            ["journalctl", "--user", "-u", "openclaw-gateway.service",
             "--since", "5 minutes ago", "--no-pager"],
            timeout=5
        )
        if rc != 0:
            return {"status": "ok", "note": "journalctl failed"}

        errors = []
        for line in out.split("\n"):
            lower = line.lower()
            if "invalid config" in lower:
                errors.append(f"config-invalid: {line.strip()[-200:]}")
            elif "gateway failed to start" in lower:
                errors.append(f"startup-failed: {line.strip()[-200:]}")
            elif "failed with result" in lower and "openclaw-gateway" in lower:
                errors.append(f"service-failed: {line.strip()[-200:]}")

        # 统计失败次数
        fail_count = len([e for e in errors if "service-failed" in e or "startup-failed" in e])

        if fail_count > 0:
            return {
                "status": "warning",
                "failures": fail_count,
                "detail": errors[:5],  # 最多5条
                "note": f"Gateway 启动过程中失败了 {fail_count} 次，最终通过修复启动",
            }
        return {"status": "ok", "failures": 0}
    except Exception as e:
        return {"status": "ok", "note": f"check failed: {e}"}


def main():
    STATE_DIR.mkdir(parents=True, exist_ok=True)

    # 等 Gateway 完全就绪
    for _ in range(15):
        rc, _, _ = run(["systemctl", "--user", "is-active", "openclaw-gateway.service"])
        if rc == 0:
            break
        time.sleep(2)
    else:
        print("ERROR: Gateway did not start within 30s", file=sys.stderr)
        sys.exit(1)

    # 再等一小段让 Gateway 内部初始化完成
    time.sleep(3)

    results = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "services": {},
        "timers": {},
        "disk": {},
        "memory": {},
        "gateway_port": {},
        "all_ok": True,
    }

    # 检查服务
    for name, unit in SERVICES.items():
        results["services"][name] = check_service(name, unit)

    # 检查定时器
    for name, unit in TIMERS.items():
        results["timers"][name] = check_timer(name, unit)

    # 检查磁盘/内存
    results["disk"] = check_disk()
    results["memory"] = check_memory()
    results["gateway_port"] = check_gateway_port()
    results["gateway_startup"] = check_gateway_startup_errors()

    # 汇总
    for svc in results["services"].values():
        if svc["status"] not in ("running", "recovered"):
            results["all_ok"] = False
    for tmr in results["timers"].values():
        if tmr["status"] not in ("active", "recovered"):
            results["all_ok"] = False
    if results["disk"].get("status") not in ("ok",):
        results["all_ok"] = False
    if results["memory"].get("status") not in ("ok",):
        results["all_ok"] = False
    if results["gateway_port"].get("status") != "reachable":
        results["all_ok"] = False
    gs = results.get("gateway_startup", {})
    if gs.get("status") == "warning" and gs.get("failures", 0) >= 3:
        results["all_ok"] = False

    # 生成摘要
    issues = []
    for name, svc in results["services"].items():
        if svc["status"] == "recovered":
            issues.append(f"🔧 {name} 已自动拉起")
        elif svc["status"] == "failed":
            issues.append(f"❌ {name} 启动失败")
    for name, tmr in results["timers"].items():
        if tmr["status"] == "recovered":
            issues.append(f"🔧 {name} 定时器已自动拉起")
        elif tmr["status"] == "inactive":
            issues.append(f"⚠️ {name} 定时器未激活")

    gs = results.get("gateway_startup", {})
    if gs.get("status") == "warning":
        issues.append(f"⚠️ Gateway 启动失败 {gs.get('failures',0)} 次后才成功（可能是配置损坏）")
    if results["disk"].get("status") == "warning":
        issues.append(f"⚠️ 磁盘使用率 {results['disk'].get('used_pct')}%")
    if results["memory"].get("status") == "warning":
        issues.append(f"⚠️ 内存使用率 {results['memory'].get('used_pct')}%")

    summary = "✅ 所有服务正常" if not issues else "\n".join(issues)
    results["summary"] = summary
    results["issue_count"] = len(issues)

    # 写状态文件
    STATE_FILE.write_text(json.dumps(results, ensure_ascii=False, indent=2))

    # ── 运行升级自检 ──
    try:
        upgrade = subprocess.run(
            [sys.executable, str(SCRIPT_DIR / "openclaw-post-upgrade-self-check.py"), "--print-boot-json"],
            capture_output=True, text=True, timeout=30
        )
        upgrade_data = json.loads(upgrade.stdout.strip())
        upgrade_msg = upgrade_data.get("bootMessage", "")
        if upgrade_data.get("versionChanged"):
            print(f"[boot] 检测到版本变化: {upgrade_data.get('previousVersion')} → {upgrade_data.get('currentVersion')}")
    except Exception as e:
        print(f"[boot] 升级自检跳过: {e}")
        upgrade_msg = ""

    # 输出 JSON 供 BOOT.md 调用
    boot_message = summary if issues else "✅ 开机体检通过，所有服务正常。"
    full_boot_msg = f"🩺 开机体检:\n{boot_message}"
    if upgrade_msg:
        full_boot_msg = f"{upgrade_msg}\n\n{full_boot_msg}"
    print(json.dumps({
        "ok": results["all_ok"],
        "issues": issues,
        "bootMessage": full_boot_msg,
        "detail": str(STATE_FILE),
    }, ensure_ascii=False))

    boot_event_key = compute_boot_event_key(results["all_ok"], issues, full_boot_msg)

    # ── 发射 broker 启动事件，让 frontstage broker 推送到聊天 ──
    try:
        from datetime import datetime, timezone
        broker_dir = Path.home() / ".local/state/openclaw/broker"
        broker_dir.mkdir(parents=True, exist_ok=True)
        event = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "source": "boot-health",
            "event": "boot.completed",
            "ok": results["all_ok"],
            "issues": issues,
            "bootMessage": full_boot_msg,
            "eventKey": boot_event_key,
            "message": full_boot_msg,
        }
        with open(broker_dir / "events.jsonl", "a") as f:
            f.write(json.dumps(event, ensure_ascii=False) + "\n")
        # 设 dirty flag 触发 frontstage broker 重建
        (broker_dir / "dirty").write_text(datetime.now(timezone.utc).isoformat())
        print(f"[boot] broker 启动事件已发射 key={boot_event_key}")
    except Exception as e:
        print(f"[boot] broker 事件发射失败: {e}")

    # ── 注入启动系统事件到主会话，触发 AGENTS.md 加载流程 ──
    try:
        startup_msg = (
            "🎬 系统启动事件\n\n"
            "请执行以下启动流程：\n\n"
            "1. 向用户发送「⏳ 贾维斯正在加载系统，请稍候...」\n"
            "2. 按 AGENTS.md 启动流程依次读取："
            "ACTIVE_RULES.md → BOOT_INDEX.md → RULES_INDEX.md → "
            "SOUL.md → USER.md → MEMORY.md → SKILL_CATALOG.md → WORKSPACE_INDEX.md\n"
            "3. 读取完成后向用户发送「✅ 系统已就绪，我在。需要我的话，直接说。」\n"
            "4. 回复 NO_REPLY"
        )
        skip, inject_info = should_skip_startup_inject(startup_msg)
        if skip:
            print(
                "[boot] 启动系统事件跳过：命中冷却窗口 "
                f"({inject_info.get('ageSeconds')}s < {STARTUP_INJECT_COOLDOWN_SECONDS}s)"
            )
        else:
            proc = subprocess.run(
                ["openclaw", "gateway", "call", "chat.inject",
                 "--params", json.dumps({"sessionKey": "agent:main:main", "message": startup_msg}),
                 "--json"],
                capture_output=True, text=True, timeout=15
            )
            if proc.returncode == 0:
                save_json(
                    INJECT_STATE_FILE,
                    {
                        "lastInjectedAt": now_sh().isoformat(),
                        "messageDigest": inject_info["digest"],
                        "sessionKey": "agent:main:main",
                        "stdout": proc.stdout.strip()[:2000],
                    },
                )
                print("[boot] 启动流程系统事件已注入主会话")
            else:
                print(f"[boot] 启动事件注入失败(returncode={proc.returncode}): {proc.stderr.strip()[:500]}")
    except Exception as e:
        print(f"[boot] 启动事件注入失败: {e}")


if __name__ == "__main__":
    main()
