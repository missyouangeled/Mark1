"""
Mark42 成本追踪模块

记录所有 LLM API 调用的 token 用量和费用。
数据存储到 ~/.local/state/openclaw/mark42/cost/costs.jsonl

定价（2026-07 查询）：
  - doubao-seed-2.0-pro: 输入 ¥0.004/千tokens, 输出 ¥0.012/千tokens
  - glm-5.2: 输入 ¥0.002/千tokens, 输出 ¥0.006/千tokens
  - agnes-2.0-flash: 输入 ¥0.003/千tokens, 输出 ¥0.008/千tokens
"""

from __future__ import annotations

import csv
import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from .config import MARK42_STATE
from .log_setup import get_logger

logger = get_logger(__name__)

# ── 常量 ──

COST_DIR = MARK42_STATE / "cost"
COSTS_FILE = COST_DIR / "costs.jsonl"

# 定价表（元/千tokens）
MODEL_PRICING = {
    "doubao-seed-2.0-pro": {"input": 0.004, "output": 0.012},
    "glm-5.2": {"input": 0.002, "output": 0.006},
    "agnes-2.0-flash": {"input": 0.003, "output": 0.008},
    "agnes-image-2.1-flash": {"input": 0.0, "output": 0.02},  # 按次计费
    "default": {"input": 0.004, "output": 0.012},  # 默认用 doubao 价格
}


@dataclass
class CostRecord:
    """单次 API 调用成本记录。"""

    timestamp: str  # ISO format
    model: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    cost_cny: float
    caller_module: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


class CostTracker:
    """成本追踪器 - 记录和查询 LLM API 调用费用。"""

    def __init__(self, costs_file: Path | None = None):
        self.costs_file = costs_file or COSTS_FILE
        self.costs_file.parent.mkdir(parents=True, exist_ok=True)

    def record(
        self,
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
        caller_module: str = "",
    ) -> CostRecord:
        """记录一次 API 调用的成本。

        Args:
            model: 模型名称
            prompt_tokens: 输入 token 数
            completion_tokens: 输出 token 数
            caller_module: 调用方模块名

        Returns:
            CostRecord 记录
        """
        total = prompt_tokens + completion_tokens
        pricing = MODEL_PRICING.get(model, MODEL_PRICING["default"])
        cost = (
            prompt_tokens / 1000 * pricing["input"]
            + completion_tokens / 1000 * pricing["output"]
        )

        record = CostRecord(
            timestamp=datetime.now(timezone.utc).isoformat(),
            model=model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total,
            cost_cny=round(cost, 6),
            caller_module=caller_module,
        )

        try:
            with open(self.costs_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(record.to_dict(), ensure_ascii=False) + "\n")
        except Exception as e:
            logger.warning("成本记录写入失败: %s", e)

        return record

    def _load_all(self) -> list[dict]:
        """加载所有记录。"""
        if not self.costs_file.exists():
            return []
        records = []
        for line in self.costs_file.read_text().strip().splitlines():
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        return records

    def get_daily_summary(self, date: str | None = None) -> dict:
        """获取某天汇总。

        Args:
            date: YYYY-MM-DD 格式，默认今天

        Returns:
            {date, total_calls, total_tokens, total_cost, by_model}
        """
        if date is None:
            date = datetime.now().strftime("%Y-%m-%d")

        records = self._load_all()
        day_records = [r for r in records if r["timestamp"][:10] == date]

        return self._summarize(day_records, f"日报 {date}")

    def get_monthly_summary(self, year_month: str | None = None) -> dict:
        """获取月度汇总。

        Args:
            year_month: YYYY-MM 格式，默认本月

        Returns:
            {month, total_calls, total_tokens, total_cost, by_model, by_day}
        """
        if year_month is None:
            year_month = datetime.now().strftime("%Y-%m")

        records = self._load_all()
        month_records = [r for r in records if r["timestamp"][:7] == year_month]

        summary = self._summarize(month_records, f"月报 {year_month}")

        # 按天分组
        by_day: dict[str, dict] = {}
        for r in month_records:
            day = r["timestamp"][:10]
            if day not in by_day:
                by_day[day] = {"calls": 0, "tokens": 0, "cost": 0.0}
            by_day[day]["calls"] += 1
            by_day[day]["tokens"] += r["total_tokens"]
            by_day[day]["cost"] += r["cost_cny"]

        summary["by_day"] = by_day
        return summary

    def get_top_callers(self, n: int = 10) -> list[dict]:
        """获取调用最多的模块。"""
        records = self._load_all()
        callers: dict[str, dict] = {}
        for r in records:
            mod = r.get("caller_module") or "unknown"
            if mod not in callers:
                callers[mod] = {"module": mod, "calls": 0, "tokens": 0, "cost": 0.0}
            callers[mod]["calls"] += 1
            callers[mod]["tokens"] += r["total_tokens"]
            callers[mod]["cost"] += r["cost_cny"]

        result = sorted(callers.values(), key=lambda x: x["cost"], reverse=True)
        return result[:n]

    def export_csv(self, start_date: str, end_date: str, output_path: str) -> int:
        """导出 CSV。

        Args:
            start_date: YYYY-MM-DD
            end_date: YYYY-MM-DD
            output_path: 输出文件路径

        Returns:
            导出的记录数
        """
        records = self._load_all()
        filtered = [
            r for r in records
            if start_date <= r["timestamp"][:10] <= end_date
        ]

        with open(output_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=[
                "timestamp", "model", "prompt_tokens",
                "completion_tokens", "total_tokens", "cost_cny", "caller_module"
            ])
            writer.writeheader()
            writer.writerows(filtered)

        return len(filtered)

    def _summarize(self, records: list[dict], label: str) -> dict:
        """汇总记录。"""
        total_calls = len(records)
        total_tokens = sum(r["total_tokens"] for r in records)
        total_cost = sum(r["cost_cny"] for r in records)

        by_model: dict[str, dict] = {}
        for r in records:
            model = r["model"]
            if model not in by_model:
                by_model[model] = {"calls": 0, "tokens": 0, "cost": 0.0}
            by_model[model]["calls"] += 1
            by_model[model]["tokens"] += r["total_tokens"]
            by_model[model]["cost"] += r["cost_cny"]

        return {
            "label": label,
            "total_calls": total_calls,
            "total_tokens": total_tokens,
            "total_cost": round(total_cost, 4),
            "by_model": by_model,
        }


def record_cost(
    model: str,
    prompt_tokens: int,
    completion_tokens: int,
    caller_module: str = "",
) -> CostRecord:
    """便捷函数：记录一次 API 调用成本。"""
    tracker = CostTracker()
    return tracker.record(
        model=model,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        caller_module=caller_module,
    )


# ── CLI 辅助函数 ──


def cli_cost_today() -> dict:
    """CLI: 今日成本汇总。"""
    tracker = CostTracker()
    summary = tracker.get_daily_summary()
    print(f"💰 今日成本 ({summary['label']})")
    print(f"  调用次数: {summary['total_calls']}")
    print(f"  总 tokens: {summary['total_tokens']}")
    print(f"  总费用: ¥{summary['total_cost']:.4f}")
    if summary['by_model']:
        print(f"  按模型:")
        for model, stats in summary['by_model'].items():
            print(f"    {model:<30} {stats['calls']} 次  {stats['tokens']} tokens  ¥{stats['cost']:.4f}")
    return summary


def cli_cost_month() -> dict:
    """CLI: 本月成本汇总。"""
    tracker = CostTracker()
    summary = tracker.get_monthly_summary()
    print(f"💰 本月成本 ({summary['label']})")
    print(f"  调用次数: {summary['total_calls']}")
    print(f"  总 tokens: {summary['total_tokens']}")
    print(f"  总费用: ¥{summary['total_cost']:.4f}")
    if summary.get('by_day'):
        print(f"  按天:")
        for day in sorted(summary['by_day'].keys()):
            d = summary['by_day'][day]
            print(f"    {day}  {d['calls']} 次  ¥{d['cost']:.4f}")
    return summary


def cli_cost_top(n: int = 10, days: int | None = None) -> list[dict]:
    """CLI: 调用最多的模块。"""
    tracker = CostTracker()
    top = tracker.get_top_callers(n=n)
    print(f"💰 调用方排名 (Top {len(top)})")
    print(f"{'模块':<25} {'调用次数':>8} {'tokens':>10} {'费用(¥)':>10}")
    print("-" * 55)
    for t in top:
        print(f"{t['module']:<25} {t['calls']:>8} {t['tokens']:>10} {t['cost']:>10.4f}")
    return top
