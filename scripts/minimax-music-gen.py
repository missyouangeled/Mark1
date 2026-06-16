#!/usr/bin/env python3
"""
MiniMax Music 2.6 音乐生成脚本（自动复用登录态）
前置条件：先用 minimax-login-save.py 登录一次并保存状态
用法：
  python3 scripts/minimax-music-gen.py --prompt "古筝竹笛,江南水乡" --lyrics "歌词内容"
  python3 scripts/minimax-music-gen.py --prompt "电子氛围,慢节奏" --instrumental
  python3 scripts/minimax-music-gen.py --prompt "民谣,温暖男声" --lyrics-optimizer
"""

import sys
import json
import time
import argparse
from pathlib import Path
from playwright.sync_api import sync_playwright

STORAGE_STATE_FILE = Path.home() / ".local/state/openclaw/minimax-storage-state.json"
PAGE_URL = "https://www.minimax.io/audio"


def main():
    parser = argparse.ArgumentParser(description="MiniMax Music 2.6 音乐生成")
    parser.add_argument("--prompt", required=True, help="音乐风格描述（英文效果更好）")
    parser.add_argument("--lyrics", help="歌词内容")
    parser.add_argument("--lyrics-optimizer", action="store_true", help="无歌词时让 AI 自动生成歌词")
    parser.add_argument("--instrumental", action="store_true", help="纯器乐模式（无歌词）")
    parser.add_argument("--song-name", help="歌曲名称")
    parser.add_argument("--out-dir", default="/home/missyouangeled/.openclaw/media/generated",
                        help="输出目录")
    parser.add_argument("--headless", action="store_true", help="无头模式（不显示浏览器）")
    parser.add_argument("--timeout", type=int, default=300, help="生成超时秒数")
    args = parser.parse_args()

    if not STORAGE_STATE_FILE.exists():
        print("❌ 未找到登录态文件，请先运行:")
        print("   python3 scripts/minimax-login-save.py")
        sys.exit(1)

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=args.headless)
        context = browser.new_context(storage_state=str(STORAGE_STATE_FILE))
        page = context.new_page()

        print("🌐 打开 MiniMax Audio 音乐创作页...")
        page.goto(f"{PAGE_URL}/music")
        page.wait_for_load_state("networkidle")
        time.sleep(2)

        # 如果有同意条款弹窗，点同意
        try:
            agree_btn = page.locator("text=Agree").first
            if agree_btn.is_visible(timeout=3000):
                agree_btn.click()
                print("✅ 已点击同意条款")
                time.sleep(1)
        except:
            pass

        # 填充歌词
        if args.lyrics:
            print("📝 填入歌词...")
            lyrics_box = page.locator("textarea[placeholder*='lyrics']") or \
                         page.locator("textarea").first
            lyrics_box.click()
            lyrics_box.fill(args.lyrics)
        elif args.lyrics_optimizer:
            print("🎤 启用 AI 自动生成歌词...")
            # 寻找 lyrics_optimizer 开关
            try:
                opt_switch = page.locator("text=Generate Lyrics").first
                if opt_switch.is_visible(timeout=3000):
                    opt_switch.click()
                else:
                    print("⚠️ 未找到歌词自动生成开关，将以纯器乐模式生成")
            except:
                print("⚠️ 将尝试纯器乐模式")

        # 填充 prompt
        print(f"🎵 填入风格: {args.prompt}")
        prompt_box = page.locator("textarea[placeholder*='style']") or \
                     page.locator("textarea[placeholder*='Describe']")
        prompt_box.click()
        prompt_box.fill(args.prompt)

        # 启用纯器乐模式
        if args.instrumental:
            print("🎹 启用纯器乐模式...")
            try:
                inst_switch = page.locator("text=Instrumental").first or \
                              page.locator("[aria-label*='instrumental']")
                if inst_switch.is_visible(timeout=3000):
                    inst_switch.click()
            except:
                pass

        # 填入歌曲名
        if args.song_name:
            name_box = page.locator("input[placeholder*='Song Name']")
            if name_box.is_visible(timeout=2000):
                name_box.fill(args.song_name)

        # 点击生成
        print("🚀 提交生成...")
        gen_btn = page.locator("button:has-text('Generate')").first or \
                  page.locator("text=Generate").first
        gen_btn.click()

        # 等待生成完成（URL 变化或出现下载按钮）
        print("⏳ 等待生成完成（最长 {} 秒）...".format(args.timeout))
        start = time.time()
        while time.time() - start < args.timeout:
            try:
                # 检查是否有下载链接
                download_btn = page.locator("a[download]").first or \
                               page.locator("button:has-text('Download')").first
                if download_btn.is_visible(timeout=2000):
                    print("✅ 生成完成！")
                    href = download_btn.get_attribute("href") or ""
                    print(f"   下载链接: {href}")
                    if href:
                        download_btn.click()
                        time.sleep(3)
                    break
            except:
                pass
            time.sleep(5)
        else:
            print("⏰ 超时，请手动检查浏览器窗口")

        print("📸 保存截图...")
        timestamp = time.strftime("%Y%m%d-%H%M%S")
        screenshot_path = out_dir / f"minimax-music-{timestamp}.png"
        page.screenshot(path=str(screenshot_path), full_page=True)
        print(f"   截图: {screenshot_path}")

        input("按 Enter 关闭浏览器...")
        browser.close()


if __name__ == "__main__":
    main()
