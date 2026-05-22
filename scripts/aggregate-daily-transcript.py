#!/usr/bin/env python3
"""
统一日报采集脚本
读取所有模型今天的会话记录，汇集成一份统一日报。
不依赖任何模型行为，纯系统层兜底。

用法:
  python3 scripts/aggregate-daily-transcript.py              # 采集今天
  python3 scripts/aggregate-daily-transcript.py --date 2026-05-21  # 采集指定日期
  python3 scripts/aggregate-daily-transcript.py --print       # 采集并打印到 stdout
  python3 scripts/aggregate-daily-transcript.py --dry-run     # 只看不写
"""

import json
import os
import sys
import argparse
from datetime import datetime, timezone, timedelta
from pathlib import Path
from collections import OrderedDict

# --- 配置 ---
WORKSPACE = Path(__file__).resolve().parent.parent
SESSIONS_JSON = Path.home() / ".openclaw" / "agents" / "main" / "sessions" / "sessions.json"
SESSIONS_DIR = Path.home() / ".openclaw" / "agents" / "main" / "sessions"
OUTPUT_DIR = WORKSPACE / "memory" / "daily"
SHANGHAI_TZ = timezone(timedelta(hours=8))

# 只采集这些 kind 的会话（排除 cron、subagent 内部工作）
INCLUDE_KINDS = {"direct"}


def load_sessions_index():
    """加载 sessions.json，返回 {sessionKey: metadata}"""
    if not SESSIONS_JSON.exists():
        print(f"[aggregate] sessions.json 不存在: {SESSIONS_JSON}", file=sys.stderr)
        return {}
    with open(SESSIONS_JSON) as f:
        return json.load(f)


def find_today_sessions(sessions: dict, target_date: str):
    """
    从 sessions 索引中找出 target_date 当天活跃的 direct dashboard 会话。
    target_date: 'YYYY-MM-DD'
    返回 [(sessionKey, sessionFile, model)] 按时间排序
    """
    day_start = datetime.fromisoformat(target_date).replace(tzinfo=SHANGHAI_TZ)
    day_end = day_start + timedelta(days=1)
    day_start_ms = int(day_start.timestamp() * 1000)
    day_end_ms = int(day_end.timestamp() * 1000)

    candidates = []
    for key, meta in sessions.items():
        # 过滤 kind
        kind = meta.get("kind", "direct")
        if kind not in INCLUDE_KINDS:
            continue
        # 过滤 dashboard 会话
        if "dashboard" not in key and key != "agent:main:main":
            continue

        updated = meta.get("updatedAt", 0)
        started = meta.get("sessionStartedAt", 0)
        last_interact = meta.get("lastInteractionAt", 0)

        # 在这个日期范围内有任何活动
        in_range = (
            (day_start_ms <= updated < day_end_ms)
            or (day_start_ms <= started < day_end_ms)
            or (day_start_ms <= last_interact < day_end_ms)
        )
        if not in_range:
            continue

        session_file = meta.get("sessionFile", "")
        if not session_file:
            session_file = SESSIONS_DIR / f"{meta.get('sessionId', '')}.jsonl"

        # 提取模型名（可能有 provider 前缀）
        model = meta.get("model", "unknown")
        candidates.append((updated, key, str(session_file), model))

    # 按更新时间排序
    candidates.sort(key=lambda x: x[0])
    return [(key, sf, model) for _, key, sf, model in candidates]


def extract_text_from_content(content):
    """从消息 content 中提取纯文本（跳过 thinking 块）"""
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        texts = []
        for block in content:
            if isinstance(block, dict):
                if block.get("type") == "text":
                    texts.append(block.get("text", ""))
                # 跳过 thinking 块
            elif isinstance(block, str):
                texts.append(block)
        return " ".join(texts).strip()
    return str(content).strip()


def parse_session_jsonl(session_file: str, target_date: str):
    """
    解析单个 session 的 JSONL，提取 target_date 当天的 user/assistant 消息。
    返回 [(timestamp, role, model, text)] 列表。
    """
    day_start = datetime.fromisoformat(target_date).replace(tzinfo=SHANGHAI_TZ)
    day_end = day_start + timedelta(days=1)

    filepath = Path(session_file)
    if not filepath.exists():
        return []

    messages = []
    seen_ids = set()

    try:
        with open(filepath) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    continue

                if obj.get("type") != "message":
                    continue

                msg = obj.get("message", {})
                role = msg.get("role", "")
                if role not in ("user", "assistant"):
                    continue

                # 解析时间戳
                ts = obj.get("timestamp", "")
                if not ts:
                    continue
                try:
                    dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                except ValueError:
                    continue

                # 过滤日期范围
                if dt < day_start or dt >= day_end:
                    continue

                # 去重
                msg_id = obj.get("id", "")
                if msg_id and msg_id in seen_ids:
                    continue
                if msg_id:
                    seen_ids.add(msg_id)

                # 提取文本
                content = msg.get("content", "")
                text = extract_text_from_content(content)
                if not text:
                    continue

                # 跳过系统指令类的用户消息（太长的 prompt 模板）
                if role == "user" and len(text) > 2000:
                    text = text[:200] + "…[系统指令已省略]"

                # 记录该消息使用的模型
                model = msg.get("model", "") or obj.get("modelId", "")

                shanghai_time = dt.astimezone(SHANGHAI_TZ)
                messages.append((shanghai_time, role, model, text))

    except Exception as e:
        print(f"[aggregate] 解析 {session_file} 出错: {e}", file=sys.stderr)

    return messages


def build_transcript_md(messages_by_session: list, target_date: str):
    """
    构建 markdown 格式的统一日报。
    messages_by_session: [(session_key, model, [(ts, role, model, text)])]
    """
    lines = [f"# {target_date} 统一日报（自动采集）", ""]

    if not messages_by_session:
        lines.append("_今日暂无对话记录_")
        return "\n".join(lines)

    # 按 session 分组输出
    for session_key, session_model, msgs in messages_by_session:
        if not msgs:
            continue
        model_display = session_model or "unknown"
        lines.append(f"## {model_display}")

        for ts, role, model, text in msgs:
            time_str = ts.strftime("%H:%M")
            if role == "user":
                lines.append(f"- **点点** · {time_str}：{text}")
            else:
                # 限制助手回复长度，避免过长
                display_text = text
                if len(display_text) > 500:
                    display_text = display_text[:500] + "…"
                lines.append(f"- 贾维斯 · {time_str}：{display_text}")

        lines.append("")

    return "\n".join(lines)


def aggregate(target_date: str, dry_run: bool = False, print_only: bool = False):
    """主入口"""
    sessions = load_sessions_index()
    if not sessions:
        print("[aggregate] 无会话数据", file=sys.stderr)
        return 0

    today_sessions = find_today_sessions(sessions, target_date)
    print(f"[aggregate] {target_date} 找到 {len(today_sessions)} 个相关会话", file=sys.stderr)

    # 按 session 采集消息
    messages_by_session = []
    total_messages = 0
    for session_key, session_file, model in today_sessions:
        msgs = parse_session_jsonl(session_file, target_date)
        if msgs:
            messages_by_session.append((session_key, model, msgs))
            total_messages += len(msgs)
            print(f"[aggregate]   {session_key}: {len(msgs)} 条消息 (模型={model})", file=sys.stderr)

    print(f"[aggregate] 总计 {total_messages} 条消息，{len(messages_by_session)} 个会话", file=sys.stderr)

    # 构建 markdown
    md = build_transcript_md(messages_by_session, target_date)

    if print_only or dry_run:
        print(md)
        if dry_run:
            print("\n--- [dry-run] 未写入文件 ---", file=sys.stderr)
        return 0

    # 写入文件
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output_path = OUTPUT_DIR / f"{target_date}-transcript.md"
    with open(output_path, "w") as f:
        f.write(md)
    print(f"[aggregate] 已写入: {output_path} ({len(md)} 字符)", file=sys.stderr)

    return 0


def main():
    parser = argparse.ArgumentParser(description="统一日报采集脚本")
    parser.add_argument("--date", default=None, help="目标日期 YYYY-MM-DD（默认今天）")
    parser.add_argument("--dry-run", action="store_true", help="只看不写文件")
    parser.add_argument("--print", dest="print_only", action="store_true", help="输出到 stdout")
    args = parser.parse_args()

    if args.date:
        target_date = args.date
    else:
        target_date = datetime.now(SHANGHAI_TZ).strftime("%Y-%m-%d")

    return aggregate(target_date, dry_run=args.dry_run, print_only=args.print_only)


if __name__ == "__main__":
    sys.exit(main())
