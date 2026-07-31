"""测试 builtin_memory.py 插件模块。"""

from typing import Any, Dict, List


class TestBuiltinMemory:
    """测试 BuiltinMemory 类及其接口契约。"""

    def test_module_importable(self):
        """测试模块可以正常导入。"""
        from mark42.plugins.builtin_memory import BuiltinMemory
        assert BuiltinMemory is not None

    def test_implements_memory_lock_interface(self):
        """测试实现了 MemoryLock 接口。"""
        from mark42.interfaces.memory import MemoryLock
        from mark42.plugins.builtin_memory import BuiltinMemory

        instance = BuiltinMemory.__new__(BuiltinMemory)
        assert isinstance(instance, MemoryLock)

    def test_search_runs_qmd_subprocess(self, mocker):
        """测试 search 方法运行 qmd 子进程。"""
        mock_completed_process = mocker.MagicMock()
        mock_completed_process.returncode = 0
        mock_completed_process.stdout = '[{"content": "test", "score": 0.95}]'

        mock_subprocess_run = mocker.patch('subprocess.run')
        mock_subprocess_run.return_value = mock_completed_process

        from mark42.plugins.builtin_memory import BuiltinMemory
        memory = BuiltinMemory()

        result = memory.search("test query", top_k=5)

        mock_subprocess_run.assert_called_once()
        call_args = mock_subprocess_run.call_args[0][0]
        assert "qmd" in call_args[0]
        assert "search" in call_args
        assert "test query" in call_args
        assert "--top-k" in call_args
        assert "5" in call_args
        assert "--json" in call_args

        assert len(result) == 1
        assert result[0]["content"] == "test"
        assert result[0]["score"] == 0.95

    def test_search_returns_empty_on_non_zero_exit_code(self, mocker):
        """测试 qmd 返回非 0 退出码时返回空列表。"""
        mock_completed_process = mocker.MagicMock()
        mock_completed_process.returncode = 1

        mock_subprocess_run = mocker.patch('subprocess.run')
        mock_subprocess_run.return_value = mock_completed_process

        from mark42.plugins.builtin_memory import BuiltinMemory
        memory = BuiltinMemory()

        result = memory.search("test query")
        assert result == []

    def test_search_handles_invalid_json(self, mocker):
        """测试 search 处理无效 JSON 输出。"""
        mock_completed_process = mocker.MagicMock()
        mock_completed_process.returncode = 0
        mock_completed_process.stdout = "invalid json"

        mock_subprocess_run = mocker.patch('subprocess.run')
        mock_subprocess_run.return_value = mock_completed_process

        from mark42.plugins.builtin_memory import BuiltinMemory
        memory = BuiltinMemory()

        result = memory.search("test query")
        assert result == []

    def test_search_handles_json_not_list(self, mocker):
        """测试 search 处理 JSON 不是列表的情况。"""
        mock_completed_process = mocker.MagicMock()
        mock_completed_process.returncode = 0
        mock_completed_process.stdout = '{"not": "a list"}'

        mock_subprocess_run = mocker.patch('subprocess.run')
        mock_subprocess_run.return_value = mock_completed_process

        from mark42.plugins.builtin_memory import BuiltinMemory
        memory = BuiltinMemory()

        result = memory.search("test query")
        assert result == []

    def test_search_handles_exception(self, mocker):
        """测试 search 处理执行异常。"""
        mock_subprocess_run = mocker.patch('subprocess.run')
        mock_subprocess_run.side_effect = Exception("subprocess failed")

        from mark42.plugins.builtin_memory import BuiltinMemory
        memory = BuiltinMemory()

        result = memory.search("test query")
        assert result == []

    def test_search_default_top_k_value(self, mocker):
        """测试 search 默认 top_k=5。"""
        mock_completed_process = mocker.MagicMock()
        mock_completed_process.returncode = 0
        mock_completed_process.stdout = '[]'

        mock_subprocess_run = mocker.patch('subprocess.run')
        mock_subprocess_run.return_value = mock_completed_process

        from mark42.plugins.builtin_memory import BuiltinMemory
        memory = BuiltinMemory()

        memory.search("test query")

        call_args = mock_subprocess_run.call_args[0][0]
        assert "5" in call_args

    def test_index_returns_expected_result(self):
        """测试 index 方法返回预期结果。"""
        from mark42.plugins.builtin_memory import BuiltinMemory
        memory = BuiltinMemory()

        test_docs: List[Dict[str, Any]] = [
            {"content": "doc1", "id": "1"},
            {"content": "doc2", "id": "2"},
        ]

        result = memory.index(test_docs)

        assert result["indexed"] == 0
        assert result["status"] == "not_implemented_for_qmd"

    def test_index_ignores_input_documents(self):
        """测试 index 不处理输入文档。"""
        from mark42.plugins.builtin_memory import BuiltinMemory
        memory = BuiltinMemory()

        empty_docs: List[Dict[str, Any]] = []
        result_empty = memory.index(empty_docs)
        assert result_empty["indexed"] == 0

        many_docs = [{"content": f"doc{i}"} for i in range(100)]
        result_many = memory.index(many_docs)
        assert result_many["indexed"] == 0

    def test_health_returns_true_when_everything_exists(self, mocker):
        """测试健康检查在所有条件满足时返回 True。"""
        # mock shutil.which
        mock_shutil = mocker.patch('shutil.which')
        mock_shutil.return_value = "/usr/bin/qmd"

        # mock os.path.isfile
        mock_isfile = mocker.patch('os.path.isfile')
        mock_isfile.return_value = True

        # mock os.path.expanduser
        mock_expanduser = mocker.patch('os.path.expanduser')
        mock_expanduser.side_effect = lambda x: x.replace("~", "/home/user")

        from mark42.plugins.builtin_memory import BuiltinMemory
        memory = BuiltinMemory()

        result = memory.health()
        assert result is True

    def test_health_returns_false_when_qmd_not_found(self, mocker):
        """测试健康检查在 qmd 不存在时返回 False。"""
        mock_shutil = mocker.patch('shutil.which')
        mock_shutil.return_value = None  # PATH 中找不到

        # 用 MagicMock 而不是 side_effect 函数来避免递归
        mock_isfile = mocker.patch('os.path.isfile')
        mock_isfile.return_value = False  # 所有文件都不存在

        from mark42.plugins.builtin_memory import BuiltinMemory
        memory = BuiltinMemory()

        result = memory.health()
        assert result is False

    def test_health_returns_false_when_index_not_found(self, mocker):
        """测试健康检查在索引文件不存在时返回 False。"""
        mock_shutil = mocker.patch('shutil.which')
        mock_shutil.return_value = "/usr/bin/qmd"

        mock_isfile = mocker.patch('os.path.isfile')
        mock_isfile.return_value = False  # 文件不存在

        mock_expanduser = mocker.patch('os.path.expanduser')
        mock_expanduser.side_effect = lambda x: x

        from mark42.plugins.builtin_memory import BuiltinMemory
        memory = BuiltinMemory()

        result = memory.health()
        assert result is False

    def test_health_checks_fallback_qmd_path(self, mocker):
        """测试健康检查检查备用路径 ~/.npm-global/bin/qmd。"""
        mock_shutil = mocker.patch('shutil.which')
        mock_shutil.return_value = None  # PATH 中找不到

        mock_isfile = mocker.patch('os.path.isfile')
        mock_isfile.return_value = True  # 所有路径都认为存在

        from mark42.plugins.builtin_memory import BuiltinMemory
        memory = BuiltinMemory()

        result = memory.health()
        assert result is True

    def test_all_methods_return_correct_types(self, mocker):
        """测试所有方法返回正确的类型。"""
        # mock subprocess
        mock_completed_process = mocker.MagicMock()
        mock_completed_process.returncode = 0
        mock_completed_process.stdout = '[]'
        mock_subprocess_run = mocker.patch('subprocess.run')
        mock_subprocess_run.return_value = mock_completed_process

        # mock shutil and os
        mock_shutil = mocker.patch('shutil.which')
        mock_shutil.return_value = "/usr/bin/qmd"

        mock_isfile = mocker.patch('os.path.isfile')
        mock_isfile.return_value = True

        mock_expanduser = mocker.patch('os.path.expanduser')
        mock_expanduser.side_effect = lambda x: x

        from mark42.plugins.builtin_memory import BuiltinMemory
        memory = BuiltinMemory()

        result_search = memory.search("query")
        result_index = memory.index([])
        result_health = memory.health()

        assert isinstance(result_search, list)
        assert isinstance(result_index, dict)
        assert isinstance(result_health, bool)


class TestBuiltinMemoryVectorSwitch:
    """测试 MARK42_QMD_VECTOR 开关（cross-encoder 接入方案）。"""

    def setup_method(self):
        """每个测试前重置环境变量。"""
        import os
        self._old_env = os.environ.get("MARK42_QMD_VECTOR")
        self._old_verbose = os.environ.get("MARK42_QMD_VERBOSE_DEGRADED")
        os.environ["MARK42_QMD_VECTOR"] = "off"
        os.environ.pop("MARK42_QMD_VERBOSE_DEGRADED", None)

    def teardown_method(self):
        import os
        if self._old_env is None:
            os.environ.pop("MARK42_QMD_VECTOR", None)
        else:
            os.environ["MARK42_QMD_VECTOR"] = self._old_env
        if self._old_verbose is None:
            os.environ.pop("MARK42_QMD_VERBOSE_DEGRADED", None)
        else:
            os.environ["MARK42_QMD_VERBOSE_DEGRADED"] = self._old_verbose

    def test_off_mode_constant(self):
        """off 模式下 QMD_VECTOR_MODE 常量应为 'off'。"""
        import os
        os.environ["MARK42_QMD_VECTOR"] = "off"
        # 强制重新导入
        import importlib
        import mark42.plugins.builtin_memory as m
        importlib.reload(m)
        assert m.QMD_VECTOR_MODE == "off"

    def test_on_mode_constant(self):
        """on 模式下 QMD_VECTOR_MODE 常量应为 'on'。"""
        import os
        os.environ["MARK42_QMD_VECTOR"] = "on"
        import importlib
        import mark42.plugins.builtin_memory as m
        importlib.reload(m)
        assert m.QMD_VECTOR_MODE == "on"

    def test_auto_mode_constant(self):
        """auto 是默认值。"""
        import os
        os.environ.pop("MARK42_QMD_VECTOR", None)
        import importlib
        import mark42.plugins.builtin_memory as m
        importlib.reload(m)
        assert m.QMD_VECTOR_MODE == "auto"

    def test_unknown_mode_falls_back_to_auto(self):
        """未知值回退到 auto。"""
        import os
        os.environ["MARK42_QMD_VECTOR"] = "garbage"
        import importlib
        import mark42.plugins.builtin_memory as m
        importlib.reload(m)
        assert m.QMD_VECTOR_MODE == "auto"

    def test_off_mode_preserves_original_behavior(self, mocker):
        """off 模式下 search 只调 qmd search，不调 vsearch。"""
        import os
        os.environ["MARK42_QMD_VECTOR"] = "off"
        import importlib
        import mark42.plugins.builtin_memory as m
        importlib.reload(m)

        mock_subprocess = mocker.patch.object(m, '_run_qmd')
        mock_subprocess.return_value = (0, '[]')

        result = m.BuiltinMemory().search("test", top_k=5)

        # 只调用一次（_qmd_search）
        assert mock_subprocess.call_count == 1
        # 调用的是 search 命令，不是 vsearch
        call_args = mock_subprocess.call_args[0][0]
        assert "search" in call_args
        assert "vsearch" not in call_args
        # 行为与改造前一致：返回 []
        assert result == []

    def test_auto_mode_triggers_vector_on_empty_recall(self, mocker):
        """auto 模式下 BM25 召回为空且 vector 可用时，触发 vsearch。"""
        import os
        os.environ["MARK42_QMD_VECTOR"] = "auto"
        import importlib
        import mark42.plugins.builtin_memory as m
        importlib.reload(m)

        # mock BM25 返回空，vector 返回 1 条
        mock_subprocess = mocker.patch.object(m, '_run_qmd')
        mock_subprocess.side_effect = [
            (0, '[]'),  # BM25 空
            (0, '[{"content": "vec hit", "score": 0.8}]'),  # vector 命中
        ]
        # mock vector_available
        mocker.patch.object(m, '_vector_available', return_value=True)

        result = m.BuiltinMemory().search("test", top_k=5)

        # 调了 2 次（BM25 + vector）
        assert mock_subprocess.call_count == 2
        # 返回 vector 结果
        assert len(result) == 1
        assert result[0]["_mode"] == "vector"
        assert result[0]["_search_mode"] == "vector"

    def test_auto_mode_skips_vector_when_unavailable(self, mocker):
        """auto 模式下 vector 不可用时，即使 BM25 空也不报错。"""
        import os
        os.environ["MARK42_QMD_VECTOR"] = "auto"
        import importlib
        import mark42.plugins.builtin_memory as m
        importlib.reload(m)

        mock_subprocess = mocker.patch.object(m, '_run_qmd')
        mock_subprocess.return_value = (0, '[]')
        mocker.patch.object(m, '_vector_available', return_value=False)

        result = m.BuiltinMemory().search("test", top_k=5)

        # 只调 1 次 BM25，没调 vector
        assert mock_subprocess.call_count == 1
        # 返回空（不抛异常）
        assert result == []

    def test_on_mode_always_uses_vector(self, mocker):
        """on 模式总是调 vector（即使 BM25 有结果）。"""
        import os
        os.environ["MARK42_QMD_VECTOR"] = "on"
        import importlib
        import mark42.plugins.builtin_memory as m
        importlib.reload(m)

        mock_subprocess = mocker.patch.object(m, '_run_qmd')
        # 第一次 BM25 返回 1 条，第二次 vector 也返回 1 条
        mock_subprocess.side_effect = [
            (0, '[{"content": "bm25 hit"}]'),
            (0, '[{"content": "vector hit", "_mode": "vector"}]'),
        ]
        mocker.patch.object(m, '_vector_available', return_value=True)

        result = m.BuiltinMemory().search("test", top_k=5)

        # 调了 2 次
        assert mock_subprocess.call_count == 2
        # 最终结果是 vector（on 模式优先 vector）
        assert result[0]["_mode"] == "vector"

    def test_detailed_health_returns_expected_fields(self, mocker):
        """detailed_health 应返回 consciousness 需要的全部字段。"""
        import os
        os.environ["MARK42_QMD_VECTOR"] = "auto"
        import importlib
        import mark42.plugins.builtin_memory as m
        importlib.reload(m)

        mocker.patch.object(m, '_model_complete', return_value=True)

        h = m.BuiltinMemory().detailed_health()

        required_fields = {
            "qmd_bin", "qmd_index", "embedding_model", "rerank_model",
            "vector_available", "rerank_available", "search_mode",
            "degraded_reason",
        }
        assert required_fields.issubset(h.keys())

    def test_model_complete_checks_ipull_suffix(self, mocker, tmp_path):
        """_model_complete 应识别 .ipull 后缀的下载中文件。"""
        import os
        os.environ["MARK42_QMD_VECTOR"] = "auto"
        import importlib
        import mark42.plugins.builtin_memory as m
        importlib.reload(m)

        # 修改 QMD_MODELS_DIR 到临时目录
        mocker.patch.object(m, 'QMD_MODELS_DIR', tmp_path)

        # 只有最终文件
        (tmp_path / "model.gguf").write_text("ok")
        assert m._model_complete("model.gguf") is True

        # 有 .ipull 后缀（下载中）
        (tmp_path / "model2.gguf.ipull").write_text("partial")
        assert m._model_complete("model2.gguf") is False

    def test_verbose_degraded_flag_returns_metadata(self, mocker):
        """MARK42_QMD_VERBOSE_DEGRADED=1 时返回降级元数据。"""
        import os
        os.environ["MARK42_QMD_VECTOR"] = "auto"
        os.environ["MARK42_QMD_VERBOSE_DEGRADED"] = "1"
        import importlib
        import mark42.plugins.builtin_memory as m
        importlib.reload(m)

        mock_subprocess = mocker.patch.object(m, '_run_qmd')
        mock_subprocess.return_value = (0, '[]')  # BM25 空
        mocker.patch.object(m, '_vector_available', return_value=False)  # vector 也不可用

        result = m.BuiltinMemory().search("test", top_k=5)

        # 降级元数据被返回
        assert len(result) == 1
        assert result[0].get("_degraded") is True
        assert "_reason" in result[0]
        assert "_mode" in result[0]
