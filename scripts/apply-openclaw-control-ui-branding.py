#!/usr/bin/env python3
# 适用机器：通用（当前已在公司（Linux）验证）
# 系统 / OS：Linux / macOS / Windows（取决于本机 OpenClaw 安装位置）
# 用途：为本机 OpenClaw Control UI 重复应用品牌补丁，覆盖左上角品牌名、图标、浏览器标题、PWA 清单，以及页面中可见的 OpenClaw 品牌字样。

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = WORKSPACE / "config" / "control-ui-branding.json"
DEFAULT_PACKAGE_ROOT = Path.home() / ".npm-global" / "lib" / "node_modules" / "openclaw"
INJECT_MARKER_START = "<!-- jarvis-branding:begin -->"
INJECT_MARKER_END = "<!-- jarvis-branding:end -->"
SCRIPT_NAME = "jarvis-branding-override.js"


def die(message: str) -> "NoReturn":
    print(f"error: {message}", file=sys.stderr)
    raise SystemExit(1)



def read_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        die(f"配置文件不存在：{path}")
    except json.JSONDecodeError as exc:
        die(f"配置文件不是合法 JSON：{path} ({exc})")



def resolve_package_root() -> Path:
    env_override = os.environ.get("OPENCLAW_PACKAGE_ROOT")
    if env_override:
        candidate = Path(env_override).expanduser().resolve()
        if (candidate / "dist" / "control-ui").exists():
            return candidate
        die(f"OPENCLAW_PACKAGE_ROOT 无效：{candidate}")

    if (DEFAULT_PACKAGE_ROOT / "dist" / "control-ui").exists():
        return DEFAULT_PACKAGE_ROOT

    try:
        npm_root = subprocess.run(
            ["npm", "root", "-g"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        candidate = Path(npm_root) / "openclaw"
        if (candidate / "dist" / "control-ui").exists():
            return candidate.resolve()
    except Exception:
        pass

    die("找不到 OpenClaw 包目录；可手动设置 OPENCLAW_PACKAGE_ROOT=/path/to/openclaw")



def resolve_source(workspace_relative: str) -> Path:
    source = (WORKSPACE / workspace_relative).resolve()
    if not source.exists():
        die(f"品牌源图片不存在：{source}")
    if not source.is_file():
        die(f"品牌源图片不是文件：{source}")
    return source



def replace_once(text: str, pattern: str, replacement: str, *, flags: int = 0, description: str) -> str:
    updated, count = re.subn(pattern, replacement, text, count=1, flags=flags)
    if count != 1:
        die(f"未能定位需要替换的 {description}")
    return updated



def inject_head_block(html: str, version: str) -> str:
    block = (
        f"{INJECT_MARKER_START}\n"
        f'    <script src="./{SCRIPT_NAME}?v={version}"></script>\n'
        f"    {INJECT_MARKER_END}"
    )
    existing = re.compile(
        rf"\s*{re.escape(INJECT_MARKER_START)}.*?{re.escape(INJECT_MARKER_END)}",
        flags=re.S,
    )
    if existing.search(html):
        html = existing.sub("\n    " + block, html, count=1)
    else:
        html = replace_once(html, r"</head>", "\n    " + block + "\n  </head>", description="index.html </head>")
    return html



def write_override_script(
    path: Path,
    *,
    brand_title: str,
    brand_eyebrow: str,
    window_title: str,
    logo_file: str,
    favicon_file: str,
    apple_touch_file: str,
    version: str,
) -> None:
    payload = {
        "brandTitle": brand_title,
        "brandEyebrow": brand_eyebrow,
        "windowTitle": window_title,
        "logoHref": f"./{logo_file}?v={version}",
        "faviconHref": f"./{favicon_file}?v={version}",
        "appleTouchHref": f"./{apple_touch_file}?v={version}",
        "logoAlt": brand_title,
        "visibleTextReplacements": [
            ["OpenClaw Control", window_title],
            ["OpenClaw", brand_title],
        ],
        "attributeNames": ["title", "aria-label", "placeholder", "alt"],
        "skipClosestSelectors": [
            "pre",
            "code",
            "textarea",
            "input",
            ".message",
            ".message-list",
            ".message-bubble",
            ".chat-thread",
            ".tool-output",
            ".tool-call",
            ".tool-result",
            ".cm-editor",
        ],
    }
    script = f"""(() => {{
  const BRAND = {json.dumps(payload, ensure_ascii=False, indent=2)};

  function setAttr(node, name, value) {{
    if (node && node.getAttribute(name) !== value) node.setAttribute(name, value);
  }}

  function setText(node, value) {{
    if (node && value && node.textContent !== value) node.textContent = value;
  }}

  function replaceLiterals(value) {{
    if (typeof value !== 'string' || !value) return value;
    let next = value;
    for (const [from, to] of BRAND.visibleTextReplacements) {{
      if (from && typeof to === 'string' && next.includes(from)) {{
        next = next.split(from).join(to);
      }}
    }}
    return next;
  }}

  function shouldSkipElement(element) {{
    if (!element || typeof element.closest !== 'function') return false;
    return BRAND.skipClosestSelectors.some((selector) => {{
      try {{
        return Boolean(element.closest(selector));
      }} catch {{
        return false;
      }}
    }});
  }}

  function patchAttribute(element, name) {{
    if (!element || shouldSkipElement(element)) return;
    const current = element.getAttribute(name);
    if (!current) return;
    const next = replaceLiterals(current);
    if (next !== current) setAttr(element, name, next);
  }}

  function patchTextNode(node) {{
    if (!node || typeof node.nodeValue !== 'string') return;
    const parent = node.parentElement;
    if (!parent || shouldSkipElement(parent)) return;
    if (['SCRIPT', 'STYLE', 'NOSCRIPT', 'TEXTAREA', 'INPUT', 'CODE', 'PRE'].includes(parent.tagName)) return;
    const current = node.nodeValue;
    const next = replaceLiterals(current);
    if (next !== current) node.nodeValue = next;
  }}

  function replaceVisibleText(root) {{
    const base = root && root.nodeType ? root : (document.body || document.documentElement);
    if (!base) return;

    if (base.nodeType === Node.ELEMENT_NODE) {{
      BRAND.attributeNames.forEach((attr) => patchAttribute(base, attr));
    }}

    const walker = document.createTreeWalker(base, NodeFilter.SHOW_TEXT);
    let textNode;
    while ((textNode = walker.nextNode())) {{
      patchTextNode(textNode);
    }}

    if (typeof base.querySelectorAll === 'function') {{
      base.querySelectorAll('*').forEach((element) => {{
        BRAND.attributeNames.forEach((attr) => patchAttribute(element, attr));
      }});
    }}
  }}

  function applyBranding(root) {{
    try {{
      if (document.title !== BRAND.windowTitle) document.title = BRAND.windowTitle;

      document.querySelectorAll('link[rel="icon"]').forEach((link) => {{
        setAttr(link, 'href', BRAND.faviconHref);
        setAttr(link, 'type', 'image/png');
      }});

      document.querySelectorAll('link[rel="apple-touch-icon"]').forEach((link) => {{
        setAttr(link, 'href', BRAND.appleTouchHref);
      }});

      const logo = document.querySelector('.sidebar-brand__logo');
      setAttr(logo, 'src', BRAND.logoHref);
      setAttr(logo, 'alt', BRAND.logoAlt);

      setText(document.querySelector('.sidebar-brand__title'), BRAND.brandTitle);
      setText(document.querySelector('.sidebar-brand__eyebrow'), BRAND.brandEyebrow);
      replaceVisibleText(root);
    }} catch (err) {{
      console.warn('[jarvis-branding] apply failed:', err);
    }}
  }}

  let scheduled = false;
  function scheduleApply(root) {{
    if (scheduled) return;
    scheduled = true;
    requestAnimationFrame(() => {{
      scheduled = false;
      applyBranding(root);
    }});
  }}

  function boot() {{
    applyBranding(document.body || document.documentElement);
    const observer = new MutationObserver((mutations) => {{
      for (const mutation of mutations) {{
        if (mutation.type === 'childList') {{
          mutation.addedNodes.forEach((node) => scheduleApply(node));
        }} else if (mutation.type === 'characterData') {{
          scheduleApply(mutation.target?.parentElement || document.body || document.documentElement);
        }}
      }}
    }});
    observer.observe(document.documentElement, {{ childList: true, subtree: true, characterData: true }});
    window.addEventListener('pageshow', () => applyBranding(document.body || document.documentElement));
    document.addEventListener('visibilitychange', () => applyBranding(document.body || document.documentElement));
  }}

  if (document.readyState === 'loading') {{
    document.addEventListener('DOMContentLoaded', boot, {{ once: true }});
  }} else {{
    boot();
  }}
}})();
"""
    path.write_text(script, encoding="utf-8")



def main() -> int:
    config_path = Path(sys.argv[1]).expanduser().resolve() if len(sys.argv) > 1 else DEFAULT_CONFIG
    cfg = read_json(config_path)

    branding = cfg.get("branding") or {}
    assets = cfg.get("assets") or {}

    brand_title = str(branding.get("brandTitle") or "贾维斯")
    brand_eyebrow = str(branding.get("brandEyebrow") or "CONTROL")
    window_title = str(branding.get("windowTitle") or f"{brand_title} Control")
    manifest_name = str(branding.get("manifestName") or window_title)
    manifest_short_name = str(branding.get("manifestShortName") or brand_title)
    notification_title = str(branding.get("notificationTitle") or brand_title)

    logo_source = resolve_source(str(assets.get("logoSource") or "avatars/jarvis-neon-20260507.png"))
    runtime_logo_file = str(assets.get("runtimeLogoFile") or f"jarvis-brand{logo_source.suffix.lower() or '.png'}")
    favicon_file = str(assets.get("favicon32File") or "favicon-32.png")
    apple_touch_file = str(assets.get("appleTouchIconFile") or "apple-touch-icon.png")

    package_root = resolve_package_root()
    dist_root = package_root / "dist" / "control-ui"
    if not dist_root.exists():
        die(f"Control UI 目录不存在：{dist_root}")

    version = str(int(time.time()))

    runtime_logo_path = dist_root / runtime_logo_file
    shutil.copyfile(logo_source, runtime_logo_path)
    shutil.copyfile(logo_source, dist_root / favicon_file)
    shutil.copyfile(logo_source, dist_root / apple_touch_file)

    index_html_path = dist_root / "index.html"
    html = index_html_path.read_text(encoding="utf-8")
    html = replace_once(html, r"<title>.*?</title>", f"<title>{window_title}</title>", flags=re.S, description="index.html 标题")
    html = inject_head_block(html, version)
    index_html_path.write_text(html, encoding="utf-8")

    override_script_path = dist_root / SCRIPT_NAME
    write_override_script(
        override_script_path,
        brand_title=brand_title,
        brand_eyebrow=brand_eyebrow,
        window_title=window_title,
        logo_file=runtime_logo_file,
        favicon_file=favicon_file,
        apple_touch_file=apple_touch_file,
        version=version,
    )

    manifest_path = dist_root / "manifest.webmanifest"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["name"] = manifest_name
    manifest["short_name"] = manifest_short_name
    manifest["icons"] = [
        {
            "src": f"./{favicon_file}",
            "sizes": "32x32",
            "type": "image/png",
        },
        {
            "src": f"./{apple_touch_file}",
            "sizes": "180x180",
            "type": "image/png",
        },
    ]
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    sw_path = dist_root / "sw.js"
    sw = sw_path.read_text(encoding="utf-8")
    sw = sw.replace('data = { title: "OpenClaw", body: event.data.text() };', f'data = {{ title: {json.dumps(notification_title, ensure_ascii=False)}, body: event.data.text() }};')
    sw = sw.replace('const title = data.title || "OpenClaw";', f'const title = data.title || {json.dumps(notification_title, ensure_ascii=False)};')
    sw_path.write_text(sw, encoding="utf-8")

    print("Applied Control UI branding patch.")
    print(f"- packageRoot: {package_root}")
    print(f"- logoSource: {logo_source}")
    print(f"- runtimeLogo: {runtime_logo_path}")
    print(f"- windowTitle: {window_title}")
    print(f"- brandTitle: {brand_title}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
