"""pytest tests for mark42/circuit_breaker.py"""

import pytest

from mark42.circuit_breaker import CircuitBreaker, BreakerState


class TestBreakerState:
    """测试 BreakerState 数据类。"""

    def test_default_state(self):
        """默认状态应为 closed，失败计数为 0。"""
        state = BreakerState(core_id="test_core")
        assert state.core_id == "test_core"
        assert state.status == "closed"
        assert state.consecutive_failures == 0
        assert state.opened_at is None

    def test_to_dict(self):
        """to_dict 应返回正确的字典格式。"""
        state = BreakerState(core_id="test_core", consecutive_failures=2)
        d = state.to_dict()
        assert d["core_id"] == "test_core"
        assert d["status"] == "closed"
        assert d["consecutive_failures"] == 2


class TestCircuitBreaker:
    """测试 CircuitBreaker 熔断器管理器。"""

    def test_initial_can_call(self):
        """初始状态下应该可以调用。"""
        cb = CircuitBreaker()
        assert cb.can_call("core_test") is True

    def test_consecutive_failures_trigger_open(self):
        """连续失败达到阈值应触发断路。"""
        cb = CircuitBreaker()
        core_id = "core_test"

        # 前 2 次失败，还没到阈值
        cb.record_failure(core_id)
        assert cb.can_call(core_id) is True
        cb.record_failure(core_id)
        assert cb.can_call(core_id) is True

        # 第 3 次失败，达到阈值，断路
        cb.record_failure(core_id)
        assert cb.can_call(core_id) is False
        state = cb.get_state(core_id)
        assert state["status"] == "open"

    def test_record_success_resets_breaker(self):
        """成功调用应重置熔断器状态。"""
        cb = CircuitBreaker()
        core_id = "core_test"

        # 先让它断路
        cb.record_failure(core_id)
        cb.record_failure(core_id)
        cb.record_failure(core_id)
        assert cb.can_call(core_id) is False

        # 手动让它到半开以便测试 success
        b = cb._get(core_id)
        b.status = "half_open"

        # 成功后应该回到 closed
        cb.record_success(core_id)
        assert cb.can_call(core_id) is True
        state = cb.get_state(core_id)
        assert state["status"] == "closed"
        assert state["consecutive_failures"] == 0

    def test_half_open_success_closes(self):
        """半开状态下成功应回到 closed。"""
        cb = CircuitBreaker()
        core_id = "core_test"

        # 先断路
        cb.record_failure(core_id)
        cb.record_failure(core_id)
        cb.record_failure(core_id)
        assert cb.can_call(core_id) is False

        # 手动设置到半开状态
        b = cb._get(core_id)
        b.status = "half_open"

        # 半开状态下应该可以调用
        assert cb.can_call(core_id) is True

        # 成功后回到 closed
        cb.record_success(core_id)
        state = cb.get_state(core_id)
        assert state["status"] == "closed"

    def test_half_open_failure_reopens(self):
        """半开状态下失败应重新断路。"""
        cb = CircuitBreaker()
        core_id = "core_test"

        # 先断路
        cb.record_failure(core_id)
        cb.record_failure(core_id)
        cb.record_failure(core_id)

        # 手动设置到半开状态
        b = cb._get(core_id)
        b.status = "half_open"

        # 半开失败应重新断路
        cb.record_failure(core_id)
        assert cb.can_call(core_id) is False
        state = cb.get_state(core_id)
        assert state["status"] == "open"

    def test_reset(self):
        """手动重置应恢复 closed 状态。"""
        cb = CircuitBreaker()
        core_id = "core_test"

        # 先断路
        cb.record_failure(core_id)
        cb.record_failure(core_id)
        cb.record_failure(core_id)
        assert cb.can_call(core_id) is False

        # 重置
        cb.reset(core_id)
        assert cb.can_call(core_id) is True
        state = cb.get_state(core_id)
        assert state["status"] == "closed"
        assert state["consecutive_failures"] == 0

    def test_reset_all(self):
        """reset_all 应重置所有熔断器。"""
        cb = CircuitBreaker()

        # 两个核心都断路
        cb.record_failure("core_1")
        cb.record_failure("core_1")
        cb.record_failure("core_1")

        cb.record_failure("core_2")
        cb.record_failure("core_2")
        cb.record_failure("core_2")

        assert cb.can_call("core_1") is False
        assert cb.can_call("core_2") is False

        # 全部重置
        cb.reset_all()

        assert cb.can_call("core_1") is True
        assert cb.can_call("core_2") is True

    def test_list_all_non_closed(self):
        """list_all 应只返回非 closed 状态的熔断器。"""
        cb = CircuitBreaker()

        # core_1 断路
        cb.record_failure("core_1")
        cb.record_failure("core_1")
        cb.record_failure("core_1")

        # core_2 正常
        cb.can_call("core_2")

        result = cb.list_all()
        assert len(result) == 1
        assert result[0]["core_id"] == "core_1"
        assert result[0]["status"] == "open"

    def test_get_state(self):
        """get_state 应返回正确的状态字典。"""
        cb = CircuitBreaker()
        core_id = "core_test"

        cb.record_failure(core_id)
        state = cb.get_state(core_id)

        assert state["core_id"] == "core_test"
        assert state["status"] == "closed"
        assert state["consecutive_failures"] == 1
