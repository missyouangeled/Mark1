"""Mark42 diff 压缩器（方向 A 算法 4）

设计文档:
- 开发手册: docs/design/mark42-开发手册-压缩子系统.md (4.5 节)

策略:
1. 保留 hunk header (@@ -N,M +N,M @@) 和 file headers (diff --git / --- / +++)
2. 连续 context lines (以 ' ' 开头) 做游程编码: N>=2 时合并成 " <N>L"
3. 连续删除行 ('-') 和添加行 ('+') 单独计数, hunk 末尾输出 "+M / -N" 汇总
4. 单条 +/- 不动, 保留可读性

接口风格: 与 compression_algorithms.py 对齐
  class Xxx + get_xxx() 单例 + xxx(code) -> tuple[str, dict]

创建日期: 2026-06-25 07:18
"""

import re

from .log_setup import get_logger
from .utils import safe_call

logger = get_logger(__name__)


class DiffCompressor:
    """git diff 压缩器"""

    def __init__(
        self, merge_context_threshold: int = 2, preserve_hunk_headers: bool = True, preserve_file_headers: bool = True
    ):
        # 连续 context 行数 >= 此值才合并为 " <N>L"
        self.merge_context_threshold = merge_context_threshold
        self.preserve_hunk_headers = preserve_hunk_headers
        self.preserve_file_headers = preserve_file_headers

    def is_diff(self, content: str) -> bool:
        """启发式: 是否像 git diff 输出"""
        if not content:
            return False
        # 必须有 hunk header 才是真 diff
        return bool(re.search(r"^@@\s+-\d+", content, re.MULTILINE))

    def compress(self, content: str) -> tuple[str, dict]:
        """压缩 diff

        Args:
            content: git diff 输出字符串

        Returns:
            (压缩后 diff, 统计信息)
        """
        stats = {
            "algorithm": "diff_compress",
            "original_bytes": len(content.encode("utf-8")),
            "original_lines": 0,
            "is_diff": False,
            "crushed_bytes": 0,
            "ratio": 0.0,
            "hunks": 0,
            "context_lines_merged": 0,
            "insertions": 0,
            "deletions": 0,
            "mode": "none",
        }

        if not content or not content.strip():
            return content, stats

        stats["original_lines"] = content.count("\n") + (1 if not content.endswith("\n") else 0)

        if not self.is_diff(content):
            stats["crushed_bytes"] = stats["original_bytes"]
            stats["mode"] = "passthrough"
            return content, stats
        stats["is_diff"] = True

        try:
            result = self._compress_diff(content, stats)
        except Exception as e:
            stats["mode"] = "error"
            stats["error"] = str(e)
            return content, stats

        stats["crushed_bytes"] = len(result.encode("utf-8"))
        stats["ratio"] = 1.0 - stats["crushed_bytes"] / max(1, stats["original_bytes"])
        stats["mode"] = "compressed"
        return result, stats

    @safe_call(default="", label="compress_diff")
    def _compress_diff(self, content: str, stats: dict) -> str:
        """主体压缩逻辑"""
        out_lines = []
        # 按 hunk 切分
        hunks = self._split_hunks(content, stats)

        for hunk in hunks:
            out_lines.extend(self._process_hunk(hunk, stats))

        return "\n".join(out_lines)

    def _split_hunks(self, content: str, stats: dict) -> list[str]:
        """把 diff 切成若干 hunk 块 (含 file header + @@ ... @@ + body)"""
        blocks = []
        current = []

        for line in content.splitlines():
            if line.startswith("@@"):
                # 新的 hunk 开始
                if current:
                    blocks.append(current)
                current = [line]
            else:
                current.append(line)
        if current:
            blocks.append(current)

        # hunks 计数按 @@ 出现次数 (语义上的 hunk 数, 不算 file header 块)
        stats["hunks"] = sum(1 for ln in content.splitlines() if ln.startswith("@@"))
        return blocks

    def _process_hunk(self, hunk_lines: list[str], stats: dict) -> list[str]:
        """处理单个 hunk block"""
        out = []
        body = []
        hunk_header_added = False

        # 先扫一遍: 区分 file header / hunk header / body
        for line in hunk_lines:
            if line.startswith("@@"):
                if self.preserve_hunk_headers and not hunk_header_added:
                    out.append(line)
                    hunk_header_added = True
                # 如果有第二个 @@ (理论上 split_hunks 不会产生), 忽略
            elif (
                line.startswith("diff ")
                or line.startswith("--- ")
                or line.startswith("+++ ")
                or line.startswith("index ")
            ):
                if self.preserve_file_headers:
                    out.append(line)
            else:
                body.append(line)

        # body 压缩: 连续同类型合并
        out_body = []
        n = len(body)
        i = 0
        while i < n:
            line = body[i]
            tag = line[:1] if line else ""
            if tag in (" ", "+", "-"):
                j = i
                while j < n and body[j][:1] == tag:
                    j += 1
                count = j - i
                if tag == " ":
                    stat_key = "context_lines_merged"
                elif tag == "+":
                    stat_key = "insertions"
                else:
                    stat_key = "deletions"

                if count >= self.merge_context_threshold:
                    label = {" ": "context", "+": "insertions", "-": "deletions"}[tag]
                    out_body.append(f"{tag} ... <{count} {label}>")
                else:
                    # 短 run 保留原文, 但仍计入总数
                    out_body.extend(body[i:j])
                # 不论长短, 都累加到统计 (含短 run)
                stats[stat_key] += count
                i = j
            elif tag == "\\":
                # "\ No newline at end of file" 保留
                out_body.append(line)
                i += 1
            else:
                # 空行 / 其他
                out_body.append(line)
                i += 1

        out.extend(out_body)
        return out


# 单例 + 函数式接口 (与 compression_algorithms.py 对齐)
_instance: DiffCompressor | None = None


def get_diff_compressor() -> DiffCompressor:
    global _instance
    if _instance is None:
        _instance = DiffCompressor()
    return _instance


@safe_call(default=None, label="diff_compress")
def diff_compress(content: str) -> tuple[str, dict]:
    return get_diff_compressor().compress(content)


# 自检 / 烟测
def _run_tests() -> bool:
    """运行测试（已提取到 tests/test_diff_compressor.py）。"""
    from tests.test_diff_compressor import run_tests

    return run_tests()


if __name__ == "__main__":
    import sys

    sys.exit(0 if _run_tests() else 1)
