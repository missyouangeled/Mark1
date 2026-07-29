"""测试 builtin_memory.py 插件模块。"""

import pytest
import sys
import os
from typing import Any, Dict, List


class TestBuiltinMemory:
    """测试 BuiltinMemory 类及其接口契约。"""

    def test_module_importable(self):
        """测试模块可以正常导入。"""
        from scripts.mark42_modules.plugins.builtin_memory import BuiltinMemory
        assert BuiltinMemory is not None

    def test_implements_memory_lock_interface(self):
        """测试实现了 MemoryLock 接口。"""
        from scripts.mark42_modules.interfaces.memory import MemoryLock
        from scripts.mark42_modules.plugins.builtin_memory import BuiltinMemory
        
        instance = BuiltinMemory.__new__(BuiltinMemory)
        assert isinstance(instance, MemoryLock)

    def test_search_runs_qmd_subprocess(self, mocker):
        """测试 search 方法运行 qmd 子进程。"""
        mock_completed_process = mocker.MagicMock()
        mock_completed_process.returncode = 0
        mock_completed_process.stdout = '[{"content": "test", "score": 0.95}]'
        
        mock_subprocess_run = mocker.patch('subprocess.run')
        mock_subprocess_run.return_value = mock_completed_process
        
        from scripts.mark42_modules.plugins.builtin_memory import BuiltinMemory
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
        
        from scripts.mark42_modules.plugins.builtin_memory import BuiltinMemory
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
        
        from scripts.mark42_modules.plugins.builtin_memory import BuiltinMemory
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
        
        from scripts.mark42_modules.plugins.builtin_memory import BuiltinMemory
        memory = BuiltinMemory()
        
        result = memory.search("test query")
        assert result == []

    def test_search_handles_exception(self, mocker):
        """测试 search 处理执行异常。"""
        mock_subprocess_run = mocker.patch('subprocess.run')
        mock_subprocess_run.side_effect = Exception("subprocess failed")
        
        from scripts.mark42_modules.plugins.builtin_memory import BuiltinMemory
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
        
        from scripts.mark42_modules.plugins.builtin_memory import BuiltinMemory
        memory = BuiltinMemory()
        
        memory.search("test query")
        
        call_args = mock_subprocess_run.call_args[0][0]
        assert "5" in call_args

    def test_index_returns_expected_result(self):
        """测试 index 方法返回预期结果。"""
        from scripts.mark42_modules.plugins.builtin_memory import BuiltinMemory
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
        from scripts.mark42_modules.plugins.builtin_memory import BuiltinMemory
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
        
        from scripts.mark42_modules.plugins.builtin_memory import BuiltinMemory
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
        
        from scripts.mark42_modules.plugins.builtin_memory import BuiltinMemory
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
        
        from scripts.mark42_modules.plugins.builtin_memory import BuiltinMemory
        memory = BuiltinMemory()
        
        result = memory.health()
        assert result is False

    def test_health_checks_fallback_qmd_path(self, mocker):
        """测试健康检查检查备用路径 ~/.npm-global/bin/qmd。"""
        mock_shutil = mocker.patch('shutil.which')
        mock_shutil.return_value = None  # PATH 中找不到
        
        mock_isfile = mocker.patch('os.path.isfile')
        mock_isfile.return_value = True  # 所有路径都认为存在
        
        from scripts.mark42_modules.plugins.builtin_memory import BuiltinMemory
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
        
        from scripts.mark42_modules.plugins.builtin_memory import BuiltinMemory
        memory = BuiltinMemory()
        
        result_search = memory.search("query")
        result_index = memory.index([])
        result_health = memory.health()
        
        assert isinstance(result_search, list)
        assert isinstance(result_index, dict)
        assert isinstance(result_health, bool)
