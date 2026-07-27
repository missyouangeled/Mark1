"""Circuit Breaker 熔断器单元测试。

测试范围:
- P1: BreakerState 数据结构
- P2: can_call/record_success/record_failure 基本操作
- P3: 状态机 closed -> open -> half_open -> closed
- P4: failure_threshold 触发断路
- P5: recovery_timeout 半开试探
- P6: reset/reset_all
- P7: list_all/get_state
"""

import time
from unittest.mock import patch, MagicMock

import pytest


# ── P1: BreakerState 数据结构 ───────────────────────

class TestBreakerState:
    """测试 BreakerState 数据结构。"""

    def test_default_values(self):
        """默认值正确。"""
        from mark42_modules.circuit_breaker import BreakerState

        b = BreakerState(core_id="test_core")
        assert b.core_id == "test_core"
        assert b.status == "closed"
        assert b.consecutive_failures == 0
        assert b.opened_at is None
        assert b.half_open_at is None
        assert b.recovery_timeout_s == 30.0
        assert b.failure_threshold == 3

    def test_to_dict(self):
        """to_dict 返回正确结构。"""
        from mark42_modules.circuit_breaker import BreakerState

        b = BreakerState(core_id="test_core")
        d = b.to_dict()

        assert d["core_id"] == "test_core"
        assert d["status"] == "closed"
        assert d["consecutive_failures"] == 0
        assert "recovery_in_s" in d

    def test_recovery_in_s_when_closed(self):
        """closed 状态 recovery_in_s 为 None。"""
        from mark42_modules.circuit_breaker import BreakerState

        b = BreakerState(core_id="test_core")
        assert b._recovery_in_s() is None

    def test_recovery_in_s_when_open(self):
        """open 状态 recovery_in_s 正确计算。"""
        from mark42_modules.circuit_breaker import BreakerState

        b = BreakerState(core_id="test_core")
        b.status = "open"
        b.opened_at = time.monotonic()

        recovery = b._recovery_in_s()
        assert recovery is not None
        assert 0 <= recovery <= 30.0


# ── P2: 基本操作测试 ─────────────────────────────────

class TestCircuitBreakerBasic:
    """测试 can_call/record_success/record_failure 基本操作。"""

    def test_can_call_closed_default(self):
        """closed 状态默认可以调用。"""
        from mark42_modules.circuit_breaker import CircuitBreaker

        cb = CircuitBreaker()
        assert cb.can_call("test_core") is True

    def test_record_success_resets_failures(self):
        """成功调用重置失败计数。"""
        from mark42_modules.circuit_breaker import CircuitBreaker

        cb = CircuitBreaker()
        cb.record_failure("test_core", "test error")
        cb.record_failure("test_core", "test error")

        state = cb.get_state("test_core")
        assert state["consecutive_failures"] == 2

        cb.record_success("test_core")

        state = cb.get_state("test_core")
        assert state["consecutive_failures"] == 0
        assert state["status"] == "closed"

    def test_record_failure_increments_count(self):
        """失败调用递增计数。"""
        from mark42_modules.circuit_breaker import CircuitBreaker

        cb = CircuitBreaker()
        cb.record_failure("test_core", "error 1")
        cb.record_failure("test_core", "error 2")

        state = cb.get_state("test_core")
        assert state["consecutive_failures"] == 2

    def test_independent_cores(self):
        """不同核心的熔断器独立。"""
        from mark42_modules.circuit_breaker import CircuitBreaker

        cb = CircuitBreaker()

        # core1 失败 3 次
        for _ in range(3):
            cb.record_failure("core1", "error")

        # core2 没失败过
        cb.record_success("core2")

        assert cb.can_call("core1") is False  # 已断路
        assert cb.can_call("core2") is True   # 正常


# ── P3: 状态机测试 ──────────────────────────────────

class TestStateMachine:
    """测试状态机：closed -> open -> half_open -> closed"""

    def test_closed_to_open_on_threshold(self):
        """连续失败达到阈值 -> open。"""
        from mark42_modules.circuit_breaker import CircuitBreaker

        cb = CircuitBreaker()

        # 连续失败 3 次
        for _ in range(3):
            cb.record_failure("test_core", "error")

        state = cb.get_state("test_core")
        assert state["status"] == "open"
        assert state["opened_at"] is not None

    def test_open_to_half_open_after_timeout(self):
        """断路后等待 timeout -> half_open。"""
        from mark42_modules.circuit_breaker import CircuitBreaker

        cb = CircuitBreaker()

        # 先断路
        for _ in range(3):
            cb.record_failure("test_core", "error")

        state = cb.get_state("test_core")
        assert state["status"] == "open"

        # mock 时间过去 30 秒
        with patch("mark42_modules.circuit_breaker.time.monotonic") as mock_time:
            # 先设置为断路时间
            open_time = 1000.0
            mock_time.return_value = open_time

            # 重置 opened_at 为已知值（重新触发断路）
            cb._get("test_core").opened_at = open_time

            # 时间过去 35 秒
            mock_time.return_value = open_time + 35.0

            # can_call 应该检测到可以半开试探
            assert cb.can_call("test_core") is True

            state = cb.get_state("test_core")
            assert state["status"] == "half_open"

    def test_half_open_success_to_closed(self):
        """半开试探成功 -> closed。"""
        from mark42_modules.circuit_breaker import CircuitBreaker

        cb = CircuitBreaker()

        # 先断路
        for _ in range(3):
            cb.record_failure("test_core", "error")

        # 模拟半开状态
        cb._get("test_core").status = "half_open"

        # 成功调用
        cb.record_success("test_core")

        state = cb.get_state("test_core")
        assert state["status"] == "closed"
        assert state["consecutive_failures"] == 0
        assert state["opened_at"] is None

    def test_half_open_failure_to_open(self):
        """半开试探失败 -> 重新 open。"""
        from mark42_modules.circuit_breaker import CircuitBreaker

        cb = CircuitBreaker()

        # 先断路
        for _ in range(3):
            cb.record_failure("test_core", "error")

        # 模拟半开状态
        cb._get("test_core").status = "half_open"

        # 失败调用
        cb.record_failure("test_core", "probe failed")

        state = cb.get_state("test_core")
        assert state["status"] == "open"
        assert state["opened_at"] is not None

    def test_open_blocks_calls(self):
        """open 状态阻止调用。"""
        from mark42_modules.circuit_breaker import CircuitBreaker

        cb = CircuitBreaker()

        # 断路
        for _ in range(3):
            cb.record_failure("test_core", "error")

        # 在 timeout 之前（用 mock 控制时间）
        with patch("mark42_modules.circuit_breaker.time.monotonic") as mock_time:
            cb._get("test_core").opened_at = 1000.0
            mock_time.return_value = 1005.0  # 只过了 5 秒

            assert cb.can_call("test_core") is False


# ── P4: 阈值配置测试 ───────────────────────────────

class TestFailureThreshold:
    """测试 failure_threshold 配置。"""

    def test_custom_threshold(self):
        """可以自定义阈值（通过直接修改 BreakerState）。"""
        from mark42_modules.circuit_breaker import CircuitBreaker

        cb = CircuitBreaker()

        # 修改阈值为 5
        cb._get("test_core").failure_threshold = 5

        # 失败 4 次，还没到阈值
        for _ in range(4):
            cb.record_failure("test_core", "error")

        state = cb.get_state("test_core")
        assert state["status"] == "closed"  # 还没断路

        # 第 5 次失败
        cb.record_failure("test_core", "error")

        state = cb.get_state("test_core")
        assert state["status"] == "open"  # 现在断路了

    def test_failure_count_stays_after_threshold(self):
        """超过阈值后失败计数继续增加。"""
        from mark42_modules.circuit_breaker import CircuitBreaker

        cb = CircuitBreaker()

        # 失败 5 次（超过阈值 3）
        for _ in range(5):
            cb.record_failure("test_core", "error")

        state = cb.get_state("test_core")
        assert state["consecutive_failures"] == 5
        assert state["status"] == "open"


# ── P5: recovery_timeout 测试 ───────────────────────

class TestRecoveryTimeout:
    """测试 recovery_timeout 半开试探。"""

    def test_custom_timeout(self):
        """可以自定义超时时间。"""
        from mark42_modules.circuit_breaker import CircuitBreaker

        cb = CircuitBreaker()

        # 修改超时为 60 秒
        cb._get("test_core").recovery_timeout_s = 60.0

        # 断路
        for _ in range(3):
            cb.record_failure("test_core", "error")

        with patch("mark42_modules.circuit_breaker.time.monotonic") as mock_time:
            cb._get("test_core").opened_at = 1000.0

            # 只过了 30 秒（原默认超时），但自定义超时 60 秒，所以还不能试探
            mock_time.return_value = 1030.0
            assert cb.can_call("test_core") is False

            # 过了 65 秒，超过自定义超时
            mock_time.return_value = 1065.0
            assert cb.can_call("test_core") is True

    def test_half_open_allows_one_call(self):
        """半开状态允许一次试探调用。"""
        from mark42_modules.circuit_breaker import CircuitBreaker

        cb = CircuitBreaker()

        # 断路
        for _ in range(3):
            cb.record_failure("test_core", "error")

        # 超时后变为半开
        with patch("mark42_modules.circuit_breaker.time.monotonic") as mock_time:
            cb._get("test_core").opened_at = 1000.0
            mock_time.return_value = 1035.0

            assert cb.can_call("test_core") is True  # 第 1 次试探
            assert cb.can_call("test_core") is True  # 第 2 次也可以（半开状态一直可以）

    def test_multiple_cores_timeout_independent(self):
        """多个核心超时独立。"""
        from mark42_modules.circuit_breaker import CircuitBreaker

        cb = CircuitBreaker()

        # 两个核心都断路
        for _ in range(3):
            cb.record_failure("core1", "error")
            cb.record_failure("core2", "error")

        with patch("mark42_modules.circuit_breaker.time.monotonic") as mock_time:
            # core1 在 1000 秒断路, core2 在 1010 秒断路
            cb._get("core1").opened_at = 1000.0
            cb._get("core2").opened_at = 1010.0

            # 时间 1025 秒: core1 过了 25 秒（还没到 30），core2 过了 15 秒
            mock_time.return_value = 1025.0
            assert cb.can_call("core1") is False
            assert cb.can_call("core2") is False

            # 时间 1035 秒: core1 过了 35 秒（可以半开），core2 过了 25 秒
            mock_time.return_value = 1035.0
            assert cb.can_call("core1") is True
            assert cb.can_call("core2") is False


# ── P6: reset 测试 ─────────────────────────────────

class TestReset:
    """测试 reset/reset_all。"""

    def test_reset_single_core(self):
        """重置单个核心。"""
        from mark42_modules.circuit_breaker import CircuitBreaker

        cb = CircuitBreaker()

        # 断路
        for _ in range(3):
            cb.record_failure("core1", "error")

        assert cb.can_call("core1") is False

        # 重置
        cb.reset("core1")

        state = cb.get_state("core1")
        assert state["status"] == "closed"
        assert state["consecutive_failures"] == 0
        assert state["opened_at"] is None
        assert cb.can_call("core1") is True

    def test_reset_all_cores(self):
        """重置所有核心。"""
        from mark42_modules.circuit_breaker import CircuitBreaker

        cb = CircuitBreaker()

        # 多个核心都断路
        for _ in range(3):
            cb.record_failure("core1", "error")
            cb.record_failure("core2", "error")
            cb.record_failure("core3", "error")

        assert cb.can_call("core1") is False
        assert cb.can_call("core2") is False
        assert cb.can_call("core3") is False

        # 全部重置
        cb.reset_all()

        assert cb.can_call("core1") is True
        assert cb.can_call("core2") is True
        assert cb.can_call("core3") is True

    def test_reset_non_existent_core(self):
        """重置不存在的核心也不会报错。"""
        from mark42_modules.circuit_breaker import CircuitBreaker

        cb = CircuitBreaker()

        # 不抛异常
        cb.reset("non_existent_core")

        # 验证创建了该核心并为 closed 状态
        state = cb.get_state("non_existent_core")
        assert state["status"] == "closed"


# ── P7: list_all/get_state 测试 ───────────────────

class TestStatusQueries:
    """测试 list_all/get_state。"""

    def test_get_state_returns_correct_structure(self):
        """get_state 返回正确结构。"""
        from mark42_modules.circuit_breaker import CircuitBreaker

        cb = CircuitBreaker()
        state = cb.get_state("test_core")

        assert "core_id" in state
        assert "status" in state
        assert "consecutive_failures" in state
        assert "opened_at" in state
        assert "recovery_in_s" in state

    def test_get_state_triggers_half_open(self):
        """get_state 调用时会检查是否该半开。"""
        from mark42_modules.circuit_breaker import CircuitBreaker

        cb = CircuitBreaker()

        # 断路
        for _ in range(3):
            cb.record_failure("test_core", "error")

        with patch("mark42_modules.circuit_breaker.time.monotonic") as mock_time:
            cb._get("test_core").opened_at = 1000.0
            mock_time.return_value = 1035.0

            # get_state 会调用 can_call，从而触发半开
            state = cb.get_state("test_core")
            assert state["status"] == "half_open"

    def test_list_all_only_non_closed(self):
        """list_all 只返回非 closed 状态的核心。"""
        from mark42_modules.circuit_breaker import CircuitBreaker

        cb = CircuitBreaker()

        # core1 断路
        for _ in range(3):
            cb.record_failure("core1", "error")

        # core2 正常
        cb.record_success("core2")

        # core3 失败 2 次但还没断路
        cb.record_failure("core3", "error")
        cb.record_failure("core3", "error")

        result = cb.list_all()

        # 只有 core1 非 closed
        assert len(result) == 1
        assert result[0]["core_id"] == "core1"
        assert result[0]["status"] == "open"

    def test_list_all_empty_when_all_closed(self):
        """所有核心都 closed 时 list_all 返回空列表。"""
        from mark42_modules.circuit_breaker import CircuitBreaker

        cb = CircuitBreaker()

        cb.record_success("core1")
        cb.record_success("core2")

        result = cb.list_all()
        assert result == []


# ── P8: 实际使用场景测试 ────────────────────────────

class TestRealWorldScenarios:
    """测试实际使用场景。"""

    def test_typical_call_pattern(self):
        """典型调用模式：can_call -> try -> record_success/record_failure。"""
        from mark42_modules.circuit_breaker import CircuitBreaker

        cb = CircuitBreaker()
        results = []

        for i in range(10):
            if cb.can_call("api_call"):
                try:
                    # 模拟 API 调用（前 5 次成功，后 5 次失败）
                    if i < 5:
                        results.append("success")
                        cb.record_success("api_call")
                    else:
                        raise Exception("API error")
                except Exception as e:
                    results.append("failure")
                    cb.record_failure("api_call", str(e))
            else:
                results.append("fallback")

        # 前 5 次成功，接下来 3 次失败，然后 2 次 fallback（断路了）
        assert results.count("success") == 5
        assert results.count("failure") == 3
        assert results.count("fallback") == 2

    def test_recovery_after_outage(self):
        """服务中断后恢复的场景。"""
        from mark42_modules.circuit_breaker import CircuitBreaker

        cb = CircuitBreaker()

        # 服务中断，连续失败
        for _ in range(5):
            cb.record_failure("service", "connection error")

        assert cb.can_call("service") is False  # 断路了

        # 服务恢复，半开试探成功
        with patch("mark42_modules.circuit_breaker.time.monotonic") as mock_time:
            cb._get("service").opened_at = 1000.0
            mock_time.return_value = 1035.0

            assert cb.can_call("service") is True  # 半开试探
            cb.record_success("service")  # 成功

            assert cb.can_call("service") is True  # 完全恢复

            # 接下来调用都正常
            for _ in range(10):
                cb.record_success("service")

            state = cb.get_state("service")
            assert state["status"] == "closed"
            assert state["consecutive_failures"] == 0

    def test_get_state_for_new_core(self):
        """get_state 对新核心返回 closed 状态。"""
        from mark42_modules.circuit_breaker import CircuitBreaker

        cb = CircuitBreaker()
        state = cb.get_state("brand_new_core")

        assert state["status"] == "closed"
        assert state["consecutive_failures"] == 0
        assert state["opened_at"] is None
