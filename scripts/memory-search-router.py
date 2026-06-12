#!/usr/bin/env python3
"""
memory-search-router.py — 统一记忆搜索路由（L1→L2→L3→L4）

实现四层搜索路由，逐层尝试，找到置信度足够的结果就短路返回。

L1: MEMORY_INDEX.json 关键词 IDF+标签（置信度 ≥0.8 → 返回，~30ms）
L2: Python BM25 + QMD fallback（置信度 ≥0.7 → 返回，30-600ms）
L2: BM25 + embedding RRF 双通道融合搜索（置信度 ≥0.65 → 返回，~300ms）
LS: 语义概念层（意图+同义词+桥接，置信度 ≥0.7 → 返回）
L3: 返回提示走云端 memory_search（不在脚本内调云端 API）
L4: 读取 session-backup context-summary

用法：
  python3 scripts/memory-search-router.py "查询词"
  python3 scripts/memory-search-router.py --layer l1 "查询词"   # 单层搜索
  python3 scripts/memory-search-router.py --layer l2 "查询词"
"""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import subprocess
import sys
import time
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parent.parent
INDEX_PATH = Path("/mnt/data/openclaw/scratch/memory-index/MEMORY_INDEX.json")  # JSON 0.03s vs YAML 5s
CONCEPTS_PATH = WORKSPACE / "memory" / "concepts.yaml"
SESSION_BACKUP_DIR = Path("/mnt/data/openclaw/session-backup")
CONTEXT_SUMMARY = "context-summary.md"

# 各层阈值
L1_CONFIDENCE_THRESHOLD = 0.73
L2_CONFIDENCE_THRESHOLD = 0.65
LAYER_TIMEOUT_S = 5


def tokenize_for_index(query: str) -> list[str]:
    """与 memory-index-builder.py 一致的 tokenize 逻辑。
    
    使用滑动窗口提取中文关键词（2/3/4字）+ 完整中文段作为长关键词，
    以匹配索引中的标题型长词（如"硬件适配性审查""安装前安全审查"）。
    """
    tokens: list[str] = []

    stopwords = {
        "用户", "希望", "新增", "确认", "强调", "补充", "进一步",
        "默认", "优先", "可以", "不要", "必须", "应该", "已经",
        "当前", "后续", "以后", "如果", "或者", "以及", "并且",
        "这一", "这些", "这类", "这种", "但是", "因为", "所以",
        "全部", "所有", "每个", "任何", "还",
    }

    # 提取中文段 → 滑动窗口生成 2/3/4 字子词 + 完整段做长关键词
    cn_segments = re.findall(r"[\u4e00-\u9fff]+", query)
    seen_cn: set[str] = set()
    for seg in cn_segments:
        # 完整段作为关键词（匹配标题型长词，权重最高）
        if len(seg) >= 4 and seg not in stopwords and seg not in seen_cn:
            seen_cn.add(seg)
            tokens.append(seg)
        for window in (2, 3, 4):
            for i in range(len(seg) - window + 1):
                sub = seg[i:i + window]
                if sub not in stopwords and sub not in seen_cn:
                    seen_cn.add(sub)
                    tokens.append(sub)

    # 提取英文词
    en_words = re.findall(r"[a-zA-Z][a-zA-Z0-9_/-]{2,}", query.lower())
    for w in en_words:
        tokens.append(w)

    return tokens


def search_l1_index(query: str) -> dict | None:
    """L1: MEMORY_INDEX.yaml 关键词匹配 + IDF + 标签加权。

    评分公式：
      raw_score = Σ(token_idf × tag_multiplier)
      confidence = raw_score / max_possible_score

    标签乘数：rule_title=2.0, concept=1.2, general=1.0, device=0.8,
              common=0.3, path=0.2
    """
    if not INDEX_PATH.exists():
        return None

    try:
        with open(INDEX_PATH, "r", encoding="utf-8") as f:
            idx = json.load(f)
    except Exception:
        return None

    if not idx or "index" not in idx:
        return None

    index = idx["index"]
    metadata: dict[str, dict] = idx.get("metadata", {})
    tokens = tokenize_for_index(query)
    if not tokens:
        return None

    # 标签乘数
    TAG_MULTIPLIER = {
        "rule_title": 2.5,
        "concept": 1.4,
        "general": 1.0,
        "device": 0.8,
        "common": 0.3,
        "path": 0.2,
    }

    def token_score(t: str) -> float:
        """计算单个 token 的得分：idf × 标签乘数。"""
        if t not in index:
            return 0.0
        m = metadata.get(t, {})
        idf = m.get("idf", 0.8)
        # 取最高权重的标签
        tags = m.get("tags", ["general"])
        best_mult = max((TAG_MULTIPLIER.get(tag, 1.0) for tag in tags), default=1.0)
        return idf * best_mult

    matches: list[dict] = []
    seen = set()
    for token in tokens:
        if token in index:
            for entry in index[token]:
                dedup_key = (entry["file"], entry["line"])
                if dedup_key not in seen:
                    seen.add(dedup_key)
                    matches.append({
                        "file": entry["file"],
                        "line": entry["line"],
                        "snippet": entry.get("snippet", ""),
                        "keyword": token,
                        "score": round(token_score(token), 3),
                    })

    if not matches:
        return None

    # 按文件分组，累加 token_score
    file_scores: dict[str, float] = {}
    file_best_kws: dict[str, set[str]] = {}
    for m in matches:
        f = m["file"]
        file_scores[f] = file_scores.get(f, 0.0) + m["score"]
        file_best_kws.setdefault(f, set()).add(m["keyword"])

    best_file = max(file_scores, key=file_scores.get) if file_scores else None
    best_score = file_scores.get(best_file, 0.0)

    # max_possible_score：仅计算最佳文件中实际命中的 token 理论满分
    # （防止跨文件散词拉高分母、压低压实命中文件的置信度）
    best_file_match_kws = file_best_kws.get(best_file, set())
    max_possible = sum(token_score(t) for t in best_file_match_kws) or 0.1
    raw_conf = best_score / max(max_possible, 0.1)

    # 文件集中度：最佳文件得分占比（防止跨文件散开）
    total_score = sum(file_scores.values())
    concentration = best_score / max(total_score, 0.01)
    # raw_conf 为主（0.7）+ 集中度（0.2），cap 0.95
    confidence = round(min(raw_conf * 0.7 + concentration * 0.2, 0.95), 3)

    return {
        "layer": "L1",
        "confidence": confidence,
        "matches": sorted(matches, key=lambda x: -x["score"])[:10],
        "best_file": best_file,
        "best_score": round(best_score, 3),
        "short_circuit": confidence >= L1_CONFIDENCE_THRESHOLD,
    }


def search_l2_bm25(query: str) -> dict | None:
    """L2: BM25 + embedding RRF 双通道融合搜索。
    
    两个独立通道各自跑 top-5，然后用 Reciprocal Rank Fusion（RRF）
    合并排序。结果同时具备关键词精度 和 语义理解。
    """

    # ── 通道 1: Python BM25 ──
    bm25_result = _search_l2_bm25_python(query)

    # ── 通道 2: embedding 语义 ──
    embed_result = _search_l2_embed_channel(query)

    # 如果两个通道都没结果
    if (not bm25_result or not bm25_result.get("matches")) and (not embed_result):
        return _search_l2_qmd_fallback(query)

    # RRF 融合
    k = 60
    rrf_scores: dict[str, float] = {}  # key: "file::line"
    entry_map: dict[str, dict] = {}

    # 通道 1: BM25
    if bm25_result and bm25_result.get("matches"):
        for rank, m in enumerate(bm25_result["matches"]):
            key = f"{m['file']}::{m['line']}"
            rrf_scores[key] = rrf_scores.get(key, 0) + 1.0 / (k + rank + 1)
            entry_map[key] = {**m, "source": "bm25", "bm25_rank": rank + 1}

    # 通道 2: embedding
    if embed_result and embed_result.get("matches"):
        for rank, m in enumerate(embed_result["matches"]):
            key = f"{m['file']}::{m['line']}"
            rrf_scores[key] = rrf_scores.get(key, 0) + 1.0 / (k + rank + 1)
            if key in entry_map:
                entry_map[key]["source"] = "both"
                entry_map[key]["embed_rank"] = rank + 1
            else:
                entry_map[key] = {**m, "source": "embed", "embed_rank": rank + 1}

    # 按 RRF 排序
    sorted_keys = sorted(rrf_scores, key=rrf_scores.get, reverse=True)[:10]
    bm25_best = bm25_result.get("confidence", 0) if bm25_result else 0
    embed_best = embed_result.get("confidence", 0) if embed_result else 0

    # 置信度：取两个通道的高值 + RRF 加成
    raw_confidence = max(bm25_best, embed_best)
    n_both = sum(1 for k in sorted_keys if entry_map.get(k, {}).get("source") == "both")
    confidence = round(min(raw_confidence + n_both * 0.05, 0.95), 3)

    return {
        "layer": "L2",
        "confidence": confidence,
        "matches": [
            {
                **entry_map[k],
                "rrf_score": round(rrf_scores[k], 5),
            }
            for k in sorted_keys
        ],
        "top_score": round(max(rrf_scores.values()), 5) if rrf_scores else 0,
        "channels": {
            "bm25_confidence": round(bm25_best, 3),
            "embed_confidence": round(embed_best, 3),
            "both_hits": n_both,
        },
        "short_circuit": confidence >= L2_CONFIDENCE_THRESHOLD,
    }


def _search_l2_embed_channel(query: str) -> dict | None:
    """L2 embedding 通道：通过 embed-sidecar HTTP 常驻服务获取语义搜索结果。"""
    import urllib.request

    EMBED_SIDECAR_URL = "http://127.0.0.1:18792"

    try:
        req = urllib.request.Request(
            f"{EMBED_SIDECAR_URL}/search",
            data=json.dumps({"query": query, "top": 5}).encode(),
            headers={"Content-Type": "application/json"},
        )
        resp = urllib.request.urlopen(req, timeout=LAYER_TIMEOUT_S)
        data = json.loads(resp.read().decode())
    except Exception:
        return None

    if not data.get("ok"):
        return None

    results = data.get("results", [])
    confidence = data.get("confidence", 0.0)

    return {
        "layer": "embed",
        "confidence": confidence,
        "matches": [
            {
                "file": r["file"],
                "line": r["line"],
                "snippet": r["content"],
                "score": r["score"],
            }
            for r in results
        ],
        "top_score": data.get("top_score", 0),
        "timing_ms": data.get("timing_ms", 0),
        "short_circuit": confidence >= L2_CONFIDENCE_THRESHOLD,
    }


def _search_l2_bm25_python(query: str) -> dict | None:
    """纯 Python BM25 评分器（基于关键词倒排索引）。

    利用已有的 MEMORY_INDEX.json 做 IDF-weighted 文档评分。
    不需要外部进程，中文/英文/混合查询通吃。

    BM25 简化公式（k1=1.2）：
      score(d, q) = Σ IDF(t) × (tf(t,d)×(k1+1)) / (tf(t,d)+k1)
      IDF(t) = ln((N-df+0.5)/(df+0.5)+1)
    """

    if not INDEX_PATH.exists():
        return None

    try:
        with open(INDEX_PATH, "r", encoding="utf-8") as f:
            idx = json.load(f)
    except Exception:
        return None

    if not idx or "index" not in idx:
        return None

    index = idx["index"]
    n_docs = idx.get("n_docs", 5)

    tokens = tokenize_for_index(query)
    if not tokens:
        return None

    valid_tokens = [t for t in tokens if t in index]
    if not valid_tokens:
        return None

    K1 = 1.2
    token_idfs: dict[str, float] = {}
    token_files: dict[str, dict[str, int]] = {}

    for token in valid_tokens:
        entries = index[token]
        df = len({e["file"] for e in entries})
        idf = math.log(max((n_docs - df + 0.5) / (df + 0.5), 0.5) + 1)
        token_idfs[token] = idf

        file_tf: dict[str, int] = {}
        for e in entries:
            f = e["file"]
            file_tf[f] = file_tf.get(f, 0) + 1
        token_files[token] = file_tf

    file_scores: dict[str, float] = {}
    for token in valid_tokens:
        idf = token_idfs[token]
        for f, tf in token_files[token].items():
            bm25_tf = (tf * (K1 + 1)) / (tf + K1)
            file_scores[f] = file_scores.get(f, 0.0) + idf * bm25_tf

    if not file_scores:
        return None

    best_file = max(file_scores, key=file_scores.get)
    best_score = file_scores[best_file]
    max_possible = sum(token_idfs.values())
    raw_conf = best_score / max(max_possible, 0.1)
    file_count = len(file_scores)
    concentration = best_score / sum(file_scores.values()) if sum(file_scores.values()) > 0 else 0
    confidence = round(min(raw_conf * 0.65 + concentration * 0.2 - file_count * 0.03, 0.93), 3)

    matches_out: list[dict] = []
    seen_entries = set()
    for token in valid_tokens:
        for entry in index.get(token, []):
            dedup = (entry["file"], entry["line"])
            if dedup not in seen_entries:
                seen_entries.add(dedup)
                matches_out.append({
                    "file": entry["file"],
                    "line": entry["line"],
                    "snippet": entry.get("snippet", ""),
                    "keyword": token,
                })

    return {
        "layer": "L2",
        "confidence": confidence,
        "matches": sorted(matches_out, key=lambda x: token_idfs.get(x["keyword"], 0), reverse=True)[:10],
        "best_file": best_file,
        "best_score": round(best_score, 3),
        "short_circuit": confidence >= L2_CONFIDENCE_THRESHOLD,
    }


def _search_l2_qmd_fallback(query: str) -> dict | None:
    """QMD BM25 全工作区搜索（fallback，用于英文词/脚本路径等不在 memory 文件中的查询）。"""
    import subprocess
    try:
        result = subprocess.run(
            ["qmd", "search", query, "--top", "5"],
            capture_output=True, text=True,
            timeout=LAYER_TIMEOUT_S,
            cwd=str(WORKSPACE),
        )
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return {"layer": "L2", "confidence": 0.0, "matches": [],
                "reason": "qmd unavailable", "short_circuit": False}

    if result.returncode != 0 or not result.stdout.strip():
        return {"layer": "L2", "confidence": 0.0, "matches": [],
                "reason": "no QMD matches", "short_circuit": False}

    lines = result.stdout.strip().split("\n")
    matches: list[dict] = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        m = re.match(r"qmd://(.+?):(\d+)\s+#\w+", line)
        if m:
            matches.append({"file": m.group(1), "line": int(m.group(2)), "raw": line})
            continue
        m_s = re.match(r"Score:\s*(\d+)%", line)
        if m_s and matches:
            matches[-1]["score"] = int(m_s.group(1)) / 100.0

    if not matches:
        return {"layer": "L2", "confidence": 0.0, "matches": [],
                "reason": "no parsed QMD matches", "short_circuit": False}

    top_score = max((m.get("score", 0) for m in matches), default=0)
    density = min(len(matches) / 3, 1.0)
    confidence = round(min(top_score * 0.7 + density * 0.3, 1.0), 3)

    return {
        "layer": "L2",
        "confidence": confidence,
        "matches": matches,
        "short_circuit": confidence >= L2_CONFIDENCE_THRESHOLD,
    }


def _load_concepts() -> dict | None:
    """加载语义概念映射（缺失时静默跳过）。"""
    if not CONCEPTS_PATH.exists():
        return None
    try:
        with open(CONCEPTS_PATH, "r", encoding="utf-8") as f:
            return _yaml.safe_load(f)
    except Exception:
        return None


def search_semantic(query: str) -> dict | None:
    """Layer S: 语义概念层 — 意图分类 + 同义词扩展 + 概念桥接。

    完全独立于其他层：依赖 memory/concepts.yaml，缺失则跳过。
    不做 embedding——用概念映射桥接"用户用语 → 系统关键词"。

    处理流程：
      1. 意图分类：匹配 query 中的意图模式 → 加权重排文件
      2. 同义词扩展：展开用户用语的同义词 → 追加搜索词
      3. 概念桥接：触发特定概念桥 → 注入系统关键词
      4. 用扩展后的查询 + 加权的文件优先级搜索引 → 返回结果
    """
    concepts = _load_concepts()
    if not concepts:
        return None

    if not INDEX_PATH.exists():
        return None

    try:
        with open(INDEX_PATH, "r", encoding="utf-8") as f:
            idx = json.load(f)
    except Exception:
        return None

    if not idx or "index" not in idx:
        return None

    index = idx["index"]
    n_docs = idx.get("n_docs", 5)
    query_lower = query.lower()

    # ── 步骤 1: 意图分类 ──
    intent_scores: dict[str, float] = {}
    intent_patterns = concepts.get("intent_patterns", {})
    for intent_name, cfg in intent_patterns.items():
        for pat in cfg.get("patterns", []):
            if pat in query or pat.lower() in query_lower:
                intent_scores[intent_name] = intent_scores.get(intent_name, 0) + 1

    # 文件加权：匹配的意图给对应文件加分
    file_intent_bonus: dict[str, float] = {}
    for intent_name, score in intent_scores.items():
        weight_files = intent_patterns[intent_name].get("weight_files", {})
        for f, w in weight_files.items():
            file_intent_bonus[f] = file_intent_bonus.get(f, 0) + score * w

    detected_intents = sorted(intent_scores, key=intent_scores.get, reverse=True)

    # ── 步骤 2: 同义词扩展 ──
    synonyms = concepts.get("synonyms", {})
    expanded_terms: list[str] = []
    for term, syns in synonyms.items():
        if term in query_lower:
            expanded_terms.extend(syns[:3])  # 最多取3个同义词

    # ── 步骤 3: 概念桥接 ──
    bridges = concepts.get("concept_bridges", {})
    triggered_bridges: list[dict] = []
    for bridge_name, cfg in bridges.items():
        query_terms = cfg.get("query_terms", [])
        # 如果有任意一个 query_term 出现在 query 中，触发桥接
        hits = [t for t in query_terms if t in query_lower]
        if hits:
            triggered_bridges.append({
                "name": bridge_name,
                "hits": hits,
                "expand": cfg.get("expand_keywords", []),
                "prefer": cfg.get("prefer_files", []),
            })

    if not triggered_bridges and not expanded_terms and not file_intent_bonus:
        return None  # 语义层无增强，静默退回

    # ── 步骤 4: 扩展查询 + BM25 搜索 ──
    # 把扩展词追加到 query token
    enriched_tokens = list(dict.fromkeys(
        tokenize_for_index(query) + expanded_terms +
        [kw for br in triggered_bridges for kw in br.get("expand", [])]
    ))

    if not enriched_tokens:
        return None

    valid_tokens = [t for t in enriched_tokens if t in index]
    if not valid_tokens:
        return None

    K1 = 1.2
    token_idfs: dict[str, float] = {}
    token_files: dict[str, dict[str, int]] = {}

    for token in valid_tokens:
        entries = index[token]
        df = len({e["file"] for e in entries})
        idf = math.log(max((n_docs - df + 0.5) / (df + 0.5), 0.5) + 1)
        token_idfs[token] = idf

        file_tf: dict[str, int] = {}
        for e in entries:
            f = e["file"]
            file_tf[f] = file_tf.get(f, 0) + 1
        token_files[token] = file_tf

    file_scores: dict[str, float] = {}
    for token in valid_tokens:
        idf = token_idfs[token]
        for f, tf in token_files[token].items():
            bm25_tf = (tf * (K1 + 1)) / (tf + K1)
            score = idf * bm25_tf
            # 意图加权
            if f in file_intent_bonus:
                score *= (1.0 + file_intent_bonus[f] * 0.15)
            # 概念桥接优先文件
            for br in triggered_bridges:
                if f in br.get("prefer", []):
                    score *= 1.3
            file_scores[f] = file_scores.get(f, 0.0) + score

    if not file_scores:
        return None

    best_file = max(file_scores, key=file_scores.get)
    best_score = file_scores[best_file]
    max_possible = sum(token_idfs.values())
    raw_conf = best_score / max(max_possible, 0.1)
    file_count = len(file_scores)
    concentration = best_score / sum(file_scores.values()) if sum(file_scores.values()) > 0 else 0
    confidence = round(min(raw_conf * 0.65 + concentration * 0.2 - file_count * 0.03, 0.93), 3)

    # 构建匹配结果
    matches_out: list[dict] = []
    seen_entries = set()
    for token in valid_tokens:
        for entry in index.get(token, []):
            dedup = (entry["file"], entry["line"])
            if dedup not in seen_entries:
                seen_entries.add(dedup)
                matches_out.append({
                    "file": entry["file"],
                    "line": entry["line"],
                    "snippet": entry.get("snippet", ""),
                    "keyword": token,
                })

    return {
        "layer": "LS",
        "confidence": confidence,
        "matches": sorted(matches_out, key=lambda x: token_idfs.get(x["keyword"], 0), reverse=True)[:10],
        "best_file": best_file,
        "best_score": round(best_score, 3),
        "intents": detected_intents,
        "bridges_triggered": [b["name"] for b in triggered_bridges],
        "expanded_terms": expanded_terms,
        "short_circuit": confidence >= L2_CONFIDENCE_THRESHOLD,
    }


def search_l3_cloud(query: str) -> dict:
    """L3: 返回提示走云端 memory_search（不在脚本内调 API）。"""
    return {
        "layer": "L3",
        "confidence": 0.0,
        "message": "本地搜索置信度不足，建议调用 memory_search 工具进行云端语义搜索",
        "action": "call_memory_search_tool",
        "short_circuit": False,
    }


def search_l4_backup(query: str) -> dict:
    """L4: 读取 session-backup context-summary。"""
    # 找到最新的 snapshot
    snapshots = sorted(
        SESSION_BACKUP_DIR.glob("snapshot-*"),
        key=lambda p: p.stat().st_mtime, reverse=True,
    ) if SESSION_BACKUP_DIR.exists() else []

    results: list[dict] = []
    for snap in snapshots[:1]:  # 只取最新一个
        summary_path = snap / CONTEXT_SUMMARY
        if not summary_path.exists():
            continue
        try:
            content = summary_path.read_text(encoding="utf-8")
            # 简单搜索：找包含查询词的行
            for i, line in enumerate(content.split("\n"), 1):
                if query.lower() in line.lower():
                    results.append({
                        "file": str(summary_path),
                        "line": i,
                        "snippet": line.strip()[:300],
                    })
        except Exception:
            continue

    confidence = min(len(results) / 3, 0.6) if results else 0.0

    return {
        "layer": "L4",
        "confidence": round(confidence, 3),
        "matches": results[:10],
        "source": str(snapshots[0]) if snapshots else None,
        "short_circuit": False,  # L4 不短路，仅作参考
    }


def route_search(query: str, max_layer: str = "L4") -> dict:
    """执行完整的 L1→L4 路由搜索。"""
    layers = ["L1", "LS", "L2", "L3", "L4"]
    start_idx = layers.index(max_layer) if max_layer in layers else 4

    results: list[dict] = []
    route_taken = None

    for i, layer_name in enumerate(layers):
        if i > start_idx:
            break

        t0 = time.time()

        if layer_name == "L1":
            l_result = search_l1_index(query)
        elif layer_name == "L2":
            l_result = search_l2_bm25(query)
        elif layer_name == "LS":
            l_result = search_semantic(query)
        elif layer_name == "L3":
            l_result = search_l3_cloud(query)
        elif layer_name == "L4":
            l_result = search_l4_backup(query)

        elapsed = time.time() - t0

        if l_result:
            l_result["elapsed_ms"] = round(elapsed * 1000)
            results.append(l_result)

            if l_result.get("short_circuit"):
                route_taken = layer_name
                break

    return {
        "query": query,
        "route_taken": route_taken or layers[min(start_idx, 4)],
        "layers_searched": [r["layer"] for r in results],
        "layers": results,
        "recommendation": results[-1] if results else None,
    }


def main():
    parser = argparse.ArgumentParser(description="统一记忆搜索路由")
    parser.add_argument("query", nargs="+", help="搜索词")
    parser.add_argument("--layer", choices=["l1", "l2", "ls", "l3", "l4"],
                        help="指定单层搜索（跳过其他层）")
    parser.add_argument("--json", action="store_true", default=True,
                        help="JSON 输出（默认）")
    args = parser.parse_args()

    query = " ".join(args.query).strip()
    if not query:
        print(json.dumps({"error": "empty query"}, ensure_ascii=False))
        return 1

    if args.layer:
        # 单层模式
        layer_map = {"l1": search_l1_index, "l2": search_l2_bm25,
                     "ls": search_semantic,
                     "l3": search_l3_cloud, "l4": search_l4_backup}
        fn = layer_map[args.layer]
        result = fn(query)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result and result.get("short_circuit") else 1

    # 全路由模式
    result = route_search(query)
    print(json.dumps(result, ensure_ascii=False, indent=2))

    if result["route_taken"] in ("L1", "L2", "LS"):
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
