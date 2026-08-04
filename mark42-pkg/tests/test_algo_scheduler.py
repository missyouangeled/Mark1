"""algo_scheduler 的 pytest 测试。

历史问题：本文件原先只有一个 run_tests() 普通函数，没有任何 test_* 函数，
pytest 收集数为 0（`pytest --collect-only` 退出码 5），因此调度器的
PII 回退泄漏与 large 桶安全策略绕过两个缺陷长期没有被测试发现。
现已改为真正会被 pytest 收集的测试。
"""

import json
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from mark42.algo_scheduler import SchedulerConfig, decide, process


# ---------------------------------------------------------------------------
# 尺寸分层与基础契约
# ---------------------------------------------------------------------------

def _small_json() -> str:
    items = ",".join(
        '{"id": ' + str(i) + ', "name": "user_' + str(i) + "_" + ("x" * 20) + '"}'
        for i in range(100)
    )
    return '{"items": [' + items + "]}"


def _medium_json_with_pii() -> str:
    users = ",".join(
        '{"email": "user' + str(i) + '@example.com", "name": "user_' + str(i) + '"}'
        for i in range(500)
    )
    return '{"users": [' + users + "]}"


def _large_json() -> str:
    return '{"data": [' + ",".join('"x"' for _ in range(50000)) + "]}"


@pytest.mark.parametrize(
    "name,content,exp_action,exp_bucket,exp_compress,exp_pii",
    [
        ("tiny_text", "hello world", "skip", "tiny", False, False),
        ("tiny_json", '{"a": 1}', "skip", "tiny", False, False),
        ("small_text", "x" * 5000, "skip", "small", False, False),
        ("small_json", _small_json(), "compress", "small", True, False),
        ("medium_json_with_pii", _medium_json_with_pii(), "compress+pii", "medium", True, True),
        ("large_json", _large_json(), "review", "large", True, True),
        ("invalid_json", "not json at all, just text " * 200, "skip", "small", False, False),
    ],
)
def test_size_bucket_contract(name, content, exp_action, exp_bucket, exp_compress, exp_pii):
    """尺寸分层与动作契约。"""
    d = process(content)["decision"]
    assert d.action == exp_action, name
    assert d.size_bucket == exp_bucket, name
    assert d.should_compress == exp_compress, name
    assert d.should_redact_pii == exp_pii, name


def test_tiny_content_unchanged():
    r = process('{"a": 1, "b": 2}')
    assert r["changed"] is False


def test_empty_input_failsafe():
    r = process("")
    assert r["result"] == ""


def test_big_json_with_pii_compresses_and_redacts():
    payload = json.dumps(
        {"logs": [{"user": f"user{i}@example.com", "msg": "x" * 100} for i in range(200)]},
        ensure_ascii=False,
    )
    r = process(payload)
    assert r["changed"] is True
    assert r["pii_stats"]["total_redactions"] > 0
    assert r["compress_stats"]["ratio"] > 0


# ---------------------------------------------------------------------------
# 安全不变量：PII 脱敏后绝不因压缩回退而返回原文
# ---------------------------------------------------------------------------

def test_pii_never_leaks_when_compression_falls_back(monkeypatch):
    """回归测试：压缩护栏回退时不得返回未脱敏原文。

    历史 bug：脱敏结果只存于局部变量，护栏提前 return 时
    result["result"] 仍是原始敏感内容。
    """
    import mark42.algo_scheduler as sched

    payload = json.dumps({"email": "leak-me@example.com", "pad": "x" * 12000})

    # 强制压缩无收益，触发 min_useful_ratio 护栏
    monkeypatch.setattr(
        sched,
        "smartcrush",
        lambda c: (c, {"ratio": 0.0, "original_bytes": len(c.encode()), "crushed_bytes": len(c.encode())}),
    )

    r = sched.process(payload)

    assert r["pii_stats"]["total_redactions"] > 0
    assert r["fallback_reason"] is not None
    assert "leak-me@example.com" not in r["result"]
    assert "[EMAIL" in r["result"] or "REDACTED" in r["result"].upper()


def test_pii_never_leaks_when_size_guard_falls_back(monkeypatch):
    """回归测试：max_safe_ratio 护栏回退同样不得泄漏原文。"""
    import mark42.algo_scheduler as sched

    payload = json.dumps({"email": "leak-me2@example.com", "pad": "y" * 12000})

    def fake_crush(c):
        original = len(c.encode())
        return c, {"ratio": 0.5, "original_bytes": original, "crushed_bytes": original}

    monkeypatch.setattr(sched, "smartcrush", fake_crush)

    r = sched.process(payload)

    assert r["fallback_reason"] is not None
    assert "leak-me2@example.com" not in r["result"]


# ---------------------------------------------------------------------------
# 安全不变量：large 桶策略不得被内容类型分支绕过
# ---------------------------------------------------------------------------

LARGE_CODE = "def f():\n return 1\n# filler\n" * 4000
LARGE_DIFF = "@@ -1,2 +1,2 @@\n-old\n+new\n" * 8000
LARGE_TEXT = ("word " * 40 + "\n") * 1200
LARGE_LOG = "\n".join(["2026-08-04 10:00:00 [ERROR] repeated failure"] * 4000)


@pytest.mark.parametrize(
    "name,content,exp_algo",
    [
        ("code", LARGE_CODE, "code"),
        ("diff", LARGE_DIFF, "diff"),
        ("text", LARGE_TEXT, "text"),
        ("log", LARGE_LOG, "log"),
    ],
)
def test_large_bucket_safety_not_bypassed_by_content_type(name, content, exp_algo):
    """回归测试：大型 code/diff/log/text 必须应用 large 桶的 PII 与 review 策略。

    历史 bug：内容类型分支使用 pii_enabled_medium，且从不设置 needs_review，
    导致 >100KB 内容在 pii_enabled_medium=False 时既不脱敏也不标记 review。
    """
    cfg = SchedulerConfig(pii_enabled_medium=False, pii_enabled_large=True)
    d = decide(content, cfg)

    assert d.size_bucket == "large", name
    assert d.route_algo == exp_algo, name
    assert d.should_redact_pii is True, f"{name}: large 桶必须脱敏"
    assert d.needs_review is True, f"{name}: large 桶必须标记 review"


def test_medium_bucket_not_escalated_to_review():
    """medium 内容不得被误升级为 review。"""
    d = decide("def f():\n return 1\n# filler\n" * 800, SchedulerConfig())
    assert d.size_bucket == "medium"
    assert d.needs_review is False


# ---------------------------------------------------------------------------
# 算法路由
# ---------------------------------------------------------------------------

def test_diff_route():
    diff_input = "@@ -1,5 +1,5 @@\n" + "\n".join(f" line{i}" for i in range(5)) + "\n-old\n+new\n"
    r = process(diff_input)
    assert r["decision"].route_algo == "diff"
    assert r["changed"]
    assert r["compress_stats"] is not None


def test_code_route():
    code_input = (
        "def foo(x, y):\n"
        '    """foo 函数 docstring"""\n'
        "    a = 1\n"
        "    b = 2\n"
        "    c = 3\n"
        "    return a + b + c\n"
        "\n"
        "class Bar:\n"
        '    """Bar 类 docstring"""\n'
        "    def __init__(self, x):\n"
        "        self.x = x\n"
        "    def method(self):\n"
        "        return self.x * 2\n"
        "    def method2(self):\n"
        "        return self.x + 100\n"
    )
    r = process(code_input)
    assert r["decision"].route_algo == "code"
    assert r["changed"]


def test_log_route():
    log_lines = ["[INFO] 2026-06-25T07:18:00 request_id=12345 status=200"] * 60 + [
        "[INFO] 2026-06-25T07:18:01 request_id=12346 status=200"
    ] * 10
    r = process("\n".join(log_lines))
    assert r["decision"].route_algo == "log"
    assert r["changed"]


def test_text_route():
    long_text = "\n".join(
        f"这是第 {i:03d} 段长文本内容，包含足够多的字符以满足平均行长要求。内容是随机的描述性句子。\n"
        f"总而言之，这是一个测试文本。使用了同义词，进行压缩，应该有效果。\n"
        f"数据库有 {10000 + i * 100} 条记录, 缓存命中 {5000 + i * 10} 次。\n"
        for i in range(50)
    )
    assert len(long_text.encode("utf-8")) >= 4 * 1024
    r = process(long_text)
    assert r["decision"].route_algo == "text"
    assert r["changed"]


def test_json_keeps_smartcrush_contract():
    json_input = json.dumps({"items": [{"id": i, "name": "user_" + str(i) * 5} for i in range(20)]})
    r = process(json_input)
    assert r["decision"].route_algo == "smartcrush"


def test_diff_route_wins_over_code():
    diff_with_code = "diff --git a/foo.py b/foo.py\n@@ -1,2 +1,2 @@\n-def foo():\n+def bar():\n pass\n"
    r = process(diff_with_code)
    assert r["decision"].route_algo == "diff"


def test_low_ratio_triggers_fallback():
    """低压缩率必须回退且不标记 changed。"""
    r = process("ERROR something\n" * 20)
    if r["compress_stats"] and r["compress_stats"]["ratio"] < 0.10:
        assert r["fallback_reason"] is not None
        assert r["changed"] is False
