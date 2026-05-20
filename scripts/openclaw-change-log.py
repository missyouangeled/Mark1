#!/usr/bin/env python3
from __future__ import annotations

import argparse
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Iterable

WORKSPACE = Path.home() / ".openclaw" / "workspace"
DEFAULT_LOG_PATH = WORKSPACE / "docs" / "通用-OpenClaw-补丁变更流水.md"
DEFAULT_MEMO_PATH = WORKSPACE / "docs" / "通用-OpenClaw-非正式修改备忘录.md"


def now_local_label() -> str:
    now = datetime.now().astimezone()
    tz = now.strftime("%z")
    tz_label = f"{tz[:3]}:{tz[3:]}" if len(tz) == 5 else tz
    return f"{now.strftime('%Y-%m-%d %H:%M:%S')} {now.tzname() or ''} ({tz_label})".strip()


def run_git(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=WORKSPACE,
        capture_output=True,
        text=True,
        check=False,
    )


def collect_files_from_git(mode: str) -> list[str]:
    if mode == "staged":
        result = run_git(["diff", "--cached", "--name-only", "--diff-filter=ACMR"])
        if result.returncode != 0:
            raise RuntimeError(result.stderr.strip() or "git diff --cached 失败")
        files = [line.strip() for line in result.stdout.splitlines() if line.strip()]
        return sorted(dict.fromkeys(files))

    if mode == "worktree":
        result = run_git(["status", "--short", "--untracked-files=all"])
        if result.returncode != 0:
            raise RuntimeError(result.stderr.strip() or "git status 失败")
        files: list[str] = []
        for raw in result.stdout.splitlines():
            line = raw.rstrip()
            if not line:
                continue
            if len(line) >= 4 and line[:2] in {" M", "M ", "MM", "A ", "AM", "??", "RM", "R ", " D", "D "}:
                path_part = line[3:]
            else:
                path_part = line.strip()
            if " -> " in path_part:
                path_part = path_part.split(" -> ", 1)[1]
            path_part = path_part.strip().strip('"')
            if path_part:
                files.append(path_part)
        return sorted(dict.fromkeys(files))

    raise ValueError(f"unsupported git mode: {mode}")


def ensure_log_header(path: Path) -> None:
    if path.exists():
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "# OpenClaw 补丁变更流水\n\n"
        "- 适用机器：通用\n"
        "- 系统 / OS：通用\n"
        "- 文档类型：按时间追加的修改 / 补丁 / 功能变更流水\n\n"
        "## 用途\n\n"
        "这份文档记录**每次实际改了什么**，重点回答：\n\n"
        "- 这次改动发生在什么时候\n"
        "- 改的是功能、补丁、修复还是维护流程\n"
        "- 影响范围是什么\n"
        "- 改了哪些文件\n"
        "- 是否已经同步到补丁注册表 / 重建清单 / 自检清单\n\n"
        "它和其它文档的关系：\n\n"
        "- `docs/通用-OpenClaw-补丁注册表.md`：记录**正式补丁清单**\n"
        "- `docs/通用-OpenClaw-补丁重建清单.md`：记录**升级后怎么重建**\n"
        "- `docs/通用-OpenClaw-升级后自检清单.md`：记录**升级后怎么快速验**\n"
        "- `docs/通用-OpenClaw-非正式修改备忘录.md`：记录**未进入正式补丁体系的临时/手工/外部修改**\n"
        "- **本文件**：记录**这次具体动了什么**\n\n"
        "## 记录规则\n\n"
        "1. 只要发生了实际修改、修补、接链路、打补丁、改脚本、改配置、改文档，就应追加一条流水。\n"
        "2. 若本次改动已经达到“正式补丁”标准，还要同步更新注册表 / 重建清单 / 必要时更新自检清单。\n"
        "3. 若只是一次性排查、临时试验、未形成稳定入口，可只记流水，不强行登记为正式补丁；若它对后续排查仍重要，再补进 `docs/通用-OpenClaw-非正式修改备忘录.md`。\n\n"
        "---\n\n",
        encoding="utf-8",
    )


def ensure_memo_header(path: Path) -> None:
    if path.exists():
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "# OpenClaw 非正式修改备忘录\n\n"
        "- 适用机器：通用\n"
        "- 系统 / OS：通用\n"
        "- 文档类型：未进入正式补丁体系的临时修复 / 手工改动 / 外部修改备忘录\n\n"
        "## 用途\n\n"
        "这份备忘录记录那些**对后续排查很重要，但暂时还不适合直接登记为正式补丁**的内容，例如：\n\n"
        "- 一次性手工修复\n"
        "- 只在外部插件 / 外部环境里发生过的修改\n"
        "- 当前故意不做成默认自动触发的维护动作\n"
        "- 尚未收敛成稳定实现入口的实验性改动\n\n"
        "它和正式补丁体系的区别：\n\n"
        "- 正式补丁 → 进 `补丁注册表 / 重建清单 / 必要时的自检清单`\n"
        "- 非正式修改 → 先进这份备忘录，后续若收敛成熟，再升级为正式补丁\n\n"
        "## 记录规则\n\n"
        "1. 只有当一条修改对后续排查/恢复仍有价值，但又还不适合登记为正式补丁时，才写这里。\n"
        "2. 写入时要明确：当前状态、为何未纳入正式补丁、以及后续若再出问题应先看哪里。\n"
        "3. 若后来它已经具备稳定入口、最小验收、可重复恢复方案，应把它升级进正式补丁体系。\n\n"
        "---\n\n",
        encoding="utf-8",
    )


def normalize_lines(values: Iterable[str] | None) -> list[str]:
    lines: list[str] = []
    for value in values or []:
        if value is None:
            continue
        text = str(value).strip()
        if text:
            lines.append(text)
    return lines


def render_bullets(lines: list[str], fallback: str = "- 无") -> str:
    if not lines:
        return fallback
    return "\n".join(f"- {line}" for line in lines)


def render_entry(args: argparse.Namespace, files: list[str]) -> str:
    summary_lines = normalize_lines(args.summary)
    verify_lines = normalize_lines(args.verify)
    note_lines = normalize_lines(args.note)
    file_block = render_bullets([f"`{file}`" for file in files], fallback="- [未记录文件]")

    lines = [
        f"## {now_local_label()} — {args.title}",
        "",
        f"- 类型：{args.kind}",
        f"- 适用范围：{args.scope}",
        f"- 补丁注册表：{args.registry_status}",
        f"- 重建清单：{args.rebuild_status}",
        f"- 升级后自检清单：{args.selfcheck_status}",
        "- 结果摘要：",
        render_bullets(summary_lines, fallback="- [待补充摘要]"),
        "- 验收 / 验证：",
        render_bullets(verify_lines, fallback="- [未记录验收]"),
    ]

    if note_lines:
        lines.extend([
            "- 备注：",
            render_bullets(note_lines),
        ])

    lines.extend([
        "- 相关文件：",
        file_block,
        "",
    ])
    return "\n".join(lines)


def render_memo_entry(args: argparse.Namespace, files: list[str]) -> str:
    reason_lines = normalize_lines(args.reason)
    recovery_lines = normalize_lines(args.recovery)
    note_lines = normalize_lines(args.note)
    file_block = render_bullets([f"`{file}`" for file in files], fallback="- [未记录文件]")

    lines = [
        f"## {now_local_label()} — {args.title}",
        "",
        f"- 类型：{args.kind}",
        f"- 适用范围：{args.scope}",
        f"- 当前状态：{args.current_status}",
        "- 未纳入正式补丁原因：",
        render_bullets(reason_lines, fallback="- [待补充原因]"),
        "- 后续排查 / 恢复提示：",
        render_bullets(recovery_lines, fallback="- [待补充恢复提示]"),
    ]

    if note_lines:
        lines.extend([
            "- 备注：",
            render_bullets(note_lines),
        ])

    lines.extend([
        "- 相关文件：",
        file_block,
        "",
    ])
    return "\n".join(lines)


def append_entry(path: Path, entry: str, *, header_kind: str = "log") -> None:
    if header_kind == "log":
        ensure_log_header(path)
    elif header_kind == "memo":
        ensure_memo_header(path)
    else:
        raise ValueError(f"unsupported header kind: {header_kind}")

    existing = path.read_text(encoding="utf-8")
    with path.open("a", encoding="utf-8") as fh:
        if existing and not existing.endswith("\n\n"):
            fh.write("\n")
        if not entry.endswith("\n"):
            entry += "\n"
        fh.write(entry)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="为 OpenClaw 修改任务追加变更流水或非正式修改备忘录。")
    sub = parser.add_subparsers(dest="command", required=True)

    capture = sub.add_parser("capture", help="追加一条变更流水")
    capture.add_argument("--title", required=True, help="本次变更标题")
    capture.add_argument("--kind", default="patch", help="变更类型，例如 patch / fix / feature / maintenance / process")
    capture.add_argument("--scope", default="通用", help="适用范围，例如 通用 / 公司（Linux） / 掌机（Windows）")
    capture.add_argument("--summary", action="append", help="结果摘要，可重复传入")
    capture.add_argument("--verify", action="append", help="验收或验证结果，可重复传入")
    capture.add_argument("--note", action="append", help="备注，可重复传入")
    capture.add_argument("--registry-status", default="未更新", help="补丁注册表状态：已更新 / 未更新 / 不适用")
    capture.add_argument("--rebuild-status", default="未更新", help="重建清单状态：已更新 / 未更新 / 不适用")
    capture.add_argument("--selfcheck-status", default="未更新", help="自检清单状态：已更新 / 未更新 / 不适用")
    capture.add_argument("--file", action="append", help="相关文件，可重复传入")
    capture.add_argument("--git-files", choices=["worktree", "staged"], help="从 git 自动收集文件")
    capture.add_argument("--log-path", default=str(DEFAULT_LOG_PATH), help="变更流水文档路径")
    capture.add_argument("--dry-run", action="store_true", help="只打印，不落盘")

    memo = sub.add_parser("memo", help="追加一条非正式修改备忘录")
    memo.add_argument("--title", required=True, help="本次备忘录标题")
    memo.add_argument("--kind", default="manual-fix", help="类型，例如 manual-fix / temp-workaround / external-change / maintenance-note")
    memo.add_argument("--scope", default="通用", help="适用范围，例如 通用 / 公司（Linux） / 掌机（Windows）")
    memo.add_argument("--current-status", default="备查", help="当前状态，例如 备查 / 已在用 / 已停用 / 仅历史记录")
    memo.add_argument("--reason", action="append", help="为何未纳入正式补丁，可重复传入")
    memo.add_argument("--recovery", action="append", help="后续排查/恢复提示，可重复传入")
    memo.add_argument("--note", action="append", help="备注，可重复传入")
    memo.add_argument("--file", action="append", help="相关文件，可重复传入")
    memo.add_argument("--git-files", choices=["worktree", "staged"], help="从 git 自动收集文件")
    memo.add_argument("--memo-path", default=str(DEFAULT_MEMO_PATH), help="非正式修改备忘录路径")
    memo.add_argument("--dry-run", action="store_true", help="只打印，不落盘")

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    files = normalize_lines(args.file)
    if getattr(args, "git_files", None):
        files.extend(collect_files_from_git(args.git_files))
    files = sorted(dict.fromkeys(files))

    if args.command == "capture":
        entry = render_entry(args, files)
        if args.dry_run:
            print(entry)
            return 0
        log_path = Path(args.log_path)
        append_entry(log_path, entry, header_kind="log")
        print(f"已写入变更流水：{log_path}")
        return 0

    if args.command == "memo":
        entry = render_memo_entry(args, files)
        if args.dry_run:
            print(entry)
            return 0
        memo_path = Path(args.memo_path)
        append_entry(memo_path, entry, header_kind="memo")
        print(f"已写入非正式修改备忘录：{memo_path}")
        return 0

    parser.error("unsupported command")
    return 2


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # pragma: no cover
        print(f"openclaw-change-log 失败：{exc}", file=sys.stderr)
        raise SystemExit(1)
