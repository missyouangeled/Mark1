"""
Mark42 v3-2 · 错误档案系统

按 v3 §4（设计原则 R5）实现：
- §4.2 错误档案的数据结构
- §4.3 学习机制（L1 记录 / L2 复用 / L3 自动批准 + 防护机制）
- §4.4 状态机（NEW → RESOLVED → AUTO_APPROVED → REJECTED）
- §4.5 与战甲意识层协作流程
- §4.6 查询接口（lookup / record / approve_for_auto / reject / increment_auto_count）
- §4.7 mark42.py archive 命令（list / show / approve / reject）

参考方案：docs/plans/40-Mark42-OS化深化方案-v3.md

设计纪律（R 编号引用 v3 §0.2）：
- R4 确定性：失败不抛异常，返回可处理的空值/警告
- R5 边界：新类型异常 → 问用户；L3 自动批准 → 必须有护栏
- R12 L3 防护：cooldown + 影响面硬黑名单（永久禁）
"""

from __future__ import annotations

import json
import logging
import os
import re
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from .config import MARK42_STATE

logger = logging.getLogger(__name__)

# ── 常量 ─────────────────────────────────────────────

CST = timezone(timedelta(hours=8))

# 数据存储位置（v3 §4.2）
ARCHIVE_DIR = MARK42_STATE / "error-archive"
ENTRIES_FILE = ARCHIVE_DIR / "entries.jsonl"
APPROVAL_LOG_FILE = ARCHIVE_DIR / "approvals.jsonl"  # L3 自动批准审计
CONFIG_FILE = ARCHIVE_DIR / "config.json"

# v3 §4.3 L3 防护默认配置
DEFAULT_L3_CONFIG: Dict[str, Any] = {
    "cooldown_max": 5,                   # 连续自动批准 ≤ 5 次
    "cooldown_window_days": 30,          # 30 天内计数窗口
    "hard_blacklist_categories": [
        "user_data_modification",
        "business_logic_modification",
        "systemd_service_modification",
        "directory_deletion",
    ],
}

# v3 §4.4 状态枚举
STATUS_NEW = "NEW"
STATUS_RESOLVED = "RESOLVED"
STATUS_AUTO_APPROVED = "AUTO_APPROVED"
STATUS_REJECTED = "REJECTED"

ALL_STATUSES = {STATUS_NEW, STATUS_RESOLVED, STATUS_AUTO_APPROVED, STATUS_REJECTED}


# ── 数据类 ───────────────────────────────────────────

@dataclass
class ArchiveEntry:
    """v3 §4.2 单条错误档案。"""
    id: str
    ts_first_seen: str
    ts_last_seen: str
    occurrence_count: int
    category: str
    signature: str
    context: Dict[str, Any] = field(default_factory=dict)
    diagnosis: str = ""
    is_new_type: bool = True

    # 解决状态（v3 §4.4）
    resolution_status: str = STATUS_NEW          # NEW / RESOLVED / AUTO_APPROVED / REJECTED
    resolution_method: str = ""                  # 例: user_confirmed_no_action / auto_remediate / advisor_approved
    resolution_decided_by: str = ""              # user / advisor / auto
    resolution_decided_at: str = ""
    resolution_notes: str = ""

    # L3 自动批准（v3 §4.3）
    auto_approved: bool = False
    auto_approval_scope: str = ""                # exact_match / similar_match / ""
    auto_approval_at: str = ""
    auto_approval_count: int = 0                 # 连续自动批准计数（cooldown 用）

    tags: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "ArchiveEntry":
        # 兼容缺字段的旧条目
        known = {f for f in cls.__dataclass_fields__.keys()}
        return cls(**{k: v for k, v in d.items() if k in known})


# ── 工具函数 ─────────────────────────────────────────

import threading
import os as _os_lock
_file_locks: Dict[str, threading.Lock] = {}
_file_locks_meta_lock = threading.Lock()


def _file_lock(path: Path) -> threading.Lock:
    """进程内文件锁（同一进程内多线程安全）。

    注意：跨进程并发需更高级的锁（flock/fcntl），单机场景下够用。
    """
    key = str(path)
    with _file_locks_meta_lock:
        if key not in _file_locks:
            _file_locks[key] = threading.Lock()
        return _file_locks[key]


def _now_iso() -> str:
    return datetime.now(CST).isoformat()


def _ensure_archive_dir() -> None:
    """确保 archive 目录存在；不存在就建。"""
    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)


def _load_l3_config() -> Dict[str, Any]:
    """从 CONFIG_FILE 读 L3 配置；不存在返回默认（不崩）。"""
    if not CONFIG_FILE.exists():
        return DEFAULT_L3_CONFIG
    try:
        with open(CONFIG_FILE, encoding="utf-8") as f:
            data = json.load(f)
        # 合并默认值（防止新增 key 时崩）
        merged = {**DEFAULT_L3_CONFIG, **data}
        return merged
    except (OSError, json.JSONDecodeError) as e:
        logger.warning("读 L3 配置失败: %s，用默认", e)
        return DEFAULT_L3_CONFIG


def _save_l3_config(cfg: Dict[str, Any]) -> None:
    _ensure_archive_dir()
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2, ensure_ascii=False)


def _read_entries() -> List[ArchiveEntry]:
    """读全部条目；不存在 → 空列表。"""
    if not ENTRIES_FILE.exists():
        return []
    out: List[ArchiveEntry] = []
    with open(ENTRIES_FILE, encoding="utf-8") as f:
        for ln, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                d = json.loads(line)
                out.append(ArchiveEntry.from_dict(d))
            except (json.JSONDecodeError, TypeError) as e:
                logger.warning("entries.jsonl 第 %d 行解析失败: %s", ln, e)
    return out


def _append_entry(entry: ArchiveEntry) -> None:
    """追加一条到 entries.jsonl（每次写一行，append-only）。"""
    _ensure_archive_dir()
    with _file_lock(ENTRIES_FILE):
        with open(ENTRIES_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry.to_dict(), ensure_ascii=False) + "\n")


def _rewrite_entries(entries: List[ArchiveEntry]) -> None:
    """整体覆盖写 entries.jsonl（用于状态变更）。

    并发安全：使用进程内锁 + os.replace 原子替换
    """
    _ensure_archive_dir()
    with _file_lock(ENTRIES_FILE):
        # 写新文件再 rename（避免半路崩了导致损坏）
        tmp = ENTRIES_FILE.with_suffix(".jsonl.tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            for e in entries:
                f.write(json.dumps(e.to_dict(), ensure_ascii=False) + "\n")
        _os_lock.replace(tmp, ENTRIES_FILE)


def _append_audit(entry_id: str, action: str, payload: Dict[str, Any]) -> None:
    """L3 自动批准的审计日志（R7 自动行为必有据可查）。"""
    _ensure_archive_dir()
    rec = {
        "ts": _now_iso(),
        "entry_id": entry_id,
        "action": action,                 # approve / reject / auto_apply / cooldown_blocked / blacklist_blocked
        **payload,
    }
    with open(APPROVAL_LOG_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")


# ── 核心 API（v3 §4.6 战甲意识层调用）───────────────

class ErrorArchive:
    """错误档案读写主类。"""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or _load_l3_config()

    # ── 查询 ──

    def lookup(self, signature: str, category: str = "") -> Optional[ArchiveEntry]:
        """根据 signature 查档案（精确匹配 + 相似匹配两阶段）。

        返回：
          - None → 没找到
          - ArchiveEntry → 命中
        行为纪律：找不到不抛；战甲 C2 调用此方法。

        匹配规则：
        - 精确匹配：signature 完全相同 + （如果给了 category）category 相同
        - 相似匹配：同 category + 同 signature 命名空间（前缀）
        """
        all_entries = _read_entries()
        # 精确匹配：signature 必须完全相同；category 给了也要匹配
        for e in all_entries:
            if e.signature == signature and e.resolution_status != STATUS_REJECTED:
                if not category or e.category == category:
                    return e
        # 相似匹配：category 完全相同 + signature 命名空间（前缀）相同
        if category:
            sig_ns = signature.split(":")[0] if ":" in signature else ""
            for e in all_entries:
                if (e.category == category
                        and e.signature.split(":")[0] == sig_ns
                        and e.signature != signature
                        and e.resolution_status != STATUS_REJECTED):
                    return e
        return None

    def list_entries(self, status: Optional[str] = None,
                     category: Optional[str] = None) -> List[ArchiveEntry]:
        """列出条目；可按 status/category 过滤。"""
        out = _read_entries()
        if status:
            out = [e for e in out if e.resolution_status == status]
        if category:
            out = [e for e in out if e.category == category]
        # 最新在前
        out.sort(key=lambda e: e.ts_last_seen, reverse=True)
        return out

    def get(self, entry_id: str) -> Optional[ArchiveEntry]:
        for e in _read_entries():
            if e.id == entry_id:
                return e
        return None

    # ── 记录 ──

    def record(self, category: str, signature: str,
               diagnosis: str = "",
               context: Optional[Dict[str, Any]] = None,
               tags: Optional[List[str]] = None,
               decided_by: str = "",
               method: str = "",
               notes: str = "",
               resolution_status: str = STATUS_NEW,
               auto_approve_scope: str = "") -> ArchiveEntry:
        """写入/更新一条档案。

        行为：
          - 已有同 signature → occurrence_count +1，ts_last_seen 更新
          - 没有 → 新建条目
        返回最终的 ArchiveEntry。
        """
        existing = self.lookup(signature, category=category)
        if existing is not None and existing.resolution_status != STATUS_REJECTED:
            # 命中已有 → 增量更新（不重复记录，仅累加计数）
            existing.occurrence_count += 1
            existing.ts_last_seen = _now_iso()
            # 重写整个文件（这种"重复事件"是少数情况，可接受）
            all_e = _read_entries()
            for i, e in enumerate(all_e):
                if e.id == existing.id:
                    all_e[i] = existing
                    break
            _rewrite_entries(all_e)
            return existing

        # 新条目
        entry = ArchiveEntry(
            id=f"ERR-{datetime.now(CST).strftime('%Y-%m-%d')}-{uuid.uuid4().hex[:6]}",
            ts_first_seen=_now_iso(),
            ts_last_seen=_now_iso(),
            occurrence_count=1,
            category=category,
            signature=signature,
            context=context or {},
            diagnosis=diagnosis,
            is_new_type=True,
            resolution_status=resolution_status,
            resolution_method=method,
            resolution_decided_by=decided_by,
            resolution_decided_at=_now_iso() if resolution_status != STATUS_NEW else "",
            resolution_notes=notes,
            tags=tags or [],
        )
        if auto_approve_scope and resolution_status == STATUS_AUTO_APPROVED:
            entry.auto_approved = True
            entry.auto_approval_scope = auto_approve_scope
            entry.auto_approval_at = _now_iso()
            entry.auto_approval_count = 1
        _append_entry(entry)
        return entry

    # ── L3 防护（v3 §4.3 R12 钉死） ──

    def approve_for_auto(self, entry_id: str, scope: str = "exact_match") -> Dict[str, Any]:
        """用户授权下次自动执行。

        返回 dict：
          ok: bool
          reason: str
          warnings: List[str]    # 给 CLI 显示的告警
        """
        if scope not in ("exact_match", "similar_match"):
            return {"ok": False, "reason": f"scope 必须是 exact_match / similar_match，当前: {scope}"}

        entry = self.get(entry_id)
        if entry is None:
            return {"ok": False, "reason": f"找不到条目 {entry_id}"}

        # 黑名单检查（永久禁）
        if entry.category in self.config["hard_blacklist_categories"]:
            msg = (f"❌ 拒绝：条目涉及 '{entry.category}'，命中 L3 硬黑名单。"
                   f" 即使用户授权 L3 自动批准，战甲也不会自动执行。")
            _append_audit(entry_id, "blacklist_blocked", {"category": entry.category})
            return {"ok": False, "reason": msg}

        # 应用授权
        entry.auto_approved = True
        entry.auto_approval_scope = scope
        entry.auto_approval_at = _now_iso()
        entry.auto_approval_count = 1     # 用户授权算第 1 次
        entry.resolution_status = STATUS_AUTO_APPROVED
        if not entry.resolution_decided_by:
            entry.resolution_decided_by = "user"
            entry.resolution_decided_at = _now_iso()
            entry.resolution_method = "user_approved_auto"

        # 写回
        all_e = _read_entries()
        for i, e in enumerate(all_e):
            if e.id == entry_id:
                all_e[i] = entry
                break
        _rewrite_entries(all_e)
        _append_audit(entry_id, "approve", {"scope": scope, "count": 1})

        return {
            "ok": True,
            "reason": f"已授权：以后{'完全匹配' if scope == 'exact_match' else '类似'}异常按本次方案自动执行",
            "warnings": [],
        }

    def increment_auto_count(self, entry_id: str) -> Dict[str, Any]:
        """战甲自动执行一次后调用：计数 +1；超 5 次强制重新确认。

        返回：
          allowed: bool           # 本次是否允许自动执行
          require_reconfirm: bool # 是否需要用户重新确认
          count: int              # 当前计数
        """
        entry = self.get(entry_id)
        if entry is None:
            return {"allowed": False, "require_reconfirm": True, "count": 0}

        # 黑名单复核（每次执行前都查）
        if entry.category in self.config["hard_blacklist_categories"]:
            _append_audit(entry_id, "blacklist_blocked", {"stage": "pre_execute"})
            return {"allowed": False, "require_reconfirm": True, "count": entry.auto_approval_count}

        # Cooldown 检查（30 天窗口内连续 5 次强制重新确认）
        cooldown_max = int(self.config.get("cooldown_max", 5))
        cooldown_days = int(self.config.get("cooldown_window_days", 30))

        # 检查窗口：auto_approval_at 在 N 天内
        try:
            ap_at = datetime.fromisoformat(entry.auto_approval_at)
            within_window = (datetime.now(CST) - ap_at).days < cooldown_days
        except (ValueError, TypeError):
            within_window = False

        # 钉死语义: ≤ cooldown_max 次允许，第 (cooldown_max+1) 次拦截
        # 起点 count = 1（用户授权），允许累加到 cooldown_max=5；第 6 次 increment 拦截
        if within_window and entry.auto_approval_count >= cooldown_max:
            _append_audit(entry_id, "cooldown_blocked",
                          {"count": entry.auto_approval_count, "max": cooldown_max})
            return {"allowed": False, "require_reconfirm": True, "count": entry.auto_approval_count}

        # 通过：累加 +1
        entry.auto_approval_count += 1
        all_e = _read_entries()
        for i, e in enumerate(all_e):
            if e.id == entry_id:
                all_e[i] = entry
                break
        _rewrite_entries(all_e)
        _append_audit(entry_id, "auto_apply", {"count": entry.auto_approval_count})

        # 是否快到上限（提前告警）— 钉死: ≤ 5 次允许, 第 5 次告警, 第 6 次拦截
        warnings: List[str] = []
        if entry.auto_approval_count == cooldown_max:
            warnings.append(
                f"⚠️ 已连续自动批准 {cooldown_max} 次（达到上限）。下次类似异常将强制要求重新确认。"
            )

        return {"allowed": True, "require_reconfirm": False,
                "count": entry.auto_approval_count, "warnings": warnings}

    def reject(self, entry_id: str, notes: str = "") -> Dict[str, Any]:
        """用户拒绝：以后不再按这个方案走（RESOLVED → REJECTED 实际是 NEW → REJECTED）。"""
        entry = self.get(entry_id)
        if entry is None:
            return {"ok": False, "reason": f"找不到条目 {entry_id}"}
        entry.resolution_status = STATUS_REJECTED
        entry.resolution_decided_by = "user"
        entry.resolution_decided_at = _now_iso()
        entry.resolution_method = "user_rejected"
        entry.resolution_notes = notes
        entry.auto_approved = False       # 撤回
        all_e = _read_entries()
        for i, e in enumerate(all_e):
            if e.id == entry_id:
                all_e[i] = entry
                break
        _rewrite_entries(all_e)
        _append_audit(entry_id, "reject", {"notes": notes})
        return {"ok": True, "reason": "已拒绝：以后不再按这个方案走"}

    # ── 工具 ──

    def stats(self) -> Dict[str, Any]:
        """统计概览（CLI 用）。"""
        all_e = _read_entries()
        by_status: Dict[str, int] = {}
        for e in all_e:
            by_status[e.resolution_status] = by_status.get(e.resolution_status, 0) + 1
        return {
            "total": len(all_e),
            "by_status": by_status,
            "auto_approved_count": sum(1 for e in all_e if e.auto_approved),
        }


# ── CLI（v3 §4.7 mark42 archive） ────────────────────

def _print_entry_row(e: ArchiveEntry) -> None:
    last_seen = e.ts_last_seen.split("T")[0] if e.ts_last_seen else "-"
    print(f"  {e.id:30s} | {e.category:30s} | {e.occurrence_count:3d} | "
          f"{e.resolution_status:15s} | {last_seen}")


def _cli() -> int:
    import argparse
    p = argparse.ArgumentParser(description="Mark42 v3-2 错误档案管理")
    sub = p.add_subparsers(dest="cmd", required=True)

    p_list = sub.add_parser("list", help="列出条目")
    p_list.add_argument("--status", choices=sorted(ALL_STATUSES), help="按状态过滤")
    p_list.add_argument("--category", help="按 category 过滤")
    p_list.add_argument("--limit", type=int, default=20, help="最多显示多少条")

    p_show = sub.add_parser("show", help="看一条详情")
    p_show.add_argument("entry_id", help="条目 ID")

    p_approve = sub.add_parser("approve", help="授权下次自动执行")
    p_approve.add_argument("entry_id", help="条目 ID")
    p_approve.add_argument("--scope", choices=["exact_match", "similar_match"],
                           default="exact_match", help="匹配范围")

    p_reject = sub.add_parser("reject", help="拒绝：以后不再按这个方案")
    p_reject.add_argument("entry_id", help="条目 ID")
    p_reject.add_argument("--notes", default="", help="拒绝原因")

    p_stats = sub.add_parser("stats", help="统计概览")

    args = p.parse_args()
    arc = ErrorArchive()

    if args.cmd == "list":
        entries = arc.list_entries(status=args.status, category=args.category)
        entries = entries[: args.limit]
        print(f"\n{'ID':32s} | {'CATEGORY':32s} | {'CNT':3s} | {'STATUS':15s} | LAST_SEEN")
        print("-" * 100)
        for e in entries:
            _print_entry_row(e)
        print(f"\n共 {len(entries)} 条（总 {arc.stats()['total']} 条）\n")

    elif args.cmd == "show":
        e = arc.get(args.entry_id)
        if e is None:
            print(f"❌ 找不到 {args.entry_id}")
            return 1
        print(json.dumps(e.to_dict(), indent=2, ensure_ascii=False))

    elif args.cmd == "approve":
        r = arc.approve_for_auto(args.entry_id, scope=args.scope)
        print(r["reason"])
        for w in r.get("warnings", []):
            print(w)
        return 0 if r["ok"] else 2

    elif args.cmd == "reject":
        r = arc.reject(args.entry_id, notes=args.notes)
        print(r["reason"])
        return 0 if r["ok"] else 2

    elif args.cmd == "stats":
        s = arc.stats()
        print(f"\n总条目: {s['total']}")
        print(f"按状态:")
        for k, v in s["by_status"].items():
            print(f"  {k:18s} {v}")
        print(f"已授权自动执行: {s['auto_approved_count']}\n")

    return 0


if __name__ == "__main__":
    raise SystemExit(_cli())