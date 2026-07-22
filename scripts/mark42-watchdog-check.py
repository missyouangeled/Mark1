#!/usr/bin/env python3
"""Mark42 Watchdog - 检查 daemon 存活并自动重启

替代旧的 `mark42 watchdog --check`（该子命令已移除）。
通过 systemctl 检查 engine-daemon 和 armor-guard 是否存活，
如果挂了就自动拉起。同时记录状态到日志。
"""

import subprocess
import sys
import json
import datetime
import os

DAEMONS = [
    ("mark42-engine-daemon.service", "循环引擎"),
    ("mark42-armor-guard.service", "上下文铠甲"),
]

STATE_DIR = os.environ.get(
    "MARK42_STATE_DIR",
    os.path.expanduser("~/.local/state/openclaw/mark42"),
)
LOG_DIR = os.environ.get(
    "MARK42_LOG_DIR",
    os.path.expanduser("~/.local/state/openclaw/mark42/logs"),
)
os.makedirs(LOG_DIR, exist_ok=True)


def log(msg: str) -> None:
    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)


def is_active(service: str) -> bool:
    r = subprocess.run(
        ["systemctl", "--user", "is-active", service],
        capture_output=True,
        text=True,
        timeout=10,
    )
    return r.stdout.strip() == "active"


def start_service(service: str) -> bool:
    r = subprocess.run(
        ["systemctl", "--user", "start", service],
        capture_output=True,
        text=True,
        timeout=15,
    )
    return r.returncode == 0


def get_mark42_status() -> dict | None:
    """调用 `mark42 status --json` 获取系统状态"""
    try:
        r = subprocess.run(
            [
                os.environ.get("MARK42_PYTHON_BIN", "/usr/bin/python3"),
                os.environ.get("MARK42_CLI", os.path.expanduser("~/.local/bin/mark42")),
                "status",
                "--json",
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if r.returncode == 0:
            return json.loads(r.stdout)
    except Exception:
        pass
    return None


def main() -> int:
    log("━" * 40)
    log("Mark42 Watchdog 检查开始")
    actions = []

    # 1. 检查 daemon 存活
    for service, label in DAEMONS:
        if is_active(service):
            log(f"✅ {label} ({service}) 运行中")
        else:
            log(f"❌ {label} ({service}) 已停止，尝试拉起...")
            if start_service(service):
                log(f"✅ {label} 已重新启动")
                actions.append(f"restart:{service}")
            else:
                log(f"🚨 {label} 拉起失败！")
                actions.append(f"restart-failed:{service}")

    # 2. 获取 Mark42 系统状态摘要
    status = get_mark42_status()
    if status:
        armor_pct = status.get("armor", {}).get("context_percent")
        loops = status.get("engine", {}).get("active_loops", 0)
        log(f"📊 上下文: {armor_pct}% | 活跃 Loop: {loops}")
    else:
        log("⚠️ 无法获取 Mark42 状态")

    # 3. 汇总
    if actions:
        log(f"🔔 本轮动作: {', '.join(actions)}")
    else:
        log("✅ 所有组件正常，无需干预")

    return 0


if __name__ == "__main__":
    sys.exit(main())
