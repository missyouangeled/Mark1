"""Tests for Mark42 Metrics HTTP Server."""

import sys
import urllib.request
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from mark42.metrics_server import (
    MetricsServer,
    _collect_metrics,
    run_server,
)


class TestMetricsGeneration:
    """Tests for _collect_metrics function."""

    def test_metrics_contains_context_metrics(self):
        """Test that metrics output contains context usage metrics."""
        with patch("mark42.metrics_server.armor_check" if False else "mark42.armor.armor_check") as mock_check:
            mock_check.return_value = {
                "usagePercent": 42.5,
                "contextWindow": 128000,
                "estimatedTokens": 54400,
            }
            # Need to reload since imports happen inside the function
            from mark42.metrics_server import _collect_metrics
            text = _collect_metrics()
            assert "mark42_context_usage_percent" in text
            assert "42.5" in text

    def test_metrics_contains_compress_stats(self):
        """Test that metrics output contains compression statistics."""
        with patch("mark42.armor.armor_llm_stats") as mock_stats:
            mock_stats.return_value = {
                "total": 10,
                "llmSuccess": 7,
                "fallback": 2,
                "errors": 1,
                "llmRate": 70.0,
                "fallbackRate": 20.0,
                "sloBreached": False,
            }
            text = _collect_metrics()
            assert "mark42_compress_total" in text
            assert "10" in text

    def test_metrics_contains_breaker_status(self):
        """Test that metrics output contains circuit breaker status."""
        text = _collect_metrics()
        assert "mark42_breakers_open" in text or "# breaker" in text

    def test_metrics_format_valid(self):
        """Test that output is valid Prometheus text format."""
        text = _collect_metrics()
        lines = [l for l in text.splitlines() if l and not l.startswith("#")]
        for line in lines:
            # Each non-comment line should contain a metric name
            assert line.split()[0].startswith("mark42_")


class TestMetricsServer:
    """Tests for MetricsServer HTTP endpoint."""

    @pytest.fixture
    def server(self):
        """Start metrics server on a random port."""
        import socket

        # Find available port
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("127.0.0.1", 0))
            port = s.getsockname()[1]

        srv = MetricsServer(port=port)
        srv.start_background()
        yield port
        srv.stop()

    def test_health_endpoint(self, server):
        """Test /health returns 200 OK."""
        r = urllib.request.urlopen(f"http://127.0.0.1:{server}/health", timeout=5)
        assert r.status == 200
        assert r.read().strip() == b"OK"

    def test_metrics_endpoint(self, server):
        """Test /metrics returns Prometheus format."""
        r = urllib.request.urlopen(f"http://127.0.0.1:{server}/metrics", timeout=5)
        assert r.status == 200
        body = r.read().decode()
        assert "mark42_" in body

    def test_unknown_path_returns_404(self, server):
        """Test that unknown paths return 404."""
        import urllib.error
        with pytest.raises(urllib.error.HTTPError) as exc_info:
            urllib.request.urlopen(f"http://127.0.0.1:{server}/unknown", timeout=5)
        assert exc_info.value.code == 404


class TestRunServer:
    """Tests for run_server function."""

    def test_run_server_exists(self):
        """Test that run_server function exists and is callable."""
        assert callable(run_server)
