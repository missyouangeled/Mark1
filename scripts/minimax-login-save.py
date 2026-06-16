#!/usr/bin/env python3
"""
MiniMax Audio 登录态保存脚本
用法：python3 scripts/minimax-login-save.py
在打开的浏览器中手动登录 MiniMax，登录成功后按 Enter，脚本自动保存 storage state。
此后所有后续脚本可复用登录态，无需再次登录。
"""

import sys
import json
from pathlib import Path
from playwright.sync_api import sync_playwright

STORAGE_STATE_FILE = Path.home() / ".local/state/openclaw/minimax-storage-state.json"

def main():
    STORAGE_STATE_FILE.parent.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()

        print("🌐 打开 MiniMax Audio 页面...")
        page.goto("https://www.minimax.io/audio")
        page.wait_for_load_state("networkidle")
        print()
        print("=" * 50)
        print("  👆 请在浏览器中登录 MiniMax")
        print("  （邮箱/手机号/Google 都可以）")
        print("  登录成功后回到终端按 Enter...")
        print("=" * 50)
        print()

        input()

        # 保存 storage state
        print("💾 保存登录态...")
        context.storage_state(path=str(STORAGE_STATE_FILE))

        browser.close()
        print(f"✅ 登录态已保存到: {STORAGE_STATE_FILE}")
        print(f"   文件大小: {STORAGE_STATE_FILE.stat().st_size} bytes")


if __name__ == "__main__":
    main()
