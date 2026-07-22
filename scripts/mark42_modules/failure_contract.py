"""
Mark42 v3 §3.6.2 · R13-D 降级响应契约 (Failure Contract)

按 v3 §3.6.2 钉死的 9 字段降级响应契约实现：
- 每个核心模块在降级/失败时输出结构化 9 字段契约
- 自动生成 FAILURE.md 人类可读报告
- 核心恢复时自动清理 FAILURE.md

9 字段规范：
  status: 状态 (ok / degraded / failed / unknown)
  core_id: 核心 ID
  core_name: 人类可读名称
  criticality: 重要性等级 (critical / optional / degradable)
  missing_capabilities: 缺失能力列表
  fallback_active: 当前启用的兜底方案
  auto_recovery_in_progress: 是否正在自动恢复
  estimated_recovery: 预计恢复时间
  user_action_required: 是否需要用户干预
  reason: 失败原因
"""

from __future__ import annotations

from .log_setup import get_logger

logger = get_logger(__name__)

from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

CST = timezone(timedelta(hours=8))

# ── 常量 ─────────────────────────────────────────────

CORE_REGISTRY_DIR = Path.home() / ".local" / "state" / "openclaw" / "mark42" / "core-registry"


def _core_failure_path(core_id: str) -> Path:
    """获取核心的 FAILURE.md 文件路径。"""
    return CORE_REGISTRY_DIR / core_id / "FAILURE.md"

# 8 个核心的预定义配置：名称、缺失能力、兜底描述
CORE_FAILURE_CONFIG: dict[str, dict[str, Any]] = {
    "core_1_main_consciousness": {
        "core_name": "主意识引擎",
        "missing_capabilities": [
            "高层推理",
            "复杂决策",
            "多步骤规划",
            "自主意识判断",
        ],
        "fallbacks": {
            "degraded": "降级到 armor_consciousness (agnes-2.0-flash)",
            "failed": "完全降级到 v2 规则引擎（无 LLM 推理）",
        },
    },
    "core_2_armor_consciousness": {
        "core_name": "铠甲意识层",
        "missing_capabilities": [
            "上下文压缩优化",
            "冗余信息自动过滤",
            "token 智能管理",
        ],
        "fallbacks": {
            "degraded": "降级到简单截断策略",
            "failed": "无压缩，直接使用原始上下文",
        },
    },
    "core_3_memory_vector_engine": {
        "core_name": "记忆向量引擎",
        "missing_capabilities": [
            "语义相似度检索",
            "L2.5 记忆召回",
            "上下文语义关联",
        ],
        "fallbacks": {
            "degraded": "降级到 L1 关键词匹配",
            "failed": "无记忆检索，仅依赖当前上下文",
        },
    },
    "core_4_text_compressor": {
        "core_name": "文本压缩引擎",
        "missing_capabilities": [
            "智能文本摘要",
            "语义保留压缩",
            "长文本自动折叠",
        ],
        "fallbacks": {
            "degraded": "降级到简单截断",
            "failed": "无压缩，完整保留所有文本",
        },
    },
    "core_5_code_understand": {
        "core_name": "代码理解引擎",
        "missing_capabilities": [
            "代码语义分析",
            "跨文件引用追踪",
            "复杂度评估",
        ],
        "fallbacks": {
            "degraded": "降级到关键词搜索",
            "failed": "跳过代码理解，直接展示原始代码",
        },
    },
    "core_6_log_classify": {
        "core_name": "日志分类引擎",
        "missing_capabilities": [
            "智能日志分类",
            "错误模式识别",
            "日志优先级判断",
        ],
        "fallbacks": {
            "degraded": "降级到按来源分类",
            "failed": "不分类，全部展示",
        },
    },
    "core_7_pii_redact": {
        "core_name": "PII 脱敏引擎",
        "missing_capabilities": [
            "敏感信息智能识别",
            "电话号码/邮箱/身份证自动脱敏",
            "信用卡号 Luhn 校验",
        ],
        "fallbacks": {
            "degraded": "降级到正则匹配脱敏",
            "failed": "无脱敏，可能暴露敏感信息",
        },
    },
    "core_8_anomaly_detect": {
        "core_name": "异常检测引擎",
        "missing_capabilities": [
            "行为异常检测",
            "性能指标异常识别",
            "趋势预测告警",
        ],
        "fallbacks": {
            "degraded": "降级到固定阈值检测",
            "failed": "无异常检测，完全依赖人工检查",
        },
    },
}


# ── 数据类 ───────────────────────────────────────────


@dataclass
class FailureContract:
    """R13-D 降级响应契约（9 字段）。"""

    status: str  # ok / degraded / failed / unknown
    core_id: str
    core_name: str
    criticality: str  # critical / optional / degradable
    missing_capabilities: list[str]
    fallback_active: str
    auto_recovery_in_progress: bool
    estimated_recovery: str
    user_action_required: bool
    reason: str

    def to_dict(self) -> dict[str, Any]:
        """转换为字典格式。"""
        return asdict(self)

    def is_ok(self) -> bool:
        """是否正常状态。"""
        return self.status == "ok"

    def is_failed(self) -> bool:
        """是否完全失败。"""
        return self.status == "failed"

    def is_degraded(self) -> bool:
        """是否降级状态。"""
        return self.status == "degraded"


# ── Contract 生成器 ──────────────────────────────────


class FailureContractGenerator:
    """根据 core_id 和状态生成 FailureContract。"""

    def __init__(self):
        self._core_config = CORE_FAILURE_CONFIG

    def generate(
        self,
        core_id: str,
        status: str,
        criticality: str,
        reason: str = "",
        auto_recovery: bool = False,
        estimated_recovery: str = "未知",
        user_action_required: bool = False,
    ) -> FailureContract:
        """
        生成 FailureContract。

        Args:
            core_id: 核心 ID
            status: 状态 (ok / degraded / failed / unknown)
            criticality: 重要性等级
            reason: 失败原因
            auto_recovery: 是否正在自动恢复
            estimated_recovery: 预计恢复时间
            user_action_required: 是否需要用户干预

        Returns:
            FailureContract 实例
        """
        config = self._core_config.get(core_id, {})
        core_name = config.get("core_name", core_id)

        if status == "ok":
            return FailureContract(
                status="ok",
                core_id=core_id,
                core_name=core_name,
                criticality=criticality,
                missing_capabilities=[],
                fallback_active="",
                auto_recovery_in_progress=False,
                estimated_recovery="",
                user_action_required=False,
                reason="",
            )

        # 状态为 degraded/failed/unknown
        missing_capabilities = config.get("missing_capabilities", [])
        fallbacks = config.get("fallbacks", {})

        if status in ("degraded", "down"):
            fallback_active = fallbacks.get("degraded", fallbacks.get("failed", "无兜底方案"))
        elif status == "failed":
            fallback_active = fallbacks.get("failed", "无兜底方案")
        else:
            fallback_active = "状态未知，兜底方案待定"

        return FailureContract(
            status=status if status != "down" else "failed",
            core_id=core_id,
            core_name=core_name,
            criticality=criticality,
            missing_capabilities=missing_capabilities,
            fallback_active=fallback_active,
            auto_recovery_in_progress=auto_recovery,
            estimated_recovery=estimated_recovery,
            user_action_required=user_action_required,
            reason=reason,
        )

    def get_core_name(self, core_id: str) -> str:
        """获取核心的人类可读名称。"""
        return self._core_config.get(core_id, {}).get("core_name", core_id)

    def get_missing_capabilities(self, core_id: str) -> list[str]:
        """获取核心的缺失能力列表。"""
        return self._core_config.get(core_id, {}).get("missing_capabilities", [])


# ── FAILURE.md 渲染 ──────────────────────────────────


def render_failure_md(contract: FailureContract, generated_at: datetime | None = None) -> str:
    """
    将 FailureContract 渲染为人类可读的 FAILURE.md。

    Args:
        contract: FailureContract 实例
        generated_at: 生成时间，默认使用当前时间

    Returns:
        Markdown 格式的字符串
    """
    if generated_at is None:
        generated_at = datetime.now(CST)

    # 状态 emoji
    status_emoji = {
        "ok": "✅",
        "degraded": "⚠️",
        "failed": "❌",
        "unknown": "❓",
    }.get(contract.status, "❓")

    # 重要性等级提示
    criticality_badge = {
        "critical": "🔴 关键核心",
        "degradable": "🟡 可降级核心",
        "optional": "🟢 可选核心",
    }.get(contract.criticality, "⚪ 未知等级")

    missing_caps_md = "\n".join([f"- {cap}" for cap in contract.missing_capabilities])
    if not missing_caps_md:
        missing_caps_md = "- 无"

    lines = [
        f"# FAILURE: {contract.core_name} ({contract.core_id})",
        "",
        f"> 生成时间：{generated_at.strftime('%Y-%m-%d %H:%M:%S %Z')}",
        f"> 状态：{status_emoji} {contract.status.upper()}",
        f"> 重要性：{criticality_badge}",
        "",
        "## 故障摘要",
        "",
        f"**核心 ID**: `{contract.core_id}`",
        "",
        f"**原因**: {contract.reason or '未提供原因'}",
        "",
        "## 影响分析",
        "",
        "**缺失的能力**:",
        "",
        missing_caps_md,
        "",
        "## 当前状态",
        "",
        f"- **兜底方案**: {contract.fallback_active}",
        f"- **自动恢复中**: {'是' if contract.auto_recovery_in_progress else '否'}",
        f"- **预计恢复时间**: {contract.estimated_recovery}",
        f"- **需要用户干预**: {'是' if contract.user_action_required else '否'}",
        "",
        "## 建议操作",
        "",
    ]

    if contract.criticality == "critical" and contract.is_failed():
        lines.extend([
            "⚠️ **关键核心失败，系统功能严重受限！**",
            "",
            "请立即执行以下操作：",
            "1. 检查网络连接和 API 服务状态",
            "2. 查看系统日志获取详细错误信息",
            "3. 如有必要，手动重启相关服务",
        ])
    elif contract.is_degraded():
        lines.extend([
            "ℹ️ 系统已降级但仍可正常使用。",
            "",
            "建议操作：",
            f"- 检查 {contract.core_name} 的健康状态",
            "- 观察相关服务是否有异常日志",
        ])
    else:
        lines.extend([
            "ℹ️ 请查看系统日志获取更多详细信息。",
        ])

    lines.extend([
        "",
        "---",
        "",
        "*本文件由 Mark42 v3 R13-D 降级响应契约自动生成。*",
        f"*当 {contract.core_id} 恢复健康时，本文件将被自动删除。*",
    ])

    return "\n".join(lines)


# ── 文件操作 ─────────────────────────────────────────


def write_failure_md(core_id: str, contract: FailureContract) -> Path:
    """
    写入 FAILURE.md 到核心目录。

    Args:
        core_id: 核心 ID
        contract: FailureContract 实例

    Returns:
        写入的文件路径
    """
    core_dir = CORE_REGISTRY_DIR / core_id
    core_dir.mkdir(parents=True, exist_ok=True)
    md_path = core_dir / "FAILURE.md"

    md_content = render_failure_md(contract)
    md_path.write_text(md_content, encoding="utf-8")
    logger.info(f"已写入 FAILURE.md: {md_path}")

    return md_path


def remove_failure_md(core_id: str) -> bool:
    """
    删除核心目录中的 FAILURE.md。

    Args:
        core_id: 核心 ID

    Returns:
        是否成功删除（文件存在且被删除返回 True）
    """
    md_path = CORE_REGISTRY_DIR / core_id / "FAILURE.md"
    if md_path.exists():
        md_path.unlink()
        logger.info(f"已删除 FAILURE.md: {md_path}")
        return True
    return False


def failure_md_exists(core_id: str) -> bool:
    """检查 FAILURE.md 是否存在。"""
    return (CORE_REGISTRY_DIR / core_id / "FAILURE.md").exists()


# ── 便捷函数 ─────────────────────────────────────────


def _get_generator() -> FailureContractGenerator:
    """获取全局 ContractGenerator 实例。"""
    return FailureContractGenerator()


def create_contract_for_core(
    core_id: str,
    status: str,
    criticality: str,
    reason: str = "",
) -> FailureContract:
    """
    为核心创建 FailureContract 的便捷函数。

    Args:
        core_id: 核心 ID
        status: 状态
        criticality: 重要性等级
        reason: 失败原因

    Returns:
        FailureContract 实例
    """
    generator = _get_generator()

    # 根据状态和重要性智能判断其他字段
    auto_recovery = criticality != "critical"
    estimated_recovery = {
        "critical": "需人工干预",
        "degradable": "30 秒",
        "optional": "10 秒",
    }.get(criticality, "未知")
    user_action_required = criticality == "critical" and status in ("failed", "down")

    return generator.generate(
        core_id=core_id,
        status=status,
        criticality=criticality,
        reason=reason,
        auto_recovery=auto_recovery,
        estimated_recovery=estimated_recovery,
        user_action_required=user_action_required,
    )
