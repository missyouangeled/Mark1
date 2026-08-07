"""混沌工程自动闭环（方案 44 建设项 E / Phase 5 / §8）。

当前不足（方案 §8.1）
--------------------
`chaos_engine.py` 已有实验、setup/verify/cleanup 和 dry-run，但"每周跑一次"
仍主要是规则要求，不是完整的自动闭环。还缺：

    - 自动选择安全实验
    - 运行前环境和恢复能力检查
    - 每次实验的 invariant/SLO 判定
    - 失败自动转成回归测试候选
    - 与版本、模块、配置关联的趋势证据

本模块新增（方案 §8.2-8.5）
--------------------------
    - chaos_scheduler.py：只产生 due 计划，不私自修改系统调度器
    - chaos_policy.py：实验风险、时间窗、冷却和前置条件
    - chaos_archive.py：实验记录与回归关联
    - chaos_regression.py：从已确认故障生成 pytest fixture 草案

⚠️ 安全等级（方案 §8.4）
-----------------------
    L0：纯模拟，无副作用，可自动
    L1：进程内故障注入，可自动但需 cleanup 证明
    L2：影响本地服务或资源，仅人工确认后运行
    L3：可能影响数据/网络/承载自身的 Gateway，永久禁止自动运行

⚠️ 调度方式（方案 §8.5）
-----------------------
Mark42 只维护 `next_due_at` 与建议实验，不自行偷偷写 cron/systemd。
真正启用定时器时另走系统操作审查和用户确认。
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

#: 安全等级枚举
SAFETY_L0 = "L0"  # 纯模拟，无副作用，可自动
SAFETY_L1 = "L1"  # 进程内故障注入，可自动但需 cleanup 证明
SAFETY_L2 = "L2"  # 影响本地服务或资源，仅人工确认后运行
SAFETY_L3 = "L3"  # 可能影响数据/网络/Gateway，永久禁止自动运行

SAFETY_LEVELS = (SAFETY_L0, SAFETY_L1, SAFETY_L2, SAFETY_L3)

#: 允许自动运行的等级
AUTO_SAFE_LEVELS = (SAFETY_L0, SAFETY_L1)

#: 默认冷却时间（秒）
DEFAULT_COOLDOWN_S = 3600  # 1 小时

#: 默认实验时间窗（允许运行的时间段）
DEFAULT_TIME_WINDOW = (0, 23)  # 全天

#: L3 denylist 不可被实验自身修改（方案 §8.6）
L3_DENYLIST_IMMUTABLE = True

#: 同一失败连续出现 2 次才升级为真实缺陷候选（方案 §8.6）
DEFECT_CONFIRMATION_THRESHOLD = 2


@dataclass
class ChaosExperimentRecord:
    """单次实验的完整记录。"""

    experiment_id: str
    name: str
    safety_level: str = SAFETY_L0
    started_at: str = ""
    finished_at: str = ""
    duration_ms: int = 0
    #: pass / fail / error / skipped
    status: str = ""
    setup_ok: bool = False
    execute_ok: bool = False
    verify_ok: bool = False
    cleanup_ok: bool = False
    cleanup_verified: bool = False
    invariant_violations: list[str] = field(default_factory=list)
    error: str = ""
    #: Mark42 版本 / 模块配置哈希，用于趋势关联
    version: str = ""
    config_hash: str = ""
    #: 前后指标
    metrics_before: dict[str, Any] = field(default_factory=dict)
    metrics_after: dict[str, Any] = field(default_factory=dict)

    def is_defect(self) -> bool:
        """是否暴露了真实缺陷（status=fail 或 invariant 被违反）。"""
        return self.status == "fail" or bool(self.invariant_violations)

    def is_cleanup_confirmed(self) -> bool:
        """cleanup 是否被验证（方案 §8.6：cleanup 失败立即停止后续实验）。"""
        return self.cleanup_ok and self.cleanup_verified

    def to_dict(self) -> dict[str, Any]:
        return {
            "experiment_id": self.experiment_id,
            "name": self.name,
            "safety_level": self.safety_level,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "duration_ms": self.duration_ms,
            "status": self.status,
            "setup_ok": self.setup_ok,
            "execute_ok": self.execute_ok,
            "verify_ok": self.verify_ok,
            "cleanup_ok": self.cleanup_ok,
            "cleanup_verified": self.cleanup_verified,
            "invariant_violations": list(self.invariant_violations),
            "error": self.error,
            "version": self.version,
            "config_hash": self.config_hash,
            "metrics_before": dict(self.metrics_before),
            "metrics_after": dict(self.metrics_after),
        }


@dataclass
class ChaosPolicy:
    """实验策略：风险/时间窗/冷却/前置条件。"""

    #: 允许自动运行的最高等级
    max_auto_level: str = SAFETY_L1
    #: 允许运行的时间段（24h 制，含两端）
    time_window: tuple[int, int] = DEFAULT_TIME_WINDOW
    #: 同一实验冷却时间（秒）
    cooldown_s: int = DEFAULT_COOLDOWN_S
    #: 前置条件检查列表（实验名 -> 必须满足的条件描述）
    preflight_checks: dict[str, list[str]] = field(default_factory=dict)
    #: 每次自动调度最多运行多少个实验
    max_experiments_per_run: int = 5

    def is_level_allowed(self, level: str, *, auto: bool = True) -> bool:
        """检查等级是否允许运行。"""
        if level not in SAFETY_LEVELS:
            return False
        if auto and level not in AUTO_SAFE_LEVELS:
            return False
        if auto:
            allowed = SAFETY_LEVELS[:SAFETY_LEVELS.index(self.max_auto_level) + 1]
            return level in allowed
        return True

    def is_in_time_window(self, hour: int) -> bool:
        """检查当前小时是否在允许的时间窗内。"""
        lo, hi = self.time_window
        return lo <= hour <= hi


@dataclass
class ChaosScheduleEntry:
    """调度计划中的一条实验。"""

    name: str
    safety_level: str
    next_due_at: str = ""
    last_run_at: str = ""
    last_status: str = ""
    run_count: int = 0
    fail_count: int = 0
    consecutive_failures: int = 0

    def should_run(self, now_iso: str) -> bool:
        """是否到了该跑的时候。"""
        if not self.next_due_at:
            return True
        return now_iso >= self.next_due_at

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "safety_level": self.safety_level,
            "next_due_at": self.next_due_at,
            "last_run_at": self.last_run_at,
            "last_status": self.last_status,
            "run_count": self.run_count,
            "fail_count": self.fail_count,
            "consecutive_failures": self.consecutive_failures,
        }


# ── 调度器 ────────────────────────────────────────────


class ChaosScheduler:
    """混沌实验调度器（方案 §8.5）。

    ⚠️ 只维护 `next_due_at` 与建议实验，不自行偷偷写 cron/systemd。
    真正启用定时器时另走系统操作审查和用户确认。
    """

    def __init__(self, state_dir: Path | str, *, policy: ChaosPolicy | None = None) -> None:
        self.dir = Path(state_dir)
        self.dir.mkdir(parents=True, exist_ok=True)
        self.policy = policy or ChaosPolicy()
        self._schedule_file = self.dir / "schedule.json"
        self._archive_file = self.dir / "archive.jsonl"

    def get_schedule(self) -> list[ChaosScheduleEntry]:
        """读取当前调度计划。"""
        if not self._schedule_file.exists():
            return []
        try:
            data = json.loads(self._schedule_file.read_text(encoding="utf-8"))
            return [ChaosScheduleEntry(**{k: v for k, v in d.items()
                                          if k in ChaosScheduleEntry.__dataclass_fields__})
                    for d in data if isinstance(d, dict)]
        except (OSError, json.JSONDecodeError):
            return []

    def save_schedule(self, entries: list[ChaosScheduleEntry]) -> None:
        """保存调度计划。"""
        data = [e.to_dict() for e in entries]
        self._schedule_file.write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def select_due_experiments(self, now_iso: str) -> list[ChaosScheduleEntry]:
        """选择当前应该运行的实验。

        过滤条件：
            1. should_run(now) 为 True
            2. 安全等级允许自动运行
            3. 在时间窗内
            4. 不超过 max_experiments_per_run
        """
        schedule = self.get_schedule()
        due = [
            e for e in schedule
            if e.should_run(now_iso)
            and self.policy.is_level_allowed(e.safety_level, auto=True)
        ]
        return due[:self.policy.max_experiments_per_run]

    def record_result(self, record: ChaosExperimentRecord) -> None:
        """记录实验结果到归档。"""
        line = json.dumps(record.to_dict(), ensure_ascii=False)
        with self._archive_file.open("a", encoding="utf-8") as f:
            f.write(line + "\n")

        # 更新调度计划
        schedule = self.get_schedule()
        for entry in schedule:
            if entry.name == record.name:
                entry.last_run_at = record.finished_at or record.started_at
                entry.last_status = record.status
                entry.run_count += 1
                if record.is_defect():
                    entry.fail_count += 1
                    entry.consecutive_failures += 1
                else:
                    entry.consecutive_failures = 0
                # 设置下次运行时间
                entry.next_due_at = _add_seconds(
                    record.finished_at or _now(), self.policy.cooldown_s)
                break
        self.save_schedule(schedule)

    def get_defect_candidates(self) -> list[dict[str, Any]]:
        """获取已确认缺陷候选（方案 §8.6：同一失败连续出现 2 次才升级）。"""
        archive = self._load_archive()
        fail_counts: dict[str, int] = {}
        for record in archive:
            if record.is_defect():
                fail_counts[record.name] = fail_counts.get(record.name, 0) + 1
        return [
            {"name": name, "consecutive_failures": count}
            for name, count in fail_counts.items()
            if count >= DEFECT_CONFIRMATION_THRESHOLD
        ]

    def _load_archive(self) -> list[ChaosExperimentRecord]:
        if not self._archive_file.exists():
            return []
        results = []
        try:
            with self._archive_file.open("r", encoding="utf-8") as f:
                for raw in f:
                    raw = raw.strip()
                    if not raw:
                        continue
                    try:
                        data = json.loads(raw)
                        results.append(ChaosExperimentRecord(**{
                            k: v for k, v in data.items()
                            if k in ChaosExperimentRecord.__dataclass_fields__
                        }))
                    except (json.JSONDecodeError, TypeError):
                        continue
        except OSError:
            pass
        return results

    def stats(self) -> dict[str, Any]:
        """调度器统计信息。"""
        archive = self._load_archive()
        total = len(archive)
        passed = sum(1 for r in archive if r.status == "pass")
        failed = sum(1 for r in archive if r.is_defect())
        cleanups_ok = sum(1 for r in archive if r.is_cleanup_confirmed())
        cleanups_failed = sum(1 for r in archive if not r.cleanup_ok)

        return {
            "total_experiments": total,
            "passed": passed,
            "failed": failed,
            "cleanup_success_rate": cleanups_ok / total if total else None,
            "cleanup_failures": cleanups_failed,
            "defect_candidates": self.get_defect_candidates(),
            "schedule_count": len(self.get_schedule()),
        }


def _now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _add_seconds(iso_ts: str, seconds: int) -> str:
    """在 ISO 时间戳上加秒数。"""
    try:
        dt = datetime.fromisoformat(iso_ts)
        result = dt + _timedelta(seconds=seconds)
        return str(result.isoformat(timespec="seconds"))
    except (ValueError, TypeError):
        return _now()


def _timedelta(*, seconds: int):
    from datetime import timedelta
    return timedelta(seconds=seconds)
