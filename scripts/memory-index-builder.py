#!/usr/bin/env python3
"""
memory-index-builder.py — 规则关键词索引构建器

扫描 memory/rules/*.md 和 MEMORY.md，提取关键词并生成
/mnt/data/openclaw/scratch/memory-index/MEMORY_INDEX.yaml

用途：为 L1 查询层（memory-search-router.py）提供精确关键词→文件+行号映射

用法：
  python3 scripts/memory-index-builder.py              # 构建索引
  python3 scripts/memory-index-builder.py --print-changes  # 打印变更摘要
"""

from __future__ import annotations

import argparse
import json as json_lib
import math
import os
import re
import sys
import time
import yaml
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parent.parent
RULES_DIR = WORKSPACE / "memory" / "rules"
MEMORY_MD = WORKSPACE / "MEMORY.md"
SCRATCH_DIR = Path("/mnt/data/openclaw/scratch/memory-index")
INDEX_PATH = SCRATCH_DIR / "MEMORY_INDEX.yaml"

# 需要建索引的源文件
SOURCE_FILES = [MEMORY_MD] + (
    sorted(RULES_DIR.glob("*.md")) if RULES_DIR.exists() else []
)


def extract_keywords_from_line(line: str) -> list[str]:
    """从一行中提取有意义的关键词。

    识别单元：以 `- `、`* `、数字编号开头的条目，
    或逗号/顿号/空格分隔的短语。
    """
    keywords: list[str] = []

    # 跳过纯元数据行
    stripped = line.strip()
    if not stripped:
        return keywords
    if stripped.startswith("#"):
        # 标题行：提取标题文本作为关键词
        title = stripped.lstrip("#").strip()
        if title and len(title) >= 2:
            keywords.append(title)
        return keywords
    if stripped.startswith("```") or stripped.startswith(">"):
        return keywords
    if stripped.startswith("|") or stripped.startswith(":"):
        return keywords

    # 过滤太泛的词
    stopwords = {
        "用户", "希望", "新增", "确认", "强调", "补充", "进一步",
        "默认", "优先", "可以", "不要", "必须", "应该", "已经",
        "当前", "后续", "以后", "如果", "或者", "以及", "并且",
        "这一", "这些", "这类", "这种", "但是", "因为", "所以",
        "全部", "所有", "每个", "任何", "还",
    }

    # 提取中文词（滑动窗口 2/3/4 字 + 完整中文段，与 router 一致）
    cn_segments = re.findall(r"[\u4e00-\u9fff]+", stripped)
    cn_words: list[str] = []
    seen_cn: set[str] = set()
    for seg in cn_segments:
        # 完整段作为关键词（匹配标题型长词）
        if len(seg) >= 4 and seg not in stopwords and seg not in seen_cn:
            seen_cn.add(seg)
            cn_words.append(seg)
        for window in (2, 3, 4):
            for i in range(len(seg) - window + 1):
                sub = seg[i:i + window]
                if sub not in stopwords and sub not in seen_cn:
                    seen_cn.add(sub)
                    cn_words.append(sub)
    en_words = re.findall(r"[a-zA-Z][a-zA-Z0-9_/-]{2,}", stripped.lower())

    for w in cn_words:
        if w not in stopwords:
            keywords.append(w)
    for w in en_words:
        if len(w) >= 3:
            keywords.append(w)

    return keywords


def build_index() -> dict[str, list[dict]]:
    """扫描所有源文件，构建关键词倒排索引。

    返回：
        {
            "keyword": [
                {"file": "memory/rules/chat-prefs.md", "line": 12, "snippet": "..."},
                ...
            ],
            ...
        }
    """
    index: dict[str, list[dict]] = {}

    for fpath in SOURCE_FILES:
        if not fpath.exists():
            continue
        rel = str(fpath.relative_to(WORKSPACE))

        try:
            lines = fpath.read_text(encoding="utf-8").split("\n")
        except Exception:
            continue

        for lineno, line in enumerate(lines, 1):
            keywords = extract_keywords_from_line(line)
            if not keywords:
                continue

            snippet = line.strip()[:200]
            for kw in keywords:
                if kw not in index:
                    index[kw] = []
                # 每个文件+行号组合只记一次
                entry = {"file": rel, "line": lineno, "snippet": snippet}
                if entry not in index[kw]:
                    index[kw].append(entry)

    return index


def classify_keyword(kw: str, entries: list[dict], doc_freq: int, total_occ: int) -> list[str]:
    """对关键词做语义标签分类。

    标签体系：
      rule_title  — ## 标题行提取的关键词（权重最高）
      concept     — 3-6字、只在1个文件出现、出现 2-5 次（高区分度）
      device      — 设备名/环境标识
      path        — 文件路径/代码路径碎片
      common      — 2字词跨≥3文件 或 单文件≥8次（低区分度噪声）
      general     — 其他普通词
    """
    tags: list[str] = []

    # rule_title: 来自 ## 标题行，≥4字
    if any(e["snippet"].strip().startswith("## ") for e in entries) and len(kw) >= 4:
        tags.append("rule_title")

    # path: 含路径特征
    if "/" in kw or (len(kw) > 10 and bool(re.search(r"[\\/._-]{2,}", kw))):
        tags.append("path")

    # device: 设备名
    if bool(re.match(r"(TABLET|DESKTOP|missyouangeled)[-_]", kw)) or kw in {"公司", "掌机", "老电脑"}:
        tags.append("device")

    # concept: 高区分度概念词
    if 3 <= len(kw) <= 6 and doc_freq == 1 and 2 <= total_occ <= 5:
        tags.append("concept")

    # common: 2字高频噪声
    if (len(kw) <= 2 and doc_freq >= 3) or (len(kw) <= 2 and total_occ >= 8):
        tags.append("common")

    if not tags:
        tags.append("general")

    return tags


def compute_keyword_metadata(index: dict[str, list[dict]], n_docs: int) -> dict[str, dict]:
    """为每个关键词计算 IDF 和标签。

    IDF = ln(N/df + 1)，base e 对数，最小值 0.22。
    """
    metadata: dict[str, dict] = {}
    for kw, entries in index.items():
        files = {e["file"] for e in entries}
        df = len(files)
        idf = round(math.log(max(n_docs / df, 1.0) + 1), 4)
        total_occ = len(entries)
        tags = classify_keyword(kw, entries, df, total_occ)
        metadata[kw] = {
            "idf": idf,
            "tags": tags,
            "doc_freq": df,
            "total_entries": total_occ,
        }
    return metadata


def save_to_yaml(output: dict) -> Path:
    """原子写入索引文件（写临时文件→rename）。"""
    SCRATCH_DIR.mkdir(parents=True, exist_ok=True)

    tmp_path = INDEX_PATH.with_suffix(".yaml.tmp")
    with open(tmp_path, "w", encoding="utf-8") as f:
        yaml.dump(output, f, allow_unicode=True, default_flow_style=False, sort_keys=False)

    tmp_path.replace(INDEX_PATH)
    return INDEX_PATH


def save_index(index: dict[str, list[dict]], metadata: dict[str, dict]) -> Path:
    """保存索引 + 关键词元数据到 YAML（可读）和 JSON（router 高速加载）。"""
    sorted_kw = sorted(index.keys())
    output = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "source_files": [str(f.relative_to(WORKSPACE)) for f in SOURCE_FILES if f.exists()],
        "total_keywords": len(index),
        "n_docs": len([f for f in SOURCE_FILES if f.exists()]),
        "index": {kw: index[kw] for kw in sorted_kw},
        "metadata": {kw: metadata[kw] for kw in sorted_kw if kw in metadata},
    }
    # YAML（可读）
    save_to_yaml(output)
    # JSON（高速加载）
    json_path = SCRATCH_DIR / "MEMORY_INDEX.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json_lib.dump(output, f, ensure_ascii=False, separators=(",", ":"))
    return INDEX_PATH


def compare_index(old: dict, new: dict) -> dict:
    """比较新旧索引，返回变更摘要。"""
    old_kw = set(old.get("index", {}).keys()) if old else set()
    new_kw = set(new["index"].keys())

    added = new_kw - old_kw
    removed = old_kw - new_kw
    changed = set()
    for k in old_kw & new_kw:
        old_entries = {(e["file"], e["line"]) for e in old["index"].get(k, [])}
        new_entries = {(e["file"], e["line"]) for e in new["index"].get(k, [])}
        if old_entries != new_entries:
            changed.add(k)

    return {
        "added_keywords": len(added),
        "removed_keywords": len(removed),
        "changed_keywords": len(changed),
        "total_old": old.get("total_keywords", 0) if old else 0,
        "total_new": new["total_keywords"],
        "added_samples": sorted(added)[:20] if added else [],
        "removed_samples": sorted(removed)[:20] if removed else [],
    }


def load_old_index() -> dict | None:
    """加载旧索引（如果存在）。"""
    if INDEX_PATH.exists():
        try:
            with open(INDEX_PATH, "r", encoding="utf-8") as f:
                return yaml.safe_load(f)
        except Exception:
            return None
    return None


def main():
    parser = argparse.ArgumentParser(description="规则关键词索引构建器")
    parser.add_argument("--print-changes", action="store_true", help="打印变更摘要")
    parser.add_argument("--print-keywords", action="store_true", help="打印所有关键词")
    args = parser.parse_args()

    old_index = load_old_index()
    new_index_raw = build_index()
    n_docs = len([f for f in SOURCE_FILES if f.exists()])
    keyword_metadata = compute_keyword_metadata(new_index_raw, n_docs)
    save_index(new_index_raw, keyword_metadata)
    output_path = INDEX_PATH

    if args.print_changes:
        current = {
            "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
            "source_files": [str(f.relative_to(WORKSPACE)) for f in SOURCE_FILES if f.exists()],
            "total_keywords": len(new_index_raw),
            "index": new_index_raw,
        }
        changes = compare_index(old_index, current)
        print(f"📊 索引变更摘要")
        print(f"   旧关键词数：{changes['total_old']}")
        print(f"   新关键词数：{changes['total_new']}")
        print(f"   新增关键词：{changes['added_keywords']}")
        print(f"   移除关键词：{changes['removed_keywords']}")
        print(f"   变更关键词：{changes['changed_keywords']}")
        if changes["added_samples"]:
            print(f"   新增样例：{', '.join(changes['added_samples'][:10])}")
    elif args.print_keywords:
        for kw in sorted(new_index_raw.keys()):
            entries = new_index_raw[kw]
            meta = keyword_metadata.get(kw, {})
            files = ", ".join(sorted(set(e["file"] for e in entries)))
            tags = ",".join(meta.get("tags", []))
            print(f"  {kw} ({tags}, idf={meta.get('idf','?')}) → {files}")
    else:
        size = output_path.stat().st_size
        n_meta = len(keyword_metadata)
        # 统计标签分布
        tag_counts: dict = {}
        for m in keyword_metadata.values():
            for t in m.get("tags", []):
                tag_counts[t] = tag_counts.get(t, 0) + 1
        tag_summary = ", ".join(f"{t}:{n}" for t, n in sorted(tag_counts.items()))
        print(f"✅ 索引已生成：{output_path} ({size} bytes, {n_meta} 关键词)")
        print(f"   源文件数：{len([f for f in SOURCE_FILES if f.exists()])}")
        print(f"   IDF 范围：{min(m['idf'] for m in keyword_metadata.values()):.3f}–{max(m['idf'] for m in keyword_metadata.values()):.3f}")
        print(f"   标签分布：{tag_summary}")


if __name__ == "__main__":
    main()
