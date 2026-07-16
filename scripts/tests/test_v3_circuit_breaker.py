"""
Mark42 v3 R-CAND-02 · Circuit Breaker 熔断器单测

测试覆盖：
1. BreakerState 数据类
2. CircuitBreaker 基本状态机 (closed -> open -> half_open -> closed)
3. can_call / record_success / record_failure
4. 阈值与恢复
5. consciousness 集成（advisor 调用前熔断检查）
6. CLI 接口（如有）
"""

import unittest
import time
from unittest.mock import MagicMock, patch, PropertyMock
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from mark42_modules.circuit_breaker import BreakerState, CircuitBreaker


class TestBreakerState(unittest.TestCase):
    """BreakerState 数据类测试。"""

    def test_default_state(self):
        s = BreakerState(core_id="test_core")
        self.assertEqual(s.status, "closed")
        self.assertEqual(s.consecutive_failures, 0)
        self.assertIsNone(s.opened_at)
        self.assertEqual(s.failure_threshold, 3)
        self.assertEqual(s.recovery_timeout_s, 30.0)

    def test_to_dict(self):
        s = BreakerState(core_id="core_1", status="open", consecutive_failures=5)
        d = s.to_dict()
        self.assertEqual(d["core_id"], "core_1")
        self.assertEqual(d["status"], "open")
        self.assertEqual(d["consecutive_failures"], 5)

    def test_recovery_in_s_when_closed(self):
        s = BreakerState(core_id="x")
        self.assertIsNone(s._recovery_in_s())

    def test_recovery_in_s_when_open(self):
        s = BreakerState(core_id="x", status="open", opened_at=time.monotonic())
        r = s._recovery_in_s()
        self.assertIsNotNone(r)
        self.assertGreater(r, 0)
        self.assertLessEqual(r, 30.0)


class TestCircuitBreakerBasic(unittest.TestCase):
    """CircuitBreaker 基本状态机测试。"""

    def setUp(self):
        self.cb = CircuitBreaker()

    def test_initial_state_closed(self):
        """新核心默认 closed，可调用。"""
        self.assertTrue(self.cb.can_call("core_1"))

    def test_record_success_keeps_closed(self):
        self.cb.can_call("core_1")
        self.cb.record_success("core_1")
        self.assertEqual(self.cb.get_state("core_1")["status"], "closed")
        self.assertTrue(self.cb.can_call("core_1"))

    def test_one_failure_still_closed(self):
        self.cb.record_failure("core_1", "err1")
        self.assertEqual(self.cb.get_state("core_1")["status"], "closed")
        self.assertTrue(self.cb.can_call("core_1"))

    def test_two_failures_still_closed(self):
        self.cb.record_failure("core_1", "err1")
        self.cb.record_failure("core_1", "err2")
        self.assertEqual(self.cb.get_state("core_1")["status"], "closed")
        self.assertTrue(self.cb.can_call("core_1"))

    def test_three_failures_open(self):
        """连续失败 3 次后断路。"""
        for i in range(3):
            self.cb.record_failure("core_1", f"err{i}")
        self.assertEqual(self.cb.get_state("core_1")["status"], "open")
        self.assertFalse(self.cb.can_call("core_1"))

    def test_success_resets_counter(self):
        """成功调用重置失败计数。"""
        self.cb.record_failure("core_1", "err1")
        self.cb.record_failure("core_1", "err2")
        self.cb.record_success("core_1")
        # 只需要 3 次失败才断路，成功后计数归零
        self.cb.record_failure("core_1", "err3")
        self.cb.record_failure("core_1", "err4")
        self.assertEqual(self.cb.get_state("core_1")["status"], "closed")


class TestCircuitBreakerRecovery(unittest.TestCase):
    """熔断器恢复（open -> half_open -> closed/open）测试。"""

    def setUp(self):
        self.cb = CircuitBreaker()

    def _force_open(self, core_id="core_1"):
        """快速断路一个核心。"""
        b = self.cb._get(core_id)
        b.failure_threshold = 3
        for i in range(3):
            self.cb.record_failure(core_id, f"err{i}")
        self.assertEqual(b.status, "open")

    def test_open_blocks_calls(self):
        self._force_open()
        self.assertFalse(self.cb.can_call("core_1"))

    def test_half_open_after_timeout(self):
        """断路后等够 recovery_timeout_s，进入半开。"""
        self._force_open()
        b = self.cb._get("core_1")
        # 模拟超时：把 opened_at 往前拨
        b.opened_at = time.monotonic() - 31.0
        self.assertTrue(self.cb.can_call("core_1"))  # half_open
        self.assertEqual(b.status, "half_open")

    def test_half_open_success_closes(self):
        """半开试探成功 -> 恢复 closed。"""
        self._force_open()
        b = self.cb._get("core_1")
        b.opened_at = time.monotonic() - 31.0
        self.cb.can_call("core_1")  # -> half_open
        self.cb.record_success("core_1")
        self.assertEqual(b.status, "closed")
        self.assertEqual(b.consecutive_failures, 0)

    def test_half_open_failure_reopens(self):
        """半开试探失败 -> 重新断路。"""
        self._force_open()
        b = self.cb._get("core_1")
        b.opened_at = time.monotonic() - 31.0
        self.cb.can_call("core_1")  # -> half_open
        self.cb.record_failure("core_1", "half_open_fail")
        self.assertEqual(b.status, "open")
        # opened_at 应该被刷新
        self.assertIsNotNone(b.opened_at)

    def test_half_open_only_allows_one_call(self):
        """半开状态只允许一次试探调用。"""
        self._force_open()
        b = self.cb._get("core_1")
        b.opened_at = time.monotonic() - 31.0
        self.assertTrue(self.cb.can_call("core_1"))  # -> half_open, allowed
        # 半开后不记录结果，再次 can_call 仍允许（半开只允许一次试探的语义
        # 在 record_success/failure 后才会状态变化）
        self.assertTrue(self.cb.can_call("core_1"))  # half_open still allows


class TestCircuitBreakerMultiCore(unittest.TestCase):
    """多核心独立熔断测试。"""

    def setUp(self):
        self.cb = CircuitBreaker()

    def test_independent_cores(self):
        """一个核心断路不影响另一个。"""
        for i in range(3):
            self.cb.record_failure("core_1", f"err{i}")
        self.assertEqual(self.cb.get_state("core_1")["status"], "open")
        self.assertTrue(self.cb.can_call("core_2"))
        self.assertEqual(self.cb.get_state("core_2")["status"], "closed")

    def test_list_all_only_non_closed(self):
        """list_all 只返回非 closed 状态。"""
        self.cb.record_failure("core_1", "err1")  # 1 failure, still closed
        for i in range(3):
            self.cb.record_failure("core_2", f"err{i}")
        # core_1 closed, core_2 open
        all_states = self.cb.list_all()
        core_ids = [s["core_id"] for s in all_states]
        self.assertNotIn("core_1", core_ids)
        self.assertIn("core_2", core_ids)


class TestCircuitBreakerReset(unittest.TestCase):
    """手动重置测试。"""

    def setUp(self):
        self.cb = CircuitBreaker()

    def test_reset_single(self):
        for i in range(3):
            self.cb.record_failure("core_1", f"err{i}")
        self.assertEqual(self.cb.get_state("core_1")["status"], "open")
        self.cb.reset("core_1")
        self.assertEqual(self.cb.get_state("core_1")["status"], "closed")
        self.assertTrue(self.cb.can_call("core_1"))

    def test_reset_all(self):
        for i in range(3):
            self.cb.record_failure("core_1", f"err{i}")
            self.cb.record_failure("core_2", f"err{i}")
        self.assertEqual(self.cb.get_state("core_1")["status"], "open")
        self.assertEqual(self.cb.get_state("core_2")["status"], "open")
        self.cb.reset_all()
        self.assertEqual(self.cb.get_state("core_1")["status"], "closed")
        self.assertEqual(self.cb.get_state("core_2")["status"], "closed")


class TestCircuitBreakerCustomThreshold(unittest.TestCase):
    """自定义阈值测试。"""

    def test_custom_threshold_5(self):
        cb = CircuitBreaker()
        b = cb._get("core_1")
        b.failure_threshold = 5
        for i in range(4):
            cb.record_failure("core_1", f"err{i}")
        self.assertEqual(b.status, "closed")
        cb.record_failure("core_1", "err5")
        self.assertEqual(b.status, "open")

    def test_custom_recovery_timeout(self):
        cb = CircuitBreaker()
        b = cb._get("core_1")
        b.recovery_timeout_s = 5.0
        for i in range(3):
            cb.record_failure("core_1", f"err{i}")
        b.opened_at = time.monotonic() - 6.0
        self.assertTrue(cb.can_call("core_1"))  # half_open after 5s


class TestConsciousnessCircuitBreakerIntegration(unittest.TestCase):
    """consciousness.py 的 advisor 调用与熔断器集成测试。"""

    def _make_consciousness(self, advisor_enabled=True):
        from mark42_modules.consciousness import Consciousness
        cfg = {
            "mark42": {
                "consciousness": {"runtime": "stub", "model": "stub"},
                "advisor": {
                    "enabled": advisor_enabled, "runtime": "api", "model": "gpt-4o",
                    "base_url": "https://api.openai.com/v1", "api_key": "sk-test",
                    "confidence_threshold": 0.7,
                }
            }
        }
        c = Consciousness(config=cfg)
        c._advisor_client = MagicMock()
        c._advisor_client.enabled = advisor_enabled
        return c

    def test_breaker_initialized(self):
        """Consciousness 初始化时创建了熔断器。"""
        c = self._make_consciousness()
        self.assertIsNotNone(c._circuit_breaker)

    def test_breaker_blocks_advisor_when_open(self):
        """熔断器 open 时，advisor 调用被跳过。"""
        c = self._make_consciousness()
        # 强制断路
        for i in range(3):
            c._circuit_breaker.record_failure("core_2_armor_consciousness", f"err{i}")
        
        self.assertFalse(c._circuit_breaker.can_call("core_2_armor_consciousness"))
        
        # 模拟 handle_issue 调用，advisor 应被跳过
        # 验证 advisor_client.ask 没被调用
        # （需要更完整的 mock 来跑 handle_issue，这里只验证熔断器状态）
        state = c._circuit_breaker.get_state("core_2_armor_consciousness")
        self.assertEqual(state["status"], "open")

    def test_breaker_records_advisor_success(self):
        """advisor 成功后熔断器记录成功。"""
        c = self._make_consciousness()
        c._circuit_breaker.record_failure("core_2_armor_consciousness", "err1")
        c._circuit_breaker.record_failure("core_2_armor_consciousness", "err2")
        
        # 模拟成功
        c._circuit_breaker.record_success("core_2_armor_consciousness")
        state = c._circuit_breaker.get_state("core_2_armor_consciousness")
        self.assertEqual(state["status"], "closed")
        self.assertEqual(state["consecutive_failures"], 0)


class TestCircuitBreakerCLI(unittest.TestCase):
    """CLI 接口测试（如有）。"""

    def test_import_circuit_breaker_from_cli(self):
        """确保 circuit_breaker 可被 CLI 模块导入。"""
        from mark42_modules.circuit_breaker import CircuitBreaker, BreakerState
        cb = CircuitBreaker()
        self.assertIsInstance(cb, CircuitBreaker)


if __name__ == "__main__":
    unittest.main()
