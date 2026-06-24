"""Mark42 模块：Session Fence 安全写入工具集。

背景：
OpenClaw 用 sessionFileFenceKey + fenceGeneration + fingerprint 机制
保护 active session 文件不被外部进程篡改。直接 `open(jsonl, "a")` 写入
会触发 `EmbeddedAttemptSessionTakeoverError`，导致 embedded agent 接管失败。

外部进程（Python armor）的合法写入渠道：
1. 不写 - 让 OpenClaw 自己 preflightCompaction 自动处理
2. `openclaw agent --message <cmd>` CLI 通道（推荐）
3. `openclaw system event --text <msg>` 系统事件（适合提醒类）
4. 写入独立的 shadow 文件（如 armor-state/, .mark42/），不碰 session

绝对禁止：
- `open(active_session, "a")` 直接 append
- 绕过 lock file 写文件
- 删除 fence key metadata

详见 docs/design/mark42-更新日志-20260624.md (13:49 故障 → 修复)
"""

import json
import subprocess
from pathlib import Path
from typing import Any

from .utils import _find_active_session, _now_iso


def is_safe_to_write_session() -> bool:
    """检查 armor 是否可以安全写入 active session。
    
    返回 False（永远不应该写）：
    - 直接写入 session 文件总是被禁止的，因为 fence 协议不信任外部进程
    """
    return False


def trigger_compact_via_cli(
    session_key: str = "agent:main:main",
    timeout_seconds: int = 120,
    cli_timeout: int = 180,
) -> dict[str, Any]:
    """通过 OpenClaw CLI 合法通道触发 /compact。
    
    Args:
        session_key: 目标 session 键，默认主会话
        timeout_seconds: agent turn 超时（秒）
        cli_timeout: subprocess 超时（秒）
    
    Returns:
        {
            "triggered": bool,
            "returncode": int,
            "stdout": str,
            "stderr": str,
            "method": "openclaw-cli",
            "sessionKey": str,
            "ts": str,
        }
    """
    result: dict[str, Any] = {
        "triggered": False,
        "method": "openclaw-cli",
        "sessionKey": session_key,
        "ts": _now_iso(),
    }
    
    # 先校验：active session 是否存在
    active = _find_active_session()
    if not active:
        result["error"] = "no-active-session"
        result["stderr"] = "未找到活跃会话"
        return result
    
    result["activeSession"] = str(active)
    
    try:
        proc = subprocess.run(
            [
                "openclaw", "agent",
                "--message", "/compact",
                "--session-key", session_key,
                "--timeout", str(timeout_seconds),
                "--json",
            ],
            capture_output=True,
            text=True,
            timeout=cli_timeout,
        )
        result["returncode"] = proc.returncode
        result["stdout"] = proc.stdout[:1000]
        result["stderr"] = proc.stderr[:1000]
        result["triggered"] = (proc.returncode == 0)
    except subprocess.TimeoutExpired:
        result["error"] = "cli-timeout"
        result["stderr"] = f"openclaw agent 调用超时 ({cli_timeout}s)"
    except FileNotFoundError:
        result["error"] = "openclaw-not-found"
        result["stderr"] = "openclaw 命令未找到，PATH 是否正确?"
    except Exception as e:
        result["error"] = str(e)
        result["stderr"] = f"未知错误: {e}"
    
    return result


def write_shadow_note(note_path: Path, payload: dict[str, Any]) -> bool:
    """写入"影子笔记"到 armor state，不触碰 active session。
    
    适用场景：
    - 压缩算法生成的记忆索引（供 OpenClaw 下次压缩时引用）
    - 健康监测快照
    - 调试日志
    
    Args:
        note_path: 影子文件路径（建议在 armor_state/ 或 .mark42/ 下）
        payload: 要写入的内容
    
    Returns:
        True if successful
    """
    try:
        note_path.parent.mkdir(parents=True, exist_ok=True)
        with open(note_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        print(f"[session_fence_safe] 影子笔记写入失败: {e}")
        return False


def append_shadow_log(log_path: Path, entry: dict[str, Any]) -> bool:
    """追加一行到影子日志（.jsonl），不触碰 active session。"""
    try:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        return True
    except Exception as e:
        print(f"[session_fence_safe] 影子日志追加失败: {e}")
        return False


# ── 自检：模块导入时跑一次 fence 协议健康检查 ──

def fence_self_check() -> dict[str, Any]:
    """运行 fence 协议自检，返回状态。
    
    检查项：
    1. is_safe_to_write_session() == False（永远为 False 是正确的）
    2. _find_active_session() 能找到当前 active session
    3. openclaw CLI 可执行
    """
    check = {
        "ts": _now_iso(),
        "isSafeToWriteSession": is_safe_to_write_session(),
        "activeSessionFound": False,
        "openclawAvailable": False,
    }
    
    active = _find_active_session()
    if active:
        check["activeSessionFound"] = True
        check["activeSession"] = str(active)
    
    try:
        proc = subprocess.run(
            ["openclaw", "--version"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if proc.returncode == 0:
            check["openclawAvailable"] = True
            check["openclawVersion"] = proc.stdout.strip()
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    
    check["healthy"] = (
        not check["isSafeToWriteSession"]  # 必须为 False
        and check["activeSessionFound"]
        and check["openclawAvailable"]
    )
    
    return check