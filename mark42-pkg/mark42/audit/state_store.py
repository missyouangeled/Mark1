"""ContextState 版本化持久化（方案 44 建设项 A / Phase 2）。

职责
----
    - 原子写入新版状态，保留历史版本（方案 §4.3 第 5 步）
    - 按 keep_versions 轮替
    - 回滚时把状态目录原子标记为 `.archived`，**不计入轮替**（方案 §14）
    - 读取上一版状态供增量合并使用

⚠️ 为什么坚持原子写
------------------
状态文件是增量压缩的唯一真相来源。若写入中途崩溃留下截断的 JSON，
下一轮读回来会解析失败 → 全量回退（还算安全）；
但更坏的情况是**解析成功却内容不全** —— 那会静默丢掉决策与约束。
所以一律 tmp + fsync + os.replace。
"""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from ..context_state import ContextState, new_empty_state, validate_context_state

STATE_STORE_SCHEMA_VERSION = 1

#: 当前版本的固定文件名（软链语义：总指向最新）
CURRENT_FILENAME = "context-state.json"

#: 历史版本文件名格式
VERSION_PREFIX = "context-state-"
VERSION_SUFFIX = ".json"

#: 归档目录后缀（方案 §14：回滚状态不参与 keep_versions 轮替）
ARCHIVE_SUFFIX = ".archived"


@dataclass
class LoadResult:
    """读取结果。"""

    state: ContextState
    #: 是否读到了有效的历史状态（False = 新建的空状态）
    found: bool = False
    #: 读取失败原因（found=False 且非首次时有值）
    error: str = ""
    path: str = ""

    def is_fresh_start(self) -> bool:
        """是否属于「没有历史、从零开始」。"""
        return not self.found and not self.error


class StateStore:
    """版本化状态存储。"""

    def __init__(self, directory: Path | str, *, keep_versions: int = 20) -> None:
        self.dir = Path(directory)
        self.keep_versions = max(1, keep_versions)

    # ── 路径 ──────────────────────────────────────────

    @property
    def current_path(self) -> Path:
        return self.dir / CURRENT_FILENAME

    def _version_path(self, ts: str) -> Path:
        return self.dir / f"{VERSION_PREFIX}{ts}{VERSION_SUFFIX}"

    def versions(self) -> list[Path]:
        """按时间倒序返回历史版本（不含 current，不含归档目录）。"""
        if not self.dir.exists():
            return []
        files = [
            p for p in self.dir.glob(f"{VERSION_PREFIX}*{VERSION_SUFFIX}")
            if p.is_file()
        ]
        return sorted(files, key=lambda p: p.name, reverse=True)

    # ── 读 ────────────────────────────────────────────

    def load_current(self) -> LoadResult:
        """读当前状态。任何失败都返回空状态 + error，让调用方全量回退。"""
        path = self.current_path
        if not path.exists():
            return LoadResult(state=new_empty_state(), found=False,
                              path=str(path))
        try:
            raw = path.read_text(encoding="utf-8")
            data = json.loads(raw)
            state = ContextState.from_dict(data)
        except (OSError, json.JSONDecodeError, TypeError) as e:
            return LoadResult(state=new_empty_state(), found=False,
                              error=f"{type(e).__name__}: {e}", path=str(path))

        report = validate_context_state(state, require_evidence=False)
        if not report.ok:
            return LoadResult(
                state=new_empty_state(), found=False,
                error=f"历史状态未通过校验: {report.summary()}", path=str(path))

        return LoadResult(state=state, found=True, path=str(path))

    # ── 写 ────────────────────────────────────────────

    def save(self, state: ContextState, *, timestamp: str | None = None) -> str:
        """原子写入新版本并更新 current。

        Returns:
            新版本文件路径。
        """
        self.dir.mkdir(parents=True, exist_ok=True)
        ts = timestamp or datetime.now().strftime("%Y%m%d-%H%M%S-%f")
        blob = state.to_json()

        version_path = self._version_path(ts)
        _atomic_write_text(version_path, blob)
        _atomic_write_text(self.current_path, blob)

        self._rotate()
        return str(version_path)

    def _rotate(self) -> None:
        """保留最近 keep_versions 份历史版本。"""
        for old in self.versions()[self.keep_versions:]:
            try:
                old.unlink()
            except OSError:
                pass

    # ── 归档（回滚用）──────────────────────────────────

    def archive(self, *, reason: str = "") -> str | None:
        """把整个状态目录原子标记为已归档（方案 §14）。

        归档目录**不参与** keep_versions 轮替，也不会被自动删除，
        便于审计或重新升级。

        Returns:
            归档后的目录路径，或 None（目录不存在）。
        """
        if not self.dir.exists():
            return None
        ts = datetime.now().strftime("%Y%m%d-%H%M%S")
        target = self.dir.with_name(f"{self.dir.name}-{ts}{ARCHIVE_SUFFIX}")
        try:
            os.replace(self.dir, target)
        except OSError:
            return None
        if reason:
            try:
                (target / "ARCHIVE_REASON.txt").write_text(
                    reason, encoding="utf-8")
            except OSError:
                pass
        return str(target)

    def archived_dirs(self) -> list[Path]:
        """列出所有归档目录（供审计）。"""
        parent = self.dir.parent
        if not parent.exists():
            return []
        return sorted(
            p for p in parent.glob(f"{self.dir.name}-*{ARCHIVE_SUFFIX}")
            if p.is_dir()
        )

    # ── 观测 ──────────────────────────────────────────

    def stats(self) -> dict[str, Any]:
        cur = self.load_current()
        return {
            "dir": str(self.dir),
            "hasCurrent": cur.found,
            "loadError": cur.error,
            "versionCount": len(self.versions()),
            "keepVersions": self.keep_versions,
            "archivedCount": len(self.archived_dirs()),
            "itemCount": cur.state.item_count() if cur.found else 0,
            "fingerprint": cur.state.fingerprint() if cur.found else "",
        }


def _atomic_write_text(path: Path, text: str) -> None:
    """原子写文本：tmp → fsync → replace。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent),
                               prefix=path.name, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise
