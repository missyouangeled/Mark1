"""内置记忆搜索锁扣实现：包装 QMD 向量引擎。

# ── 跨编码器接入方案 (2026-07-31) ──
设计文档: docs/design/mark42-跨编码器接入方案-20260731.md

运行模式（MARK42_QMD_VECTOR 环境变量）:
  - off: 纯 BM25 搜索（与改造前完全一致，零风险回滚）
  - on:  强制启用 vector 搜索（会触发 qmd 模型下载，首次 ~1.28GB）
  - auto: 默认。先 BM25 试，召回为空时降级到 vector（推荐）

召回为空判定: top_k 结果数 < MIN_RECALL_THRESHOLD
Vector 可用判定: 模型文件已完整（不存在 .ipull 后缀）且 timeout 内能返回
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any


# ── 模式配置 ──
QMD_VECTOR_MODE = os.environ.get("MARK42_QMD_VECTOR", "auto").lower()
if QMD_VECTOR_MODE not in ("off", "on", "auto"):
    QMD_VECTOR_MODE = "auto"  # 未知值回退到 auto

MIN_RECALL_THRESHOLD = 1  # 召回 < 此值触发降级
VECTOR_TIMEOUT = 30  # vsearch 超时（秒）
QMD_BIN_CANDIDATES = [
    os.environ.get("QMD_BIN", ""),
    shutil.which("qmd") or "",
    os.path.expanduser("~/.npm-global/bin/qmd"),
]
QMD_BIN = next((p for p in QMD_BIN_CANDIDATES if p and os.path.isfile(p)), "")
QMD_INDEX = os.path.expanduser("~/.cache/qmd/index.sqlite")
QMD_MODELS_DIR = Path(os.path.expanduser("~/.cache/qmd/models"))


def _model_complete(model_filename: str) -> bool:
    """检查模型文件是否完整（不存在 .ipull 后缀的临时文件）。

    qmd 下载中会在文件名后加 .ipull 后缀，下载完成后去掉。
    """
    final = QMD_MODELS_DIR / model_filename
    in_progress = QMD_MODELS_DIR / f"{model_filename}.ipull"
    return final.exists() and not in_progress.exists()


def _vector_available() -> bool:
    """vector 搜索是否可用：binary + index + embedding 模型完整。"""
    return bool(QMD_BIN) and os.path.isfile(QMD_INDEX) and _model_complete(
        "hf_ggml-org_embeddinggemma-300M-Q8_0.gguf"
    )


def _rerank_available() -> bool:
    """rerank 是否可用：vector 可用 + rerank 模型完整。"""
    return _vector_available() and _model_complete(
        "hf_tobil_qmd-query-expansion-1.7B-q4_k_m.gguf"
    )


def _run_qmd(args: list[str], timeout: int) -> tuple[int, str]:
    """统一 qmd 调用封装。"""
    if not QMD_BIN:
        return (-1, "")
    try:
        result = subprocess.run(
            [QMD_BIN] + args,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return (result.returncode, result.stdout)
    except subprocess.TimeoutExpired:
        return (-2, "")
    except Exception:
        return (-3, "")


def _qmd_search(query: str, top_k: int) -> list[dict[str, Any]]:
    """BM25 关键词搜索。返回结果列表（可能为空）。"""
    code, stdout = _run_qmd(
        ["search", query, "--top-k", str(top_k), "--json"], timeout=10
    )
    if code != 0 or not stdout.strip():
        return []
    try:
        data = json.loads(stdout)
        if not isinstance(data, list):
            return []
        for item in data:
            item["_mode"] = "bm25"
        return data
    except json.JSONDecodeError:
        return []


def _qmd_vsearch(query: str, top_k: int) -> list[dict[str, Any]]:
    """向量搜索。需要 embedding 模型完整。"""
    code, stdout = _run_qmd(
        ["vsearch", query, "-n", str(top_k), "--json"], timeout=VECTOR_TIMEOUT
    )
    if code != 0 or not stdout.strip():
        return []
    try:
        data = json.loads(stdout)
        if not isinstance(data, list):
            return []
        for item in data:
            item["_mode"] = "vector"
        return data
    except json.JSONDecodeError:
        return []


class BuiltinMemory:
    """将 QMD 向量搜索引擎包装为 MemoryLock 接口。

    三种运行模式:
    - off: 仅 BM25，与改造前一致
    - on:  强制 vector（首次需模型完整）
    - auto: BM25 优先，召回为空时降级到 vector
    """

    def search(self, query: str, top_k: int = 5) -> list[dict[str, Any]]:
        # 1) 总是先跑 BM25（fast path）
        results = _qmd_search(query, top_k)
        mode_used = "bm25"

        # 2) 判断是否要降级到 vector
        need_vector = (
            QMD_VECTOR_MODE == "on"
            or (QMD_VECTOR_MODE == "auto" and len(results) < MIN_RECALL_THRESHOLD)
        )
        if need_vector and _vector_available() and len(results) < top_k:
            v_results = _qmd_vsearch(query, top_k)
            if v_results:
                results = v_results
                mode_used = "vector"

        # 3) 打标：标记是否降级
        for item in results:
            item.setdefault("_search_mode", mode_used)

        # 4) 即使没降级，如果召回仍不足，标记 degraded
        # 注意：默认保持原有行为（返回 []），只在环境变量要求时才返回降级标记
        if not results and QMD_VECTOR_MODE != "off":
            if os.environ.get("MARK42_QMD_VERBOSE_DEGRADED", "0") == "1":
                return [{"_degraded": True,
                         "_reason": "no_recall_bm25_and_vector_unavailable",
                         "_mode": QMD_VECTOR_MODE}]
        return results

    def index(self, documents: list[dict[str, Any]]) -> dict[str, Any]:
        # QMD 通过文件系统索引，不直接支持程序化写入
        return {"indexed": 0, "status": "not_implemented_for_qmd"}

    def health(self) -> bool:
        """二进制 + 索引 + 任一模型完整即视为可用。"""
        return bool(QMD_BIN) and os.path.isfile(QMD_INDEX)

    def detailed_health(self) -> dict[str, Any]:
        """详细健康报告，供 consciousness C2 健康检查使用。"""
        return {
            "qmd_bin": "ok" if QMD_BIN else "missing",
            "qmd_index": "ok" if os.path.isfile(QMD_INDEX) else "missing",
            "embedding_model": (
                "ok" if _model_complete("hf_ggml-org_embeddinggemma-300M-Q8_0.gguf")
                else "missing_or_downloading"
            ),
            "rerank_model": (
                "ok" if _model_complete("hf_tobil_qmd-query-expansion-1.7B-q4_k_m.gguf")
                else "missing_or_downloading"
            ),
            "vector_available": _vector_available(),
            "rerank_available": _rerank_available(),
            "search_mode": QMD_VECTOR_MODE,
            "degraded_reason": (
                None if _vector_available()
                else "vector_or_rerank_model_incomplete"
            ),
        }
