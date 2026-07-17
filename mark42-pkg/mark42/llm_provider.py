"""
Mark42 v3-1 · 可插拔 LLM Provider

按 v3 §2 钉死的"三层可插拔"结构（Runtime / Model / API）实现：
- LLMProvider Protocol：统一 chat 接口（OpenAI Chat Completions 兼容）
- 3 个 runtime 实现：ollama / api / stub
- 配置来源：~/.config/mark42/model.yaml（不配 → 用 stub 默认）

设计原则（R 编号引用 v3 §0.2）：
- R1 可插拔：换 runtime/model/api 只改配置
- R4 确定性：fallback 链路走不通时降级到 stub，不抛异常崩战甲
- R9 强制读协议：read_protocol 钩子（v3-3 阶段接入）
"""

from __future__ import annotations

import json
import logging
import os
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Protocol, runtime_checkable

try:
    import yaml  # PyYAML
    _HAS_YAML = True
except ImportError:
    _HAS_YAML = False

from .log_setup import get_logger

logger = get_logger(__name__)

# ── 常量 ─────────────────────────────────────────────

# 配置文件查找顺序（按优先级）
CONFIG_PATHS = [
    Path(os.environ.get("MARK42_MODEL_CONFIG", "")) if os.environ.get("MARK42_MODEL_CONFIG") else None,
    Path.home() / ".config" / "mark42" / "model.yaml",
    Path.home() / ".config" / "mark42" / "model.yml",
]

# 默认配置（用户不配就用这个）
DEFAULT_CONFIG: Dict[str, Any] = {
    "mark42": {
        "consciousness": {
            "runtime": "stub",          # 可换: ollama | api | stub
            "model": "stub-model",      # 可换: 任何模型 ID
            "base_url": "",             # 本地默认
            "api_key": "",              # 本地不需要
            "timeout_seconds": 60,
            "max_retries": 1,
        },
        "fallback_chain": ["stub"],    # v3-1 阶段只接 stub fallback
        "advisor": {
            "enabled": False,           # 默认关闭（用户开了才接）
            "runtime": "api",
            "model": "",
            "base_url": "",
            "api_key": "",
        },
    }
}


# ── 数据类 ───────────────────────────────────────────

@dataclass
class ChatMessage:
    """OpenAI 风格单条消息。"""
    role: str   # system | user | assistant
    content: str

    def to_dict(self) -> Dict[str, str]:
        return {"role": self.role, "content": self.content}


@dataclass
class ChatResponse:
    """统一响应结构（不论哪个 runtime 都返回这个）。"""
    content: str
    model: str = ""
    usage: Dict[str, int] = field(default_factory=dict)
    raw: Optional[Dict[str, Any]] = None

    @property
    def ok(self) -> bool:
        return bool(self.content)


# ── Provider 接口（R1 钉死 · 锁接口签名）──────────────

@runtime_checkable
class LLMProvider(Protocol):
    """可插拔 LLM 接口。所有 runtime 必须实现 chat()。

    返回 ChatResponse；失败抛 LLMProviderError（不抛通用 Exception）。
    """

    runtime: str
    model: str

    def chat(self, messages: List[ChatMessage], **kwargs: Any) -> ChatResponse: ...


class LLMProviderError(Exception):
    """Provider 调用失败的统一异常。"""


# ── 配置加载 ─────────────────────────────────────────

def load_config(path: Optional[Path] = None) -> Dict[str, Any]:
    """加载 model.yaml；找不到或解析失败 → 返回默认配置（不崩）。

    行为契约：
    - 显式传 path → 只读 path；找不到/解析失败 → 默认配置 + WARNING 日志
    - 不传 path → 按 CONFIG_PATHS 顺序找第一个存在的
    - 都不存在 → 默认配置
    """
    cfg = DEFAULT_CONFIG
    candidates = [path] if path else [p for p in CONFIG_PATHS if str(p)]

    for p in candidates:
        if not p or not Path(p).exists():
            continue
        try:
            text = Path(p).read_text(encoding="utf-8")
            if not _HAS_YAML:
                logger.warning("PyYAML 未装，无法解析 %s，使用默认配置", p)
                return DEFAULT_CONFIG
            loaded = yaml.safe_load(text)
            if isinstance(loaded, dict):
                cfg = loaded
                logger.info("已加载 model 配置: %s", p)
                break
        except (OSError, yaml.YAMLError) as e:
            logger.warning("加载 %s 失败: %s，使用默认配置", p, e)
            return DEFAULT_CONFIG

    return cfg


def get_consciousness_cfg(cfg: Dict[str, Any]) -> Dict[str, Any]:
    """从配置里取 consciousness 段；缺则补默认。"""
    return cfg.get("mark42", {}).get("consciousness", DEFAULT_CONFIG["mark42"]["consciousness"])


def get_advisor_cfg(cfg: Dict[str, Any]) -> Dict[str, Any]:
    return cfg.get("mark42", {}).get("advisor", DEFAULT_CONFIG["mark42"]["advisor"])


def get_fallback_chain(cfg: Dict[str, Any]) -> List[str]:
    return cfg.get("mark42", {}).get("fallback_chain", ["stub"])


# ── Runtime 实现 ─────────────────────────────────────

class OllamaRuntime:
    """本地 Ollama runtime（v3-1 实现，v3-6 真实跑通）。"""

    runtime = "ollama"

    def __init__(self, model: str, base_url: str = "", api_key: str = "",
                 timeout_seconds: int = 60, max_retries: int = 1, **kwargs: Any):
        self.model = model
        self.base_url = base_url.rstrip("/") or "http://127.0.0.1:11434"
        # Ollama 本地不需要 key，但若提供则透传（兼容远端代理场景）
        self.api_key = api_key
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries

    def chat(self, messages: List[ChatMessage], **kwargs: Any) -> ChatResponse:
        url = f"{self.base_url}/v1/chat/completions"
        body = {
            "model": self.model,
            "messages": [m.to_dict() for m in messages],
        }
        # 透传温度/max_tokens 等参数
        for k in ("temperature", "max_tokens", "top_p", "stream"):
            if k in kwargs:
                body[k] = kwargs[k]

        return _http_post_json(url, body, self.api_key, self.timeout_seconds, self.max_retries,
                               extra_log=f"[ollama/{self.model}]")


class APIRuntime:
    """通用 OpenAI Chat Completions 兼容 runtime。

    适用于：OpenAI / Anthropic (via proxy) / 国产 / minimax / taotoken / LiteLLM 等。
    配置给什么 base_url + model + api_key，就能用。
    """

    runtime = "api"

    def __init__(self, model: str, base_url: str = "", api_key: str = "",
                 timeout_seconds: int = 60, max_retries: int = 1, **kwargs: Any):
        self.model = model
        self.base_url = base_url.rstrip("/")
        if not self.base_url:
            raise LLMProviderError("APIRuntime 缺 base_url")
        if not api_key:
            raise LLMProviderError("APIRuntime 缺 api_key")
        self.api_key = api_key
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries

    def chat(self, messages: List[ChatMessage], **kwargs: Any) -> ChatResponse:
        url = f"{self.base_url}/chat/completions"
        body = {
            "model": self.model,
            "messages": [m.to_dict() for m in messages],
        }
        for k in ("temperature", "max_tokens", "top_p", "stream", "response_format"):
            if k in kwargs:
                body[k] = kwargs[k]

        return _http_post_json(url, body, self.api_key, self.timeout_seconds, self.max_retries,
                               extra_log=f"[api/{self.model}]")


class StubRuntime:
    """Stub runtime——不调任何外部服务，用于：
    - 测试 / 单测
    - 用户没装 Ollama / 没配 API key 的兜底
    - 战甲降级（v3 启动时确认没装就退化到 stub）

    行为契约：返回固定 echo + 模型 ID，**永不抛异常**。
    """

    runtime = "stub"

    def __init__(self, model: str = "stub-model", **kwargs: Any):
        self.model = model

    def chat(self, messages: List[ChatMessage], **kwargs: Any) -> ChatResponse:
        # 取最后一条用户消息作为 echo 内容（能让上层验证调用是否真过了）
        # R4 确定性：None / 缺字段 不崩
        last_user = next((m.content for m in reversed(messages) if m.role == "user"), "") or ""
        content = f"[stub/{self.model}] 收到 {len(messages)} 条消息。最后一条: {str(last_user)[:120]}"
        prompt_tokens = sum(len(str(m.content or "")) for m in messages) // 2
        return ChatResponse(
            content=content,
            model=self.model,
            usage={"prompt_tokens": prompt_tokens,
                   "completion_tokens": len(content) // 2,
                   "total_tokens": prompt_tokens + len(content) // 2},
            raw={"stub": True, "msg_count": len(messages)},
        )


# ── HTTP 工具（避免每个 runtime 都重复 try/except） ────

def _http_post_json(url: str, body: Dict[str, Any], api_key: str,
                    timeout_seconds: int, max_retries: int,
                    extra_log: str = "") -> ChatResponse:
    """POST JSON 到 OpenAI 兼容接口，统一错误处理。"""
    data = json.dumps(body, ensure_ascii=False).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    last_err: Optional[Exception] = None
    for attempt in range(1 + max_retries):
        req = urllib.request.Request(url, data=data, method="POST")
        for k, v in headers.items():
            req.add_header(k, v)
        try:
            with urllib.request.urlopen(req, timeout=timeout_seconds) as r:
                resp_body = json.loads(r.read().decode("utf-8"))
            choices = resp_body.get("choices") or []
            if not choices:
                raise LLMProviderError(f"{extra_log} 响应无 choices: {resp_body}")
            content = choices[0].get("message", {}).get("content", "")
            return ChatResponse(
                content=content,
                model=resp_body.get("model", ""),
                usage=resp_body.get("usage", {}) or {},
                raw=resp_body,
            )
        except (urllib.error.URLError, urllib.error.HTTPError, json.JSONDecodeError) as e:
            last_err = e
            logger.warning("%s 第 %d 次失败: %s", extra_log, attempt + 1, e)
            if attempt < max_retries:
                continue
            break

    raise LLMProviderError(f"{extra_log} 重试 {max_retries} 次仍失败: {last_err}")


# ── Provider 工厂（R1 可插拔 · 一行换 runtime） ────────

_RUNTIME_REGISTRY = {
    "ollama": OllamaRuntime,
    "api": APIRuntime,
    "stub": StubRuntime,
}


def build_provider(cfg_section: Dict[str, Any]) -> LLMProvider:
    """根据配置段构造 Provider。未知 runtime → 降级 StubRuntime（不崩）。"""
    runtime_name = (cfg_section.get("runtime") or "stub").lower()
    cls = _RUNTIME_REGISTRY.get(runtime_name)
    if cls is None:
        logger.warning("未知 runtime '%s'，降级到 stub", runtime_name)
        return StubRuntime(model=cfg_section.get("model", "stub-model"))

    try:
        return cls(
            model=cfg_section.get("model", ""),
            base_url=cfg_section.get("base_url", ""),
            api_key=cfg_section.get("api_key", ""),
            timeout_seconds=int(cfg_section.get("timeout_seconds", 60)),
            max_retries=int(cfg_section.get("max_retries", 1)),
        )
    except LLMProviderError as e:
        # 配置错误（缺 base_url / api_key 等）→ 降级 stub
        logger.warning("构造 %s 失败: %s，降级到 stub", runtime_name, e)
        return StubRuntime(model=cfg_section.get("model", "stub-model"))


def build_consciousness(cfg: Optional[Dict[str, Any]] = None) -> LLMProvider:
    """构造战甲意识层 Provider（主用）。"""
    if cfg is None:
        cfg = load_config()
    return build_provider(get_consciousness_cfg(cfg))


def build_advisor(cfg: Optional[Dict[str, Any]] = None) -> Optional[LLMProvider]:
    """构造外部 advisor Provider；未启用 → 返回 None。"""
    if cfg is None:
        cfg = load_config()
    adv = get_advisor_cfg(cfg)
    if not adv.get("enabled"):
        return None
    return build_provider(adv)


# ── 顶层 chat 封装（带 fallback 链）────────────────────

def chat_with_fallback(messages: List[ChatMessage],
                       cfg: Optional[Dict[str, Any]] = None,
                       **kwargs: Any) -> ChatResponse:
    """按 fallback_chain 依次尝试，直到一个成功为止。全失败 → 返回 stub 回声。"""
    if cfg is None:
        cfg = load_config()

    chain = get_fallback_chain(cfg)
    # 主 provider 排第一
    primary = build_consciousness(cfg)
    providers_to_try = [primary]
    # 然后跑 fallback chain
    for runtime_name in chain:
        try:
            sec_cfg = {**get_consciousness_cfg(cfg), "runtime": runtime_name}
            providers_to_try.append(build_provider(sec_cfg))
        except Exception as e:
            logger.warning("构造 fallback %s 失败: %s", runtime_name, e)

    last_err: Optional[Exception] = None
    for p in providers_to_try:
        try:
            return p.chat(messages, **kwargs)
        except LLMProviderError as e:
            last_err = e
            logger.warning("Provider %s/%s 失败: %s", p.runtime, p.model, e)

    # 全失败 → 兜底 stub，绝不抛
    logger.error("所有 provider 全失败（含 fallback），最后错误: %s", last_err)
    fallback = StubRuntime(model="emergency-stub")
    return fallback.chat(messages, **kwargs)


# ── CLI（开发期调试用 · 生产时由 consciousness.py 接管） ─

def _cli() -> int:
    import argparse
    p = argparse.ArgumentParser(description="Mark42 LLM Provider · v3-1 可插拔 demo")
    p.add_argument("--runtime", choices=["ollama", "api", "stub"], help="覆盖配置里的 runtime")
    p.add_argument("--model", help="覆盖模型名")
    p.add_argument("--prompt", default="回复 pong", help="单轮 prompt")
    p.add_argument("--config", type=Path, help="显式指定 model.yaml 路径")
    args = p.parse_args()

    cfg = load_config(args.config)
    if args.runtime or args.model:
        cc = get_consciousness_cfg(cfg)
        if args.runtime:
            cc["runtime"] = args.runtime
        if args.model:
            cc["model"] = args.model

    provider = build_consciousness(cfg)
    logger.info(f"→ 构造 Provider: {provider.runtime} / {provider.model}")
    msgs = [ChatMessage(role="user", content=args.prompt)]
    try:
        resp = provider.chat(msgs)
    except LLMProviderError as e:
        logger.error(f"❌ 失败: {e}")
        return 2

    logger.info(f"✅ 模型返回: {resp.model}")
    logger.info(f"   content: {resp.content[:300]}")
    if resp.usage:
        logger.info(f"   usage: {resp.usage}")
    return 0


if __name__ == "__main__":
    raise SystemExit(_cli())