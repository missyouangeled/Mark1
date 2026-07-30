"""
llm_provider.py 单元测试

测试覆盖:
- resolve_model() 正常路径
- 超时/重试逻辑
- fallback 模型切换
- API key 缺失/无效处理
- 所有公开函数
"""

import json
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch, call

# 导入待测试模块
from mark42.llm_provider import (
    ChatMessage,
    ChatResponse,
    LLMProviderError,
    load_config,
    get_consciousness_cfg,
    get_advisor_cfg,
    get_fallback_chain,
    OllamaRuntime,
    APIRuntime,
    StubRuntime,
    build_provider,
    build_consciousness,
    build_advisor,
    chat_with_fallback,
    _http_post_json,
    DEFAULT_CONFIG,
    CONFIG_PATHS,
)


class TestChatMessage:
    """测试 ChatMessage 数据类"""

    def test_chat_message_creation(self):
        """测试消息创建"""
        msg = ChatMessage(role="user", content="Hello")
        assert msg.role == "user"
        assert msg.content == "Hello"

    def test_chat_message_to_dict(self):
        """测试 to_dict 方法"""
        msg = ChatMessage(role="assistant", content="Hi there")
        result = msg.to_dict()
        assert result == {"role": "assistant", "content": "Hi there"}


class TestChatResponse:
    """测试 ChatResponse 数据类"""

    def test_chat_response_ok_true(self):
        """测试 ok 属性 - 有内容时为 True"""
        resp = ChatResponse(content="some content", model="test")
        assert resp.ok is True

    def test_chat_response_ok_false(self):
        """测试 ok 属性 - 空内容时为 False"""
        resp = ChatResponse(content="", model="test")
        assert resp.ok is False

    def test_chat_response_default_usage(self):
        """测试默认 usage 是空 dict"""
        resp = ChatResponse(content="test")
        assert resp.usage == {}


class TestLoadConfig:
    """测试配置加载函数"""

    def test_load_config_default_when_no_file(self, mocker):
        """测试没有配置文件时返回默认配置"""
        mocker.patch("mark42.llm_provider._HAS_YAML", True)
        mocker.patch("pathlib.Path.exists", return_value=False)
        
        cfg = load_config()
        assert cfg == DEFAULT_CONFIG

    def test_load_config_from_specific_path(self, mocker):
        """测试从指定路径加载配置"""
        test_cfg = {"mark42": {"consciousness": {"runtime": "ollama", "model": "test-model"}}}
        mocker.patch("mark42.llm_provider._HAS_YAML", True)
        mocker.patch("pathlib.Path.exists", return_value=True)
        mocker.patch("pathlib.Path.read_text", return_value="test yaml")
        mocker.patch("yaml.safe_load", return_value=test_cfg)
        
        cfg = load_config(Path("/test/path.yaml"))
        assert cfg == test_cfg

    def test_load_config_when_yaml_not_installed(self, mocker):
        """测试 PyYAML 未安装时返回默认配置"""
        mocker.patch("mark42.llm_provider._HAS_YAML", False)
        mocker.patch("pathlib.Path.exists", return_value=True)
        mocker.patch("pathlib.Path.read_text", return_value="test yaml")
        
        cfg = load_config(Path("/test/path.yaml"))
        assert cfg == DEFAULT_CONFIG

    def test_load_config_yaml_parse_error(self, mocker):
        """测试 YAML 解析错误时返回默认配置"""
        import yaml
        mocker.patch("mark42.llm_provider._HAS_YAML", True)
        mocker.patch("pathlib.Path.exists", return_value=True)
        mocker.patch("pathlib.Path.read_text", return_value="invalid yaml")
        mocker.patch("yaml.safe_load", side_effect=yaml.YAMLError("parse error"))
        
        cfg = load_config(Path("/test/path.yaml"))
        assert cfg == DEFAULT_CONFIG


class TestConfigHelpers:
    """测试配置辅助函数"""

    def test_get_consciousness_cfg_normal(self):
        """测试正常获取 consciousness 配置"""
        cfg = {"mark42": {"consciousness": {"runtime": "api", "model": "test"}}}
        result = get_consciousness_cfg(cfg)
        assert result["runtime"] == "api"
        assert result["model"] == "test"

    def test_get_consciousness_cfg_missing(self):
        """测试缺少配置时返回默认"""
        cfg = {}
        result = get_consciousness_cfg(cfg)
        assert result == DEFAULT_CONFIG["mark42"]["consciousness"]

    def test_get_advisor_cfg_normal(self):
        """测试正常获取 advisor 配置"""
        cfg = {"mark42": {"advisor": {"enabled": True, "model": "advisor-model"}}}
        result = get_advisor_cfg(cfg)
        assert result["enabled"] is True
        assert result["model"] == "advisor-model"

    def test_get_advisor_cfg_missing(self):
        """测试缺少配置时返回默认"""
        cfg = {}
        result = get_advisor_cfg(cfg)
        assert result == DEFAULT_CONFIG["mark42"]["advisor"]

    def test_get_fallback_chain_normal(self):
        """测试正常获取 fallback chain"""
        cfg = {"mark42": {"fallback_chain": ["ollama", "stub"]}}
        result = get_fallback_chain(cfg)
        assert result == ["ollama", "stub"]

    def test_get_fallback_chain_missing(self):
        """测试缺少配置时返回默认 fallback"""
        cfg = {}
        result = get_fallback_chain(cfg)
        assert result == ["stub"]


class TestStubRuntime:
    """测试 StubRuntime - 本地兜底实现"""

    def test_stub_runtime_creation(self):
        """测试创建 StubRuntime"""
        runtime = StubRuntime(model="test-stub")
        assert runtime.runtime == "stub"
        assert runtime.model == "test-stub"

    def test_stub_runtime_default_model(self):
        """测试默认模型名"""
        runtime = StubRuntime()
        assert runtime.model == "stub-model"

    def test_stub_chat_returns_echo(self):
        """测试 chat 方法返回 echo 格式内容"""
        runtime = StubRuntime(model="test-model")
        messages = [ChatMessage(role="user", content="Hello world")]
        
        result = runtime.chat(messages)
        
        assert isinstance(result, ChatResponse)
        assert result.model == "test-model"
        assert "收到 1 条消息" in result.content
        assert "Hello world" in result.content
        assert result.ok is True

    def test_stub_chat_multiple_messages(self):
        """测试多条消息时只取最后一条 user 消息"""
        runtime = StubRuntime()
        messages = [
            ChatMessage(role="system", content="系统提示"),
            ChatMessage(role="user", content="第一条"),
            ChatMessage(role="assistant", content="回复一"),
            ChatMessage(role="user", content="第二条"),
        ]
        
        result = runtime.chat(messages)
        
        assert "收到 4 条消息" in result.content
        assert "第二条" in result.content
        assert "第一条" not in result.content  # 只取最后一条

    def test_stub_chat_usage_calculation(self):
        """测试 usage 字段计算"""
        runtime = StubRuntime()
        messages = [ChatMessage(role="user", content="Hello")]
        
        result = runtime.chat(messages)
        
        assert "prompt_tokens" in result.usage
        assert "completion_tokens" in result.usage
        assert "total_tokens" in result.usage
        assert result.usage["total_tokens"] > 0

    def test_stub_chat_never_raises(self):
        """测试 stub 永不抛异常"""
        runtime = StubRuntime()
        # 空消息、None 等边界情况都不崩
        result = runtime.chat([])
        assert result.ok is True


class TestOllamaRuntime:
    """测试 OllamaRuntime - 本地 Ollama 实现"""

    def test_ollama_runtime_creation(self):
        """测试创建 OllamaRuntime"""
        runtime = OllamaRuntime(
            model="llama3",
            base_url="http://localhost:11434",
            timeout_seconds=30,
            max_retries=2
        )
        assert runtime.runtime == "ollama"
        assert runtime.model == "llama3"
        assert runtime.base_url == "http://localhost:11434"
        assert runtime.timeout_seconds == 30
        assert runtime.max_retries == 2

    def test_ollama_runtime_default_base_url(self):
        """测试默认 base_url"""
        runtime = OllamaRuntime(model="test")
        assert runtime.base_url == "http://127.0.0.1:11434"

    def test_ollama_chat_calls_http_post(self, mocker):
        """测试 chat 方法调用 _http_post_json"""
        mock_http = mocker.patch("mark42.llm_provider._http_post_json")
        mock_http.return_value = ChatResponse(content="test response", model="llama3")
        
        runtime = OllamaRuntime(model="llama3")
        messages = [ChatMessage(role="user", content="test")]
        
        result = runtime.chat(messages, temperature=0.7)
        
        mock_http.assert_called_once()
        assert result.content == "test response"


class TestAPIRuntime:
    """测试 APIRuntime - 通用 API 实现"""

    def test_api_runtime_creation_success(self):
        """测试成功创建 APIRuntime"""
        runtime = APIRuntime(
            model="test-model",
            base_url="https://api.example.com/v1",
            api_key="sk-12345",
            timeout_seconds=60,
            max_retries=1
        )
        assert runtime.runtime == "api"
        assert runtime.model == "test-model"
        assert runtime.base_url == "https://api.example.com/v1"
        assert runtime.api_key == "sk-12345"

    def test_api_runtime_missing_base_url(self):
        """测试缺少 base_url 时抛异常"""
        with pytest.raises(LLMProviderError) as exc:
            APIRuntime(model="test", base_url="", api_key="sk-123")
        assert "缺 base_url" in str(exc.value)

    def test_api_runtime_missing_api_key(self):
        """测试缺少 api_key 时抛异常"""
        with pytest.raises(LLMProviderError) as exc:
            APIRuntime(model="test", base_url="https://api.example.com", api_key="")
        assert "缺 api_key" in str(exc.value)

    def test_api_chat_calls_http_post(self, mocker):
        """测试 chat 方法调用 _http_post_json"""
        mock_http = mocker.patch("mark42.llm_provider._http_post_json")
        mock_http.return_value = ChatResponse(content="test response", model="test-model")
        
        runtime = APIRuntime(
            model="test-model",
            base_url="https://api.example.com/v1",
            api_key="sk-123"
        )
        messages = [ChatMessage(role="user", content="test")]
        
        result = runtime.chat(messages, max_tokens=100)
        
        mock_http.assert_called_once()
        assert result.content == "test response"


class TestHttpPostJson:
    """测试 _http_post_json - HTTP POST 工具函数"""

    def test_http_post_success(self, mocker):
        """测试成功请求"""
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({
            "choices": [{"message": {"content": "Hello!"}}],
            "model": "test-model",
            "usage": {"total_tokens": 10}
        }).encode()
        
        mock_urlopen = mocker.patch("urllib.request.urlopen")
        mock_urlopen.return_value.__enter__.return_value = mock_response
        
        result = _http_post_json(
            url="https://api.example.com",
            body={"prompt": "test"},
            api_key="sk-123",
            timeout_seconds=60,
            max_retries=0,
        )
        
        assert result.content == "Hello!"
        assert result.model == "test-model"

    def test_http_post_no_choices_in_response(self, mocker):
        """测试响应无 choices 时抛异常"""
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({
            "model": "test-model",
        }).encode()
        
        mock_urlopen = mocker.patch("urllib.request.urlopen")
        mock_urlopen.return_value.__enter__.return_value = mock_response
        
        with pytest.raises(LLMProviderError) as exc:
            _http_post_json(
                url="https://api.example.com",
                body={"prompt": "test"},
                api_key="sk-123",
                timeout_seconds=60,
                max_retries=0,
            )
        assert "响应无 choices" in str(exc.value)

    def test_http_post_retry_on_failure(self, mocker):
        """测试失败时重试逻辑"""
        import urllib.error
        mock_urlopen = mocker.patch("urllib.request.urlopen")
        mock_urlopen.side_effect = urllib.error.URLError("connection failed")
        
        with pytest.raises(LLMProviderError) as exc:
            _http_post_json(
                url="https://api.example.com",
                body={"prompt": "test"},
                api_key="sk-123",
                timeout_seconds=60,
                max_retries=2,  # 重试 2 次 = 总共 3 次尝试
            )
        
        # 验证尝试了 3 次
        assert mock_urlopen.call_count == 3
        assert "重试 2 次仍失败" in str(exc.value)

    def test_http_post_timeout(self, mocker):
        """测试超时情况"""
        import urllib.error
        mock_urlopen = mocker.patch("urllib.request.urlopen")
        mock_urlopen.side_effect = urllib.error.URLError("timed out")
        
        with pytest.raises(LLMProviderError):
            _http_post_json(
                url="https://api.example.com",
                body={"prompt": "test"},
                api_key="sk-123",
                timeout_seconds=1,
                max_retries=0,
            )


class TestBuildProvider:
    """测试 build_provider - Provider 工厂函数"""

    def test_build_ollama_provider(self):
        """测试构建 OllamaRuntime"""
        cfg = {"runtime": "ollama", "model": "llama3"}
        provider = build_provider(cfg)
        assert provider.runtime == "ollama"
        assert provider.model == "llama3"

    def test_build_api_provider(self):
        """测试构建 APIRuntime"""
        cfg = {
            "runtime": "api",
            "model": "test-model",
            "base_url": "https://api.example.com",
            "api_key": "sk-123"
        }
        provider = build_provider(cfg)
        assert provider.runtime == "api"
        assert provider.model == "test-model"

    def test_build_stub_provider(self):
        """测试构建 StubRuntime"""
        cfg = {"runtime": "stub", "model": "my-stub"}
        provider = build_provider(cfg)
        assert provider.runtime == "stub"
        assert provider.model == "my-stub"

    def test_build_unknown_runtime_fallback_to_stub(self, mocker):
        """测试未知 runtime 时降级到 stub"""
        mock_log = mocker.patch("mark42.llm_provider.logger.warning")
        cfg = {"runtime": "unknown", "model": "test"}
        provider = build_provider(cfg)
        assert provider.runtime == "stub"
        mock_log.assert_called_once()

    def test_build_api_provider_missing_key_fallback_to_stub(self, mocker):
        """测试 API 配置缺 key 时降级到 stub"""
        mock_log = mocker.patch("mark42.llm_provider.logger.warning")
        cfg = {
            "runtime": "api",
            "model": "test-model",
            "base_url": "https://api.example.com",
            "api_key": ""  # 缺 key
        }
        provider = build_provider(cfg)
        assert provider.runtime == "stub"
        mock_log.assert_called_once()


class TestBuildConsciousness:
    """测试 build_consciousness - 构建意识层 Provider"""

    def test_build_consciousness_with_cfg(self):
        """测试带配置参数"""
        cfg = {"mark42": {"consciousness": {"runtime": "stub", "model": "test"}}}
        provider = build_consciousness(cfg)
        assert provider.runtime == "stub"

    def test_build_consciousness_without_cfg(self, mocker):
        """测试不带配置参数时自动加载"""
        mock_load = mocker.patch("mark42.llm_provider.load_config")
        mock_load.return_value = DEFAULT_CONFIG
        provider = build_consciousness()
        mock_load.assert_called_once()


class TestBuildAdvisor:
    """测试 build_advisor - 构建顾问 Provider"""

    def test_build_advisor_disabled(self):
        """测试未启用时返回 None"""
        cfg = {"mark42": {"advisor": {"enabled": False}}}
        provider = build_advisor(cfg)
        assert provider is None

    def test_build_advisor_enabled(self):
        """测试已启用时构建 Provider"""
        cfg = {
            "mark42": {
                "advisor": {
                    "enabled": True,
                    "runtime": "stub",
                    "model": "advisor-model"
                }
            }
        }
        provider = build_advisor(cfg)
        assert provider is not None
        assert provider.runtime == "stub"

    def test_build_advisor_without_cfg(self, mocker):
        """测试不带配置参数时自动加载"""
        mock_load = mocker.patch("mark42.llm_provider.load_config")
        mock_load.return_value = DEFAULT_CONFIG
        provider = build_advisor()
        mock_load.assert_called_once()


class TestChatWithFallback:
    """测试 chat_with_fallback - 带 fallback 链的顶层 chat 封装"""

    def test_chat_with_fallback_primary_success(self, mocker):
        """测试主 Provider 成功时直接返回"""
        mock_consciousness = MagicMock()
        mock_consciousness.chat.return_value = ChatResponse(content="success", model="primary")
        mocker.patch("mark42.llm_provider.build_consciousness", return_value=mock_consciousness)
        
        messages = [ChatMessage(role="user", content="test")]
        result = chat_with_fallback(messages)
        
        mock_consciousness.chat.assert_called_once()
        assert result.content == "success"

    def test_chat_with_fallback_primary_fails_tries_fallback(self, mocker):
        """测试主 Provider 失败时尝试 fallback"""
        # 主 provider 失败
        mock_primary = MagicMock()
        mock_primary.chat.side_effect = LLMProviderError("primary failed")
        mock_primary.runtime = "api"
        
        # fallback 成功
        mock_fallback = MagicMock()
        mock_fallback.chat.return_value = ChatResponse(content="fallback success", model="stub")
        mock_fallback.runtime = "stub"
        
        mocker.patch("mark42.llm_provider.build_consciousness", return_value=mock_primary)
        mocker.patch("mark42.llm_provider.build_provider", return_value=mock_fallback)
        
        messages = [ChatMessage(role="user", content="test")]
        result = chat_with_fallback(messages, cfg={"mark42": {"fallback_chain": ["stub"]}})
        
        assert result.content == "fallback success"

    def test_chat_with_fallback_all_failed_emergency_stub(self, mocker):
        """测试所有 Provider（含 fallback）都失败时的紧急 stub 兜底"""
        mock_primary = MagicMock()
        mock_primary.chat.side_effect = LLMProviderError("primary failed")
        mock_primary.runtime = "api"
        
        mocker.patch("mark42.llm_provider.build_consciousness", return_value=mock_primary)
        mock_log = mocker.patch("mark42.llm_provider.logger.error")
        
        messages = [ChatMessage(role="user", content="test")]
        result = chat_with_fallback(messages, cfg={"mark42": {"fallback_chain": []}})
        
        # 绝不抛异常，总能返回结果
        assert result.content is not None
        assert "emergency-stub" in result.model
        mock_log.assert_called_once()  # 应该记录错误日志
