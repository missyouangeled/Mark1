"""installer.py 单元测试"""
import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path

from mark42.installer import install_systemd, uninstall_systemd


class TestInstallSystemd:
    def test_install_returns_none(self, tmp_path):
        result = install_systemd(str(tmp_path))
        assert result is None or result is True

    def test_install_with_empty_workspace(self):
        result = install_systemd("")
        assert result is None or result is True


class TestUninstallSystemd:
    def test_uninstall_returns_none(self):
        result = uninstall_systemd()
        assert result is None or result is True
