"""压缩场景 fixture（方案 44 Phase 0：基线冻结）。

用途
----
Phase 1 的探针基线、Phase 2 的 shadow A/B 都依赖**固定输入**。
方案 §11 要求 Phase 0 先冻结 schema 与 fixture，避免"探针先于数据契约"。

原则
----
1. 场景内容**不含真实隐私**：人名/路径都是可公开的项目信息或化名；
2. 每个场景自带**期望断言**，让确定性评分可以在无模型环境下跑；
3. 场景一旦冻结就不随意改动——改了等于换了尺子，历史趋势不可比。
   确需修改时升 `SCENARIO_SET_VERSION`。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from mark42.context_state import ContextState, SourceCursor, new_empty_state

#: 场景集版本。改动任何既有场景内容时必须升版本。
SCENARIO_SET_VERSION = 1


@dataclass
class CompactionScenario:
    """一个压缩场景。"""

    name: str
    description: str
    #: 压缩前的会话消息（模拟 session 尾部）
    messages: list[dict[str, Any]] = field(default_factory=list)
    #: 该场景**期望**的结构化状态（人工标注的 ground truth）
    expected_state: ContextState = field(default_factory=new_empty_state)
    #: 各探针维度期望在响应中出现的关键词
    probe_expectations: dict[str, list[str]] = field(default_factory=dict)
    #: 该场景要验证的不变量说明
    invariants: list[str] = field(default_factory=list)


def _msg(role: str, content: str, mid: str) -> dict[str, Any]:
    return {
        "type": "message",
        "id": mid,
        "message": {"role": role, "content": content},
    }


# ── 场景 1：工作任务连续性 ────────────────────────────


def scenario_work_continuity() -> CompactionScenario:
    """典型工作场景：明确目标 + 决策 + 改过的文件 + 下一步。

    验证核心：连续 10 次增量压缩后，初始目标、未完成任务、
    明确约束仍然存在（方案 §4.6）。
    """
    st = new_empty_state(session_intent="按方案 44 补全 Mark42 的六条闭环")
    st.active_task = {
        "title": "Phase 0 基线冻结",
        "status": "in_progress",
        "description": "冻结 ContextState 与探针 schema",
    }
    st.decisions = [
        {
            "decision_id": "d-compaction-model",
            "summary": "compaction 换用 doubao-seed-2.0-pro",
            "rationale": "glm-5.2 在 <=512 预算下四档全 finish=length，三档正文为空",
            "rejected": ["agnes-2.0-flash（静默丢数据）", "glm-5.2（正文为空）"],
            "evidence": "m-3",
        },
        {
            "decision_id": "d-phase-order",
            "summary": "先做能力探针，再改压缩算法",
            "rationale": "先补'怎么判断好坏'，否则改完无法验证",
            "evidence": "m-5",
        },
    ]
    st.constraints = [
        {
            "constraint_id": "c-lang-zh",
            "text": "只用中文回复，禁止英文",
            "strength": "hard",
            "priority": "P0",
            "source": "SOUL.md",
            "evidence": "SOUL.md:6",
        },
        {
            "constraint_id": "c-flag-default-off",
            "text": "新增能力默认关闭或 shadow",
            "strength": "hard",
            "priority": "P1",
            "source": "plan-44",
            "evidence": "m-2",
        },
        {
            "constraint_id": "c-recall-vs-infer",
            "text": "召回只返回证据，不得把推断伪装成事实",
            "strength": "hard",
            "priority": "P0",
            "source": "MEMORY.md",
            "evidence": "m-2",
        },
    ]
    st.artifacts = [
        {"path": "mark42/context_state.py", "status": "created", "evidence": "m-7"},
        {"path": "mark42/audit/probes.py", "status": "created", "evidence": "m-8"},
    ]
    st.next_steps = [
        {"summary": "建 fixture 场景集", "evidence": "m-8"},
        {"summary": "Phase 1 探针接入 builtin_audit（shadow）", "evidence": "m-8"},
    ]
    st.evidence_refs = [
        {"message_id": "m-3", "excerpt": "豆包 128 起稳定 finish=stop"},
        {"message_id": "m-5", "excerpt": "先补怎么判断好坏，再改压缩算法"},
    ]
    st.set_cursor(SourceCursor(
        session_id="scenario-work",
        source_path="/fixtures/work.jsonl",
        inode=1001,
        byte_offset=2048,
        last_message_id="m-8",
        observed_size=2048,
        prefix_hash="fixture-hash-work",
        message_count=8,
    ))

    return CompactionScenario(
        name="work_continuity",
        description="工作任务：目标/决策/文件/下一步全都在",
        messages=[
            _msg("user", "按方案 44 继续开发 Mark42，六条闭环都要补", "m-1"),
            _msg("assistant", "新增能力默认关闭或 shadow，召回只返回证据", "m-2"),
            _msg("assistant", "compaction 换 doubao-seed-2.0-pro：glm-5.2 四档全 finish=length", "m-3"),
            _msg("user", "顺序你定", "m-4"),
            _msg("assistant", "先做能力探针再改压缩算法，否则改完无法验证", "m-5"),
            _msg("user", "开始吧", "m-6"),
            _msg("assistant", "已建 mark42/context_state.py，冻结 ContextState schema", "m-7"),
            _msg("assistant", "已建 mark42/audit/probes.py，六类探针 schema 冻结", "m-8"),
        ],
        expected_state=st,
        probe_expectations={
            "intent": ["Mark42"],
            "continuity": ["fixture"],
            "decision": ["doubao"],
            "artifact": ["context_state.py"],
            "evidence": ["m-3"],
            "instruction": ["中文"],
        },
        invariants=[
            "session_intent 不得丢失",
            "hard 约束条数不得减少",
            "active_task 不得被摘要清空",
            "artifacts 路径不得丢失",
        ],
    )


# ── 场景 2：约束密集 ──────────────────────────────────


def scenario_constraint_heavy() -> CompactionScenario:
    """约束密集场景：验证 hard 约束在压缩后 100% 存活（方案 §6.5）。"""
    st = new_empty_state(session_intent="确认所有硬约束在压缩后仍然生效")
    st.constraints = [
        {"constraint_id": "c-lang-zh", "text": "只用中文回复",
         "strength": "hard", "priority": "P0", "evidence": "SOUL.md:6"},
        {"constraint_id": "c-ask-before-send", "text": "发送邮件/推文/公开内容前先问",
         "strength": "hard", "priority": "P0", "evidence": "AGENTS.md"},
        {"constraint_id": "c-no-gateway-restart", "text": "主会话内禁止 restart/stop gateway",
         "strength": "hard", "priority": "P0", "evidence": "CASE-012"},
        {"constraint_id": "c-dry-run-default", "text": "高风险脚本默认 dry-run",
         "strength": "hard", "priority": "P1", "evidence": "ACTIVE_RULES.md"},
        {"constraint_id": "c-read-cases", "text": "高风险系统操作前先读崩坏案例",
         "strength": "hard", "priority": "P1", "evidence": "AGENTS.md"},
        {"constraint_id": "c-no-list-ending", "text": "日常聊天不要清单式收尾",
         "strength": "soft", "priority": "P2", "evidence": "rules/chat.md"},
    ]
    st.active_task = {"title": "约束合规验证", "status": "in_progress"}
    st.set_cursor(SourceCursor(
        session_id="scenario-constraint",
        source_path="/fixtures/constraint.jsonl",
        inode=1002,
        byte_offset=512,
        last_message_id="m-3",
        observed_size=512,
        prefix_hash="fixture-hash-constraint",
        message_count=3,
    ))

    return CompactionScenario(
        name="constraint_heavy",
        description="6 条约束（5 hard / 1 soft），验证静态存活率",
        messages=[
            _msg("user", "把所有硬约束列一遍", "m-1"),
            _msg("assistant", "只用中文；公开发送前先问；主会话禁止 restart gateway", "m-2"),
            _msg("assistant", "高风险默认 dry-run；操作前读崩坏案例；聊天不清单式收尾", "m-3"),
        ],
        expected_state=st,
        probe_expectations={
            "instruction": ["中文"],
            "intent": ["约束"],
        },
        invariants=[
            "5 条 hard 约束必须全部存活",
            "soft 约束丢失只记趋势不阻断",
            "P0 约束丢失必须阻断",
        ],
    )


# ── 场景 3：推断与事实混杂 ────────────────────────────


def scenario_inference_mixed() -> CompactionScenario:
    """验证召回与推断分离：推断必须单列，不得混进 evidence。"""
    st = new_empty_state(session_intent="排查 timer 停摆")
    st.decisions = [
        {
            "decision_id": "d-timer-harden",
            "summary": "user 级 timer 改用 OnStartupSec 三重保障",
            "rationale": "OnBootSec 在 user manager 首次登录才启动的场景下会被跳过",
            "evidence": "man systemd.timer",
        },
    ]
    st.inferences = [
        {
            "summary": "根盘增长可能与 session 快照累积有关",
            "confidence": 0.4,
            "basis": "快照每 5 分钟一份，但未验证体积占比",
        },
    ]
    st.evidence_refs = [
        {"message_id": "m-2", "excerpt": "实测开机 +86s 起 manager、+94s 起 timer"},
    ]
    st.active_task = {"title": "timer 加固复验", "status": "pending"}
    st.set_cursor(SourceCursor(
        session_id="scenario-inference",
        source_path="/fixtures/inference.jsonl",
        inode=1003,
        byte_offset=768,
        last_message_id="m-3",
        observed_size=768,
        prefix_hash="fixture-hash-inference",
        message_count=3,
    ))

    return CompactionScenario(
        name="inference_mixed",
        description="事实 + 推断混杂，验证两者不得合并",
        messages=[
            _msg("user", "两个 timer 停了 12 小时，为什么", "m-1"),
            _msg("assistant", "实测开机 +86s 起 manager、+94s 起 timer，OnBootSec=90s 已过去", "m-2"),
            _msg("assistant", "根盘增长我猜可能和快照累积有关，但没验证过占比", "m-3"),
        ],
        expected_state=st,
        probe_expectations={
            "decision": ["OnStartupSec"],
            "evidence": ["m-2"],
        },
        invariants=[
            "inferences 不得被提升为 decisions",
            "推断条目必须保留 confidence",
            "evidence_refs 不得包含推断内容",
        ],
    )


# ── 场景 4：空/退化输入 ───────────────────────────────


def scenario_sparse() -> CompactionScenario:
    """稀疏场景：上游本就没什么证据。

    用途：验证 `evidence_absent` 豁免逻辑——此时探针低分
    **不应**被归因为模型缺陷（否则趋势数据会被污染）。
    """
    st = new_empty_state(session_intent="")
    st.set_cursor(SourceCursor(
        session_id="scenario-sparse",
        source_path="/fixtures/sparse.jsonl",
        inode=1004,
        byte_offset=64,
        last_message_id="m-1",
        observed_size=64,
        prefix_hash="fixture-hash-sparse",
        message_count=1,
    ))

    return CompactionScenario(
        name="sparse",
        description="几乎无内容，验证 evidence_absent 豁免",
        messages=[_msg("user", "在吗", "m-1")],
        expected_state=st,
        probe_expectations={},
        invariants=[
            "空状态必须通过 schema 校验",
            "低分必须标 evidence_absent，不计入严格 SLO",
        ],
    )


# ── 注册表 ────────────────────────────────────────────

ALL_SCENARIOS = (
    scenario_work_continuity,
    scenario_constraint_heavy,
    scenario_inference_mixed,
    scenario_sparse,
)


def load_all() -> list[CompactionScenario]:
    """加载全部场景（每次返回新实例，避免测试间互相污染）。"""
    return [factory() for factory in ALL_SCENARIOS]


def load_by_name(name: str) -> CompactionScenario:
    for factory in ALL_SCENARIOS:
        sc = factory()
        if sc.name == name:
            return sc
    raise KeyError(f"未知场景: {name!r}，可用: {[f().name for f in ALL_SCENARIOS]}")
