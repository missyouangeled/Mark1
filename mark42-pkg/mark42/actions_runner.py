"""Mark42 Phase 2：确认后执行 / dry-run 动作入口。

设计原则：
  - 仅做"半自动"骨架；不替用户做主决策
  - 默认 --dry-run；必须 --yes 才真执行
  - 所有动作执行都写 broker 留痕
  - 仅暴露当前阶段白名单内的 action id，未在白名单内的拒绝执行

使用入口：
  - mark42.py actions --list
  - mark42.py actions --run <action-id> --agent <name> --dry-run
  - mark42.py actions --run <action-id> --agent <name> --yes

白名单动作：
  - restart-assemble                  ✅ 已支持
  - rebalance-default-agent           🔒 当前阶段仅 dry-run，跳过执行
  - rebalance-heavy-tasks             🔒 当前阶段仅 dry-run，跳过执行
"""

from __future__ import annotations

import argparse
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from .log_setup import get_logger

logger = get_logger(__name__)


# ─────────────────────── 动作白名单 ───────────────────────

# 当前阶段支持真正执行的 action id 集合
EXECUTABLE_WHITELIST = {"restart-assemble"}
EXECUTABLE_WHITELIST.add("refresh-actions")

# 仅支持 dry-run 预览的 action id 集合
DRY_RUN_ONLY = {
    "rebalance-default-agent",
    "rebalance-heavy-tasks",
}


@dataclass
class ActionResult:
    """单个动作执行/预览的结果。"""

    actionId: str
    executed: bool
    level: str  # "info" | "warning" | "error"
    summary: str
    commandPreview: str = ""
    agent: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


# ─────────────────────── 路径 & broker 桥接 ───────────────────────


def actions_queue_path() -> Path:
    """最近一次 status 生成的 suggestedActions 桥接文件路径。"""
    from .config import MARK42_STATE

    return MARK42_STATE / "actions-pending.json"


def _read_pending_actions() -> list[dict[str, Any]]:
    """读取最近一次 status 写入的 suggestedActions 桥接列表。

    容错：文件缺失/格式错误时返回空列表。
    """
    path = actions_queue_path()
    if not path.exists():
        return []
    try:
        import json

        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return []
    if isinstance(data, list):
        return [item for item in data if isinstance(item, dict)]
    return []


def _write_pending_actions(actions: list[dict[str, Any]]) -> None:
    """写入当前 suggestedActions 桥接。"""
    import json

    path = actions_queue_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(actions, f, indent=2, ensure_ascii=False)


def _append_broker_event(
    action_id: str, executed: bool, agent: str | None, summary: str, command_preview: str = ""
) -> None:
    """写一条 broker 事件，记录动作执行/预览结果。"""
    try:
        from .utils import _append_broker
    except ImportError:
        return
    _append_broker(
        "actions-runner",
        "actions.executed" if executed else "actions.previewed",
        f"action {action_id}",
        "info",
        summary,
        {
            "actionId": action_id,
            "executed": executed,
            "agent": agent,
            "commandPreview": command_preview,
        },
    )


# ─────────────────────── 动作执行器 ───────────────────────


class _ActionNotFoundError(Exception):
    pass


class _ActionRefusedError(Exception):
    pass


def list_actions() -> list[dict[str, Any]]:
    """列出当前可操作的 action 列表（仅 dry-run 视图）。"""
    pending = _read_pending_actions()
    out: list[dict[str, Any]] = []
    for item in pending:
        action_id = item.get("id") or item.get("actionId")
        if not action_id:
            continue
        executable = action_id in EXECUTABLE_WHITELIST
        out.append(
            {
                "actionId": action_id,
                "title": item.get("title", ""),
                "reason": item.get("reason", ""),
                "commandPreview": item.get("commandPreview", ""),
                "priority": item.get("priority", "low"),
                "executableNow": executable,
                "dryRunOnly": not executable,
                "agent": item.get("sourceAgent") or item.get("targetAgent"),
            }
        )
    return out


def _build_handlers() -> dict[str, Callable[..., ActionResult]]:
    """按 action id 返回对应的执行函数。"""

    def handle_restart_assemble(dry_run: bool, agent: str | None) -> ActionResult:
        from .cli import assemble_restart  # 延迟导入，避免循环

        target = agent or "main"
        preview = f"mark42.py assemble (agent={target})"
        if dry_run:
            return ActionResult(
                actionId="restart-assemble",
                executed=False,
                level="info",
                summary=f"DRY-RUN: 将重启 assemble (agent={target})",
                commandPreview=preview,
                agent=target,
            )
        result = assemble_restart(agent=target)
        return ActionResult(
            actionId="restart-assemble",
            executed=True,
            level="info",
            summary=f"已重启 assemble: pid={result.get('pid')}",
            commandPreview=preview,
            agent=target,
            metadata={"pid": result.get("pid"), "log": result.get("log")},
        )

    def handle_refresh_actions(dry_run: bool, agent: str | None) -> ActionResult:
        from .cli import status_dashboard  # 延迟导入，避免循环

        preview = "mark42.py status --all-agents --json"
        if dry_run:
            return ActionResult(
                actionId="refresh-actions",
                executed=False,
                level="info",
                summary="DRY-RUN: 将刷新 suggestedActions / actions-pending 队列",
                commandPreview=preview,
                agent=agent,
            )

        aggregate = status_dashboard(json_mode=True, all_agents=True)
        action_count = len((aggregate or {}).get("suggestedActions", []))
        return ActionResult(
            actionId="refresh-actions",
            executed=True,
            level="info",
            summary=f"已刷新建议队列: {action_count} 条动作",
            commandPreview=preview,
            agent=agent,
            metadata={"actionCount": action_count},
        )

    return {
        "restart-assemble": handle_restart_assemble,
        "refresh-actions": handle_refresh_actions,
    }


def execute_action(action_id: str, agent: str | None = None, dry_run: bool = True) -> ActionResult:
    """执行/预览单个动作。

    参数：
      - action_id: 动作 ID
      - agent: 目标 agent（默认 None，由动作自行决定）
      - dry_run: True 仅预览；False 才真执行（调用方应已确认）
    """
    handlers = _build_handlers()
    if action_id not in handlers:
        # 区分两种情况：
        # - 存在于 dry-run-only 集合 → 静默拒绝并返回 dry-run 视图
        # - 完全未识别 → 抛错
        if action_id in DRY_RUN_ONLY:
            preview = self_preview_for(action_id, agent)
            if not dry_run:
                # 即便用户加了 --yes，本阶段也只做 dry-run，不静默执行
                result = ActionResult(
                    actionId=action_id,
                    executed=False,
                    level="warning",
                    summary="当前阶段仅支持 dry-run 预览",
                    commandPreview=preview,
                    agent=agent,
                    metadata={"refusedBySafetyPolicy": True},
                )
                _append_broker_event(action_id, False, agent, result.summary, preview)
                return result
            result = ActionResult(
                actionId=action_id,
                executed=False,
                level="info",
                summary=f"DRY-RUN: {preview}",
                commandPreview=preview,
                agent=agent,
            )
            _append_broker_event(action_id, False, agent, result.summary, preview)
            return result
        raise _ActionNotFoundError(f"未知动作: {action_id}")

    handler = handlers[action_id]
    result = handler(dry_run=dry_run, agent=agent)
    _append_broker_event(
        action_id,
        result.executed,
        result.agent,
        result.summary,
        result.commandPreview,
    )
    return result


def self_preview_for(action_id: str, agent: str | None) -> str:
    """对未支持的 action 给出命令预览。"""
    target = agent or "main"
    if action_id == "rebalance-default-agent":
        return f"建议把新 loop / heavy 任务优先下发到空闲 agent (当前 agent={target})"
    if action_id == "rebalance-heavy-tasks":
        return f"建议后续 heavy 任务优先分配到其他 agent (当前 agent={target})"
    return ""


# ─────────────────────── CLI 桥接 ───────────────────────


def main(argv: list[str] | None = None) -> int:
    """actions 子命令的入口桥。返回 0 / 1 / 2。"""
    parser = argparse.ArgumentParser(
        prog="mark42 actions",
        description="Mark42 多Agent 协调建议执行入口（Phase 2）",
    )
    parser.add_argument("--list", action="store_true", help="列出当前可操作动作")
    parser.add_argument("--run", type=str, default=None, help="执行/预览指定 action id")
    parser.add_argument("--agent", type=str, default=None, help="目标 agent")
    parser.add_argument("--dry-run", action="store_true", default=True, help="仅预览，不真执行（默认开启）")
    parser.add_argument("--yes", action="store_true", help="明确确认后才会真执行；缺省时 action 不会执行")

    args = parser.parse_args(argv)

    if args.list:
        actions = list_actions()
        import json

        logger.info(json.dumps({"actions": actions}, ensure_ascii=False, indent=2))
        return 0

    if not args.run:
        parser.print_help()
        return 1

    dry_run = not args.yes
    try:
        result = execute_action(args.run, agent=args.agent, dry_run=dry_run)
    except _ActionNotFoundError as exc:
        logger.error(f"❌ {exc}")
        return 2
    except Exception as exc:
        logger.error(f"❌ 执行失败: {exc}")
        return 1

    import json

    logger.info(json.dumps(asdict(result), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
