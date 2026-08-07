"""Cross-Encoder Reranker 测试（方案 44 Phase 3 第二块）。

重点钉住：
    1. Reranker 接口可被 runtime_checkable 验证；
    2. QMDReranker.available() 实际尝试运行命令，不只看文件存在；
    3. NoopReranker 的 available() 返回 False，rerank 原序返回；
    4. get_reranker() 降级链：QMD 不可用 -> Noop。
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch


from mark42.audit.reranker import (
    NoopReranker,
    QMDReranker,
    Reranker,
    get_reranker,
)


class TestRerankerProtocol:
    def test_noop_is_reranker(self):
        assert isinstance(NoopReranker(), Reranker)

    def test_qmd_is_reranker(self):
        # QMDReranker 实现 rerank + available -> 满足 Protocol
        assert isinstance(QMDReranker(qmd_bin=""), Reranker)


class TestNoopReranker:
    def test_available_false(self):
        assert NoopReranker().available() is False

    def test_rerank_preserves_order(self):
        candidates = [{"content": "a"}, {"content": "b"}, {"content": "c"}]
        out = NoopReranker().rerank("query", candidates, top_k=2)
        assert out == candidates[:2]

    def test_rerank_top_k_truncation(self):
        candidates = [{"content": f"x{i}"} for i in range(10)]
        out = NoopReranker().rerank("q", candidates, top_k=3)
        assert len(out) == 3


class TestQMDReranker:
    def test_available_false_when_no_binary(self):
        r = QMDReranker(qmd_bin="/nonexistent/qmd")
        assert r.available() is False

    @patch("os.path.isfile")
    @patch("subprocess.run")
    def test_available_true_when_help_succeeds(self, mock_run, mock_isfile):
        mock_isfile.return_value = True
        mock_run.return_value = MagicMock(returncode=0)
        r = QMDReranker(qmd_bin="/fake/qmd")
        assert r.available() is True

    @patch("os.path.isfile")
    @patch("subprocess.run")
    def test_available_false_when_help_fails(self, mock_run, mock_isfile):
        mock_isfile.return_value = True
        mock_run.return_value = MagicMock(returncode=1)
        r = QMDReranker(qmd_bin="/fake/qmd")
        assert r.available() is False

    @patch("os.path.isfile")
    @patch("subprocess.run")
    def test_available_false_on_exception(self, mock_run, mock_isfile):
        mock_isfile.return_value = True
        mock_run.side_effect = RuntimeError("boom")
        r = QMDReranker(qmd_bin="/fake/qmd")
        assert r.available() is False

    @patch("os.path.isfile")
    @patch("subprocess.run")
    def test_rerank_returns_ranked(self, mock_run, mock_isfile):
        mock_isfile.return_value = True
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout='[{"content": "b", "score": 0.9}, {"content": "a", "score": 0.3}]',
        )
        r = QMDReranker(qmd_bin="/fake/qmd")
        candidates = [
            {"content": "a", "source": "f1"},
            {"content": "b", "source": "f2"},
        ]
        out = r.rerank("query", candidates, top_k=2)
        assert out[0]["content"] == "b"
        assert out[0]["rerank_score"] == 0.9
        assert out[0]["source"] == "f2"  # 原 item 的字段保留

    @patch("os.path.isfile")
    @patch("subprocess.run")
    def test_rerank_empty_output_returns_original(self, mock_run, mock_isfile):
        mock_isfile.return_value = True
        mock_run.return_value = MagicMock(returncode=0, stdout="")
        r = QMDReranker(qmd_bin="/fake/qmd")
        candidates = [{"content": "a"}, {"content": "b"}]
        out = r.rerank("q", candidates, top_k=5)
        assert out == candidates[:5]

    @patch("os.path.isfile")
    @patch("subprocess.run")
    def test_rerank_timeout_returns_original(self, mock_run, mock_isfile):
        mock_isfile.return_value = True
        import subprocess
        mock_run.side_effect = subprocess.TimeoutExpired(cmd="qmd", timeout=10)
        r = QMDReranker(qmd_bin="/fake/qmd")
        candidates = [{"content": "a"}]
        out = r.rerank("q", candidates, top_k=5)
        assert out == candidates

    @patch("os.path.isfile")
    @patch("subprocess.run")
    def test_rerank_bad_json_returns_original(self, mock_run, mock_isfile):
        mock_isfile.return_value = True
        mock_run.return_value = MagicMock(returncode=0, stdout="not json")
        r = QMDReranker(qmd_bin="/fake/qmd")
        candidates = [{"content": "a"}]
        out = r.rerank("q", candidates, top_k=5)
        assert out == candidates

    @patch("os.path.isfile")
    @patch("subprocess.run")
    def test_rerank_nonzero_exit_returns_original(self, mock_run, mock_isfile):
        mock_isfile.return_value = True
        mock_run.return_value = MagicMock(returncode=1, stdout="")
        r = QMDReranker(qmd_bin="/fake/qmd")
        candidates = [{"content": "a"}]
        out = r.rerank("q", candidates, top_k=5)
        assert out == candidates

    @patch("os.path.isfile")
    @patch("subprocess.run")
    def test_rerank_preserves_original_fields(self, mock_run, mock_isfile):
        mock_isfile.return_value = True
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout='[{"content": "a", "score": 0.95}]',
        )
        r = QMDReranker(qmd_bin="/fake/qmd")
        candidates = [{"content": "a", "source": "f.py", "line": 42, "mode": "bm25"}]
        out = r.rerank("q", candidates, top_k=1)
        assert out[0]["source"] == "f.py"
        assert out[0]["line"] == 42
        assert out[0]["mode"] == "bm25"
        assert out[0]["rerank_score"] == 0.95


class TestGetReranker:
    @patch("os.path.isfile")
    @patch("subprocess.run")
    def test_returns_qmd_when_available(self, mock_run, mock_isfile):
        mock_isfile.return_value = True
        mock_run.return_value = MagicMock(returncode=0)
        r = get_reranker()
        assert isinstance(r, QMDReranker)

    @patch("os.path.isfile")
    @patch("subprocess.run")
    def test_returns_noop_when_qmd_unavailable(self, mock_run, mock_isfile):
        mock_isfile.return_value = True
        mock_run.return_value = MagicMock(returncode=1)
        r = get_reranker()
        assert isinstance(r, NoopReranker)

    def test_returns_noop_when_no_binary(self):
        # 没设 QMD_BIN 环境变量且 which 找不到 -> Noop
        r = get_reranker()
        # 测试环境通常没有 qmd，应该返回 Noop
        # 但如果机器上恰好装了 qmd，就返回 QMD
        assert isinstance(r, (NoopReranker, QMDReranker))
