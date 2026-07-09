#!/usr/bin/env python3
"""通过 WebSocket 直接连 Gateway，调用 chat.history 看 raw payload。
目的：判断 WebChat 渲染异常是 Gateway 投影造成 (Q2) 还是仅前端渲染 bug (Q1)。
"""
import asyncio
import json
import sys
from pathlib import Path

# 用 urllib 拿 token（从 openclaw.json）
CFG = json.loads(Path("/home/missyouangeled/.openclaw/openclaw.json").read_text())
TOKEN = CFG.get("gateway", {}).get("auth", {}).get("token")
URL = f"ws://127.0.0.1:18789"
SESSIONS_OF_INTEREST = [
    "agent:main:main",
    "agent:main:dashboard:293bd72d-4fb7-4a5f-805a-48e10b0a5270",
]

# 原始 import，避免 wexpect; 用标准库
try:
    import websockets
except ImportError:
    print("ERROR: pip install websockets", file=sys.stderr)
    sys.exit(2)


async def call(ws, method, params, label):
    req_id = f"probe-{method}-{label}"
    req = {"jsonrpc": "2.0", "id": req_id, "method": method, "params": params}
    print(f"\n===== {method} {label} =====")
    print(f"REQ: {json.dumps(req)[:500]}")
    await ws.send(json.dumps(req))
    try:
        raw = await asyncio.wait_for(ws.recv(), timeout=15)
    except asyncio.TimeoutError:
        print("TIMEOUT")
        return None
    try:
        resp = json.loads(raw)
    except Exception as e:
        print(f"NON-JSON RESP: {e}: {raw[:400]}")
        return raw
    print(f"RESP keys: {list(resp.keys())}")
    if "result" in resp:
        result = resp["result"]
        # 仅打印结构 + 摘要，不打印大块内容
        if isinstance(result, dict):
            print(f"result keys: {list(result.keys())}")
            # 摘要里搜 attachment / media / file / url / path
            keys_of_interest = [k for k in result.keys() if any(
                x in k.lower() for x in ("attach", "media", "file", "url", "path", "tool", "canvas"))]
            if keys_of_interest:
                print(f"keys_of_interest: {keys_of_interest}")
            # 如果是 messages 列表，统计
            for k in ("messages", "entries", "items"):
                if k in result and isinstance(result[k], list):
                    print(f"  {k}: count={len(result[k])}")
                    # 统计 attachment / media
                    att = sum(1 for m in result[k] if isinstance(m, dict) and any(
                        a in (m.get('role') or '') or a in json.dumps(m).lower()[:200]
                        for a in ("attach", "media", "MEDIA:")))
                    print(f"    contains 'attach'/'media'/'MEDIA:' in first 200 chars: ~{att}")
                    # 抽第一条结构
                    if result[k]:
                        first = result[k][0]
                        if isinstance(first, dict):
                            print(f"    first entry keys: {list(first.keys())}")
                            print(f"    first role: {first.get('role')}")
                            # 看 content 类型
                            c = first.get("content")
                            if isinstance(c, str):
                                print(f"    content type: str (len={len(c)})")
                            elif isinstance(c, list):
                                print(f"    content type: list (len={len(c)})")
                                for j, blk in enumerate(c[:3]):
                                    if isinstance(blk, dict):
                                        print(f"      block[{j}] keys: {list(blk.keys())}, type={blk.get('type')}")
    if "error" in resp:
        print(f"ERROR: {resp['error']}")
    return resp


async def main():
    headers = [("Authorization", f"Bearer {TOKEN}")]
    async with websockets.connect(URL, additional_headers=headers) as ws:
        # hello / 认证
        hello = await ws.recv()
        print(f"HELLO preview: {hello[:200]}")
        # 几个测试调用
        await call(ws, "sessions.list", {}, "sessions.list")
        for sk in SESSIONS_OF_INTEREST:
            await call(ws, "chat.history", {"sessionKey": sk, "limit": 5}, f"history({sk})")
        # 找最近一条 messageId，再做 chat.message.get
        await call(ws, "chat.history", {
            "sessionKey": "agent:main:main",
            "limit": 3
        }, "history-recent")
        # 看 health 确认响应形式
        await call(ws, "health", {}, "health")


if __name__ == "__main__":
    asyncio.run(main())