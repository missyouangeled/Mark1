#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
cognition-distill-prep.py — COGNITION.md 每日提炼「取料脚本」

用途：
    给 cron 每日提炼任务(cognition-daily-distill)准备原料。
    本脚本只负责「取料 + 判断该不该提炼」，真正的认知提炼由 AI 在 agentTurn 里完成。
    脚本输出会作为上下文喂给 AI，AI 读完当天对话后决定往 COGNITION.md 写什么。

设计原则（点点 2026-07-29 定）：
    1. 写得足够详细，以后换任何模型都能照着跑，不依赖 AI「记得」这套机制
    2. 所有自动行为必须有据可查——每次提炼在 COGNITION.md 精炼记录表留痕
    3. 没内容就跳过，不硬写（当天没有实质对话就不提炼）

调用方式：
    python3 scripts/cognition/cognition-distill-prep.py            # 提炼今天
    python3 scripts/cognition/cognition-distill-prep.py 2026-07-28  # 提炼指定日期

输出：
    stdout 打印 JSON，包含：
      - should_distill: 是否值得提炼(bool)
      - reason: 判断理由
      - date: 目标日期
      - transcript_path: 当天 transcript 路径
      - transcript_content: 当天对话原文(截断到 40000 字)
      - cognition_path: COGNITION.md 路径
      - last_distill_date: 上次提炼日期(从精炼记录表读)
      - needs_biweekly: 是否到了每两周全面精炼的时间点

维护记录：
    2026-07-29 初版。cron 任务 cognition-daily-distill 每天 20:00 调用。
"""
import sys
import os
import json
import re
from datetime import datetime, timedelta

WORKSPACE = os.path.expanduser("~/.openclaw/workspace")
DAILY_DIR = os.path.join(WORKSPACE, "memory", "daily")
COGNITION = os.path.join(WORKSPACE, "COGNITION.md")
MAX_TRANSCRIPT_CHARS = 40000
BIWEEKLY_DAYS = 14


def get_target_date():
    if len(sys.argv) > 1:
        return sys.argv[1]
    return datetime.now().strftime("%Y-%m-%d")


def find_transcript(date):
    """优先用 transcript 全文，没有就退回 daily 摘要。"""
    candidates = [
        os.path.join(DAILY_DIR, f"{date}-transcript.md"),
        os.path.join(DAILY_DIR, f"{date}.md"),
    ]
    for path in candidates:
        if os.path.exists(path):
            return path
    return None


def read_content(path):
    if not path or not os.path.exists(path):
        return ""
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def is_meaningful(content):
    """判断当天对话是否值得提炼。"""
    if not content:
        return False, "当天没有 transcript 或 daily 文件"
    # 去掉模板占位
    stripped = content.replace("待整理", "").replace("暂无", "")
    # 去掉纯 heartbeat / HEARTBEAT_OK 噪声
    lines = [l for l in stripped.splitlines()
             if l.strip()
             and "heartbeat poll" not in l.lower()
             and "HEARTBEAT_OK" not in l
             and "[OpenClaw heartbeat" not in l]
    body = "\n".join(lines)
    # 有效正文太短就跳过
    if len(body) < 300:
        return False, f"有效对话内容过短({len(body)}字)，不值得提炼"
    return True, f"有效对话 {len(body)} 字，值得提炼"


def get_last_distill_date(cognition_content):
    """从精炼记录表读最后一次提炼日期。"""
    dates = re.findall(r"\|\s*(\d{4}-\d{2}-\d{2})\s*\|", cognition_content)
    if not dates:
        return None
    return sorted(dates)[-1]


def needs_biweekly(last_date, target_date):
    """距上次提炼是否已满 14 天，需要全面精炼。"""
    if not last_date:
        return True
    try:
        d1 = datetime.strptime(last_date, "%Y-%m-%d")
        d2 = datetime.strptime(target_date, "%Y-%m-%d")
        return (d2 - d1).days >= BIWEEKLY_DAYS
    except ValueError:
        return False


def main():
    date = get_target_date()
    transcript_path = find_transcript(date)
    transcript_content = read_content(transcript_path)
    should, reason = is_meaningful(transcript_content)

    cognition_content = read_content(COGNITION)
    last_distill = get_last_distill_date(cognition_content)

    # 检查目标日期是否已经提炼过(幂等，避免重复)
    already_done = date in cognition_content and last_distill == date

    truncated = transcript_content[:MAX_TRANSCRIPT_CHARS]
    if len(transcript_content) > MAX_TRANSCRIPT_CHARS:
        truncated += "\n\n...[原文过长已截断]..."

    result = {
        "date": date,
        "should_distill": should and not already_done,
        "reason": ("今日已提炼过，跳过" if already_done else reason),
        "already_done": already_done,
        "transcript_path": transcript_path or "(无)",
        "transcript_content": truncated,
        "cognition_path": COGNITION,
        "last_distill_date": last_distill,
        "needs_biweekly": needs_biweekly(last_distill, date),
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
