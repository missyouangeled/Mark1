"""
R1 验收测试 · 可插拔模型层

验证 v3 §2.4 钉死的"换任何模型都能继续开发"硬标准：
- 换 runtime -> 改 1 行配置，战甲继续工作
- 换 model -> 改 1 行配置，战甲继续工作
- 换 API provider -> 改 1 行配置 + 1 行 api_key，战甲继续工作
- 卸载本地小模型 -> 改 1 行配置 enabled: false，战甲退化到 v2（不崩）
- 接入外部大模型 -> 改 1 行配置 advisor.enabled: true，战甲获得主动交流能力
"""

import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

import mark42_modules.llm_provider as lp


# ── 辅助函数 ──


def _make_config(runtime: str = "stub", model: str = "stub-model", **extra) -> dict:
    """构造测试配置。"""
    consciousness = {
        "runtime": runtime,
        "model": model,
        "base_url": extra.get("base_url", ""),
        "api_key": extra.get("api_key", ""),
        "timeout_seconds": extra.get("timeout_seconds", 5),
        "max_retries": extra.get("max_retries", 0),
    }
    return {
        "mark42": {
            "consciousness": consciousness,
            "fallback_chain": extra.get("fallback_chain", ["stub"]),
            "advisor": {
                "enabled": extra.get("advisor_enabled", False),
                "runtime": extra.get("advisor_runtime", "api"),
                "model": extra.get("advisor_model", ""),
                "base_url": extra.get("advisor_base_url", ""),
                "api_key": extra.get("advisor_api_key", ""),
            },
        }
    }


# ── R1 验收测试 ──


class TestR1PluggableModel:
    """R1: 可插拔模型层验收。"""

    def test_runtime_stub(self):
        """stub runtime 可构造。"""
        cfg = _make_config(runtime="stub", model="test-stub")
        p = lp.build_consciousness(cfg)
        assert type(p).__name__ == "StubRuntime"
        assert p.model == "test-stub"

    def test_runtime_ollama(self):
        """ollama runtime 可构造（不真实调用）。"""
        cfg = _make_config(
            runtime="ollama", model="qwen3:4b", base_url="http://127.0.0.1:11434"
        )
        p = lp.build_consciousness(cfg)
        assert type(p).__name__ == "OllamaRuntime"
        assert p.model == "qwen3:4b"

    def test_runtime_api(self):
        """api runtime 可构造。"""
        cfg = _make_config(
            runtime="api",
            model="gpt-4o",
            base_url="https://api.openai.com/v1",
            api_key="***",
        )
        p = lp.build_consciousness(cfg)
        assert type(p).__name__ == "APIRuntime"
        assert p.model == "gpt-4o"

    def test_runtime_unknown_falls_back_to_stub(self):
        """未知 runtime 降级到 stub（不崩）。"""
        cfg = _make_config(runtime="nonexistent", model="test")
        p = lp.build_consciousness(cfg)
        assert type(p).__name__ == "StubRuntime"

    def test_change_one_line_runtime(self):
        """验收项 1: 换 runtime 只改配置。"""
        # 从 stub 换到 ollama
        cfg_stub = _make_config(runtime="stub", model="test")
        cfg_ollama = _make_config(runtime="ollama", model="qwen3:4b", base_url="http://localhost:11434")

        p1 = lp.build_consciousness(cfg_stub)
        p2 = lp.build_consciousness(cfg_ollama)

        assert type(p1).__name__ != type(p2).__name__
        assert type(p1).__name__ == "StubRuntime"
        assert type(p2).__name__ == "OllamaRuntime"

    def test_change_one_line_model(self):
        """验收项 2: 换 model 只改配置。"""
        cfg1 = _make_config(runtime="ollama", model="qwen3:4b", base_url="http://localhost:11434")
        cfg2 = _make_config(runtime="ollama", model="gemma3:4b", base_url="http://localhost:11434")

        p1 = lp.build_consciousness(cfg1)
        p2 = lp.build_consciousness(cfg2)

        assert p1.model == "qwen3:4b"
        assert p2.model == "gemma3:4b"

    def test_change_api_provider(self):
        """验收项 3: 换 API provider 改配置 + api_key。"""
        cfg1 = _make_config(
            runtime="api", model="gpt-4o", base_url="https://api.openai.com/v1", api_key="***"
        )
        cfg2 = _make_config(
            runtime="api",
            model="deepseek-chat",
            base_url="https://api.deepseek.com/v1",
            api_key="***",
        )

        p1 = lp.build_consciousness(cfg1)
        p2 = lp.build_consciousness(cfg2)

        assert p1.base_url == "https://api.openai.com/v1"
        assert p2.base_url == "https://api.deepseek.com/v1"

    def test_disable_consciousness_falls_to_stub(self):
        """验收项 4: 卸载本地小模型退化到 v2（stub）。"""
        cfg = _make_config(runtime="stub", model="disabled")
        p = lp.build_consciousness(cfg)
        assert type(p).__name__ == "StubRuntime"

        # stub 永不抛异常
        resp = p.chat([lp.ChatMessage(role="user", content="测试")])
        assert resp.ok

    def test_enable_advisor(self):
        """验收项 5: 接入外部大模型获得主动交流能力。"""
        # 关闭 advisor
        cfg_off = _make_config(advisor_enabled=False)
        assert lp.build_advisor(cfg_off) is None

        # 开启 advisor
        cfg_on = _make_config(
            advisor_enabled=True,
            advisor_model="gpt-4o",
            advisor_base_url="https://api.openai.com/v1",
            advisor_api_key="sk-test",
        )
        p = lp.build_advisor(cfg_on)
        assert p is not None
        assert type(p).__name__ == "APIRuntime"
        assert p.model == "gpt-4o"

    def test_fallback_chain(self):
        """fallback 链路：主 provider 失败 -> stub 兜底。"""
        cfg = _make_config(
            runtime="api",
            model="nonexistent",
            base_url="http://127.0.0.1:1",  # 必失败的地址
            api_key="***",
            fallback_chain=["stub"],
            max_retries=0,
        )
        resp = lp.chat_with_fallback([lp.ChatMessage(role="user", content="测试")], cfg=cfg)
        assert resp.ok  # stub 兜底成功

    def test_provider_protocol(self):
        """所有 runtime 都实现 LLMProvider Protocol。"""
        providers = [
            lp.StubRuntime(model="test"),
            lp.OllamaRuntime(model="test", base_url="http://localhost:11434"),
        ]
        for p in providers:
            assert hasattr(p, "runtime")
            assert hasattr(p, "model")
            assert hasattr(p, "chat")

    def test_config_file_loading(self):
        """配置文件不存在时用默认配置（不崩）。"""
        cfg = lp.load_config(Path("/nonexistent/path/model.yaml"))
        assert "mark42" in cfg
        assert "consciousness" in cfg["mark42"]

    def test_api_runtime_missing_key_falls_to_stub(self):
        """APIRuntime 缺 api_key 降级到 stub。"""
        cfg = _make_config(
            runtime="api", model="test", base_url="https://api.test.com/v1", api_key=""
        )
        p = lp.build_consciousness(cfg)
        assert type(p).__name__ == "StubRuntime"

    def test_api_runtime_missing_url_falls_to_stub(self):
        """APIRuntime 缺 base_url 降级到 stub。"""
        cfg = _make_config(
            runtime="api", model="test", base_url="", api_key="***"
        )
        p = lp.build_consciousness(cfg)
        assert type(p).__name__ == "StubRuntime"

    def test_stub_never_raises(self):
        """stub runtime 永不抛异常（R4 确定性）。"""
        p = lp.StubRuntime(model="test")
        # 空消息列表
        resp = p.chat([])
        assert resp.ok
        # None 内容
        resp2 = p.chat([lp.ChatMessage(role="user", content="")])
        assert resp2.ok

    def test_get_advisor_cfg_correct_path(self):
        """advisor 配置路径正确（mark42.advisor）。"""
        cfg = _make_config(advisor_enabled=True, advisor_model="gpt-4o")
        adv = lp.get_advisor_cfg(cfg)
        assert adv["enabled"] is True
        assert adv["model"] == "gpt-4o"
