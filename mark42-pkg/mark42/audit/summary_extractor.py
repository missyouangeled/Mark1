"""摘要提取器：从 session 读 compact 后的 compaction 摘要。

OpenClaw 实现：从 session SQLite/JSONL 读 compaction 条目。
其他平台：实现 SummaryExtractor 接口即可。
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

from ..utils import _find_active_session

# ── 接口 ──────────────────────────────────────────────


@runtime_checkable
class SummaryExtractor(Protocol):
    """摘要提取器接口 -- 不同平台实现不同。"""

    def find_post_compact_summary(self, compact_timestamp: str) -> dict[str, Any] | None:
        """找到 compact 后的摘要。

        Args:
            compact_timestamp: compact 完成时间

        Returns:
            {"source": "openclaw-session", "path": str, "timestamp": str}
            或 None
        """
        ...

    def extract_summary_text(self, summary: dict[str, Any]) -> str:
        """提取摘要文本。"""
        ...


# ── OpenClaw 默认实现 ─────────────────────────────────


class OpenClawSummaryExtractor:
    """从 OpenClaw session 读 compaction 摘要。

    OpenClaw compact 后会在 session transcript 里写入一条 compaction 条目，
    包含 LLM 生成的摘要文本。

    实现策略：
        1. 找到活跃 session 的 JSONL 文件
        2. 从末尾搜索 compaction 条目（role=system, content 以 <summary> 开头
           或包含 compaction 标记）
        3. 如果 JSONL 不存在，尝试从 SQLite 读（通过 openclaw CLI）
    """

    # OpenClaw compaction 条目的标记
    # OpenClaw 的 compaction 条目格式：{"type": "compaction", "summary": "...", ...}
    _COMPACTION_MARKERS = [
        '"type":"compaction"',      # OpenClaw 标准 compaction 条目
        '"type": "compaction"',     # 带空格的变体
    ]

    def find_post_compact_summary(self, compact_timestamp: str) -> dict[str, Any] | None:
        """找到 compact 后的摘要。"""
        session_path = _find_active_session()
        if session_path is None or not session_path.exists():
            return None

        return {
            "source": "openclaw-session",
            "path": str(session_path),
            "timestamp": compact_timestamp,
        }

    def extract_summary_text(self, summary: dict[str, Any]) -> str:
        """从 session 提取 compaction 摘要文本。"""
        session_path = Path(summary.get("path", ""))
        if not session_path.exists():
            return self._extract_from_sqlite(summary)

        # 尝试从 JSONL 读
        text = self._extract_from_jsonl(session_path)
        if text:
            return text

        # JSONL 读取失败，尝试 SQLite
        return self._extract_from_sqlite(summary)

    def _extract_from_jsonl(self, session_path: Path) -> str:
        """从 JSONL 文件读最后几条消息，找 compaction 摘要。

        OpenClaw compaction 条目格式：
            {"type": "compaction", "summary": "## Decisions\n...", ...}
        摘要文本在 `summary` 字段里，不在 `content` 字段里。
        """
        try:
            # 读最后 100 行（compaction 摘要通常在最近）
            lines = []
            with open(session_path, encoding="utf-8", errors="replace") as f:
                # 从末尾读
                f.seek(0, 2)
                size = f.tell()
                chunk = min(size, 50000)  # 读最后 50KB
                f.seek(max(0, size - chunk))
                lines = f.readlines()

            # 从后往前找 compaction 条目
            for line in reversed(lines):
                line = line.strip()
                if not line:
                    continue
                try:
                    msg = json.loads(line)
                except (json.JSONDecodeError, TypeError):
                    continue

                # OpenClaw compaction 条目：type == "compaction"
                if msg.get("type") == "compaction":
                    # 摘要文本在 summary 字段里
                    summary = msg.get("summary", "")
                    # 字段可能是任意 JSON 类型，只接受非空字符串（P3-4）
                    if isinstance(summary, str) and summary:
                        return summary
                    # summary 为空时，尝试 details 里的补充信息
                    details = msg.get("details", {})
                    if isinstance(details, dict):
                        parts = []
                        if details.get("readFiles"):
                            parts.append(f"读取文件: {', '.join(details['readFiles'][:5])}")
                        if details.get("modifiedFiles"):
                            parts.append(f"修改文件: {', '.join(details['modifiedFiles'][:5])}")
                        if parts:
                            return "\n".join(parts)

                # 兼容旧格式：有些版本 compaction 摘要在 system 消息的 content 里
                content = msg.get("content", "")
                role = msg.get("role", "")
                if (
                    role == "system"
                    and isinstance(content, str)
                    and "<summary>" in content
                ):
                    return content

            # 如果没找到明确标记，返回最后几条消息作为"当前上下文"
            # 这能让我们检查 compact 后实际保留了什么
            tail_lines = lines[-20:] if len(lines) > 20 else lines
            tail_text = ""
            for line in tail_lines:
                line = line.strip()
                if not line:
                    continue
                try:
                    msg = json.loads(line)
                    role = msg.get("role", "")
                    content = msg.get("content", "")
                    if content:
                        tail_text += f"[{role}] {content}\n"
                except (json.JSONDecodeError, TypeError):
                    continue

            return tail_text or "(empty session)"

        except OSError:
            return ""

    def _extract_from_sqlite(self, summary: dict[str, Any]) -> str:
        """从 SQLite 读 compaction 摘要（通过 openclaw CLI）。"""
        try:
            result = subprocess.run(
                ["openclaw", "sessions", "history", "--limit", "10",
                 "--format", "json"],
                capture_output=True, text=True, timeout=15,
            )
            if result.returncode == 0 and result.stdout:
                # 解析输出找 compaction 摘要
                lines = result.stdout.strip().splitlines()
                for line in reversed(lines):
                    try:
                        msg = json.loads(line)
                        content = msg.get("content", "")
                        if not isinstance(content, str):
                            continue
                        if any(
                            marker in content
                            for marker in self._COMPACTION_MARKERS
                        ):
                            return content
                    except (json.JSONDecodeError, TypeError):
                        continue

                # 没找到明确摘要，返回最近的对话
                return result.stdout[-3000:] if result.stdout else "(no data)"
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
            pass

        return ""
