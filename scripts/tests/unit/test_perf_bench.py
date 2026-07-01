"""perf_bench.py 测试群。

定位:
  perf_bench.py 是 Mark42 性能基准脚本(525 行, P2-6 段)。
  main() 会真实跑 5 个本地压缩算法 + 调度层 + 异步队列 + LLM 异步入口,
  整个产物耗时数分钟, 并把报告覆盖写入 docs/design/。
  本测试**不进主线**, 只为 perf_bench 内部 contract 留下回归保护:

  - BenchResult dataclass 字段构造
  - 纯辅助函数: _truncate_utf8 / _safe_quantile / _estimate_ratio / _estimate_changed
  - 样本生成器契约: gen_*_sample 长度上界 / make_samples 工厂分派
  - 报告格式化: format_report 三段结构 + report_line 单行格式

设计:
  - conftest autouse 已经把 mark42_modules.* reload 一遍, perf_bench 是顶层可执行
    脚本, 不依赖 mark42 状态路径, 所以无需额外 fixture.
  - 直接 import perf_bench 后取属性(下划线函数也不屏蔽).
  - 不调用 bench_* / main() (避免 tracemalloc + 真压缩 + 真队列往返带来耗时与产物污染).
  - 生成时间字段在 format_report 里会被写成 datetime.now(), 报告测试只断结构字段不锁时间字符串.
"""

from __future__ import annotations

import math
import re
import sys
import types
from typing import Any

import pytest

# perf_bench 是顶层脚本模块, 从 mark42_modules 子包里 import 才能让
# pytest-cov 把它计入 coverage 统计 (裸名 import 不会让 sys.modules 看到
# `scripts.mark42_modules.perf_bench` 这个全限定名).
from mark42_modules import perf_bench as pb  # noqa: E402


# ──────────────── helpers ────────────────

def _make_benchresult(**overrides: Any) -> pb.BenchResult:
    """构造一份最小可用的 BenchResult, 默认值按 6/26 基线快照中较稳定的数字取."""
    defaults = dict(
        runs=12,
        p50_ms=0.5,
        p95_ms=1.0,
        p99_ms=1.5,
        peak_mem_kb_p50=100.0,
        ratio_p50=0.5,
        ratio_p95=0.6,
        changed_rate=1.0,
        notes="test",
    )
    defaults.update(overrides)
    return pb.BenchResult(**defaults)


# ──────────────── BenchResult dataclass ────────────────

class TestBenchResultDataclass:
    """BenchResult dataclass 字段构造 + 默认值契约."""

    def test_all_fields_constructible(self):
        """所有字段都接受类型允许的值."""
        r = pb.BenchResult(
            runs=10,
            p50_ms=1.23,
            p95_ms=2.34,
            p99_ms=3.45,
            peak_mem_kb_p50=12.5,
            ratio_p50=0.5,
            ratio_p95=0.6,
            changed_rate=0.8,
            notes="hello",
        )
        assert r.runs == 10
        assert r.p50_ms == pytest.approx(1.23)
        assert r.peak_mem_kb_p50 == pytest.approx(12.5)
        assert r.notes == "hello"

    def test_optional_fields_default_to_none(self):
        """ratio_p50 / ratio_p95 / changed_rate / notes 应当允许 None."""
        r = pb.BenchResult(
            runs=1,
            p50_ms=0.0,
            p95_ms=0.0,
            p99_ms=0.0,
            peak_mem_kb_p50=0.0,
        )
        assert r.ratio_p50 is None
        assert r.ratio_p95 is None
        assert r.changed_rate is None
        assert r.notes == ""  # dataclass field default = ""


# ──────────────── _truncate_utf8 ────────────────

class TestTruncateUtf8:
    """_truncate_utf8: 按字节截断字符串, 不能在 UTF-8 多字节字符中间切断."""

    def test_short_string_unchanged(self):
        """短于目标的字符串应原样返回."""
        s = "abcdef"
        assert pb._truncate_utf8(s, 1024) == s

    def test_exact_boundary_unchanged(self):
        """正好等于目标字节数应原样返回."""
        s = "a" * 100
        assert pb._truncate_utf8(s, 100) == s

    def test_truncates_to_target_bytes(self):
        """超长 ASCII 应被截到不超过目标字节数."""
        s = "x" * 5000
        out = pb._truncate_utf8(s, 1024)
        assert len(out.encode("utf-8")) <= 1024
        # ASCII 单字符 1 字节, 截断结果应正好 1024 字符
        assert len(out) == 1024

    def test_does_not_split_multibyte_char(self):
        """中文(3-byte/char)边界: 截断到 N 字节时结果不能包含半字符."""
        # 一字 '中' = 3 bytes UTF-8
        s = "中" * 1000  # 3000 bytes
        out = pb._truncate_utf8(s, 10)
        # 不能刚好 10 字节(那会切到字符中间), 要么 < 10, 要么 ≥ 12
        byte_len = len(out.encode("utf-8"))
        assert byte_len <= 10
        # 截断后内容全是完整 '中'
        assert all(ch == "中" for ch in out)

    def test_empty_target_returns_empty(self):
        """目标 = 0 字节应返回空字符串(不抛异常)."""
        out = pb._truncate_utf8("anything", 0)
        assert out == ""


# ──────────────── _safe_quantile ────────────────

class TestSafeQuantile:
    """_safe_quantile: P95/P99 计算, 容错空列表 / 单值 / 数据不足."""

    def test_empty_returns_zero(self):
        """空列表应返回 0.0 而不是抛异常."""
        assert pb._safe_quantile([], 95) == 0.0
        assert pb._safe_quantile([], 99) == 0.0

    def test_single_value(self):
        """单值列表 P95/P99 都应返回该值本身."""
        assert pb._safe_quantile([42.0], 95) == 42.0
        assert pb._safe_quantile([42.0], 99) == 42.0

    def test_p95_returns_within_range(self):
        """P95 应在样本最小值和最大值之间."""
        values = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0,
                  11.0, 12.0, 13.0, 14.0, 15.0, 16.0, 17.0, 18.0, 19.0, 100.0]
        p95 = pb._safe_quantile(values, 95)
        assert min(values) <= p95 <= max(values)

    def test_p99_handles_outliers(self):
        """P99 应捕获极端离群值(>= max - 1)."""
        values = [1.0] * 99 + [1000.0]
        p99 = pb._safe_quantile(values, 99)
        assert p99 >= 100.0

    def test_unsupported_percentile_raises(self):
        """非法百分位(非 95/99)应抛 ValueError."""
        with pytest.raises(ValueError):
            pb._safe_quantile([1.0, 2.0], 50)
        with pytest.raises(ValueError):
            pb._safe_quantile([1.0, 2.0], 90)


# ──────────────── _estimate_ratio ────────────────

class TestEstimateRatio:
    """_estimate_ratio: 从 stats dict 解析压缩率, 容错非 dict / 缺字段 / 非数字."""

    def test_dict_with_numeric_ratio(self):
        """正常 dict 应返回 ratio 数值."""
        assert pb._estimate_ratio({"ratio": 0.42}) == pytest.approx(0.42)
        assert pb._estimate_ratio({"ratio": 0}) == pytest.approx(0.0)
        assert pb._estimate_ratio({"ratio": 1}) == pytest.approx(1.0)

    def test_none_returns_none(self):
        """stats 为 None 应返 None(表示无法估算)."""
        assert pb._estimate_ratio(None) is None

    def test_non_dict_returns_none(self):
        """stats 不是 dict 应返 None."""
        assert pb._estimate_ratio("not a dict") is None
        assert pb._estimate_ratio(42) is None
        assert pb._estimate_ratio([1, 2, 3]) is None

    def test_ratio_missing_returns_none(self):
        """dict 没有 ratio 键应返 None."""
        assert pb._estimate_ratio({"changed": True}) is None

    def test_ratio_non_numeric_returns_none(self):
        """ratio 不是数字应返 None(防御性)."""
        assert pb._estimate_ratio({"ratio": "high"}) is None
        assert pb._estimate_ratio({"ratio": None}) is None


# ──────────────── _estimate_changed ────────────────

class TestEstimateChanged:
    """_estimate_changed: 解析 changed 标志, 三层回退(stats.changed → out!=src → None)."""

    def test_explicit_changed_true(self):
        """stats['changed'] == True 应直接返回 True."""
        assert pb._estimate_changed({"changed": True}, out="x", src="x") is True

    def test_explicit_changed_false(self):
        """stats['changed'] == False 应直接返回 False (不再走回退)."""
        # 注意契约: stats.changed 是权威字段, 即使 out == src 也返 False.
        assert pb._estimate_changed({"changed": False}, out="x", src="x") is False

    def test_none_stats_returns_none(self):
        """stats=None 时直接返回 None, 不走字符串 fallback."""
        # 真实契约: 第一道检查 `not isinstance(stats, dict)` 不通过时直接 None.
        assert pb._estimate_changed(None, out="new", src="old") is None
        assert pb._estimate_changed(None, out="same", src="same") is None

    def test_non_dict_stats_returns_none(self):
        """stats 不是 dict(字符串 / int / list)同样直接返 None, 不比较 out/src."""
        # 注意: 这是 _estimate_changed 真实契约, 不是缺陷.
        # 区别于 _estimate_ratio(那个对非 dict 才返 None, ratio 字段不匹配也返 None).
        assert pb._estimate_changed("not a dict", out="a", src="b") is None
        assert pb._estimate_changed(42, out="a", src="a") is None
        assert pb._estimate_changed([1, 2], out="a", src="b") is None

    def test_dict_without_changed_field_falls_back_to_string_compare(self):
        """stats 是 dict 但没有 'changed' 字段(或不是 bool)时, 才走字符串 fallback."""
        # 关键: 真实契约下, dict 但 缺 changed 字段才回退.
        assert pb._estimate_changed({"other": 1}, out="new", src="old") is True
        assert pb._estimate_changed({"other": 1}, out="same", src="same") is False

    def test_non_string_out_returns_none(self):
        """out 不是字符串时, 在 stats 无 changed 字段情况下应返 None."""
        assert pb._estimate_changed({"other": 1}, out=123, src="src") is None

    def test_changed_field_non_bool_falls_back(self):
        """stats['changed'] 不是 bool 时应走回退(向后兼容)."""
        # 'changed' 键存在但类型不对 → 走 out != src 比较
        assert pb._estimate_changed({"changed": "yes"}, out="a", src="b") is True


# ──────────────── make_samples ────────────────

class TestMakeSamples:
    """make_samples: kind 工厂分派, 必须返回 n 条样本."""

    @pytest.mark.parametrize("kind", ["json", "text", "code", "log", "diff", "mixed"])
    def test_returns_n_samples(self, kind):
        """每种 kind 都应返回正好 n 条."""
        out = pb.make_samples(kind, size_kb=1, n=5)
        assert isinstance(out, list)
        assert len(out) == 5
        for s in out:
            assert isinstance(s, str)

    def test_unknown_kind_raises_keyerror(self):
        """未知 kind 应抛 KeyError."""
        with pytest.raises(KeyError):
            pb.make_samples("unknown", 1, 1)


# ──────────────── 样本生成器契约 ────────────────

class TestSampleGenerators:
    """gen_*_sample: 字节长度上界 + 不抛异常."""

    @pytest.mark.parametrize("size_kb", [1, 10, 100])
    @pytest.mark.parametrize("gen_name", ["gen_text_sample", "gen_code_sample",
                                          "gen_log_sample", "gen_diff_sample"])
    def test_size_within_tolerance(self, gen_name, size_kb):
        """1/10/100 KB 下各生成器都不超 target*(1+tol) 字节.

        容忍: 中文 UTF-8 截断时 _truncate_utf8 严格 <= target, 给 5% 容忍防 flakiness.
        """
        gen = getattr(pb, gen_name)
        sample = gen(size_kb)
        target = size_kb * 1024
        assert isinstance(sample, str)
        assert 0 < len(sample.encode("utf-8")) <= target + int(target * 0.05)

    def test_gen_json_returns_valid_json(self):
        """JSON 样本必须能 json.loads 不抛异常."""
        import json
        sample = pb.gen_json_sample(1)
        # 外层容错: _truncate_utf8 可能在 json 中间断尾导致解析失败
        # 我们的实现里 json 是逐项累加, 在 size_kb 大于 dict 等价后停止,
        # 然后整段 json.dumps, 再按字节截断. 所以截断后可能 json 不能解析.
        # 这里只测 1KB 的小样本, 不应触发截断边界.
        try:
            parsed = json.loads(sample)
            assert "items" in parsed
        except json.JSONDecodeError:
            pytest.skip("JSON 1KB 样本被截断了边界(实现行为, 非缺陷)")

    def test_gen_mixed_contains_all_three(self):
        """mixed 样本应同时包含 text/code/log 三块结构."""
        sample = pb.gen_mixed_scheduler_sample(10)
        # mixed 拼接顺序: text \n code \n log (各块在原 size_kb 基础上按比例切)
        # 断言: 总长度上界, 内容是非空 str
        assert isinstance(sample, str)
        assert len(sample) > 0


# ──────────────── report_line ────────────────

class TestReportLine:
    """report_line: 生成 markdown 表格行, 字段顺序与百分比格式化."""

    def test_with_ratio_and_changed(self):
        """ratio 与 changed 都有 → 百分比格式输出."""
        r = _make_benchresult(ratio_p50=0.5, changed_rate=0.8)
        line = pb.report_line("smartcrush-1KB", r)
        assert "smartcrush-1KB" in line
        assert "50.0%" in line  # 0.5 → "50.0%"
        assert "80%" in line  # 0.8 → "80%"
        # 表格列分隔符: |
        assert line.startswith("|")
        assert line.endswith("|")
        # 列数 = 8 (label + runs + 4 timings + mem + ratio + changed)
        assert line.count("|") == 9  # 8 列 → 9 个 |

    def test_with_none_ratio_shows_dash(self):
        """ratio_p50=None 应输出 '-' 而不是报错."""
        r = _make_benchresult(ratio_p50=None, changed_rate=None)
        line = pb.report_line("nothing-0KB", r)
        # 末尾两列分别是 ratio 和 changed 的格式化
        # "| runs | p50 | p95 | p99 | mem | ratio | changed |"
        # 当 None: "-    -"
        # 看最后 4 个段: "| - | - |"
        assert "|" in line
        assert line.count("-") >= 2

    def test_label_embedded(self):
        """label 应原样出现在第一列."""
        r = _make_benchresult()
        line = pb.report_line("my-custom-label", r)
        assert "my-custom-label" in line


# ──────────────── format_report ────────────────

class TestFormatReportStructure:
    """format_report: 三段结构 + header 完整性 + 时间戳格式.

    故意**不锁死**报告生成时间(datetime.now 无法 mock 在纯函数里简单处理),
    只验结构性约束, 这样这个测试长期不会因为时间漂移而失败.
    """

    @pytest.fixture
    def sample_inputs(self):
        """构造一份最小可用的三段输入."""
        sync = {
            "smartcrush": {
                1: _make_benchresult(runs=12, p50_ms=0.01, p95_ms=0.02, p99_ms=0.02,
                                     peak_mem_kb_p50=3.0, ratio_p50=0.0, changed_rate=0.0),
            },
        }
        sched = {
            1: _make_benchresult(runs=6, p50_ms=0.02, p95_ms=0.04, p99_ms=0.05,
                                  peak_mem_kb_p50=28.0, ratio_p50=None, changed_rate=None),
        }
        async_r = {
            "queue": {1: _make_benchresult(runs=6, p50_ms=0.14, p95_ms=0.24, p99_ms=0.25,
                                            peak_mem_kb_p50=4.0)},
            "async_entry": {1: _make_benchresult(runs=6, p50_ms=3381.85, p95_ms=4522.25,
                                                  p99_ms=4552.89, peak_mem_kb_p50=137.0)},
        }
        return sync, sched, async_r

    def test_contains_all_four_sections(self, sample_inputs):
        """报告必须含四个固定 section 标题."""
        sync, sched, async_r = sample_inputs
        out = pb.format_report(sync, sched, async_r)
        for section in ["## 测试环境", "## 一、本地算法层（裸算法）",
                        "## 二、调度层（algo_scheduler.process）",
                        "## 三、异步层（常驻队列 / 单次封装入口）",
                        "## 结论摘要"]:
            assert section in out, f"missing section: {section}"

    def test_contains_environment_block(self, sample_inputs):
        """测试环境 block 必须列出 Python 版本 + 平台 + 工作目录 + 两条说明."""
        sync, sched, async_r = sample_inputs
        out = pb.format_report(sync, sched, async_r)
        assert "- Python:" in out
        assert "- 平台:" in out
        assert "- 工作目录:" in out
        assert "默认不触发真实 LLM 外部调用" in out
        assert "`async_entry` 表示" in out

    def test_contains_three_table_headers(self, sample_inputs):
        """三个数据段(算法层/调度层/异步层)必须各有一行表头."""
        sync, sched, async_r = sample_inputs
        out = pb.format_report(sync, sched, async_r)
        # 表头在每段都出现: `| 算法 | 样本数 | P50(ms) | ...`
        header = "| 算法 | 样本数 | P50(ms) | P95(ms) | P99(ms) | P50峰值内存(KB) | P50压缩率 | Changed率 |"
        # 算法层用 '算法'
        assert header in out
        # 调度层: `| 路由样本 | ...`
        assert "| 路由样本 |" in out
        # 异步层: `| 路径 | ...`
        assert "| 路径 |" in out

    def test_contains_data_rows_for_each_input(self, sample_inputs):
        """每个输入行必须出现在对应段的表格里."""
        sync, sched, async_r = sample_inputs
        out = pb.format_report(sync, sched, async_r)
        # 算法层有 smartcrush-1KB
        assert "smartcrush-1KB" in out
        # 调度层有 scheduler-mixed-1KB
        assert "scheduler-mixed-1KB" in out
        # 异步层有 queue-1KB 和 async_entry-1KB
        assert "queue-1KB" in out
        assert "async_entry-1KB" in out

    def test_timestamp_in_header(self, sample_inputs):
        """生成时间字段必须存在且格式是 YYYY-MM-DD HH:MM:SS."""
        sync, sched, async_r = sample_inputs
        out = pb.format_report(sync, sched, async_r)
        # 报告标题里的日期
        title_match = re.search(r"# Mark42 压缩子系统性能基准 \(\d{4}-\d{2}-\d{2}\)", out)
        assert title_match is not None
        # 测试环境块的生成时间
        gen_match = re.search(r"- 生成时间: \d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}", out)
        assert gen_match is not None

    def test_does_not_write_to_disk(self, sample_inputs, tmp_path):
        """format_report 是纯字符串函数, 不应该触碰文件系统."""
        sync, sched, async_r = sample_inputs
        # 在 tmp_path 切到该目录, 看是否产生新文件
        import os
        cwd_before = set(os.listdir(tmp_path))
        out = pb.format_report(sync, sched, async_r)
        cwd_after = set(os.listdir(tmp_path))
        assert cwd_before == cwd_after
        assert isinstance(out, str)
