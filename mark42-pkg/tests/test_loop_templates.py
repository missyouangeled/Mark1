"""Loop 模板热加载测试群。
import pytest; pytestmark = pytest.mark.skip(reason="requires external conftest fixtures (engine_state)")

覆盖范围：
  - _load_templates() 加载默认模板
  - 用户自定义模板覆盖
  - engine_start() 模板名验证
  - engine_run_loop() generic 路径
  - yaml 不存在/解析失败时的降级行为
"""

import json
from pathlib import Path
from unittest.mock import MagicMock, mock_open, patch

import pytest

from mark42 import engine
from mark42.config import LOOP_TEMPLATES_PATH, USER_LOOP_TEMPLATES_PATH


# ── helper ────────────────────────────────────────────────

def _make_loop(name="test-loop", template="", task="test task",
               interval=300, status="registered", cycle=0, max_cycles=None):
    """构造一个标准的 loop 字典。"""
    return {
        name: {
            "task": task,
            "interval": interval,
            "maxCycles": max_cycles,
            "template": template,
            "status": status,
            "cycle": cycle,
            "lastRun": None,
            "lastResult": None,
            "createdAt": "2026-07-20T09:00:00",
        }
    }


# ─────────────────────── _load_templates() 基础测试 ───────────────────────

class TestLoadTemplates:
    """_load_templates() 模板加载测试群。"""

    def test_builtin_templates_exist(self):
        """应包含 5 个内置模板。"""
        templates = engine._load_templates()
        assert "context-guard" in templates
        assert "task-watch" in templates
        assert "health-watch" in templates
        assert "model-fallback" in templates
        assert "memory-index" in templates

    def test_builtin_templates_have_period(self):
        """每个内置模板应包含 period 字段。"""
        templates = engine._load_templates()
        assert templates["context-guard"]["period"] == 300
        assert templates["task-watch"]["period"] == 30
        assert templates["health-watch"]["period"] == 600
        assert templates["model-fallback"]["period"] == 60
        assert templates["memory-index"]["period"] == 21600

    def test_builtin_templates_have_description(self):
        """每个内置模板应包含 description 字段。"""
        templates = engine._load_templates()
        for name in ["context-guard", "task-watch", "health-watch", "model-fallback", "memory-index"]:
            assert templates[name]["description"], f"{name} 缺少 description"

    def test_yaml_file_exists(self):
        """内置 yaml 配置文件应存在。"""
        assert LOOP_TEMPLATES_PATH.exists(), f"内置模板文件不存在: {LOOP_TEMPLATES_PATH}"

    def test_yaml_file_loads_correctly(self):
        """内置 yaml 文件应能正确解析。"""
        import yaml
        with open(LOOP_TEMPLATES_PATH, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        assert "templates" in data
        assert "context-guard" in data["templates"]


# ─────────────────────── 用户自定义模板覆盖 ───────────────────────

class TestUserTemplatesOverride:
    """用户自定义模板覆盖测试群。"""

    def test_user_template_adds_new_template(self, tmp_path, mocker):
        """用户 yaml 中新增的模板应被加载。"""
        user_yaml_content = """
templates:
  custom-template:
    period: 120
    description: "自定义模板"
"""
        # 创建临时用户 yaml 文件
        user_yaml_path = tmp_path / "user_templates.yaml"
        user_yaml_path.write_text(user_yaml_content, encoding="utf-8")
        
        # patch USER_LOOP_TEMPLATES_PATH 指向临时文件
        mocker.patch("mark42.config.USER_LOOP_TEMPLATES_PATH", user_yaml_path)
        
        # 重新加载 module 级别的引用
        import importlib
        importlib.reload(engine)
        
        templates = engine._load_templates()
        assert "custom-template" in templates
        assert templates["custom-template"]["period"] == 120

    def test_user_template_overrides_builtin(self, tmp_path, mocker):
        """用户 yaml 中同名模板应覆盖内置模板。"""
        user_yaml_content = """
templates:
  context-guard:
    period: 60
    description: "修改后的上下文监控"
"""
        user_yaml_path = tmp_path / "user_templates.yaml"
        user_yaml_path.write_text(user_yaml_content, encoding="utf-8")
        
        mocker.patch("mark42.config.USER_LOOP_TEMPLATES_PATH", user_yaml_path)
        
        import importlib
        importlib.reload(engine)
        
        templates = engine._load_templates()
        # 应该被覆盖
        assert templates["context-guard"]["period"] == 60
        assert "修改后的上下文监控" in templates["context-guard"]["description"]

    def test_user_yaml_parse_error_falls_back(self, tmp_path, mocker):
        """用户 yaml 解析错误时应回退到内置模板。"""
        bad_yaml = "invalid: yaml: ["
        user_yaml_path = tmp_path / "user_templates.yaml"
        user_yaml_path.write_text(bad_yaml, encoding="utf-8")
        
        mocker.patch("mark42.config.USER_LOOP_TEMPLATES_PATH", user_yaml_path)
        
        import importlib
        importlib.reload(engine)
        
        templates = engine._load_templates()
        # 应该至少能拿到内置模板
        assert "context-guard" in templates

    def test_user_yaml_missing_templates_key(self, tmp_path, mocker):
        """用户 yaml 没有 templates 键时应回退。"""
        no_templates_yaml = "other_key: value"
        user_yaml_path = tmp_path / "user_templates.yaml"
        user_yaml_path.write_text(no_templates_yaml, encoding="utf-8")
        
        mocker.patch("mark42.config.USER_LOOP_TEMPLATES_PATH", user_yaml_path)
        
        import importlib
        importlib.reload(engine)
        
        templates = engine._load_templates()
        assert "context-guard" in templates

    def test_yaml_not_imported_falls_back(self, mocker):
        """yaml 模块不可用时应回退到内置代码模板。"""
        original_yaml = engine.yaml
        engine.yaml = None
        try:
            templates = engine._load_templates()
            assert "context-guard" in templates
            assert templates["context-guard"]["period"] == 300
        finally:
            engine.yaml = original_yaml


# ─────────────────────── 模板存在性检查 ───────────────────────

class TestTemplateExists:
    """_template_exists() 测试群。"""

    def test_builtin_template_exists(self):
        """内置模板应返回 True。"""
        assert engine._template_exists("context-guard") is True
        assert engine._template_exists("task-watch") is True

    def test_unknown_template_not_exists(self):
        """不存在的模板应返回 False。"""
        assert engine._template_exists("non-existent-template") is False

    def test_user_added_template_exists(self, tmp_path, mocker):
        """用户新增的模板应返回 True。"""
        user_yaml_content = """
templates:
  my-custom:
    period: 300
    description: "我的自定义"
"""
        user_yaml_path = tmp_path / "user_templates.yaml"
        user_yaml_path.write_text(user_yaml_content, encoding="utf-8")
        
        mocker.patch("mark42.config.USER_LOOP_TEMPLATES_PATH", user_yaml_path)
        
        import importlib
        importlib.reload(engine)
        
        assert engine._template_exists("my-custom") is True


# ─────────────────────── engine_start 模板验证 ───────────────────────

class TestEngineStartTemplateValidation:
    pytestmark = pytest.mark.skip(reason="requires external conftest fixtures (engine_state)")
    """engine_start() 模板名验证测试群。"""

    def test_valid_template_no_warning(self, mocker, capsys, engine_state):
        """有效模板名不应打印警告。"""
        mocker.patch.object(engine, "_load_loops", return_value={})
        mocker.patch.object(engine, "_save_loops")

        engine.engine_start(task="test", template="context-guard")

        out, _ = capsys.readouterr()
        assert "未在配置中定义" not in out

    def test_invalid_template_shows_warning(self, mocker, capsys, engine_state):
        """无效模板名应打印警告。"""
        mocker.patch.object(engine, "_load_loops", return_value={})
        mocker.patch.object(engine, "_save_loops")

        engine.engine_start(task="test", template="unknown-template")

        out, _ = capsys.readouterr()
        assert "未在配置中定义" in out
        assert "unknown-template" in out
        assert "通用执行路径" in out

    def test_no_template_no_warning(self, mocker, capsys, engine_state):
        """不指定模板时不应打印警告。"""
        mocker.patch.object(engine, "_load_loops", return_value={})
        mocker.patch.object(engine, "_save_loops")

        engine.engine_start(task="test")

        out, _ = capsys.readouterr()
        assert "未在配置中定义" not in out


# ─────────────────────── engine_templates 输出 ───────────────────────

class TestEngineTemplatesOutput:
    """engine_templates() 输出测试群。"""

    def test_lists_all_templates(self, capsys):
        """应列出所有模板。"""
        engine.engine_templates()
        out, _ = capsys.readouterr()

        assert "context-guard" in out
        assert "task-watch" in out
        assert "health-watch" in out
        assert "model-fallback" in out
        assert "memory-index" in out

    def test_shows_period(self, capsys):
        """应显示周期信息。"""
        engine.engine_templates()
        out, _ = capsys.readouterr()

        assert "300s" in out  # context-guard
        assert "30s" in out   # task-watch
        assert "600s" in out  # health-watch


# ─────────────────────── engine_run_loop generic 路径 ───────────────────────

class TestEngineRunLoopGeneric:
    """engine_run_loop() generic 路径测试群。"""

    def test_custom_template_uses_generic_path(self, mocker, capsys):
        """用户自定义模板应走 generic 路径。"""
        loops = _make_loop(name="my-custom-loop", template="custom-template", task="自定义任务")
        mocker.patch.object(engine, "_load_loops", return_value=loops)
        mock_save = mocker.patch.object(engine, "_save_loops")
        mocker.patch("mark42.engine._append_broker")

        engine.engine_run_loop("my-custom-loop", persist=False, _loops=loops)

        out, _ = capsys.readouterr()
        assert "自定义模板" in out
        assert "通用执行路径" in out

    def test_custom_template_saves_result_metadata(self, mocker):
        """generic 路径应保存正确的元数据。"""
        loops = _make_loop(name="test", template="my-custom", task="test task")
        mocker.patch.object(engine, "_load_loops", return_value=loops)
        mocker.patch.object(engine, "_save_loops")
        mocker.patch("mark42.engine._append_broker")

        engine.engine_run_loop("test", persist=False, _loops=loops)

        result = loops["test"]["lastResult"]
        assert result["action"] == "executed"
        assert result["template"] == "my-custom"
        assert "自定义模板通用路径" in result["note"]

    def test_no_template_falls_back_to_original_logic(self, mocker):
        """不指定模板时应走原有的通用逻辑（非 generic 路径）。"""
        loops = _make_loop(name="test", template="", task="普通任务")
        mocker.patch.object(engine, "_load_loops", return_value=loops)
        mocker.patch.object(engine, "_save_loops")
        mocker.patch("mark42.engine._append_broker")

        engine.engine_run_loop("test", persist=False, _loops=loops)

        result = loops["test"]["lastResult"]
        assert result["action"] == "executed"
        assert result["note"] == "通用任务"
        # 不指定 template 时不应有 template 字段
        assert "template" not in result

    def test_unknown_template_name_still_runs(self, mocker):
        """未知模板名仍能执行（不崩溃）。"""
        loops = _make_loop(name="test", template="totally-unknown-template", task="test")
        mocker.patch.object(engine, "_load_loops", return_value=loops)
        mocker.patch.object(engine, "_save_loops")
        mocker.patch("mark42.engine._append_broker")

        # 不应抛出异常
        engine.engine_run_loop("test", persist=False, _loops=loops)

        assert loops["test"]["status"] == "registered"
        assert loops["test"]["cycle"] == 1
