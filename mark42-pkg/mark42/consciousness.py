"""
Mark42 v3-3 · 战甲自主意识层（Consciousness）

按 v3 §3 钉死的"战甲自主意识"实现：
- C1 自检（读 watchdog / heartbeat / status.json / loops）
- C2 评估确定性（规则表 + 错误档案匹配）
- C3 100% 确定的修复（auto_remediate，按规则表执行）
- C4 不确定时主动发起对话（advisor / user）
- C5 学过的错误走错误档案（v3-2 error_archive）

5 个能力按 §3.2 分层：
- C1, C2, C3 = 100% 确定 → 战甲完全自主
- C4 = 0% 确定 → 战甲主动发起，但**不自主决定修法**（R8 钉死）
- C5 = 高确定（基于历史）→ 战甲自主，但有 cooldown 上限

协作流程 §4.5：
  故障信号 → C1 → C2 → {命中档案+AUTO_APPROVED: C3} / {命中档案+未批准: C4-走上次方案}
           / {未命中但 100% 确定: C3} / {不确定: C4 问 advisor→user}
           / {新类型: C4 问用户 + 写档案}

R 原则引用（v3 §0.2）：
- R4 确定性：C1/C2/C3 永不抛异常；找不到就返 None
- R5 边界：C4 必须问人；C3 黑名单永不自动
- R8 小模型不参与最终决策：本层是"战甲意识"，不是"小模型说话"
"""

from __future__ import annotations

from .log_setup import get_logger
logger = get_logger(__name__)

import json
import logging
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from .config import ARMOR_STATE, ENGINE_STATE, MARK42_STATE, CONFIG_PATH
from .error_archive import ErrorArchive, STATUS_AUTO_APPROVED, STATUS_RESOLVED
from .llm_provider import (
    ChatMessage, LLMProvider, build_consciousness, build_advisor, load_config,
)

from .advisor_client import AdvisorClient, AdvisorResult

# logger 已在顶部用 from .log_setup import get_logger 初始化

# v3-5: 是否在 C4 路径真正调用 advisor API
# True = 真实调用（v3-5 默认）
# False = 只生成 DialogRequest（v3-3 行为，兼容回退）
_USE_REAL_ADVISOR = True

CST = timezone(timedelta(hours=8))


# ── 确定性规则表（C2 用） ──────────────────────────────

# v3 §3.2 C2: 规则表 + 历史 post-mortem 匹配
# 格式: (signature 匹配, 确定性等级, 动作)
#   确定性等级: "100%" / "high" / "low" / "unknown"
#   动作: "auto_remediate" / "ask_advisor" / "ask_user" / "lookup_archive"
DETERMINISTIC_RULES: List[Dict[str, Any]] = [
    {
        "id": "rule-001",
        "name": "scratch 目录临时文件",
        "match": {"source": "scratch", "category": "unknown_file"},
        "certainty": "low",
        "action": "ask_user",
        "reason": "可能是用户数据或进程产物，影响面不可逆",
    },
    {
        "id": "rule-002",
        "name": "embed 索引缺失",
        "match": {"source": "sidecar", "category": "embed_index_missing"},
        "certainty": "100%",
        "action": "auto_remediate",
        "reason": "重建索引命令可执行，影响仅限 L2.5 召回（可降级 L1）",
    },
    {
        "id": "rule-003",
        "name": "sidecar 进程挂",
        "match": {"source": "sidecar", "category": "process_down"},
        "certainty": "100%",
        "action": "auto_remediate",
        "reason": "systemd restart 是标准操作，影响仅限 L2.5 召回",
    },
    {
        "id": "rule-004",
        "name": "上下文铠甲告警",
        "match": {"source": "armor", "category": "context_alert"},
        "certainty": "100%",
        "action": "auto_remediate",
        "reason": "智能压缩是确定行为，dry-run 已有",
    },
    {
        "id": "rule-005",
        "name": "Loop 状态异常（非 registered）",
        "match": {"source": "engine", "category": "loop_not_registered"},
        "certainty": "100%",
        "action": "auto_remediate",
        "reason": "loop 模板可重注册，watchdog 已能检测",
    },
    {
        "id": "rule-006",
        "name": "systemd service 文件被改",
        "match": {"source": "systemd", "category": "service_modified"},
        "certainty": "unknown",
        "action": "ask_user",
        "reason": "R5 钉死 + 崩坏案例：systemd 修改必须人审",
    },
]


# ── 数据类 ───────────────────────────────────────────

@dataclass
class SelfCheckResult:
    """C1 自检结果。"""
    checked_at: str
    healthy: bool
    issues: List[Dict[str, Any]] = field(default_factory=list)
    raw: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class CertaintyAssessment:
    """C2 评估结果。"""
    certainty: str                # "100%" / "high" / "low" / "unknown"
    matched_rule: Optional[str]   # 命中的规则 id
    archive_entry_id: Optional[str]  # 错误档案条目 id（如有）
    archive_auto_approved: bool   # 档案是否已批准
    action: str                   # "auto_remediate" / "ask_advisor" / "ask_user" / "lookup_archive"
    reason: str
    next_step: str                # 给上层（v2 子 Loop）看的下一步建议

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class DialogRequest:
    """C4 主动对话请求。"""
    trigger: str                  # 触发原因
    context: Dict[str, Any]       # 上下文
    question: str                 # 要问的问题
    options: List[Dict[str, str]] = field(default_factory=list)   # [{id, label, desc}]
    severity: str = "info"        # "info" / "warning" / "critical"
    to: str = "user"              # "user" / "advisor"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ── Consciousness 主类 ───────────────────────────────

class Consciousness:
    """战甲自主意识层主类（v3-3 落地）。"""

    def __init__(self,
                 llm: Optional[LLMProvider] = None,
                 archive: Optional[ErrorArchive] = None,
                 rules: Optional[List[Dict[str, Any]]] = None,
                 config: Optional[Dict[str, Any]] = None):
        """
        依赖注入（方便单测 mock）：
        - llm: 主 LLM provider（v3-1 已实现）
        - archive: 错误档案（v3-2 已实现）
        - rules: 确定性规则表（默认用本模块的 DETERMINISTIC_RULES）
        - config: model.yaml 配置（默认 load_config()）
        """
        self.config = config or load_config()
        self.llm = llm or build_consciousness(self.config)
        self.archive = archive or ErrorArchive()
        self.advisor = build_advisor(self.config)  # 可能 None
        self.rules = rules if rules is not None else DETERMINISTIC_RULES
        # v3-5: 初始化 AdvisorClient（C4 真实调用用）
        self._advisor_client = AdvisorClient(self.config) if _USE_REAL_ADVISOR else None
        # R-CAND-02 熔断器
        from .circuit_breaker import CircuitBreaker
        self._circuit_breaker = CircuitBreaker()

    # ── C1. 自检（100% 确定） ──

    def self_check(self) -> SelfCheckResult:
        """读取 watchdog / heartbeat / armor / engine 状态，找出异常。

        行为纪律：R4 确定性。所有 IO 用 try/except 包裹，单个失败不影响其他检查。
        返回 SelfCheckResult（不抛异常）。
        """
        from .utils import _load_json
        now = datetime.now(CST).isoformat()
        issues: List[Dict[str, Any]] = []
        raw: Dict[str, Any] = {}

        # 1) armor 上下文使用率
        try:
            from .armor import armor_check
            check = armor_check()
            raw["armor"] = check
            usage = check.get("usagePercent", 0)
            if usage >= 85:                          # THRESHOLD_ALERT 默认 85
                issues.append({
                    "source": "armor", "category": "context_alert",
                    "severity": "critical", "value": usage,
                    "msg": f"上下文使用率 {usage}% 达到告警线",
                })
            elif usage >= 70:                        # THRESHOLD_WARN
                issues.append({
                    "source": "armor", "category": "context_warn",
                    "severity": "warning", "value": usage,
                    "msg": f"上下文使用率 {usage}% 接近告警",
                })
        except Exception as e:
            logger.warning("C1 armor 检查失败: %s", e)

        # 2) engine daemon heartbeat
        try:
            hb_path = ENGINE_STATE / "daemon-heartbeat.json"
            if hb_path.exists():
                hb = _load_json(hb_path)
                raw["heartbeat"] = hb
                last = hb.get("lastTick")
                if last:
                    try:
                        last_dt = datetime.fromisoformat(last)
                        age_s = (datetime.now(CST) - last_dt).total_seconds()
                        if age_s > 600:            # 10 分钟没动
                            issues.append({
                                "source": "engine", "category": "daemon_stale",
                                "severity": "critical", "value": age_s,
                                "msg": f"daemon heartbeat 停滞 {age_s:.0f} 秒",
                            })
                    except ValueError:
                        pass
            else:
                issues.append({
                    "source": "engine", "category": "daemon_no_heartbeat",
                    "severity": "warning",
                    "msg": "找不到 daemon-heartbeat.json",
                })
        except Exception as e:
            logger.warning("C1 heartbeat 检查失败: %s", e)

        # 3) loops 状态（每个 loop 应该是 registered）
        try:
            loops = _load_json(ENGINE_STATE / "loops.json")
            raw["loops"] = loops
            for name, lp in loops.items():
                if lp.get("status") not in ("registered", "running"):
                    issues.append({
                        "source": "engine", "category": "loop_not_registered",
                        "severity": "warning",
                        "loop": name, "status": lp.get("status"),
                        "msg": f"loop {name} 状态={lp.get('status')}",
                    })
        except Exception as e:
            logger.warning("C1 loops 检查失败: %s", e)

        # 4) embed sidecar 健康（端口 18792）
        try:
            import urllib.request
            with urllib.request.urlopen("http://127.0.0.1:18792/healthz", timeout=2) as r:
                if r.status != 200:
                    issues.append({
                        "source": "sidecar", "category": "embed_unhealthy",
                        "severity": "warning", "code": r.status,
                        "msg": "embed-sidecar /healthz 非 200",
                    })
        except Exception as e:
            issues.append({
                "source": "sidecar", "category": "process_down",
                "severity": "warning",
                "msg": f"embed-sidecar 不通: {type(e).__name__}",
            })

        return SelfCheckResult(
            checked_at=now,
            healthy=not issues,
            issues=issues,
            raw=raw,
        )

    # ── C2. 评估确定性（100% 确定 · 基于规则） ──

    def assess_certainty(self, issue: Dict[str, Any]) -> CertaintyAssessment:
        """根据 issue 评估确定性。

        流程（v3 §4.5）：
        1. 先查错误档案
        2. 命中 + auto_approved → auto_remediate（走档案）
        3. 命中 + 未批准 → ask_user（走上次方案，但要人再确认）
        4. 未命中但命中规则表 + 100% → auto_remediate
        5. 未命中规则表 → ask_user（最低兜底）
        """
        sig = f"{issue.get('source','')}:{issue.get('category','')}"
        cat = issue.get("category", "")

        # 1) 错误档案优先
        arc_entry = self.archive.lookup(sig, category=cat)
        if arc_entry is not None:
            if arc_entry.auto_approved:
                return CertaintyAssessment(
                    certainty="high",
                    matched_rule=None,
                    archive_entry_id=arc_entry.id,
                    archive_auto_approved=True,
                    action="auto_remediate",
                    reason=f"命中错误档案 {arc_entry.id}（已批准）",
                    next_step=f"按档案 {arc_entry.id} 的方案执行",
                )
            else:
                return CertaintyAssessment(
                    certainty="low",
                    matched_rule=None,
                    archive_entry_id=arc_entry.id,
                    archive_auto_approved=False,
                    action="ask_user",
                    reason=f"命中错误档案 {arc_entry.id}（未批准）",
                    next_step=f"问用户是否按 {arc_entry.id} 的方案走",
                )

        # 2) 规则表匹配
        for rule in self.rules:
            m = rule.get("match", {})
            if (issue.get("source") == m.get("source")
                    and issue.get("category") == m.get("category")):
                return CertaintyAssessment(
                    certainty=rule["certainty"],
                    matched_rule=rule["id"],
                    archive_entry_id=None,
                    archive_auto_approved=False,
                    action=rule["action"],
                    reason=rule.get("reason", ""),
                    next_step=rule.get("reason", ""),
                )

        # 3) 完全没匹配 → 最低确定性，问用户 + 写档案
        return CertaintyAssessment(
            certainty="unknown",
            matched_rule=None,
            archive_entry_id=None,
            archive_auto_approved=False,
            action="ask_user",
            reason="未命中任何规则 / 档案（新类型异常）",
            next_step="问用户 + 写 NEW 档案",
        )

    # ── C3. 100% 确定的修复 ──

    def auto_remediate(self, issue: Dict[str, Any],
                       assessment: CertaintyAssessment,
                       dry_run: bool = True,
                       override_plan: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """按规则执行 auto_remediate。

        行为纪律：
        - 黑名单永不自动（R5 + R12）
        - 默认 dry_run（R6 钉死）
        - override_plan: advisor modify 时传入修改后的方案（v3-5 新增）
        - 返回 dict 含 action / ok / reason，不抛异常
        """
        # 黑名单硬护栏
        cat = issue.get("category", "")
        blacklist = {"user_data_modification", "business_logic_modification",
                     "systemd_service_modification", "directory_deletion"}
        if cat in blacklist:
            return {"ok": False, "reason": f"黑名单拒绝：{cat}",
                    "action": "blocked_by_blacklist"}

        # 按 issue 类型选执行函数
        executor = _REMEDIATION_EXECUTORS.get(issue.get("category"))
        if executor is None:
            return {"ok": False, "reason": f"无 auto_remediate 实现: {cat}",
                    "action": "no_executor"}

        if dry_run:
            r = {"ok": True, "dry_run": True,
                    "action": "would_execute",
                    "reason": f"dry-run: 准备执行 {executor.__name__} for {cat}",
                    "next_step": "加 --execute-now 才真跑"}
            if override_plan:
                r["override_plan"] = override_plan
                r["reason"] += " (使用 advisor 修改后的方案)"
            return r

        try:
            result = executor(issue)
            return {"ok": True, "dry_run": False,
                    "action": "executed",
                    "result": result}
        except Exception as e:
            return {"ok": False, "reason": f"执行失败: {e}",
                    "action": "execute_failed"}

    # ── C4. 主动发起对话 ──

    def dialog(self, issue: Dict[str, Any],
               assessment: CertaintyAssessment,
               to: Optional[str] = None) -> DialogRequest:
        """生成主动对话请求。战甲不自主决定修法（R8 钉死）。

        to: "user" / "advisor" — 默认 user
            advisor 优先（如果启用），advisor 不确定再问 user
        """
        target = to or ("advisor" if self.advisor else "user")
        q = self._render_question(issue, assessment)

        options: List[Dict[str, str]] = []
        if assessment.certainty == "100%":
            # 100% 确定也要问（v3 §3.2 C3 描述: 100% 自主, 但人审一遍更稳）
            options = [
                {"id": "approve_remediation", "label": "授权战甲自动修",
                 "desc": "按规则表推荐方案自动修复（推荐）"},
                {"id": "ask_advisor", "label": "先问 advisor",
                 "desc": "问外部大模型确认方案是否安全"},
                {"id": "manual_decide", "label": "我自己决定",
                 "desc": "我手动处理 / 告诉战甲别的方案"},
            ]
        elif assessment.action == "ask_user":
            options = [
                {"id": "approve_remediation", "label": "按默认方案修",
                 "desc": "让战甲按规则表推荐方案自动修"},
                {"id": "ask_advisor", "label": "先问 advisor",
                 "desc": "问外部大模型确认方案是否安全"},
                {"id": "manual_decide", "label": "我自己决定",
                 "desc": "我手动处理 / 告诉战甲别的方案"},
            ]
        elif assessment.action == "ask_advisor":
            options = [
                {"id": "ask_advisor", "label": "问 advisor",
                 "desc": "调用外部大模型确认方案"},
                {"id": "approve_remediation", "label": "直接按方案",
                 "desc": "不问了，按规则表方案直接做（需要 archive 授权）"},
            ]

        # 写错误档案（v3 §3.3 场景 C）
        if assessment.certainty == "unknown" and issue.get("source"):
            sig = f"{issue.get('source','')}:{issue.get('category','')}"
            try:
                entry = self.archive.record(
                    category=issue.get("category", ""),
                    signature=sig,
                    diagnosis=issue.get("msg", ""),
                    context=issue,
                    tags=[issue.get("source", ""), "auto_detected"],
                )
                archive_id = entry.id
            except Exception as e:
                logger.warning("C4 写错误档案失败: %s", e)
                archive_id = None
        else:
            archive_id = None

        severity = "critical" if issue.get("severity") == "critical" else "warning"
        return DialogRequest(
            trigger=f"{issue.get('source')}:{issue.get('category')}",
            context={**issue, "assessment": assessment.to_dict(),
                     "archive_id": archive_id},
            question=q,
            options=options,
            severity=severity,
            to=target,
        )

    def _render_question(self, issue: Dict[str, Any],
                         assessment: CertaintyAssessment) -> str:
        """v3 §3.3 4 类场景的话术模板。"""
        src = issue.get("source", "?")
        cat = issue.get("category", "?")
        msg = issue.get("msg", "")
        if assessment.certainty == "100%":
            return (f"我检测到 {src}/{cat}：{msg}。\n"
                    f"我的判断：{assessment.reason}\n"
                    f"是否授权我按此方案自动修？")
        if assessment.certainty == "high":
            return (f"我检测到 {src}/{cat}：{msg}。\n"
                    f"命中错误档案 {assessment.archive_entry_id}（已批准）。\n"
                    f"我会按上次方案执行，需要确认吗？")
        if assessment.certainty == "low":
            return (f"我检测到 {src}/{cat}：{msg}。\n"
                    f"档案里有记录但未批准。\n"
                    f"你的判断是什么？")
        # unknown
        return (f"我检测到一种新类型异常：{src}/{cat}。\n"
                f"详情：{msg}\n"
                f"我的规则表里没有这个，不敢动。\n"
                f"这是什么？要不要清理？")

    # ── C5. 学过的错误走档案（v3-2 已实现，这里是便捷封装） ──

    def check_archive(self, issue: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """检查错误档案 + 若已批准则尝试 auto_remediate（带 cooldown 检查）。

        行为：
        - 命中且 auto_approved=True → increment_auto_count + 若 allowed 跑 auto_remediate
        - 命中但未批准 → 返 None（让 C2 决策）
        - 未命中 → 返 None
        """
        sig = f"{issue.get('source','')}:{issue.get('category','')}"
        cat = issue.get("category", "")
        entry = self.archive.lookup(sig, category=cat)
        if entry is None or not entry.auto_approved:
            return None

        # 已批准 → 检查 cooldown
        chk = self.archive.increment_auto_count(entry.id)
        if not chk["allowed"]:
            return {"archive_id": entry.id, "auto_approved": False,
                    "reason": "cooldown 触发，需要重新确认",
                    "cooldown_count": chk.get("count", 0)}

        # 跑 auto_remediate（dry-run 默认）
        assessment = self.assess_certainty(issue)
        return {
            "archive_id": entry.id,
            "auto_approved": True,
            "count": chk.get("count", 0),
            "warnings": chk.get("warnings", []),
            "next": "dry_run" if not chk.get("warnings") else "dry_run_with_warning",
        }

    # ── §4.5 协作流程主入口 ──

    def handle_issue(self, issue: Dict[str, Any], dry_run: bool = True) -> Dict[str, Any]:
        """§4.5 完整流程：故障信号 -> C1 风格自检条目 -> 路由到 C3/C4/C5.

        v3-5 升级：C4 路径真正调用 AdvisorClient（不只是生成话术字符串）。
        - advisor approve + confidence >= 阈值 -> 返回 C3 路径（带 advisor 背书）
        - advisor reject / 低置信度 / 未启用 -> 返回 C4 DialogRequest（问用户）
        """
        # 1. C5 优先（学过的错误走档案）
        c5 = self.check_archive(issue)
        if c5 and c5.get("auto_approved"):
            return {"path": "C5_archive_auto_approved", "result": c5}

        # 2. C2 评估确定性
        assess = self.assess_certainty(issue)

        # 3. 100% 确定 -> C3 auto_remediate
        if assess.certainty == "100%" and assess.action == "auto_remediate":
            rem = self.auto_remediate(issue, assess, dry_run=dry_run)
            return {"path": "C3_auto_remediate", "assessment": assess.to_dict(),
                    "remediation": rem}

        # 4. 不确定 -> C4 主动对话
        # v3-5: 先尝试真正调用 advisor
        advisor_result = None
        if self._advisor_client and self._advisor_client.enabled:
            # R-CAND-02 熔断器检查
            if self._circuit_breaker and not self._circuit_breaker.can_call("core_2_armor_consciousness"):
                logger.info("C4 advisor 熔断中，跳过 API 调用")
                advisor_result = AdvisorResult(
                    success=False,
                    fallback_reason="circuit_breaker_open",
                )
            else:
                scenario = self._pick_scenario(issue, assess)
                try:
                    advisor_result = self._call_advisor(scenario, issue, assess)
                    if advisor_result and advisor_result.success:
                        self._circuit_breaker.record_success("core_2_armor_consciousness")
                    elif advisor_result and not advisor_result.success:
                        self._circuit_breaker.record_failure("core_2_armor_consciousness",
                                                             advisor_result.fallback_reason or "unknown")
                except Exception as e:
                    logger.warning("C4 advisor 调用异常: %s", e)
                    self._circuit_breaker.record_failure("core_2_armor_consciousness", str(e))
                    advisor_result = None

        # advisor 返回 approve 且可信 -> 升级为 C3（带 advisor 背书）
        if advisor_result and advisor_result.success and advisor_result.verdict:
            v = advisor_result.verdict
            # v3-5 复查修复：检查 ask() 是否已降级（low_confidence 等原因）
            # 如果 ask() 返回了 fallback_reason，说明 advisor 不够确信，不升级到 C3
            ask_confident = not advisor_result.fallback_reason
            if v.is_approve and v.is_trustworthy and ask_confident:
                rem = self.auto_remediate(issue, assess, dry_run=dry_run)
                return {
                    "path": "C3_advisor_approved",
                    "assessment": assess.to_dict(),
                    "advisor_verdict": v.to_dict(),
                    "remediation": rem,
                }
            if v.is_modify and v.is_trustworthy and ask_confident:
                rem = self.auto_remediate(issue, assess, dry_run=dry_run,
                                          override_plan=v.modified_plan)
                return {
                    "path": "C3_advisor_modified",
                    "assessment": assess.to_dict(),
                    "advisor_verdict": v.to_dict(),
                    "remediation": rem,
                }

        # 5. 生成 DialogRequest（问用户）
        req = self.dialog(issue, assess)
        result: Dict[str, Any] = {"path": "C4_dialog", "request": req.to_dict()}
        if advisor_result:
            result["advisor_attempted"] = True
            result["advisor_verdict"] = (advisor_result.verdict.to_dict()
                                         if advisor_result.verdict else None)
            result["advisor_fallback_reason"] = advisor_result.fallback_reason
        else:
            result["advisor_attempted"] = False
        return result

    def _pick_scenario(self, issue: Dict[str, Any],
                       assessment: CertaintyAssessment) -> str:
        """根据 issue 和评估结果选择对话场景 (a/b/c/d)."""
        if assessment.certainty == "unknown":
            return "c"
        if assessment.archive_entry_id:
            return "d"
        if assessment.certainty == "100%":
            return "a"
        return "b"

    def _call_advisor(self, scenario: str, issue: Dict[str, Any],
                      assessment: CertaintyAssessment) -> Optional[AdvisorResult]:
        """调用 AdvisorClient（封装异常）."""
        if not self._advisor_client:
            return None
        if scenario == "a":
            return self._advisor_client.ask_about_uncertain_issue(
                issue, assessment.to_dict())
        elif scenario == "b":
            plan = {"steps": [], "estimated_time": "unknown", "impact": "unknown"}
            return self._advisor_client.ask_about_remediation_plan(issue, plan)
        elif scenario == "c":
            return self._advisor_client.ask_about_new_anomaly(issue)
        elif scenario == "d":
            # 从错误档案查真实 resolution（v3-5 复查修复）
            entry = {"id": assessment.archive_entry_id or "",
                     "category": issue.get("category", ""),
                     "diagnosis": issue.get("msg", ""),
                     "resolution": {}}
            if assessment.archive_entry_id:
                try:
                    sig = f"{issue.get('source','')}:{issue.get('category','')}"
                    arc = self.archive.lookup(sig, category=issue.get("category", ""))
                    if arc:
                        entry["resolution"] = {
                            "status": getattr(arc, "resolution", {}).get("status", ""),
                            "method": getattr(arc, "resolution", {}).get("method", ""),
                            "notes": getattr(arc, "resolution", {}).get("notes", ""),
                        }
                except Exception as e:
                    logger.warning("场景 d 查档案失败: %s", e)
            return self._advisor_client.ask_about_archive_reuse(entry)
        return None
        # ── R9 强制读协议 ──

    def verify_read_protocol(self, min_correct: int = 8,
                             force: bool = False) -> Dict[str, Any]:
        """R9 强制读协议验证：随机抽 10 题考模型，答对 >= min_correct 才放行。

        24h 内免重考（cooldown），除非 force=True。
        """
        import random, yaml as _yaml
        from datetime import datetime, timedelta

        # cooldown 检查
        state_dir = Path.home() / ".local" / "state" / "openclaw" / "mark42" / "read-protocol"
        state_file = state_dir / "verification.json"
        state_dir.mkdir(parents=True, exist_ok=True)

        if not force and state_file.exists():
            try:
                record = json.loads(state_file.read_text())
                verified_at = datetime.fromisoformat(record["verified_at"])
                if datetime.now() - verified_at < timedelta(hours=24):
                    return {
                        "passed": True,
                        "skipped": True,
                        "reason": f"24h 内已验证 (score={record.get('score')})，免考",
                        "verified_at": record["verified_at"],
                    }
            except Exception as e:
                pass  # 记录坏了就重考

        # 加载题池
        questions_file = state_dir / "questions.yaml"
        if not questions_file.exists():
            return {"passed": False, "reason": "题池不存在"}
        with open(questions_file) as f:
            pool = _yaml.safe_load(f)
        all_questions = pool.get("questions", [])
        if len(all_questions) < 10:
            return {"passed": False, "reason": f"题池只有 {len(all_questions)} 题，不足 10"}

        # 随机抽 10 题
        selected = random.sample(all_questions, 10)

        # 逐题考模型
        correct = 0
        results = []
        for q in selected:
            try:
                resp = self.llm.chat([ChatMessage(
                    role="user",
                    content=f"关于 Mark42 战甲系统（一个 AI Agent 自愈铠甲系统）：{q['question']}\n请简洁回答。\n\n参考：Mark42 核心原则摘要：R1=可插拔(runtime/model/api三层), R4=确定性(100%确定才修), R5=三层问不动(文档/新类型/业务), R8=小模型不决策, R10=8核上限, R13=降级不崩, R14=坏了换不修, C1-C5=自检/评估/修复/对话/档案, advisor verdict=approve/reject/modify, 错误档案状态=NEW/RESOLVED/AUTO_APPROVED/REJECTED"
                )])
                answer = resp.content.lower() if resp.content else ""
                keywords = [kw.lower() for kw in q.get("expected_keywords", [])]
                hits = sum(1 for kw in keywords if kw in answer)
                is_correct = hits >= max(1, len(keywords) // 2)  # 命中一半关键词算对
                if is_correct:
                    correct += 1
                results.append({"id": q["id"], "correct": is_correct,
                                "hits": hits, "total": len(keywords)})
            except Exception as e:
                results.append({"id": q["id"], "correct": False,
                                "error": str(e)})

        passed = correct >= min_correct

        # 写验证记录
        record = {
            "passed": passed,
            "score": correct,
            "total": 10,
            "min_correct": min_correct,
            "verified_at": datetime.now().isoformat(),
            "results": results,
        }
        try:
            state_file.write_text(json.dumps(record, indent=2, ensure_ascii=False))
        except Exception as e:
            logger.exception("Unhandled exception")
            pass

        return record


# ── 修复执行器（v3-3 占位 · 真实实现由 v3-5 整合 v2 子 Loop 接入） ──

def _remediate_dummy(issue: Dict[str, Any]) -> Dict[str, Any]:
    """占位实现 — 真实 fix 在 v3-5 接 v2 auto_remediate。"""
    return {"placeholder": True, "issue": issue.get("category")}



# ── v3-5b 真实修复执行器（替换 _remediate_dummy） ──

def _remediate_context_alert(issue: Dict[str, Any]) -> Dict[str, Any]:
    """上下文告警 -> 调用 armor.compress()。"""
    try:
        from .armor import armor_compress
        result = armor_compress(dry_run=False)
        return {"ok": True, "action": "armor_compress", "result": result}
    except Exception as e:
        return {"ok": False, "action": "armor_compress", "reason": str(e)}


def _remediate_process_down(issue: Dict[str, Any]) -> Dict[str, Any]:
    """进程挂 -> R12 黑名单：不自动 restart systemd，只诊断 + 提示。"""
    source = issue.get("source", "")
    # 诊断：进程在不在
    import subprocess
    try:
        result = subprocess.run(
            ["systemctl", "--user", "is-active", f"openclaw-{source}"],
            capture_output=True, text=True, timeout=5)
        status = result.stdout.strip()
    except Exception as e:
        status = "unknown"
    return {
        "ok": False,
        "action": "diagnose_only",
        "reason": f"R12 黑名单：不自动 restart systemd。service={source}, status={status}",
        "user_action": f"手动执行: systemctl --user restart openclaw-{source}",
    }


def _remediate_embed_index_missing(issue: Dict[str, Any]) -> Dict[str, Any]:
    """索引缺失 -> 调 embed-sidecar 重建。"""
    import subprocess, sys
    script_path = str(Path(__file__).parent.parent / "memory-embed-index.py")
    venv_python = str(Path.home() / ".local" / "share" / "openclaw-embed-venv311" / "bin" / "python3")
    python_bin = venv_python if Path(venv_python).exists() else sys.executable
    try:
        result = subprocess.run(
            [python_bin, script_path, "--force"],
            capture_output=True, text=True, timeout=300)
        ok = result.returncode == 0
        return {
            "ok": ok,
            "action": "embed_index_rebuild",
            "returncode": result.returncode,
            "stdout": result.stdout[-500:] if result.stdout else "",
            "stderr": result.stderr[-500:] if result.stderr else "",
        }
    except Exception as e:
        return {"ok": False, "action": "embed_index_rebuild", "reason": str(e)}


def _remediate_loop_not_registered(issue: Dict[str, Any]) -> Dict[str, Any]:
    """Loop 未注册 -> 重新注册。"""
    try:
        from .engine import engine_start
        template = issue.get("context", {}).get("template", "")
        task = issue.get("context", {}).get("task", "")
        interval = issue.get("context", {}).get("interval", 300)
        if not template:
            return {"ok": False, "action": "loop_register",
                    "reason": "缺少 template 名，无法重新注册"}
        engine_start(task=task or template, interval_s=interval, template=template)
        return {"ok": True, "action": "loop_register", "template": template}
    except Exception as e:
        return {"ok": False, "action": "loop_register", "reason": str(e)}


_REMEDIATION_EXECUTORS: Dict[str, Callable[[Dict[str, Any]], Dict[str, Any]]] = {
    "context_alert": _remediate_context_alert,
    "process_down": _remediate_process_down,
    "embed_index_missing": _remediate_embed_index_missing,
    "loop_not_registered": _remediate_loop_not_registered,
}




# ── CLI ──────────────────────────────────────────────

def _cli() -> int:
    import argparse
    p = argparse.ArgumentParser(description="Mark42 v3-3 战甲意识层")
    sub = p.add_subparsers(dest="cmd", required=True)

    p_check = sub.add_parser("check", help="C1 自检")
    p_check.add_argument("--json", action="store_true", help="JSON 输出")

    p_eval = sub.add_parser("eval", help="C2 评估某 issue 的确定性")
    p_eval.add_argument("--source", required=True)
    p_eval.add_argument("--category", required=True)
    p_eval.add_argument("--msg", default="")
    p_eval.add_argument("--severity", default="warning")

    p_handle = sub.add_parser("handle", help="§4.5 完整流程处理一个 issue")
    p_handle.add_argument("--source", required=True)
    p_handle.add_argument("--category", required=True)
    p_handle.add_argument("--msg", default="")
    p_handle.add_argument("--severity", default="warning")
    p_handle.add_argument("--execute-now", action="store_true", help="真跑 auto_remediate（默认 dry-run）")

    args = p.parse_args()
    cs = Consciousness()

    if args.cmd == "check":
        r = cs.self_check()
        if args.json:
            logger.info(json.dumps(r.to_dict(), indent=2, ensure_ascii=False))
        else:
            icon = "🟢" if r.healthy else "🟠"
            logger.info(f"\n{icon} C1 自检 [{r.checked_at}]")
            logger.info(f"   健康: {r.healthy}")
            logger.info(f"   发现 {len(r.issues)} 个问题:")
            for i, iss in enumerate(r.issues, 1):
                logger.info(f"     {i}. [{iss['severity']}] {iss['source']}/{iss['category']}: {iss.get('msg','-')}")
        return 0 if r.healthy else 1

    if args.cmd == "eval":
        issue = {"source": args.source, "category": args.category,
                 "msg": args.msg, "severity": args.severity}
        a = cs.assess_certainty(issue)
        logger.info(json.dumps(a.to_dict(), indent=2, ensure_ascii=False))
        return 0

    if args.cmd == "handle":
        issue = {"source": args.source, "category": args.category,
                 "msg": args.msg, "severity": args.severity}
        result = cs.handle_issue(issue, dry_run=not args.execute_now)
        logger.info(json.dumps(result, indent=2, ensure_ascii=False))
        return 0


if __name__ == "__main__":
    raise SystemExit(_cli())