"""Tests for CompressorRegistry and algo_scheduler."""

import sys
from pathlib import Path
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from mark42.algo_scheduler import CompressorRegistry, _compressor_registry


class TestCompressorRegistry:
    """Tests for CompressorRegistry class."""

    def test_register_and_list(self):
        """Test registering and listing compressors."""
        registry = CompressorRegistry()
        mock_func = MagicMock()

        registry.register("smartcrush", mock_func, "json", 100)
        registry.register("text", mock_func, "text", 50)

        compressors = registry.list()
        assert len(compressors) == 2
        assert compressors[0]["name"] == "smartcrush"  # Higher priority first
        assert compressors[0]["priority"] == 100
        assert compressors[1]["name"] == "text"
        assert compressors[1]["priority"] == 50

    def test_register_multiple_same_type(self):
        """Test registering multiple compressors for same content type."""
        registry = CompressorRegistry()
        registry.register("algo_low", MagicMock(), "json", 50)
        registry.register("algo_high", MagicMock(), "json", 100)

        name, func = registry.select('{"test": "data"}')
        assert name == "algo_high"
        # func is resolved from module globals, not the MagicMock
        assert callable(func)

    def test_select_json_content(self):
        """Test selecting compressor for JSON content."""
        registry = CompressorRegistry()
        registry.register("smartcrush", MagicMock(), "json", 100)
        registry.register("text", MagicMock(), "text", 50)

        name, func = registry.select('{"users": [{"id": 1}]}')
        assert name == "smartcrush"
        assert callable(func)

    def test_select_code_content(self):
        """Test selecting compressor for code content."""
        registry = CompressorRegistry()
        registry.register("code", MagicMock(), "code", 80)
        registry.register("text", MagicMock(), "text", 50)

        name, func = registry.select("def hello():\n    print('world')")
        assert name == "code"
        assert callable(func)

    def test_select_diff_content(self):
        """Test selecting compressor for diff content."""
        registry = CompressorRegistry()
        registry.register("diff", MagicMock(), "diff", 90)
        registry.register("text", MagicMock(), "text", 50)

        name, func = registry.select("--- a/file.py\n+++ b/file.py\n@@ -1,3 +1,3 @@")
        assert name == "diff"
        assert callable(func)

    def test_select_log_content(self):
        """Test selecting compressor for log content."""
        registry = CompressorRegistry()
        registry.register("log", MagicMock(), "log", 70)
        registry.register("text", MagicMock(), "text", 50)

        name, func = registry.select("[2026-01-01 12:00:00] INFO Starting daemon\n[2026-01-01 12:00:01] ERROR Failed")
        assert name == "log"
        assert callable(func)

    def test_select_text_fallback(self):
        """Test selecting compressor for plain text."""
        registry = CompressorRegistry()
        registry.register("smartcrush", MagicMock(), "json", 100)
        registry.register("text", MagicMock(), "text", 50)

        name, func = registry.select("Just some plain text without special structure")
        assert name == "text"
        assert callable(func)

    def test_select_explicit_content_type(self):
        """Test selecting with explicit content_type override."""
        registry = CompressorRegistry()
        registry.register("smartcrush", MagicMock(), "json", 100)
        registry.register("text", MagicMock(), "text", 50)

        name, func = registry.select("plain text", content_type="json")
        assert name == "smartcrush"

    def test_select_fallback_when_no_matching_type(self):
        """Test fallback to text when no matching content type."""
        registry = CompressorRegistry()
        registry.register("text", MagicMock(), "text", 50)

        name, func = registry.select('{"key": "value"}')
        # No json compressor, falls back to text
        assert name == "text"

    def test_empty_registry_returns_identity(self):
        """Test that empty registry returns identity compressor."""
        registry = CompressorRegistry()
        name, func = registry.select("some content")
        assert name == "identity"
        result, stats = func("some content")
        assert result == "some content"


class TestContentDetection:
    """Tests for content type detection."""

    def test_detect_json(self):
        """Test JSON detection."""
        registry = CompressorRegistry()
        registry.register("smartcrush", MagicMock(), "json", 100)
        name, _ = registry.select('{"key": "value"}')
        assert name == "smartcrush"

    def test_detect_diff(self):
        """Test diff detection."""
        registry = CompressorRegistry()
        registry.register("diff", MagicMock(), "diff", 90)
        name, _ = registry.select("--- a/file.py\n+++ b/file.py\n@@ -1 +1 @@")
        assert name == "diff"

    def test_detection_priority_diff_over_code(self):
        """Test that diff is detected over code when both match."""
        registry = CompressorRegistry()
        registry.register("code", MagicMock(), "code", 80)
        registry.register("diff", MagicMock(), "diff", 90)
        name, _ = registry.select("--- a/file.py\n+++ b/file.py\n@@ -1 +1 @@\n-def old()\n+def new()")
        assert name == "diff"


class TestGlobalRegistry:
    """Tests for the module-level global registry."""

    def test_global_registry_has_defaults(self):
        """Test that global registry has default compressors."""
        compressors = _compressor_registry.list()
        names = [c["name"] for c in compressors]
        assert "smartcrush" in names
        assert "text" in names
