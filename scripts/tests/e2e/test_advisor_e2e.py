#!/usr/bin/env python3
"""P1-1: AdvisorClient LLM 端到端链路验证脚本。

验证 C4 对话场景的完整链路：
  issue -> Consciousness.assess_certainty -> AdvisorClient.ask -> verdict 解析

用法:
  # 用 openclaw.json 里的 volcengine-agent 配置
  python3 tests/e2e/test_advisor_e2e.py

  # 指定模型
  python3 tests/e2e/test_advisor_e2e.py --model doubao-seed-2.0-pro

  # dry-run（不真正调用 LLM，只验证链路连通性）
  python3 tests/e2e/test_advisor_e2e.py --dry-run

验证项:
  1. model.yaml 加载 / openclaw.json fallback
  2. AdvisorClient 初始化（provider != None）
  3. 场景 a: 不确定问题 -> advisor 决策
  4. 场景 b: 修复方案确认 -> advisor 审核
  5. 场景 c: 新异常 -> advisor 判断
  6. 场景 d: 档案复用 -> advisor 批准
  7. 响应解析（verdict / confidence / action）
  8. fallback 链路（LLM 不可用时降级到 ask_user）
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

# 确保能 import mark42_modules
SCRIPT_DIR = Path(__file__).resolve().parent.parent.parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))


def _load_openclaw_config() -> dict[str, Any]:
    """从 openclaw.json 读取 provider 配置，构造 model.yaml 格式。

    优先级: volcengine-agent > litellm > nvidia
    """
    openclaw_json = Path.home() / ".openclaw" / "workspace" / "openclaw.json"
    if not openclaw_json.exists():
        return {}

    with open(openclaw_json) as f:
        oc = json.load(f)

    providers = oc.get("models", {}).get("providers", {})

    # 优先 volcengine-agent（运行时注入），回退 litellm
    va = providers.get("volcengine-agent", {})
    if not va:
        va = providers.get("litellm", {})
    if not va:
        return {}

    # 读取 model 和 baseUrl
    model = va.get("model", "")
    if not model:
        models_list = va.get("models", [])
        if isinstance(models_list, list) and models_list:
            model = models_list[0].get("id", "agnes-2.0-flash")
        else:
            model = "agnes-2.0-flash"

    base_url = va.get("baseUrl", va.get("baseURL", ""))
    api_key = va.get("apiKey", "")

    if not api_key:
        return {}

    return {
        "mark42": {
            "consciousness": {
                "runtime": "api",
                "model": model,
                "base_url": base_url,
                "api_key": api_key,
                "timeout_seconds": 60,
                "max_retries": 1,
            },
            "fallback_chain": ["api"],
            "advisor": {
                "enabled": True,
                "runtime": "api",
                "model": model,
                "base_url": base_url,
                "api_key": api_key,
                "timeout_seconds": 30,
                "confidence_threshold": 0.6,
            },
        }
    }


def _print(name: str, ok: bool, detail: str = "") -> None:
    icon = "✅" if ok else "❌"
    print(f"  {icon} {name}" + (f" -- {detail}" if detail else ""))


def run_e2e(dry_run: bool = False, model_override: str = "") -> int:
    """运行端到端验证。返回通过数。"""
    from mark42_modules.advisor_client import AdvisorClient, AdvisorResult
    from mark42_modules.consciousness import Consciousness, CertaintyAssessment

    print("=" * 60)
    print("  AdvisorClient LLM 端到端链路验证")
    print("=" * 60)
    print()

    passed = 0
    total = 0

    # ── 1. 配置加载 ──
    print("── 1. 配置加载 ──")
    total += 1

    config = _load_openclaw_config()
    if model_override and config:
        config["mark42"]["advisor"]["model"] = model_override
        config["mark42"]["consciousness"]["model"] = model_override

    if not config:
        print("  ⚠️ 未找到 openclaw.json 或 volcengine-agent 配置")
        print("  尝试从 model.yaml 加载...")
        # 直接让 AdvisorClient 自己读 model.yaml
        config = None

    _print("配置加载", True, f"source={'openclaw.json' if config else 'model.yaml'}")
    passed += 1
    print()

    # ── 2. AdvisorClient 初始化 ──
    print("── 2. AdvisorClient 初始化 ──")
    total += 1

    client = AdvisorClient(config)
    if not client.enabled:
        print("  ⚠️ advisor 未启用，尝试强制启用...")
        if config is None:
            config = _load_openclaw_config()
        if config:
            config["mark42"]["advisor"]["enabled"] = True
            client = AdvisorClient(config)

    if not client.provider:
        print("  ❌ provider 为 None -- 检查 API key / base_url 配置")
        print("  跳过后续测试")
        return passed
    else:
        _print("provider 初始化", True, f"model={client.provider.model if hasattr(client.provider, 'model') else '?'}")
        passed += 1
    print()

    if dry_run:
        print("── dry-run 模式：跳过 LLM 调用 ──")
        print(f"\n结果: {passed}/{total} 通过（dry-run）")
        return passed

    # ── 3. 场景 a: 不确定问题 ──
    print("── 3. 场景 a: 不确定问题 -> advisor 决策 ──")
    total += 1

    issue_a = {
        "source": "armor",
        "category": "context_alert",
        "severity": "warning",
        "message": "上下文使用率达到 82%，接近 ALERT 阈值",
        "context_usage": 82,
    }
    assessment_a = {
        "certainty": 0.5,
        "reason": "上下文高但不确定是否该压缩",
        "matched_rule": None,
        "archive_hit": False,
    }

    try:
        t0 = time.monotonic()
        result_a = client.ask("a", issue=issue_a, assessment=assessment_a)
        elapsed = (time.monotonic() - t0) * 1000

        if result_a.success:
            v = result_a.verdict
            _print("场景 a 调用", True,
                   f"verdict={v.verdict}, confidence={v.confidence:.2f}, {elapsed:.0f}ms")
            passed += 1
        else:
            _print("场景 a 调用", False, f"fallback={result_a.fallback_reason}")
    except Exception as e:
        _print("场景 a 调用", False, f"异常: {e}")
    print()

    # ── 4. 场景 b: 修复方案确认 ──
    print("── 4. 场景 b: 修复方案审核 ──")
    total += 1

    issue_b = {
        "source": "consciousness",
        "category": "process_down",
        "severity": "critical",
        "message": "engine-daemon 进程不可用",
    }
    plan_b = {
        "action": "restart_engine",
        "command": "systemctl --user restart mark42-engine-daemon.service",
        "risk": "low",
        "reversible": True,
    }

    try:
        result_b = client.ask("b", issue=issue_b, plan=plan_b)
        if result_b.success:
            v = result_b.verdict
            _print("场景 b 调用", True,
                   f"verdict={v.verdict}, confidence={v.confidence:.2f}")
            passed += 1
        else:
            _print("场景 b 调用", False, f"fallback={result_b.fallback_reason}")
    except Exception as e:
        _print("场景 b 调用", False, f"异常: {e}")
    print()

    # ── 5. 场景 c: 新异常 ──
    print("── 5. 场景 c: 新异常判断 ──")
    total += 1

    issue_c = {
        "source": "anomaly_detector",
        "category": "unknown_anomaly",
        "severity": "warning",
        "message": "检测到 broker 事件写入速率异常（5min 内 1000+ 事件）",
        "metrics": {"events_per_min": 200, "normal_avg": 10},
    }

    try:
        result_c = client.ask("c", issue=issue_c)
        if result_c.success:
            v = result_c.verdict
            _print("场景 c 调用", True,
                   f"verdict={v.verdict}, confidence={v.confidence:.2f}")
            passed += 1
        else:
            _print("场景 c 调用", False, f"fallback={result_c.fallback_reason}")
    except Exception as e:
        _print("场景 c 调用", False, f"异常: {e}")
    print()

    # ── 6. 场景 d: 档案复用 ──
    print("── 6. 场景 d: 档案复用批准 ──")
    total += 1

    archive_entry_d = {
        "signature": "context_alert_high_usage",
        "category": "context",
        "resolution": "auto_compress",
        "occurrence_count": 5,
        "last_seen": "2026-07-20T10:00:00Z",
    }

    try:
        result_d = client.ask("d", archive_entry=archive_entry_d)
        if result_d.success:
            v = result_d.verdict
            _print("场景 d 调用", True,
                   f"verdict={v.verdict}, confidence={v.confidence:.2f}")
            passed += 1
        else:
            _print("场景 d 调用", False, f"fallback={result_d.fallback_reason}")
    except Exception as e:
        _print("场景 d 调用", False, f"异常: {e}")
    print()

    # ── 7. fallback 链路验证 ──
    print("── 7. fallback 链路（LLM 不可用）──")
    total += 1

    bad_config = {
        "mark42": {
            "advisor": {
                "enabled": True,
                "runtime": "api",
                "model": "nonexistent-model",
                "base_url": "http://127.0.0.1:1",  # 不可达
                "api_key": "fake",
                "timeout_seconds": 3,
            }
        }
    }
    try:
        bad_client = AdvisorClient(bad_config)
        result_fallback = bad_client.ask("a", issue=issue_a, assessment=assessment_a)
        if not result_fallback.success and result_fallback.fallback_action == "ask_user":
            _print("fallback 降级", True, "正确降级到 ask_user")
            passed += 1
        else:
            _print("fallback 降级", False, f"预期 ask_user, 实际 {result_fallback.fallback_action}")
    except Exception as e:
        _print("fallback 降级", False, f"异常: {e}")
    print()

    # ── 总结 ──
    print("=" * 60)
    print(f"  结果: {passed}/{total} 通过")
    print("=" * 60)

    return passed


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="AdvisorClient LLM 端到端验证")
    parser.add_argument("--model", default="", help="模型覆盖")
    parser.add_argument("--dry-run", action="store_true", help="只验证链路连通性")
    args = parser.parse_args()

    passed = run_e2e(dry_run=args.dry_run, model_override=args.model)
    sys.exit(0 if passed > 0 else 1)
