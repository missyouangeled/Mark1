"""快照读取器：从数据盘读 compact 前的快照，提取关键信息。

OpenClaw 实现：从 /mnt/data/openclaw/session-backup/ 读最新快照。
其他平台：实现 SnapshotReader 接口即可。

抽取的信息分 5 类：
    identity:       用户名、AI名、称呼
    preferences:    规则、习惯、禁忌
    projects:       项目状态、TODO
    decisions:      技术方案、架构决策
    recent_topics:  最近对话话题
"""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

# ── 数据盘快照根目录 ──────────────────────────────────

_SNAPSHOT_ROOT = Path("/mnt/data/openclaw/session-backup")


# ── 接口 ──────────────────────────────────────────────


@runtime_checkable
class SnapshotReader(Protocol):
    """快照读取器接口 -- 不同平台实现不同。"""

    def find_latest_before(self, timestamp: str) -> dict[str, Any] | None:
        """找到指定时间之前最新的快照。

        Args:
            timestamp: ISO-8601 时间戳

        Returns:
            {"source": "data-disk", "path": str, "timestamp": str}
            或 None（找不到）
        """
        ...

    def extract_key_info(self, snapshot: dict[str, Any]) -> dict[str, list[str]]:
        """从快照中提取关键信息。

        Returns:
            {
                "identity": ["用户名", "AI名", ...],
                "preferences": ["规则1", ...],
                "projects": ["项目状态1", ...],
                "decisions": ["决策1", ...],
                "recent_topics": ["话题1", ...],
            }
        """
        ...


# ── OpenClaw 默认实现 ─────────────────────────────────


class OpenClawSnapshotReader:
    """从数据盘 session-backup 读快照。

    快照目录结构：
        snapshot-YYYY-MM-DDTHHMMSS/
            context-summary.md      (对话摘要)
            daily-YYYY-MM-DD-transcript.md  (对话原文)
            MEMORY.md               (长期记忆)
            SOUL.md                 (人格)
            USER.md                 (用户信息)
            session-state.json      (session 元数据)
    """

    def __init__(self, snapshot_root: Path | None = None) -> None:
        self.root = snapshot_root or _SNAPSHOT_ROOT

    def find_latest_before(self, timestamp: str) -> dict[str, Any] | None:
        """找到指定时间之前最新的快照目录。"""
        if not self.root.exists():
            return None

        try:
            target_ts = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        except (ValueError, TypeError):
            target_ts = datetime.now()

        snapshots = []
        for entry in self.root.iterdir():
            if not entry.is_dir() or not entry.name.startswith("snapshot-"):
                continue
            # 解析目录名中的时间戳: snapshot-2026-07-29T105432
            ts_str = entry.name.replace("snapshot-", "")
            try:
                snap_ts = datetime.strptime(ts_str, "%Y-%m-%dT%H%M%S")
            except ValueError:
                continue
            if snap_ts <= target_ts:
                snapshots.append((snap_ts, entry))

        if not snapshots:
            return None

        snapshots.sort(key=lambda x: x[0], reverse=True)
        snap_ts, snap_path = snapshots[0]

        return {
            "source": "data-disk",
            "path": str(snap_path),
            "timestamp": snap_ts.isoformat(),
        }

    def extract_key_info(self, snapshot: dict[str, Any]) -> dict[str, list[str]]:
        """从快照中提取 5 类关键信息。"""
        snap_path = Path(snapshot.get("path", ""))
        if not snap_path.exists():
            return {cat: [] for cat in
                    ["identity", "preferences", "projects", "decisions", "recent_topics"]}

        info: dict[str, list[str]] = {
            "identity": [],
            "preferences": [],
            "projects": [],
            "decisions": [],
            "recent_topics": [],
            "artifacts": [],
        }

        # 1. 从 USER.md / SOUL.md / MEMORY.md 提取身份和偏好
        info["identity"] = self._extract_identity(snap_path)
        info["preferences"] = self._extract_preferences(snap_path)

        # 2. 从 context-summary.md 提取项目、决策、文件变更
        summary_path = snap_path / "context-summary.md"
        if summary_path.exists():
            text = summary_path.read_text(encoding="utf-8", errors="replace")
            info["projects"] = self._extract_projects(text)
            info["decisions"] = self._extract_decisions(text)
            info["recent_topics"] = self._extract_recent_topics(text)
            info["artifacts"] = self._extract_artifacts(text)

        # 3. 从 daily transcript 补充近期话题和文件变更
        transcripts = sorted(snap_path.glob("daily-*-transcript.md"))
        if transcripts:
            transcript_text = transcripts[-1].read_text(encoding="utf-8", errors="replace")
            topics = self._extract_topics_from_transcript(transcript_text)
            # 合并去重
            for t in topics:
                if t not in info["recent_topics"]:
                    info["recent_topics"].append(t)
            # 从 transcript 补充文件变更
            transcript_artifacts = self._extract_artifacts_from_transcript(transcript_text)
            for a in transcript_artifacts:
                if a not in info["artifacts"]:
                    info["artifacts"].append(a)

        return info

    # ── 内部提取方法 ──────────────────────────────────

    def _extract_identity(self, snap_path: Path) -> list[str]:
        """从 USER.md / SOUL.md 提取身份信息。"""
        items = []

        for fname in ["USER.md", "SOUL.md", "MEMORY.md"]:
            fpath = snap_path / fname
            if not fpath.exists():
                continue
            text = fpath.read_text(encoding="utf-8", errors="replace")

            if fname == "USER.md":
                # 提取 Name / 称呼
                for pattern in [
                    r"\*\*Name:\*\*\s*(.+)",
                    r"\*\*What to call them:\*\*\s*(.+)",
                ]:
                    m = re.search(pattern, text)
                    if m:
                        items.append(f"用户: {m.group(1).strip()}")

            if fname == "SOUL.md":
                # AI 名
                m = re.search(r"名字.*?[:：]\s*(.+)", text)
                if m:
                    items.append(f"AI: {m.group(1).strip()}")

            if fname == "MEMORY.md":
                m = re.search(r"我的名字是[\"\"'](.+?)[\"\"']", text)
                if m:
                    items.append(f"AI名: {m.group(1)}")
                # 用户生日
                m = re.search(r"生日.*?[:：]\s*(.+)", text)
                if m:
                    items.append(f"用户生日: {m.group(1).strip()}")

        return items

    def _extract_preferences(self, snap_path: Path) -> list[str]:
        """从 MEMORY.md + memory/rules/ 提取偏好规则。

        快照里可能不包含 memory/rules/ 目录，但如果包含，
        优先从里面提取详细偏好规则。
        """
        items = []
        mem_path = snap_path / "MEMORY.md"
        if mem_path.exists():
            text = mem_path.read_text(encoding="utf-8", errors="replace")
            # 提取标题行和关键规则
            for line in text.splitlines():
                line = line.strip()
                if line.startswith("## ") or line.startswith("### "):
                    # 跳过纯结构标题，保留有意义的
                    title = line.lstrip("# ").strip()
                    if title and not title.startswith("⚠️"):
                        items.append(title)
                elif line.startswith("- **") and ("**：" in line or "**:" in line):
                    # 提取粗体规则项
                    m = re.match(r"- \*\*(.+?)\*\*[：:]\s*(.+)", line)
                    if m:
                        items.append(f"{m.group(1)}: {m.group(2)}")

        # 从 memory/rules/ 目录补充详细偏好规则
        rules_dir = snap_path / "memory" / "rules"
        if rules_dir.exists():
            for rule_file in sorted(rules_dir.glob("*.md")):
                try:
                    rule_text = rule_file.read_text(encoding="utf-8", errors="replace")
                    for line in rule_text.splitlines():
                        line = line.strip()
                        # 提取规则标题和关键规则行
                        if line.startswith("## ") and not line.startswith("## ⚠"):
                            title = line.lstrip("# ").strip()
                            if title and title not in items:
                                items.append(f"[{rule_file.stem}] {title}")
                        elif line.startswith("- ") and len(line) > 10:
                            # 简短规则行，截取前 80 字符
                            item = line[2:][:80]
                            if item not in items:
                                items.append(item)
                except Exception:  # noqa: S112 (跳过损坏行，继续解析)
                    continue

        return items[:30]  # 限制数量避免过长

    def _extract_projects(self, text: str) -> list[str]:
        """从 context-summary 提取项目状态。"""
        items = []
        # 提取带「项目」「Project」「Mark42」等关键词的段落
        for m in re.finditer(r"(?:项目|Project|Mark42|TODO)[：:]\s*(.+)", text):
            item = m.group(1).strip()[:100]
            if item and item not in items:
                items.append(item)
        return items[:10]

    def _extract_decisions(self, text: str) -> list[str]:
        """从 context-summary 提取决策。"""
        items = []
        for m in re.finditer(r"(?:决策|方案|决定|架构|策略)[：:]\s*(.+)", text):
            item = m.group(1).strip()[:100]
            if item and item not in items:
                items.append(item)
        return items[:10]

    def _extract_recent_topics(self, text: str) -> list[str]:
        """从 context-summary 提取近期话题。"""
        items = []
        # 提取对话摘要里的行
        for line in text.splitlines():
            line = line.strip()
            if line.startswith("- ") and len(line) > 10:
                # 简短截取
                item = line[2:][:80]
                if item not in items:
                    items.append(item)
        return items[:15]

    def _extract_artifacts(self, text: str) -> list[str]:
        """从 context-summary 提取修改的文件列表。

        Factory.ai 研究发现 compact 后最容易丢的是「改了哪些文件」。
        """
        items = []
        # 匹配 edit/write/tool result 里提到的文件路径
        for m in re.finditer(r'(?:edit|write|read|修改|创建|删除|更新)[：:]?\s*[`"]?(\S+\.(?:py|md|json|js|ts|tsx|sh|yml|yaml|toml|txt))[`"]?', text, re.IGNORECASE):
            path = m.group(1).strip()
            if path and path not in items:
                items.append(path)
        # 也匹配明确的文件路径模式
        for m in re.finditer(r'[`"]((?:~/|/|\.\./)?[\w/.-]+\.(?:py|md|json|js|ts|tsx|sh|yml|yaml|toml))[`":]', text):
            path = m.group(1).strip()
            if path and path not in items:
                items.append(path)
        return items[:15]

    def _extract_artifacts_from_transcript(self, text: str) -> list[str]:
        """从 daily transcript 提取文件变更。"""
        items = []
        # 匹配 Tool result 里的 edit/write 成功消息
        for m in re.finditer(r'(?:Successfully|成功|写入|修改|创建)[：:]?\s*[`"]?(\S+\.(?:py|md|json|js|ts|tsx|sh|yml|yaml|toml|txt))[`":]?', text):
            path = m.group(1).strip()
            if path and path not in items:
                items.append(path)
        return items[:10]

    def _extract_topics_from_transcript(self, text: str) -> list[str]:
        """从 daily transcript 提取话题。"""
        items = []
        # 提取用户消息
        for m in re.finditer(r"贾维斯[·•]?\s*\d{2}:\d{2}[：:]\s*(.+)", text):
            item = m.group(1).strip()[:80]
            if item and item not in items:
                items.append(item)
        return items[:10]
