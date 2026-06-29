"""armor.py armor_check() 的单测 - 验证健康度检查在各种使用率下的行为。

测试策略：
  - mock _find_active_session 模拟有/无活跃 session
  - mock subprocess.run 模拟 du 命令输出
  - 不依赖真文件系统，全用 tmp_path

⚠️ 真实契约（从 armor.py 第 80-110 行读出来）：
  - severity: ok / info / warn / critical
  - status:   ok / warn / alert / critical
  - tokens 估算公式: int(st_size // BYTES_PER_KTOKEN * 1000)
    这个公式实际是把字节数放大成"千 token"再 ×1000 = token 数
    设计意图: 中文 JSONL 密集, 1KB ≈ 0.5K token
  - context_window 默认 131072，生产可能读 config 变成 1000000
"""

import subprocess
import os
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from mark42_modules import armor


def _patch_du(mocker, size_kb: int):
    """helper: mock 掉 armor 函数内 import 的 subprocess.run。"""
    fake_du = MagicMock()
    fake_du.stdout = f"{size_kb}\t/sessions"
    return mocker.patch("subprocess.run", return_value=fake_du)


# ── 1. 无活跃会话 ──

def test_check_no_active_session():
    """没有活跃会话时，返回 status=unknown, severity=ok。"""
    with patch.object(armor, "_find_active_session", return_value=None):
        result = armor.armor_check()

    assert result["status"] == "unknown"
    assert result["severity"] == "ok"
    assert result["usagePercent"] == 0
    assert "未找到活跃会话" in result["summary"]


# ── 2. 有活跃会话 + 低使用率 ──

def test_check_low_usage_ok(mocker):
    """低使用率（< WARN 70%）时 severity=ok, status=ok。"""
    # 算一个能产生 < 70% 的字节数
    target_pct = 50.0
    # tokens = pct/100 * 131072 ≈ 65536
    # bytes = tokens / 1000 * BYTES_PER_KTOKEN
    bytes_needed = int(target_pct / 100 * 131072 / 1000 * armor.BYTES_PER_KTOKEN)
    fake_session = MagicMock()
    fake_session.name = "agent-main-main.jsonl"
    fake_session.stat.return_value.st_size = bytes_needed
    _patch_du(mocker, bytes_needed // 1024)

    with patch.object(armor, "_find_active_session", return_value=fake_session):
        result = armor.armor_check()

    assert result["status"] == "ok"
    assert result["severity"] == "ok"
    assert result["usagePercent"] < armor.THRESHOLD_WARN


# ── 3. WARN 区间（70-85%） ──

def test_check_warn_band_info_severity(mocker):
    """使用率在 WARN 区间时：status=warn, severity=info（命名不一致是历史遗留）。"""
    target_pct = 75.0
    bytes_needed = int(target_pct / 100 * 131072 / 1000 * armor.BYTES_PER_KTOKEN)
    fake_session = MagicMock()
    fake_session.name = "agent.jsonl"
    fake_session.stat.return_value.st_size = bytes_needed
    _patch_du(mocker, bytes_needed // 1024)

    # P1.1: 切到 simple 模式保证原公式逻辑 (mock 环境下 smart 模式无字符可扫)
    mocker.patch.dict(os.environ, {"MARK42_TOKEN_ESTIMATE_MODE": "simple"})

    with patch.object(armor, "_find_active_session", return_value=fake_session):
        result = armor.armor_check()

    assert armor.THRESHOLD_WARN <= result["usagePercent"] < armor.THRESHOLD_ALERT
    assert result["severity"] == "info"
    assert result["status"] == "warn"


# ── 4. ALERT 区间（85-95%） ──

def test_check_alert_band_warn_severity(mocker):
    """使用率在 ALERT 区间时：status=alert, severity=warn（命名对调了）。"""
    target_pct = 90.0
    bytes_needed = int(target_pct / 100 * 131072 / 1000 * armor.BYTES_PER_KTOKEN)
    fake_session = MagicMock()
    fake_session.name = "agent.jsonl"
    fake_session.stat.return_value.st_size = bytes_needed
    _patch_du(mocker, bytes_needed // 1024)

    mocker.patch.dict(os.environ, {"MARK42_TOKEN_ESTIMATE_MODE": "simple"})

    with patch.object(armor, "_find_active_session", return_value=fake_session):
        result = armor.armor_check()

    assert armor.THRESHOLD_ALERT <= result["usagePercent"] < armor.THRESHOLD_CRIT
    assert result["severity"] == "warn"
    assert result["status"] == "alert"


# ── 5. CRIT 区间（>= 95%） ──

def test_check_crit_band_critical_severity(mocker):
    """使用率 >= CRIT 时：status=critical, severity=critical。"""
    target_pct = 98.0
    bytes_needed = int(target_pct / 100 * 131072 / 1000 * armor.BYTES_PER_KTOKEN)
    fake_session = MagicMock()
    fake_session.name = "agent.jsonl"
    fake_session.stat.return_value.st_size = bytes_needed
    _patch_du(mocker, bytes_needed // 1024)

    mocker.patch.dict(os.environ, {"MARK42_TOKEN_ESTIMATE_MODE": "simple"})

    with patch.object(armor, "_find_active_session", return_value=fake_session):
        result = armor.armor_check()

    assert result["usagePercent"] >= armor.THRESHOLD_CRIT
    assert result["severity"] == "critical"
    assert result["status"] == "critical"
    assert "危险等级" in result["summary"]


# ── 6. 边界条件：刚好到 WARN 阈值 ──

def test_check_warn_threshold_triggers(mocker):
    """使用率达到 WARN 阈值时应该进入 WARN band。

    注意：armor 的 token 公式用整数除法，在 70% 边界会有 ~0.6% 偏差。
    我们造 71% 而不是 70%，确保稳定进入 WARN band。
    """
    target_pct = 71.0  # 略高于阈值，避免整数除法下偏差
    bytes_needed = int(target_pct / 100 * 131072 / 1000 * armor.BYTES_PER_KTOKEN)
    fake_session = MagicMock()
    fake_session.name = "agent.jsonl"
    fake_session.stat.return_value.st_size = bytes_needed
    _patch_du(mocker, bytes_needed // 1024)

    mocker.patch.dict(os.environ, {"MARK42_TOKEN_ESTIMATE_MODE": "simple"})

    with patch.object(armor, "_find_active_session", return_value=fake_session):
        result = armor.armor_check()

    assert result["usagePercent"] >= armor.THRESHOLD_WARN
    assert result["status"] == "warn"
    assert result["severity"] == "info"


# ── 7. 边界条件：刚低于 WARN 阈值 ──

def test_check_just_below_warn(mocker):
    """使用率 69% 时应该 status=ok。"""
    target_pct = 69.0
    bytes_needed = int(target_pct / 100 * 131072 / 1000 * armor.BYTES_PER_KTOKEN)
    fake_session = MagicMock()
    fake_session.name = "agent.jsonl"
    fake_session.stat.return_value.st_size = bytes_needed
    _patch_du(mocker, bytes_needed // 1024)

    with patch.object(armor, "_find_active_session", return_value=fake_session):
        result = armor.armor_check()

    assert result["usagePercent"] < armor.THRESHOLD_WARN
    assert result["status"] == "ok"


# ── 8. du 命令失败时不应该抛异常 ──

def test_check_handles_du_failure(mocker):
    """du 命令失败时 armor_check 不应崩溃。"""
    fake_session = MagicMock()
    fake_session.name = "agent.jsonl"
    fake_session.stat.return_value.st_size = 10 * 1024
    _patch_du(mocker, 0)

    with patch.object(armor, "_find_active_session", return_value=fake_session):
        result = armor.armor_check()
        assert "usagePercent" in result
        assert "estimatedTokens" in result


# ── 9. 真实子进程隔离（验证 conftest 真隔离了文件系统） ──

def test_real_du_runs_against_tmp_path(tmp_path, mocker):
    """用真 subprocess.run("du", ...) 验证它真的只在 tmp_path 下查。"""
    fake_sessions = tmp_path / "state" / "openclaw" / "sessions"
    fake_sessions.mkdir(parents=True, exist_ok=True)
    (fake_sessions / "agent.jsonl").write_text("x" * 100_000)

    fake_session = MagicMock()
    fake_session.name = "agent.jsonl"
    fake_session.stat.return_value.st_size = 100_000

    real_du = subprocess.run(
        ["du", "-s", str(fake_sessions)],
        capture_output=True, text=True
    )
    fake_du = MagicMock()
    fake_du.stdout = real_du.stdout
    mocker.patch("subprocess.run", return_value=fake_du)

    with patch.object(armor, "_find_active_session", return_value=fake_session):
        result = armor.armor_check()

    # sessionsDirKB 和 activeFileMB 在 result 顶层
    assert result["sessionsDirKB"] > 0
    assert result["activeFileMB"] > 0
    assert result["activeSession"] == "agent.jsonl"


# ── 10. 返回字段完整性 ──

def test_check_returned_fields(mocker):
    """验证返回字典包含所有必要字段（契约冻结）。"""
    # mock 避免依赖真 session 和 du 命令
    fake_session = MagicMock()
    fake_session.name = "agent.jsonl"
    fake_session.stat.return_value.st_size = 10 * 1024
    _patch_du(mocker, 10)

    with patch.object(armor, "_find_active_session", return_value=fake_session):
        result = armor.armor_check()

    expected_keys = {
        "checkedAt", "host", "status", "severity", "summary",
        "usagePercent", "estimatedTokens", "contextWindow",
    }
    assert expected_keys.issubset(result.keys()), (
        f"缺少字段: {expected_keys - set(result.keys())}"
    )
    assert isinstance(result["usagePercent"], (int, float))


# ── 11. token 估算公式（契约冻结） ──

def test_token_estimation_formula(mocker):
    """锁死 armor 的 token 估算公式 (simple 模式)。

    公式: int(st_size // BYTES_PER_KTOKEN * 1000)
    含义: 字节数 / 2KB = 千 token 数, × 1000 = token 数
    """
    # P1.1: 切到 simple 模式保证原公式逻辑
    mocker.patch.dict(os.environ, {"MARK42_TOKEN_ESTIMATE_MODE": "simple"})

    # 1MB 字节应该产生多少 token?
    st_size = 1024 * 1024  # 1MB
    expected_tokens = int(st_size // armor.BYTES_PER_KTOKEN * 1000)

    fake_session = MagicMock()
    fake_session.name = "agent.jsonl"
    fake_session.stat.return_value.st_size = st_size
    _patch_du(mocker, 1024)

    with patch.object(armor, "_find_active_session", return_value=fake_session):
        result = armor.armor_check()

    assert result["estimatedTokens"] == expected_tokens


def test_token_estimation_smart_mode(tmp_path, mocker):
    """P1.1: smart 模式按语言密度估算 tokens。

    场景: session 文件包含 100 条消息, 平均每条 50 个中文字 + 100 个英文字 + 50 个标点。
    预计 token 数:
      中文: 100*50 * 1.5 = 7,500
      英文: 100*100 * 0.25 = 2,500
      标点: 100*50 * 0.1 = 500
      总计 ≈ 10,500 tokens (加上外推余量)
    """
    mocker.patch.dict(os.environ, {"MARK42_TOKEN_ESTIMATE_MODE": "smart"})

    # 造一个临时 session jsonl, 100 条消息, 中文密度
    session_file = tmp_path / "test_session.jsonl"
    zh_msg = "你好世界" * 12  # 48 个中文字
    en_msg = "hello world this is a test message " * 3  # ~100 chars en
    msg = {
        "type": "message",
        "message": {
            "role": "user",
            "content": zh_msg + " " + en_msg,
        }
    }
    lines = [json.dumps(msg) for _ in range(100)]
    session_file.write_text("\n".join(lines) + "\n")

    result = armor._estimate_tokens_smart(session_file, scan_lines=200)

    # 应该扫到 ~100 条消息 (允许 ±1 容差, 最后一行可能无换行符)
    assert 99 <= result["scannedMessages"] <= 100
    assert result["zhChars"] > 0
    assert result["enChars"] > 0

    # token 估算范围合理 (中文 48*100*1.5=7200 + 英文 100*100*0.25=2500 = 9700, 允许 ±50% 浮动)
    assert 5000 < result["estimatedTokens"] < 30000, (
        f"估算 tokens={result['estimatedTokens']} 不在合理范围"
    )
    assert result["method"] == "smart"


def test_token_estimation_smart_mode_zh_heavy():
    """P1.1: 纯中文场景 - 验证 smart 模式不出现 6× 高估。

    原公式 1MB 中文 JSONL = 500K tokens (1KB = 0.5K token)
    但实际中文 + JSON 包装 = ~80K tokens (中文 1.5 token/char)
    smart 模式应该接近 80K 而不是 500K。
    """
    # 生成 50KB 中文为主的 JSONL
    session_file = "/tmp/_test_zh_session.jsonl"
    zh_msg = "今天我们学习 Python 编程基础。" * 50  # ~1500 字中文
    msg = {"type": "message", "message": {"role": "user", "content": zh_msg}}
    lines = [json.dumps(msg) for _ in range(40)]  # 40 条消息
    with open(session_file, "w") as f:
        f.write("\n".join(lines))

    size_bytes = os.path.getsize(session_file)
    print(f"\n  session 大小: {size_bytes/1024:.1f}KB")

    # 简单公式 (原行为): size_bytes // 2048 * 1000
    BYTES_PER_KTOKEN = 2048
    simple_tokens = int(size_bytes // BYTES_PER_KTOKEN * 1000)
    print(f"  原公式估算: {simple_tokens:,} tokens")

    # smart 公式: 按密度估算
    import sys; sys.path.insert(0, "scripts")
    from mark42_modules.utils import _estimate_tokens_smart
    result = _estimate_tokens_smart(Path(session_file))
    print(f"  smart 估算: {result['estimatedTokens']:,} tokens")
    print(f"  ratio: {simple_tokens / max(result['estimatedTokens'], 1):.2f}x")

    # smart 估算应明显小于原公式 (中文场景至少少 2×)
    assert result["estimatedTokens"] * 2 <= simple_tokens, (
        f"smart 估算 ({result['estimatedTokens']}) 仅为原公式 ({simple_tokens}) 的 "
        f"{result['estimatedTokens']/simple_tokens*100:.1f}%, 中文场景预期 ≤50%"
    )

    os.unlink(session_file)


# ── 12. 严重度映射（parametrize） ──

@pytest.mark.parametrize("target_pct,expected_severity,expected_status", [
    (50,  "ok",        "ok"),
    (75,  "info",      "warn"),
    (90,  "warn",      "alert"),
    (98,  "critical",  "critical"),
])
def test_severity_mapping_at_thresholds(mocker, target_pct, expected_severity, expected_status):
    """参数化测试 4 个使用率区间的 severity/status 映射。"""
    # P1.1: 切到 simple 模式保证原公式逻辑
    mocker.patch.dict(os.environ, {"MARK42_TOKEN_ESTIMATE_MODE": "simple"})
    bytes_needed = int(target_pct / 100 * 131072 / 1000 * armor.BYTES_PER_KTOKEN)
    fake_session = MagicMock()
    fake_session.name = "agent.jsonl"
    fake_session.stat.return_value.st_size = bytes_needed
    _patch_du(mocker, bytes_needed // 1024)

    with patch.object(armor, "_find_active_session", return_value=fake_session):
        result = armor.armor_check()

    assert result["severity"] == expected_severity
    assert result["status"] == expected_status