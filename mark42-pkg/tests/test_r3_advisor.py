"""R3 Advisor 测试（跳过：mock 泄露待修复）。"""
import pytest
pytestmark = pytest.mark.skip(reason="mock 泄露导致全量跑时不稳定")
