"""Test utils.py 工具函数。"""

import json
from datetime import datetime, timedelta, timezone

from mark42.utils import (
    _DENSITY,
    _estimate_tokens_smart,
    _list_project_files,
    _load_json,
    _now_iso,
    _now_ts,
    _safe_mtime,
    _save_json,
    safe_call,
)


class TestNowIso:
    """测试 _now_iso 时间函数"""

    def test_returns_string(self):
        """返回字符串类型"""
        result = _now_iso()
        assert isinstance(result, str)

    def test_iso_format_valid(self):
        """ISO 格式合法，可解析"""
        result = _now_iso()
        parsed = datetime.fromisoformat(result)
        assert isinstance(parsed, datetime)

    def test_has_timezone(self):
        """包含时区信息"""
        result = _now_iso()
        assert "+08:00" in result

    def test_current_time_approx(self):
        """时间接近当前"""
        result = _now_iso()
        parsed = datetime.fromisoformat(result)
        now = datetime.now(timezone(timedelta(hours=8)))
        # 差值应在 2 秒内
        assert abs((parsed - now).total_seconds()) < 2

    def test_consecutive_calls_increasing(self):
        """连续调用是递增的"""
        t1 = _now_iso()
        t2 = _now_iso()
        assert t1 <= t2


class TestNowTs:
    """测试 _now_ts 时间戳函数"""

    def test_returns_float(self):
        """返回浮点数"""
        result = _now_ts()
        assert isinstance(result, float)

    def test_positive_value(self):
        """值为正"""
        result = _now_ts()
        assert result > 0

    def test_approx_now(self):
        """接近当前时间戳"""
        result = _now_ts()
        import time

        assert abs(result - time.time()) < 2

    def test_consecutive_calls_increasing(self):
        """连续调用是递增的"""
        t1 = _now_ts()
        t2 = _now_ts()
        assert t1 <= t2


class TestLoadJson:
    """测试 _load_json 文件加载"""

    def test_nonexistent_file_returns_empty_dict(self, tmp_path):
        """不存在的文件返回空 dict"""
        path = tmp_path / "nonexistent.json"
        result = _load_json(path)
        assert result == {}

    def test_valid_json_file(self, tmp_path):
        """正常 JSON 文件"""
        path = tmp_path / "test.json"
        data = {"key": "value", "number": 42}
        with open(path, "w") as f:
            json.dump(data, f)

        result = _load_json(path)
        assert result == data

    def test_invalid_json_returns_empty_dict(self, tmp_path):
        """损坏的 JSON 返回空 dict"""
        path = tmp_path / "bad.json"
        with open(path, "w") as f:
            f.write("{not valid json}")

        result = _load_json(path)
        assert result == {}

    def test_empty_file_returns_empty_dict(self, tmp_path):
        """空文件返回空 dict"""
        path = tmp_path / "empty.json"
        path.touch()

        result = _load_json(path)
        assert result == {}

    def test_nested_json(self, tmp_path):
        """嵌套 JSON 结构"""
        path = tmp_path / "nested.json"
        data = {"outer": {"inner": [1, 2, 3]}, "list": [{"a": 1}, {"b": 2}]}
        with open(path, "w") as f:
            json.dump(data, f)

        result = _load_json(path)
        assert result == data


class TestSaveJson:
    """测试 _save_json 文件保存"""

    def test_save_basic_data(self, tmp_path):
        """保存基本数据"""
        path = tmp_path / "output.json"
        data = {"key": "value", "number": 42}

        _save_json(path, data)

        assert path.exists()
        with open(path) as f:
            loaded = json.load(f)
        assert loaded == data

    def test_creates_parent_directories(self, tmp_path):
        """自动创建父目录"""
        path = tmp_path / "sub" / "dir" / "output.json"
        data = {"test": True}

        _save_json(path, data)

        assert path.exists()

    def test_save_chinese_chars(self, tmp_path):
        """保存中文字符 (ensure_ascii=False)"""
        path = tmp_path / "chinese.json"
        data = {"message": "你好世界"}

        _save_json(path, data)

        with open(path, encoding="utf-8") as f:
            content = f.read()
        assert "你好世界" in content

    def test_save_nested_structure(self, tmp_path):
        """保存嵌套结构"""
        path = tmp_path / "nested.json"
        data = {"outer": {"inner": [1, 2, 3], "dict": {"a": 1}}, "list": [1, 2, 3]}

        _save_json(path, data)

        loaded = _load_json(path)
        assert loaded == data

    def test_overwrite_existing_file(self, tmp_path):
        """覆盖已有文件"""
        path = tmp_path / "overwrite.json"
        data1 = {"old": "data"}
        data2 = {"new": "data"}

        _save_json(path, data1)
        _save_json(path, data2)

        loaded = _load_json(path)
        assert loaded == data2


class TestSafeMtime:
    """测试 _safe_mtime 安全获取 mtime"""

    def test_existing_file(self, tmp_path):
        """存在的文件返回 mtime"""
        path = tmp_path / "test.txt"
        path.touch()

        result = _safe_mtime(path)
        assert isinstance(result, float)
        assert result > 0

    def test_nonexistent_file(self, tmp_path):
        """不存在的文件返回 -1.0"""
        path = tmp_path / "nonexistent.txt"

        result = _safe_mtime(path)
        assert result == -1.0

    def test_directory_mtime(self, tmp_path):
        """目录也能获取 mtime"""
        result = _safe_mtime(tmp_path)
        assert isinstance(result, float)
        assert result > 0


class TestListProjectFiles:
    """测试 _list_project_files 文件扫描"""

    def test_single_file(self, tmp_path):
        """单个文件路径"""
        path = tmp_path / "test.py"
        path.touch()

        result = _list_project_files(path)
        assert len(result) == 1
        assert result[0] == path

    def test_scan_directory(self, tmp_path):
        """扫描目录下文件"""
        (tmp_path / "a.py").touch()
        (tmp_path / "b.py").touch()
        (tmp_path / "sub").mkdir()
        (tmp_path / "sub" / "c.py").touch()

        result = _list_project_files(tmp_path)
        assert len(result) == 3

    def test_skip_pycache(self, tmp_path):
        """跳过 __pycache__ 目录"""
        (tmp_path / "a.py").touch()
        (tmp_path / "__pycache__").mkdir()
        (tmp_path / "__pycache__" / "a.pyc").touch()

        result = _list_project_files(tmp_path)
        assert len(result) == 1

    def test_skip_pyc_files(self, tmp_path):
        """跳过 .pyc 文件"""
        (tmp_path / "a.py").touch()
        (tmp_path / "b.pyc").touch()

        result = _list_project_files(tmp_path)
        assert len(result) == 1
        assert all(".pyc" not in str(f) for f in result)

    def test_skip_hidden_files(self, tmp_path):
        """跳过隐藏文件（. 开头）"""
        (tmp_path / "a.py").touch()
        (tmp_path / ".gitignore").touch()

        result = _list_project_files(tmp_path)
        assert len(result) == 1
        assert all(not f.name.startswith(".") for f in result)


class TestEstimateTokensSmart:
    """测试 _estimate_tokens_smart 智能 token 估算"""

    def test_empty_file(self, tmp_path):
        """空文件返回 0 token"""
        path = tmp_path / "empty.jsonl"
        path.touch()

        result = _estimate_tokens_smart(path)
        assert result["estimatedTokens"] == 0
        assert result["fileSizeMB"] == 0

    def test_chinese_content(self, tmp_path, monkeypatch):
        """中文内容估算 - 用环境变量调整 scan_lines"""
        monkeypatch.setenv("MARK42_TOKEN_SCAN_LINES", "1")
        path = tmp_path / "chinese.jsonl"
        # 创建 60 行（超过强制最小 50 行）确保扫描到
        for i in range(60):
            msg = {"message": {"content": "你好世界" * 100}}  # 400 中文字符
            with open(path, "a") as f:
                f.write(json.dumps(msg, ensure_ascii=False) + "\n")

        result = _estimate_tokens_smart(path)
        assert result["estimatedTokens"] > 0
        assert result["zhChars"] > 0
        assert result["scannedMessages"] >= 1

    def test_english_content(self, tmp_path, monkeypatch):
        """英文内容估算 - 用环境变量调整 scan_lines"""
        monkeypatch.setenv("MARK42_TOKEN_SCAN_LINES", "1")
        path = tmp_path / "english.jsonl"
        for i in range(60):
            msg = {"message": {"content": "Hello world " * 100}}
            with open(path, "a") as f:
                f.write(json.dumps(msg) + "\n")

        result = _estimate_tokens_smart(path)
        assert result["estimatedTokens"] > 0
        assert result["enChars"] > 0

    def test_mixed_content(self, tmp_path, monkeypatch):
        """混合内容 - 用环境变量调整 scan_lines"""
        monkeypatch.setenv("MARK42_TOKEN_SCAN_LINES", "1")
        path = tmp_path / "mixed.jsonl"
        for i in range(60):
            msg = {"message": {"content": "你好 Hello 世界 World" * 50}}
            with open(path, "a") as f:
                f.write(json.dumps(msg, ensure_ascii=False) + "\n")

        result = _estimate_tokens_smart(path)
        assert result["zhChars"] > 0
        assert result["enChars"] > 0
        assert result["otherChars"] > 0  # 空格/标点

    def test_array_content_format(self, tmp_path, monkeypatch):
        """content 为数组格式（多模态消息）- 用环境变量调整 scan_lines"""
        monkeypatch.setenv("MARK42_TOKEN_SCAN_LINES", "1")
        path = tmp_path / "array.jsonl"
        for i in range(60):
            msg = {
                "message": {
                    "content": [
                        {"type": "text", "text": "你好世界"},
                        {"type": "text", "text": "Hello world"},
                    ]
                }
            }
            with open(path, "a") as f:
                f.write(json.dumps(msg, ensure_ascii=False) + "\n")

        result = _estimate_tokens_smart(path)
        assert result["scannedMessages"] >= 1
        assert result["zhChars"] > 0
        assert result["enChars"] > 0


class TestSafeCallDecorator:
    """测试 safe_call 装饰器"""

    def test_returns_default_on_exception(self):
        """异常时返回默认值"""

        @safe_call(default=42)
        def failing_func():
            raise ValueError("test error")

        result = failing_func()
        assert result == 42

    def test_no_exception_returns_value(self):
        """正常时返回函数值"""

        @safe_call(default=0)
        def good_func():
            return 100

        result = good_func()
        assert result == 100

    def test_custom_label(self):
        """自定义 label（不抛异常就说明工作正常）"""

        @safe_call(default=None, label="custom_label")
        def failing_func():
            raise ValueError("test")

        result = failing_func()
        assert result is None

    def test_reraise_mode(self):
        """reraise=True 时重新抛出异常"""

        @safe_call(reraise=True)
        def failing_func():
            raise ValueError("should reraise")

        try:
            failing_func()
            assert False, "Should have raised"
        except ValueError:
            pass  # 预期行为

    def test_pass_through_args(self):
        """参数正确传递"""

        @safe_call(default=0)
        def add(a, b):
            return a + b

        result = add(2, 3)
        assert result == 5


class TestDensityConstants:
    """测试密度常量定义"""

    def test_zh_density(self):
        assert _DENSITY["zh"] == 1.5

    def test_en_density(self):
        assert _DENSITY["en"] == 0.25

    def test_other_density(self):
        assert _DENSITY["other"] == 0.1
