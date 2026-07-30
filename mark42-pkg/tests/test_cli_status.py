"""cli/status.py 单元测试"""
import pytest
from unittest.mock import patch, MagicMock

from mark42.cli.status import status_dashboard


class TestStatusDashboard:
    def test_returns_dict_or_none(self, tmp_path, monkeypatch):
        monkeypatch.setenv("MARK42_STATE_DIR", str(tmp_path))
        result = status_dashboard()
        assert result is None or isinstance(result, dict)

    def test_verbose_mode(self, tmp_path, monkeypatch):
        monkeypatch.setenv("MARK42_STATE_DIR", str(tmp_path))
        result = status_dashboard(verbose=True)
        assert result is None or isinstance(result, dict)

    def test_json_mode(self, tmp_path, monkeypatch):
        monkeypatch.setenv("MARK42_STATE_DIR", str(tmp_path))
        result = status_dashboard(json_mode=True)
        assert result is None or isinstance(result, dict)
