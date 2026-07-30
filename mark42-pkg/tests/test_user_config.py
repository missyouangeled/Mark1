"""user_config.py 单元测试"""
import json
import pytest
from pathlib import Path
from unittest.mock import patch

from mark42.user_config import (
    load_config, get, get_section, get_config_path, get_default_config_path, reload,
)


class TestLoadConfig:
    def test_load_returns_dict(self):
        result = load_config()
        assert isinstance(result, dict)

    def test_force_reload(self):
        result1 = load_config()
        result2 = load_config(force_reload=True)
        assert isinstance(result2, dict)


class TestGet:
    def test_get_with_section_and_key(self):
        result = get("model", "primary", default="fallback")
        # 可能返回 default 或实际值
        assert result is not None

    def test_get_missing_returns_default(self):
        result = get("nonexistent_section", "nonexistent_key", default="default")
        assert result == "default"


class TestGetSection:
    def test_get_section_returns_dict(self):
        result = get_section("nonexistent")
        assert isinstance(result, dict)

    def test_reload(self):
        result = reload()
        assert isinstance(result, dict)


class TestGetConfigPath:
    def test_returns_path(self):
        result = get_config_path()
        assert isinstance(result, Path)

    def test_default_path(self):
        result = get_default_config_path()
        assert isinstance(result, Path)
