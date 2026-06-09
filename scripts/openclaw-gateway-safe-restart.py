#!/usr/bin/env python3
"""
Gateway 安全重启脚本
适用机器：公司（Linux）/ 通用

在重启 Gateway 前自动保存工作区状态（git），发通知，
重启后等待 Gateway 恢复健康再返回。

用法：
  python3 scripts/openclaw-gateway-safe-restart.py          # 安全重启
  python3 scripts/openclaw-gateway-safe-restart.py --reason "内存超限"  # 带原因
  python3 scripts/openclaw-gateway-safe-restart.py --dry-run           # 预演不执行
  python3 scripts/openclaw-gateway-safe-restart.py --notify-only       # 只通知不重启
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

WORKSPACE = Path.home() / ".openclaw/workspace"
FRONTSTAGE_STATE = Path.home() / ".local/state/openclaw/frontstage-broker"
NOTIFY_FILE = FRONTSTAGE_STATE / "pending-notify.json"


# ── 工作区保存 ────────────────────────────────────────────

def save_workspace_state(reason: str) -> dict:
    """Git 暂存并提交工作区变更，确保重启不丢数据。"""
    result = {
        "saved": False,
        "commitHash": None,
        "filesChanged": [],
        "error": None,
    }

    try:
        # 检查是否有未提交变更
        status = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=str(WORKSPACE),
            capture_output=True, text=True, timeout=30,
        )
        changed = [line[3:] for line in status.stdout.strip().split("\n") if line.strip()]
        result["filesChanged"] = changed

        if not changed:
            result["saved"] = True
            result["note"] = "工作区干净，无需保存"
            return result

        # 暂存所有变更
        subprocess.run(
            ["git", "add", "-A"],
            cwd=str(WORKSPACE),
            capture_output=True, text=True, timeout=30, check=True,
        )

        # 提交
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        commit_msg = f"auto-save: pre-gateway-restart — {reason} [{ts}]"
        commit = subprocess.run(
            ["git", "commit", "-m", commit_msg],
            cwd=str(WORKSPACE),
            capture_output=True, text=True, timeout=30, check=True,
        )
        result["commitHash"] = commit.stdout.strip().split()[-1][:8] if commit.stdout else "unknown"
        result["saved"] = True

    except Exception as exc:
        result["error"] = str(exc)

    return result


# ── 通知 ──────────────────────────────────────────────────

def send_notification(reason: str, phase: str) -> bool:
    """向前台发送重启通知。"""
    FRONTSTAGE_STATE.mkdir(parents=True, exist_ok=True)

    messages = {
        "pre": f"🔄 Gateway 即将安全重启（原因：{reason}）\n正在保存工作区状态...",
        "saved": f"✅ 工作区已保存，正在重启 Gateway...",
        "post": f"✅ Gateway 已恢复运行，所有服务正常。",
        "failed": f"❌ Gateway 重启后未能恢复，请手动检查。",
    }

    msg = messages.get(phase, f"[Gateway 安全重启] {phase}: {reason}")

    notify = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "phase": phase,
        "message": msg,
        "reason": reason,
    }

    try:
        NOTIFY_FILE.write_text(json.dumps(notify, ensure_ascii=False))
        return True
    except Exception:
        return False


# ── Gateway 操作 ──────────────────────────────────────────

def check_gateway_healthy(timeout: int = 45) -> tuple[bool, str]:
    """检查 Gateway 是否可达。"""
    try:
        result = subprocess.run(
            ["openclaw", "status", "--json"],
            capture_output=True, text=True, timeout=timeout,
        )
        if result.returncode != 0:
            return False, f"status 命令失败: {result.stderr[:200]}"
        data = json.loads(result.stdout)
        reachable = data.get("gateway", {}).get("reachable", False)
        if reachable:
            latency = data.get("gateway", {}).get("connectLatencyMs", "?")
            return True, f"可达 (延迟 {latency}ms)"
        return False, "gateway.reachable=false"
    except subprocess.TimeoutExpired:
        return False, "status 命令超时"
    except Exception as exc:
        return False, str(exc)


def restart_gateway() -> tuple[bool, str]:
    """执行 Gateway 重启。"""
    try:
        result = subprocess.run(
            ["systemctl", "--user", "restart", "openclaw-gateway"],
            capture_output=True, text=True, timeout=60,
        )
        if result.returncode != 0:
            return False, f"systemctl 失败: {result.stderr[:200]}"
        return True, "重启命令已执行"
    except subprocess.TimeoutExpired:
        return False, "systemctl 命令超时"
    except Exception as exc:
        return False, str(exc)


def wait_for_gateway(max_wait: int = 90, poll_interval: int = 5) -> tuple[bool, str]:
    """等待 Gateway 恢复健康。"""
    deadline = time.monotonic() + max_wait
    attempts = 0

    # 先等 Gateway 进程起来
    time.sleep(10)

    while time.monotonic() < deadline:
        attempts += 1
        healthy, detail = check_gateway_healthy(timeout=30)
        if healthy:
            return True, f"第 {attempts} 次检查恢复: {detail}"
        time.sleep(poll_interval)

    return False, f"等待 {max_wait}s 后仍未恢复 (共 {attempts} 次检查)"


# ── 主流程 ────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Gateway 安全重启")
    parser.add_argument("--reason", default="手动触发", help="重启原因")
    parser.add_argument("--dry-run", action="store_true", help="预演不执行")
    parser.add_argument("--notify-only", action="store_true", help="只发通知不重启")
    parser.add_argument("--max-wait", type=int, default=90, help="恢复等待最大秒数")
    args = parser.parse_args()

    print(f"🔧 Gateway 安全重启 — {args.reason}")
    print()

    if args.dry_run:
        print("🧪 预演模式，不会实际执行重启。")
        print()

    # 1. 通知：准备重启
    print("📢 发送预重启通知...")
    send_notification(args.reason, "pre")
    print("   → 通知已发送")

    # 2. 保存工作区
    print("💾 保存工作区状态...")
    if args.dry_run:
        saved = {"saved": True, "note": "预演模式，跳过实际保存", "filesChanged": ["(预演)"], "commitHash": "DRY-RUN"}
    else:
        saved = save_workspace_state(args.reason)

    if saved["saved"]:
        if saved.get("filesChanged"):
            print(f"   → 已保存 {len(saved['filesChanged'])} 个文件")
            print(f"   → commit: {saved.get('commitHash', '?')}")
        else:
            print(f"   → {saved.get('note', '已保存')}")
    else:
        print(f"   ⚠️ 保存失败: {saved['error']}")
        if not args.dry_run:
            print("   ❌ 终止重启 — 工作区保存失败")
            send_notification(args.reason, "failed")
            return 1

    # 3. 通知：已保存
    send_notification(args.reason, "saved")

    if args.notify_only:
        print()
        print("✅ 仅通知模式，不执行重启。")
        return 0

    # 4. 重启前的 Gateway 状态
    print()
    print("🔍 重启前 Gateway 状态:")
    healthy_before, detail_before = check_gateway_healthy()
    print(f"   → {detail_before}")

    # 5. 执行重启
    print()
    if args.dry_run:
        print("🧪 [预演] 跳过实际重启")
    else:
        print("🔄 重启 Gateway...")
        ok, msg = restart_gateway()
        if not ok:
            print(f"   ❌ 重启失败: {msg}")
            send_notification(args.reason, "failed")
            return 1
        print(f"   → {msg}")

    # 6. 等待恢复
    print()
    print(f"⏳ 等待 Gateway 恢复 (最多 {args.max_wait}s)...")
    if args.dry_run:
        print("🧪 [预演] 跳过等待")
        recovered, recovery_detail = True, "预演模式"
    else:
        recovered, recovery_detail = wait_for_gateway(max_wait=args.max_wait)
    print(f"   → {recovery_detail}")

    # 7. 最终通知
    print()
    if recovered:
        send_notification(args.reason, "post")
        print("✅ Gateway 安全重启完成")
        return 0
    else:
        send_notification(args.reason, "failed")
        print("❌ Gateway 未能恢复，请手动检查")
        return 1


if __name__ == "__main__":
    sys.exit(main())
