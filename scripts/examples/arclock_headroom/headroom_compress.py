"""
Headroom CompressLock Adapter - 第三方 ArcLock 适配器示例

这是一个完整的第三方实现示例，演示如何将 Headroom 上下文压缩服务
接入到 Mark42 的 ArcLock 通用适配层接口。

特点:
- 不 import 任何 mark42 内部模块
- 只需要方法签名匹配 Protocol 就能"吸上"
- 用 stub/mock 模拟 API 调用（不发真实 HTTP 请求）
"""

from __future__ import annotations
from typing import Any, Dict
import random
import time


class HeadroomCompress:
    """Headroom 上下文压缩适配器。

    实现 ArcLock 的 CompressLock Protocol，不需要继承任何类。
    只要方法签名正确，就能被 Mark42 的 ArcLock 注册器识别。
    """

    def __init__(self, api_key: str = "", model: str = "gpt-4o",
                 base_url: str = "https://api.headroom.ai"):
        """初始化适配器。

        参数来自 arclock.yaml 配置文件的 config 节。
        """
        self.api_key = api_key
        self.model = model
        self.base_url = base_url
        self._mock_data = self._init_mock_data()

    def _init_mock_data(self) -> Dict[str, Any]:
        """初始化 mock 数据，模拟 Headroom API 响应。"""
        return {
            "current_usage": random.uniform(30, 85),
            "severity_levels": ["low", "medium", "high", "critical"],
            "compression_options": ["summarize", "extract_key_points", "prune_duplicates"],
        }

    def _mock_api_call(self, endpoint: str, method: str = "GET", **kwargs) -> Dict[str, Any]:
        """模拟 API 调用，返回 stub 数据。

        真实实现中，这里应该调用真实的 Headroom API：
            import requests
            resp = requests.get(f"{self.base_url}{endpoint}",
                                headers={"Authorization": f"Bearer {self.api_key}"})
            return resp.json()
        """
        # 模拟网络延迟
        time.sleep(0.01)

        if endpoint == "/context/status":
            usage = self._mock_data["current_usage"]
            severity_idx = min(int(usage / 25), 3)
            return {
                "usage": usage,
                "level": self._mock_data["severity_levels"][severity_idx],
                "token_count": int(usage * 100),
                "max_tokens": 4096,
                "provider": "headroom",
            }

        elif endpoint == "/context/compress":
            dry_run = kwargs.get("dry_run", True)
            before = self._mock_data["current_usage"]
            after = before * random.uniform(0.5, 0.8) if not dry_run else before
            method = random.choice(self._mock_data["compression_options"])

            return {
                "action": "dry_run" if dry_run else "compressed",
                "method": method,
                "before": round(before, 2),
                "after": round(after, 2),
                "saved_percent": round(100 - (after / before * 100), 2) if before > 0 else 0,
                "tokens_removed": int((before - after) * 100) if not dry_run else 0,
                "would_compress": True,
            }

        elif endpoint == "/context/diagnose":
            return {
                "provider": "headroom",
                "model": self.model,
                "base_url": self.base_url,
                "has_api_key": bool(self.api_key),
                "supported_methods": self._mock_data["compression_options"],
                "mock_mode": True,
                "status": "operational",
            }

        return {"error": "unknown_endpoint"}

    def check(self) -> Dict[str, Any]:
        """检查当前上下文状态。

        实现 CompressLock Protocol 要求的 check() 方法。

        返回格式要求:
            {"usagePercent": float, "severity": str, ...}
        """
        api_result = self._mock_api_call("/context/status")

        # 按照 Mark42 CompressLock 约定的格式返回
        return {
            "usagePercent": api_result["usage"],
            "severity": api_result["level"],
            "tokenCount": api_result["token_count"],
            "maxTokens": api_result["max_tokens"],
            "provider": api_result["provider"],
        }

    def compress(self, dry_run: bool = True, **kwargs: Any) -> Dict[str, Any]:
        """执行上下文压缩。

        实现 CompressLock Protocol 要求的 compress() 方法。

        参数:
            dry_run: True 只分析不执行，False 真实执行
            **kwargs: 额外参数（如 target_ratio、strategy 等）

        返回格式要求:
            {"action": str, "before": float, "after": float, ...}
        """
        api_result = self._mock_api_call("/context/compress", dry_run=dry_run, **kwargs)

        # 按照 Mark42 CompressLock 约定的格式返回
        return {
            "action": api_result["action"],
            "before": api_result["before"],
            "after": api_result["after"],
            "savedPercent": api_result["saved_percent"],
            "tokensRemoved": api_result["tokens_removed"],
            "method": api_result["method"],
            "wouldCompress": api_result["would_compress"],
        }

    def diagnose(self) -> Dict[str, Any]:
        """压缩诊断。

        实现 CompressLock Protocol 要求的 diagnose() 方法。
        返回详细的分析信息，供调试和监控使用。
        """
        return self._mock_api_call("/context/diagnose")


# ── 独立运行时的快速测试 ──

if __name__ == "__main__":
    # 这个演示证明：第三方代码不需要任何 mark42 依赖就能独立运行
    print("=" * 60)
    print("Headroom CompressLock Adapter - 独立测试（不依赖 Mark42）")
    print("=" * 60)

    adapter = HeadroomCompress(api_key="test-key", model="gpt-4o-mini")

    print("\n1. check() - 上下文状态检查:")
    result = adapter.check()
    print(f"   usagePercent: {result['usagePercent']:.2f}%")
    print(f"   severity: {result['severity']}")
    print(f"   provider: {result['provider']}")

    print("\n2. compress(dry_run=True) - 预览压缩:")
    result = adapter.compress(dry_run=True)
    print(f"   action: {result['action']}")
    print(f"   wouldCompress: {result['wouldCompress']}")
    print(f"   method: {result['method']}")

    print("\n3. compress(dry_run=False) - 真实压缩:")
    result = adapter.compress(dry_run=False)
    print(f"   action: {result['action']}")
    print(f"   before: {result['before']}% -> after: {result['after']}%")
    print(f"   savedPercent: {result['savedPercent']}%")
    print(f"   tokensRemoved: {result['tokensRemoved']}")

    print("\n4. diagnose() - 适配器诊断:")
    result = adapter.diagnose()
    for key, value in result.items():
        print(f"   {key}: {value}")

    print("\n✅ 第三方适配器可以完全独立运行，不依赖 Mark42 任何代码！")
    print("   只要方法签名正确，就能被 ArcLock 注册器'吸上'。")
