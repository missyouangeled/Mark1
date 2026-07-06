#!/usr/bin/env python3
"""
卡住会话检测器 (Stuck Session Detector)

监控网关日志中的 `long-running session` 警告，检测卡在 model_call 的会话，
通过 broker 向前台报告，帮助及时发现和恢复被阻塞的会话。

设计原则：
  - 只分析最近 N 分钟的网关日志
  - 关注 activeWorkKind=model_call + recovery=none 的卡住会话
  - 特别关注 agent:main:main（主会话被阻塞 = 用户发消息无响应）
  - 输出 JSON 供 health-collector 集成
  - 通过 broker emit 向前台报告

用法：
  python3 scripts/openclaw-stuck-session-detector.py --print-json
  python3 scripts/openclaw-stuck-session-detector.py --report

阈值：
  - STUCK_THRESHOLD_S: age 超过此值视为"卡住"（默认 120s）
  - LOOKBACK_MINUTES: 只分析最近 N 分钟的日志（默认 5min）
  - MAIN_SESSION_CRITICAL_S: 主会话被卡住超过此值视为严重（默认 60s）
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

WORKSPACE = Path(__file__).resolve().parent.parent
SCRIPTS = WORKSPACE / "scripts"
GATEWAY_LOG_DIR = Path("/tmp/openclaw")
STATE_DIR = Path(
    os.environ.get("XDG_STATE_HOME", str(Path.home() / ".local" / "state"))
) / "openclaw" / "stuck-session-detector"
STATUS_PATH = STATE_DIR / "status.json"
RECOVERY_PATH = STATE_DIR / "recovery-state.json"
LOG_PATH = STATE_DIR / "detector.log"

# ── 检测阈值 ──
STUCK_THRESHOLD_S = 120       # age > 此值 → 视为卡住
MAIN_SESSION_CRITICAL_S = 60  # 主会话卡住 > 此值 → 严重
LOOKBACK_MINUTES = 5           # 只分析最近 N 分钟的日志
LOG_ROTATE_MAX_BYTES = 256 * 1024
LOG_ROTATE_KEEP_BYTES = 64 * 1024

# ── 自动恢复阈值 ──
# 需要连续 N 次检测到同一会话卡住，才触发恢复（避免单次误报）
# 健康采集器每 60s 运行一次 → 2 次 ≈ 2 分钟确认
MAIN_STUCK_CONSECUTIVE_FOR_RESTART = 2   # 主会话连续 2 次检测到卡住 → 重启
OTHER_STUCK_CONSECUTIVE_FOR_RESTART = 3  # 其他会话连续 3 次检测到卡住 → 重启
# 两次自动重启之间的最小间隔（防止重启循环）
RESTART_COOLDOWN_S = 600           # 10 分钟

# 排除的 sessionKey 前缀（子会话卡住不影响主会话通信）
NON_BLOCKING_PREFIXES = [
    "agent:main:subagent:",
    "agent:main:cron:",
]

# 排除的 sessionId 前缀（boot 会话的 model_call 是系统级后台 run，不阻塞用户消息）
NON_BLOCKING_SID_PREFIXES = [
    "boot-",
]


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def maybe_rotate_log() -> None:
    if LOG_PATH.exists() and LOG_PATH.stat().st_size > LOG_ROTATE_MAX_BYTES:
        content = LOG_PATH.read_text(errors="replace")
        LOG_PATH.write_text(content[-LOG_ROTATE_KEEP_BYTES:], errors="replace")


def log_line(msg: str) -> None:
    """追加一行日志"""
    maybe_rotate_log()
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    line = f"[{now_iso()}] {msg}\n"
    with open(LOG_PATH, "a") as f:
        f.write(line)


def get_gateway_log_path() -> Path:
    env_path = os.environ.get("OPENCLAW_GATEWAY_LOG_PATH")
    if env_path:
        return Path(env_path).expanduser()

    today_name = f"openclaw-{datetime.now().date().isoformat()}.log"
    today_path = GATEWAY_LOG_DIR / today_name
    if today_path.exists():
        return today_path

    candidates = sorted(GATEWAY_LOG_DIR.glob("openclaw-*.log"), reverse=True)
    if candidates:
        return candidates[0]
    return today_path


def parse_long_running_entry(raw: str) -> dict | None:
    """解析 long-running session 日志条目"""
    # 格式: long-running session: sessionId=X sessionKey=Y state=processing age=Zs ...
    try:
        body = raw.split("long-running session: ", 1)[-1]
    except (ValueError, IndexError):
        return None

    result: dict[str, Any] = {}
    # 解析 key=value 对（value 可能含后缀如 141s）
    parts = body.strip().split()
    for part in parts:
        if "=" in part:
            k, v = part.split("=", 1)
            # 数值字段（去除 s/min/h 等后缀）
            numeric_keys = ("age", "queueDepth", "stalledAfterS", "lastProgressAge")
            if k in numeric_keys:
                v = v.rstrip("s")
                try:
                    result[k] = int(v)
                except ValueError:
                    result[k] = v
            else:
                result[k] = v

    return result if "sessionId" in result else None


def get_recent_long_running_entries() -> list[dict]:
    """从网关日志获取最近的 long-running session 条目"""
    gateway_log = get_gateway_log_path()
    if not gateway_log.exists():
        return []

    try:
        # 用 Python 解析 JSONL 日志
        entries = []
        cutoff_time = time.time() - (LOOKBACK_MINUTES * 60)
        
        with open(gateway_log, "r", errors="replace") as f:
            # 从尾部读取（日志较大时高效）
            f.seek(0, 2)
            file_size = f.tell()
            # 读最后 2MB
            read_start = max(0, file_size - 2 * 1024 * 1024)
            f.seek(read_start)
            if read_start > 0:
                f.readline()  # 跳过不完整的第一行
            
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    d = json.loads(line)
                except json.JSONDecodeError:
                    continue
                
                msg = d.get("message", "")
                if "long-running session:" in msg:
                    t_str = d.get("time", "")
                    try:
                        ts = datetime.fromisoformat(t_str).timestamp()
                    except (ValueError, OSError):
                        continue
                    if ts >= cutoff_time:
                        parsed = parse_long_running_entry(msg)
                        if parsed:
                            parsed["_logTime"] = t_str
                            parsed["_logTs"] = ts
                            entries.append(parsed)
        return entries
    except Exception as e:
        log_line(f"ERROR reading gateway log: {e}")
        return []


def is_blocking_session(session_key: str, session_id: str = "") -> bool:
    """判断是否为会阻塞主会话通信的 sessionKey 或 sessionId"""
    for prefix in NON_BLOCKING_PREFIXES:
        if session_key.startswith(prefix):
            return False
    for prefix in NON_BLOCKING_SID_PREFIXES:
        if session_id.startswith(prefix):
            return False
    return True


def analyze_stuck_sessions(entries: list[dict]) -> dict:
    """分析卡住会话，返回汇总"""
    now_ts = time.time()
    stuck_sessions = []
    critical_count = 0
    blocked_main = False

    # 去重 + 过滤：只关心 model_call + recovery=none 的卡住会话
    # 按 sessionId 去重，保留 model_call 条目中 age 最大的
    seen: dict[str, dict] = {}
    for e in entries:
        sid = e.get("sessionId", "")
        age = e.get("age", 0)
        work_kind = e.get("activeWorkKind", "")
        recovery = e.get("recovery", "none")
        
        # 只考虑 model_call + recovery=none + 超过阈值
        if work_kind != "model_call":
            continue
        if recovery != "none":
            continue
        if age < STUCK_THRESHOLD_S:
            continue
        
        if sid not in seen or age > seen[sid].get("age", 0):
            seen[sid] = e

    for sid, e in seen.items():
        age = e.get("age", 0)
        work_kind = e.get("activeWorkKind", "")
        recovery = e.get("recovery", "none")
        session_key = e.get("sessionKey", "")
        last_progress_age = e.get("lastProgressAge", 0)
        log_ts = e.get("_logTs", 0)
        
        # 计算当前真实 age：logged age + 自日志以来的秒数
        real_age = int(age + max(0, time.time() - log_ts)) if log_ts else age

        is_blocking = is_blocking_session(session_key, sid)
        is_critical = is_blocking and real_age >= MAIN_SESSION_CRITICAL_S

        stuck_info = {
            "sessionId": sid,
            "sessionKey": session_key,
            "age": real_age,
            "loggedAge": age,
            "queueDepth": e.get("queueDepth", 0),
            "activeWorkKind": work_kind,
            "lastProgressAge": last_progress_age,
            "recovery": recovery,
            "loggedAt": e.get("_logTime", ""),
            "isBlocking": is_blocking,
            "isCritical": is_critical,
        }
        stuck_sessions.append(stuck_info)
        
        if is_critical:
            critical_count += 1
            if session_key == "agent:main:main":
                blocked_main = True

    # 按严重程度排序
    stuck_sessions.sort(key=lambda x: (not x["isCritical"], -x["age"]))

    return {
        "checkedAt": now_iso(),
        "totalStuck": len(stuck_sessions),
        "criticalCount": critical_count,
        "blockedMain": blocked_main,
        "sessions": stuck_sessions,
        "ok": critical_count == 0,  # 非阻塞会话不视为问题
        "summary": "未发现卡住会话" if not stuck_sessions else
                   ("发现 1 个卡住会话（非阻塞，已忽略）" if critical_count == 0 and len(stuck_sessions) == 1 else
                   ("发现 1 个卡住会话，⚠ 主会话被阻塞！" if blocked_main and len(stuck_sessions) == 1 else
                   f"发现 {len(stuck_sessions)} 个卡住会话"
                   + (f"，⚠ 主会话被阻塞！" if blocked_main else ""))),
    }


def emit_to_broker(report: dict) -> bool:
    """通过 broker emit 向前台报告"""
    broker_script = SCRIPTS / "openclaw-frontstage-broker.py"
    if not broker_script.exists():
        log_line("WARN broker script not found, skipping emit")
        return False

    blocked_main = report.get("blockedMain", False)
    stuck_count = report.get("totalStuck", 0)
    
    if not blocked_main and stuck_count == 0:
        return True  # nothing to report

    level = "critical" if blocked_main else "warn"
    summary = report.get("summary", "")
    detail = ""
    for s in report.get("sessions", [])[:3]:
        detail += f"  {s['sessionKey']} 卡住 {s['age']}s (model_call, recovery=none)\n"

    payload = json.dumps({
        "kind": "stuck-session",
        "source": "stuck-session-detector",
        "level": level,
        "eventKey": f"stuck-sessions:{stuck_count}",
        "text": f"🔴 {summary}\n{detail}" if blocked_main else f"⚠ {summary}\n{detail}",
    })

    try:
        result = subprocess.run(
            [
                sys.executable, str(broker_script),
                "emit",
                "--payload", payload,
                "--source", "stuck-session-detector",
            ],
            capture_output=True, text=True, timeout=15,
            cwd=str(WORKSPACE),
        )
        return result.returncode == 0
    except Exception as e:
        log_line(f"ERROR broker emit failed: {e}")
        return False


def save_status(report: dict) -> None:
    """保存状态文件"""
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    STATUS_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2), errors="replace")


# ═══════════════════════════════════════════════════════════
#  自动恢复逻辑
# ═══════════════════════════════════════════════════════════

def load_recovery_state() -> dict[str, Any]:
    """加载恢复状态"""
    if RECOVERY_PATH.exists():
        try:
            data = json.loads(RECOVERY_PATH.read_text(errors="replace"))
            if isinstance(data, dict):
                return data
        except (json.JSONDecodeError, OSError):
            pass
    return {"lastRestartAt": None, "restartCount": 0, "restartedFor": []}


def save_recovery_state(state: dict) -> None:
    """保存恢复状态"""
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    RECOVERY_PATH.write_text(json.dumps(state, ensure_ascii=False, indent=2), errors="replace")


def is_main_session_actually_blocked(sessions: list[dict]) -> bool:
    """
    二次验证：主会话是否真的被阻塞了。
    
    检查近期是否有成功发送到前台的 chat.send（网关日志里的回执消息）。
    如果有，说明主会话仍在正常通信 → 卡住会话可能是后台系统 run，不阻塞用户。
    """
    gateway_log = get_gateway_log_path()
    if not gateway_log.exists():
        return True  # 无法验证，保守认为阻塞
    
    cutoff = time.time() - 120  # 最近 2 分钟
    has_recent_chat = False
    
    try:
        with open(gateway_log, "r", errors="replace") as f:
            f.seek(0, 2)
            size = f.tell()
            start = max(0, size - 128 * 1024)
            f.seek(start)
            if start > 0:
                f.readline()
            
            for line in f:
                try:
                    d = json.loads(line.strip())
                except json.JSONDecodeError:
                    continue
                
                t_str = d.get("time", "")
                try:
                    ts = datetime.fromisoformat(t_str).timestamp()
                except (ValueError, OSError):
                    continue
                
                if ts < cutoff:
                    continue
                
                msg = d.get("message", "")
                # 检查是否有成功的 chat.send 回执
                if "✓ chat.send" in msg:
                    has_recent_chat = True
                    break
    except Exception:
        return True  # 无法验证，保守认为阻塞
    
    # 没有最近成功消息 = 可能真的阻塞了
    return not has_recent_chat


def should_restart(report: dict, state: dict) -> tuple[bool, str]:
    """
    判断是否应触发网关重启。
    要求连续多次检测到同一会话卡住，避免单次误报（日志条目可能已过期）。
    返回 (should_restart, reason)。
    """
    sessions = report.get("sessions", [])
    if not sessions:
        # 没有卡住会话 → 清空所有检测计数
        if state.get("detectionCounts"):
            state["detectionCounts"] = {}
            save_recovery_state(state)
        return False, ""
    
    # 检查冷却期
    last_restart = state.get("lastRestartAt")
    if last_restart:
        try:
            last_ts = datetime.fromisoformat(last_restart).timestamp()
            elapsed = time.time() - last_ts
            if elapsed < RESTART_COOLDOWN_S:
                remaining = int(RESTART_COOLDOWN_S - elapsed)
                return False, f"冷却期中（{remaining}s 后可用）"
        except (ValueError, OSError):
            pass
    
    # 更新连续检测计数
    counts: dict[str, int] = state.get("detectionCounts", {})
    if not isinstance(counts, dict):
        counts = {}
    
    # 清除不在当前报告中的旧计数
    current_sids = {s["sessionId"] for s in sessions}
    for sid in list(counts.keys()):
        if sid not in current_sids:
            del counts[sid]
    
    # 递增当前卡住会话的计数
    for s in sessions:
        sid = s["sessionId"]
        counts[sid] = counts.get(sid, 0) + 1
    
    state["detectionCounts"] = counts
    save_recovery_state(state)
    
    # 已经为这些会话触发过重启（本次卡住周期内）
    restarted_for = set(state.get("restartedFor", []))
    
    # 二次验证：主会话是否真的被阻塞了
    # 如果有最近 2 分钟内的成功消息，说明主会话正常 → 跳过恢复
    if any(s.get("sessionKey") == "agent:main:main" for s in sessions):
        if not is_main_session_actually_blocked(sessions):
            log_line("SKIP recovery: main session has recent successful messages, not actually blocked")
            return False, "主会话仍有正常通信，跳过恢复（卡住会话可能是后台系统 run）"
    
    # 检查是否达到重启阈值
    for s in sessions:
        sid = s.get("sessionId", "")
        sk = s.get("sessionKey", "")
        count = counts.get(sid, 0)
        age = s.get("age", 0)
        
        if sid in restarted_for:
            continue
        
        # 主会话：连续 2 次检测到 → 重启
        if sk == "agent:main:main" and count >= MAIN_STUCK_CONSECUTIVE_FOR_RESTART:
            return True, f"主会话 agent:main:main 连续 {count} 次检测到卡住 (age={age}s)，触发自动恢复"
        
        # 其他阻塞会话：连续 3 次检测到 → 重启
        if s.get("isBlocking") and count >= OTHER_STUCK_CONSECUTIVE_FOR_RESTART:
            return True, f"{sk} 连续 {count} 次检测到卡住 (age={age}s)，触发自动恢复"
    
    return False, ""


def trigger_gateway_restart(report: dict, state: dict, reason: str) -> dict[str, Any]:
    """
    触发网关重启以恢复卡住的会话。
    返回恢复结果。
    """
    stuck_sids = [s["sessionId"] for s in report.get("sessions", [])]
    stuck_keys = list(set(s["sessionKey"] for s in report.get("sessions", [])))
    
    # 1. 先通过 broker 向前台报告
    detail_lines = [f"  卡住会话: {sk}" for sk in stuck_keys[:5]]
    detail = "\n".join(detail_lines)
    restart_msg = json.dumps({
        "kind": "stuck-session-recovery",
        "source": "stuck-session-detector",
        "level": "critical",
        "eventKey": f"auto-restart:{int(time.time())}",
        "text": f"🔄 检测到卡住会话，正在自动重启网关以恢复...\n原因: {reason}\n{detail}",
    })
    
    broker_script = SCRIPTS / "openclaw-frontstage-broker.py"
    if broker_script.exists():
        subprocess.run(
            [sys.executable, str(broker_script), "emit",
             "--payload", restart_msg, "--source", "stuck-session-detector"],
            capture_output=True, text=True, timeout=15,
            cwd=str(WORKSPACE),
        )
    
    log_line(f"RECOVERY: restarting gateway. reason={reason} sessions={stuck_keys}")
    
    # 2. 执行重启
    result = {"action": "gateway-restart", "ok": False, "reason": reason, "stuckSessionIds": stuck_sids}
    
    try:
        proc = subprocess.run(
            ["openclaw", "gateway", "restart"],
            capture_output=True, text=True, timeout=60,
            cwd=str(WORKSPACE),
        )
        result["ok"] = proc.returncode == 0
        result["exitCode"] = proc.returncode
        result["stdout"] = (proc.stdout or "")[:500]
        result["stderr"] = (proc.stderr or "")[:500]
        
        if proc.returncode == 0:
            log_line(f"RECOVERY: gateway restarted successfully")
        else:
            log_line(f"RECOVERY: gateway restart FAILED rc={proc.returncode} stderr={(proc.stderr or '')[:200]}")
    except subprocess.TimeoutExpired:
        result["error"] = "gateway restart timed out after 60s"
        log_line("RECOVERY: gateway restart TIMEOUT")
    except Exception as exc:
        result["error"] = str(exc)
        log_line(f"RECOVERY: gateway restart EXCEPTION {exc}")
    
    # 3. 更新恢复状态
    state["lastRestartAt"] = now_iso()
    state["restartCount"] = state.get("restartCount", 0) + 1
    state["restartedFor"] = stuck_sids
    save_recovery_state(state)
    
    # 4. 报告结果
    if result["ok"]:
        result_msg = json.dumps({
            "kind": "stuck-session-recovery-done",
            "source": "stuck-session-detector",
            "level": "info",
            "eventKey": f"auto-restart-done:{int(time.time())}",
            "text": f"✅ 网关已自动重启完成。{len(stuck_sids)} 个卡住会话已清理，主会话应恢复正常。",
        })
    else:
        result_msg = json.dumps({
            "kind": "stuck-session-recovery-failed",
            "source": "stuck-session-detector",
            "level": "critical",
            "eventKey": f"auto-restart-fail:{int(time.time())}",
            "text": f"❌ 网关自动重启失败！({result.get('error') or result.get('stderr','')[:200]})\n可能需要手动重启：openclaw gateway restart",
        })
    
    if broker_script.exists():
        subprocess.run(
            [sys.executable, str(broker_script), "emit",
             "--payload", result_msg, "--source", "stuck-session-detector"],
            capture_output=True, text=True, timeout=15,
            cwd=str(WORKSPACE),
        )
    
    return result


def main() -> None:
    global LOOKBACK_MINUTES, STUCK_THRESHOLD_S
    parser = argparse.ArgumentParser(description="卡住会话检测器 + 自动恢复")
    parser.add_argument("--print-json", action="store_true", help="输出 JSON 到 stdout")
    parser.add_argument("--report", action="store_true", help="通过 broker 向前台报告")
    parser.add_argument("--recover", action="store_true", default=True,
                        help="启用自动恢复（默认启用）")
    parser.add_argument("--no-recover", action="store_false", dest="recover",
                        help="禁用自动恢复")
    parser.add_argument("--lookback-minutes", type=int, default=LOOKBACK_MINUTES)
    parser.add_argument("--stuck-threshold", type=int, default=STUCK_THRESHOLD_S)
    parser.add_argument("--gateway-log-path", help="可选：显式指定网关日志文件路径")
    args = parser.parse_args()

    LOOKBACK_MINUTES = args.lookback_minutes
    STUCK_THRESHOLD_S = args.stuck_threshold
    if args.gateway_log_path:
        os.environ["OPENCLAW_GATEWAY_LOG_PATH"] = args.gateway_log_path

    entries = get_recent_long_running_entries()
    report = analyze_stuck_sessions(entries)

    # ── 自动恢复 ──
    recovery_result = None
    if args.recover and not report.get("ok"):
        rstate = load_recovery_state()
        do_restart, reason = should_restart(report, rstate)
        if do_restart:
            recovery_result = trigger_gateway_restart(report, rstate, reason)
            report["recovery"] = recovery_result
    
    save_status(report)

    if args.report:
        emit_to_broker(report)

    if args.print_json:
        print(json.dumps(report, ensure_ascii=False, indent=2))

    # 日志记录
    stuck_sessions = report.get("sessions", [])
    if stuck_sessions:
        log_line(f"STUCK: {len(stuck_sessions)} sessions"
                 + (", MAIN BLOCKED" if report.get("blockedMain") else "")
                 + (f", auto-restarted" if recovery_result and recovery_result.get("ok") else ""))


if __name__ == "__main__":
    main()
