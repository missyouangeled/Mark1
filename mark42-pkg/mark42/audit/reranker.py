"""Cross-Encoder Reranker 接口与适配器（方案 44 建设项 F / Phase 3 第二块）。

当前不足（方案 §9.1 校正）
--------------------------
`_rerank_available()` 是当前唯一相关代码，但其结果**不被搜索路径使用**。
实际功能层面没有 cross-encoder 接口、适配器或重排调用路径。

本模块从零新增实际 Reranker 接口、适配器和调用路径（方案 §9.3）。

设计原则
--------
- 模型不可用时不阻塞检索（降级到 hybrid 结果）
- 首选复用 QMD 真正支持 rerank 的命令
- 独立适配器可替换（未来可接入其他 reranker）

⚠️ 不做的事
-----------
- 不做 query expansion（QMD 的 rerank 命令会捆绑 expansion，本模块只用纯 rerank）
- 不自动下载模型（由用户预先安装）
- 不阻塞检索主流程
"""

from __future__ import annotations

import logging
import subprocess
from typing import Any, Protocol, runtime_checkable

logger = logging.getLogger(__name__)

#: rerank 超时（秒）
RERANK_TIMEOUT = 10

#: rerank 候选上限（方案 §9.2 candidate_n）
DEFAULT_CANDIDATE_N = 20

#: rerank 返回 top_k
DEFAULT_RERANK_TOP_K = 5


# ── 接口 ──────────────────────────────────────────────


@runtime_checkable
class Reranker(Protocol):
    """Cross-Encoder 重排器接口（方案 §9.3）。"""

    def rerank(
        self,
        query: str,
        candidates: list[dict[str, Any]],
        top_k: int = DEFAULT_RERANK_TOP_K,
    ) -> list[dict[str, Any]]:
        """对候选结果重排。

        Args:
            query: 查询文本
            candidates: 候选列表，每项至少含 content 字段
            top_k: 返回数量

        Returns:
            重排后的列表，每项含 rerank_score
        """
        ...

    def available(self) -> bool:
        """重排器是否可用。"""
        ...




# ── QMD Reranker 适配器 ───────────────────────────────


class QMDReranker:
    """使用 QMD 的 rerank 命令做 cross-encoder 重排。

    ⚠️ QMD 的 rerank 命令会捆绑 query expansion。
    若 expansion 不想要，需用 --no-expand 参数（如 QMD 支持）。
    若 QMD 版本不支持纯 rerank，整个适配器返回 available()=False，
    检索路径降级到 hybrid 结果。

    QMD rerank 命令格式（预期）：
        qmd rerank <query> --top-k <k> --json --no-expand
        stdin: JSON 数组 [{"content": "...", ...}, ...]
        stdout: JSON 数组 [{"content": "...", "score": 0.xx, ...}, ...]
    """

    def __init__(
        self,
        qmd_bin: str = "",
        timeout: int = RERANK_TIMEOUT,
    ) -> None:
        self._qmd_bin = qmd_bin
        self._timeout = timeout

    def available(self) -> bool:
        """检查 QMD rerank 命令是否可用。

        不只检查模型文件在不在（旧 `_rerank_available()` 的问题），
        而是实际尝试运行 `qmd rerank --help` 确认命令存在。
        """
        import os
        import shutil

        if not self._qmd_bin:
            self._qmd_bin = (
                os.environ.get("QMD_BIN", "")
                or shutil.which("qmd") or ""
            )
        if not self._qmd_bin or not os.path.isfile(self._qmd_bin):
            return False
        try:
            result = subprocess.run(
                [self._qmd_bin, "rerank", "--help"],
                capture_output=True, text=True, timeout=5,
            )
            return result.returncode == 0
        except Exception:
            return False

    def rerank(
        self,
        query: str,
        candidates: list[dict[str, Any]],
        top_k: int = DEFAULT_RERANK_TOP_K,
    ) -> list[dict[str, Any]]:
        """用 QMD rerank 命令重排候选结果。

        输入：JSON 数组到 stdin
        输出：JSON 数组从 stdout，每项含 score 字段
        """
        import json

        if not self._qmd_bin:
            return candidates[:top_k]

        # 准备输入：只发 content 给 QMD，保留原 item 的其他字段
        input_items = [{"content": str(c.get("content", ""))} for c in candidates]
        input_json = json.dumps(input_items, ensure_ascii=False)

        try:
            result = subprocess.run(
                [self._qmd_bin, "rerank", query,
                 "--top-k", str(top_k), "--json", "--no-expand"],
                input=input_json,
                capture_output=True, text=True, timeout=self._timeout,
            )
            if result.returncode != 0 or not result.stdout.strip():
                return candidates[:top_k]

            ranked = json.loads(result.stdout)
            if not isinstance(ranked, list):
                return candidates[:top_k]

            # QMD 返回的是 content + score，需要和原 candidates 关联
            content_to_original = {
                str(c.get("content", "")): c for c in candidates
            }
            output: list[dict[str, Any]] = []
            for item in ranked:
                content = str(item.get("content", ""))
                score = float(item.get("score", 0.0))
                original = content_to_original.get(content, {})
                merged = {**original, "rerank_score": score}
                output.append(merged)

            return output[:top_k]

        except (subprocess.TimeoutExpired, json.JSONDecodeError, Exception):
            return candidates[:top_k]


# ── Noop Reranker（降级用）────────────────────────────


class NoopReranker:
    """空重排器：不做任何重排，直接返回原序。

    用于 reranker 不可用时的降级路径。
    它实现了 Reranker 接口，但 available() 返回 False。
    """

    def rerank(
        self,
        query: str,
        candidates: list[dict[str, Any]],
        top_k: int = DEFAULT_RERANK_TOP_K,
    ) -> list[dict[str, Any]]:
        return candidates[:top_k]

    def available(self) -> bool:
        return False


# ── 工厂 ──────────────────────────────────────────────


def get_reranker() -> Reranker:
    """获取可用的重排器，降级到 NoopReranker。

    优先尝试 QMD rerank，不可用则返回 NoopReranker。
    """
    qmd = QMDReranker()
    if qmd.available():
        return qmd
    return NoopReranker()
