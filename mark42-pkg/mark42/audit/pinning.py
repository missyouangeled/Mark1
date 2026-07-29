"""约束保护：compact 后将关键约束重新注入上下文。

灵感来源：
    - arxiv 2606.22528 "Governance Decay" 论文的 Constraint Pinning
    - Claude Code 的 PostCompact hook
    - OpenClaw 的 postCompactionSections

工作原理：
    1. 从 SOUL.md / AGENTS.md / USER.md 提取不可丢弃的约束（pinned constraints）
    2. compact 后将这些约束注入为 system 消息
    3. 注入方式：broker 事件 -> armor 状态 -> 下一个 turn 的上下文

设计原则：
    - 极低耦合：不修改 OpenClaw 的 compact 流程
    - 只读不写：只从文件提取约束，不修改文件
    - 可配置：pinned files 列表可配置
    - 失败安全：注入失败不影响主流程
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, List, Optional, Any

from ..config import WORKSPACE


# ── 默认 pinned 文件 ─────────────────────────────────

DEFAULT_PINNED_FILES = [
    "SOUL.md",
    "USER.md",
    "AGENTS.md",
]

# 每个文件最多提取的行数（避免注入过多 token）
MAX_LINES_PER_FILE = 30

# 注入的最大总字符数
MAX_TOTAL_CHARS = 4000


class ConstraintPinner:
    """从关键文件提取约束，compact 后重新注入。

    用法：
        pinner = ConstraintPinner()
        pinned = pinner.extract_pinned_constraints()
        # pinned 是一个字符串，包含所有关键约束
        # compact 后将其注入为 system 消息或 broker 事件
    """

    def __init__(self, workspace: Path | None = None) -> None:
        self.workspace = workspace or WORKSPACE

    def extract_pinned_constraints(self) -> str:
        """从 pinned 文件提取关键约束。

        Returns:
            约束文本，可直接注入为 system 消息
        """
        sections: List[str] = []
        total_chars = 0

        for fname in DEFAULT_PINNED_FILES:
            fpath = self.workspace / fname
            if not fpath.exists():
                continue

            try:
                text = fpath.read_text(encoding="utf-8", errors="replace")
                extracted = self._extract_essential_lines(text, fname)
                if extracted and total_chars + len(extracted) <= MAX_TOTAL_CHARS:
                    sections.append(extracted)
                    total_chars += len(extracted)
            except Exception:
                continue

        if not sections:
            return ""

        header = "## Post-Compact 约束重注入\n\n"
        header += "以下是 compact 前的关键约束，必须继续遵守：\n\n"
        return header + "\n---\n".join(sections)

    def _extract_essential_lines(self, text: str, filename: str) -> str:
        """从文件中提取最关键的行。

        策略：
            - SOUL.md: 提取语言规则 + 核心准则 + 边界
            - USER.md: 提取名字 + 时区 + 称呼
            - AGENTS.md: 提取基本规则摘要
        """
        lines = text.splitlines()
        essential: List[str] = []
        count = 0

        if filename == "SOUL.md":
            # 提取语言锁定规则和核心准则
            for line in lines:
                stripped = line.strip()
                # 语言规则是最重要的
                if "中文" in stripped or "English" in stripped or "语言" in stripped:
                    essential.append(stripped)
                    count += 1
                # 核心准则
                elif stripped.startswith("**") and stripped.endswith("**") and count < MAX_LINES_PER_FILE:
                    essential.append(stripped)
                    count += 1
                # 边界
                elif stripped.startswith("- ") and ("私密" in stripped or "不" in stripped or "前" in stripped):
                    if count < MAX_LINES_PER_FILE:
                        essential.append(stripped)
                        count += 1

        elif filename == "USER.md":
            # 提取名字、时区、称呼
            for line in lines:
                stripped = line.strip()
                if stripped.startswith("- **") and ("**" in stripped[4:]):
                    if any(kw in stripped for kw in ["Name", "call", "Timezone", "Birthday", "Notes"]):
                        essential.append(stripped)
                        count += 1
                        if count >= MAX_LINES_PER_FILE:
                            break

        elif filename == "AGENTS.md":
            # 提取基本规则（包括短规则）
            for line in lines:
                stripped = line.strip()
                if stripped.startswith("- ") and len(stripped) > 5:
                    essential.append(stripped)
                    count += 1
                    if count >= MAX_LINES_PER_FILE:
                        break

        if not essential:
            return ""

        return f"### {filename}\n\n" + "\n".join(essential)

    def inject_via_broker(self, constraints: str | None = None) -> bool:
        """通过 broker 事件注入约束。

        armor 的下一个 context-guard 周期会读到这个事件，
        然后在回复前把约束注入上下文。

        Returns:
            True 表示注入成功
        """
        if constraints is None:
            constraints = self.extract_pinned_constraints()

        if not constraints:
            return False

        try:
            from ..utils import _append_broker, _now_iso
            _append_broker(
                "armor",
                "mark42.armor.audit.constraint_reinject",
                "Post-Compact 约束重注入",
                "info",
                constraints[:200],  # broker detail 限长
                {
                    "timestamp": _now_iso(),
                    "constraintsLength": len(constraints),
                    "source": "constraint_pinner",
                },
            )
            return True
        except Exception:
            return False

    def inject_to_file(self, constraints: str | None = None) -> Optional[str]:
        """将约束写入临时文件，供 armor 下次检查时读取。

        Returns:
            文件路径，或 None 表示失败
        """
        if constraints is None:
            constraints = self.extract_pinned_constraints()

        if not constraints:
            return None

        try:
            from ..config import ARMOR_STATE
            from ..utils import _now_iso

            inject_dir = ARMOR_STATE / "audit" / "injections"
            inject_dir.mkdir(parents=True, exist_ok=True)

            from datetime import datetime
            ts = datetime.now().strftime("%Y%m%d-%H%M%S")
            inject_path = inject_dir / f"pinned-{ts}.md"
            inject_path.write_text(constraints, encoding="utf-8")

            return str(inject_path)
        except Exception:
            return None
