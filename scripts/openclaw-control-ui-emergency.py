#!/usr/bin/env python3
# 适用机器：通用（当前先在公司 Linux 验证）
# 系统 / OS：Linux / macOS / Windows（依赖本机 openclaw CLI 与 Python 标准库）
# 用途：Control UI 黑屏/打不开时，从浏览器视角到 OpenClaw Control UI 相关插件逐层诊断与低侵入修复。

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

WORKSPACE = Path(__file__).resolve().parents[1]
SCRIPTS = WORKSPACE / "scripts"
DEFAULT_PACKAGE_ROOT = Path.home() / ".npm-global" / "lib" / "node_modules" / "openclaw"
DEFAULT_BASE_URL = "http://127.0.0.1:18789/"
BRANDING_START = "<!-- jarvis-branding:begin -->"
BRANDING_END = "<!-- jarvis-branding:end -->"
BRANDING_SCRIPT_NAME = "jarvis-branding-override.js"


@dataclass
class Step:
    name: str
    ok: bool
    level: str
    detail: str
    action: str | None = None
    data: dict[str, Any] | None = None

    def as_dict(self) -> dict[str, Any]:
        out = {
            "name": self.name,
            "ok": self.ok,
            "level": self.level,
            "detail": self.detail,
        }
        if self.action:
            out["action"] = self.action
        if self.data:
            out["data"] = self.data
        return out


def now_label() -> str:
    return time.strftime("%Y%m%d-%H%M%S")


def run(cmd: list[str], timeout: int = 60, dry_run: bool = False) -> dict[str, Any]:
    if dry_run:
        return {"ok": True, "exitCode": 0, "stdout": "", "stderr": "", "cmd": cmd, "dryRun": True}
    try:
        proc = subprocess.run(cmd, cwd=WORKSPACE, capture_output=True, text=True, timeout=timeout, check=False)
        return {
            "ok": proc.returncode == 0,
            "exitCode": proc.returncode,
            "stdout": (proc.stdout or "").strip(),
            "stderr": (proc.stderr or "").strip(),
            "cmd": cmd,
        }
    except subprocess.TimeoutExpired:
        return {"ok": False, "exitCode": -1, "stdout": "", "stderr": f"TIMEOUT({timeout}s)", "cmd": cmd}
    except Exception as exc:
        return {"ok": False, "exitCode": -2, "stdout": "", "stderr": str(exc), "cmd": cmd}


def resolve_package_root() -> Path | None:
    env = os.environ.get("OPENCLAW_PACKAGE_ROOT")
    candidates: list[Path] = []
    if env:
        candidates.append(Path(env).expanduser())
    candidates.append(DEFAULT_PACKAGE_ROOT)
    npm_root = run(["npm", "root", "-g"], timeout=10)
    if npm_root.get("ok") and npm_root.get("stdout"):
        candidates.append(Path(str(npm_root["stdout"]).strip()) / "openclaw")
    for candidate in candidates:
        root = candidate.expanduser().resolve()
        if (root / "dist" / "control-ui").exists():
            return root
    return None


def dist_root(package_root: Path | None) -> Path | None:
    return package_root / "dist" / "control-ui" if package_root else None


def fetch_url(url: str, timeout: int = 8, max_bytes: int = 2_000_000) -> dict[str, Any]:
    try:
        req = urllib.request.Request(url, headers={"Cache-Control": "no-cache", "Pragma": "no-cache"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read(max_bytes)
            return {
                "ok": 200 <= int(resp.status) < 400,
                "status": int(resp.status),
                "contentType": resp.headers.get("content-type", ""),
                "size": len(body),
                "text": body.decode("utf-8", "replace") if body else "",
                "error": None,
            }
    except Exception as exc:
        status = getattr(exc, "code", None)
        return {"ok": False, "status": status, "contentType": "", "size": 0, "text": "", "error": f"{type(exc).__name__}: {exc}"}


def extract_assets(html: str, base_url: str) -> list[str]:
    refs = re.findall(r'(?:src|href)=["\']([^"\']+)["\']', html)
    assets: list[str] = []
    for ref in refs:
        if ref.startswith("http://") or ref.startswith("https://"):
            # 外部文档链接不影响本地 Control UI 启动。
            continue
        if ref.startswith("#") or ref.startswith("data:"):
            continue
        assets.append(urllib.parse.urljoin(base_url, ref))
    return list(dict.fromkeys(assets))


def inspect_index(base_url: str) -> tuple[Step, str, list[str]]:
    res = fetch_url(base_url)
    if not res["ok"]:
        return Step("browser.http.index", False, "L1", f"GET {base_url} failed: {res.get('error') or res.get('status')}", data={"status": res.get("status")}), "", []
    html = res["text"]
    checks = {
        "hasOpenclawApp": "<openclaw-app" in html,
        "hasModuleScript": 'type="module"' in html and "assets/index-" in html,
        "hasMountFallback": "openclaw-mount-fallback" in html,
        "hasBrandingInject": BRANDING_START in html and BRANDING_END in html,
    }
    ok = checks["hasOpenclawApp"] and checks["hasModuleScript"]
    detail = f"HTTP {res['status']} len={res['size']} app={checks['hasOpenclawApp']} module={checks['hasModuleScript']} branding={checks['hasBrandingInject']}"
    return Step("browser.http.index", ok, "L2", detail, data=checks), html, extract_assets(html, base_url)


def inspect_assets(urls: list[str]) -> Step:
    results: list[dict[str, Any]] = []
    bad: list[str] = []
    for url in urls:
        res = fetch_url(url, timeout=8, max_bytes=200_000)
        item = {"url": url, "ok": res["ok"] and res["size"] > 0, "status": res.get("status"), "size": res.get("size"), "contentType": res.get("contentType"), "error": res.get("error")}
        results.append(item)
        if not item["ok"]:
            bad.append(url)
    ok = not bad
    return Step("browser.http.assets", ok, "L2", f"assets {len(urls)-len(bad)}/{len(urls)} ok" + (f"; bad={bad[:3]}" if bad else ""), data={"assets": results[:40]})


def inspect_gateway() -> Step:
    res = run(["openclaw", "gateway", "status"], timeout=35)
    stdout = res.get("stdout", "")
    ok = bool(res.get("ok")) and "Runtime: running" in stdout and "Connectivity probe: ok" in stdout
    runtime = ""
    probe = ""
    for line in stdout.splitlines():
        if line.startswith("Runtime:"):
            runtime = line.strip()
        if line.startswith("Connectivity probe:"):
            probe = line.strip()
    detail = "; ".join(x for x in [runtime, probe] if x) or (res.get("stderr") or stdout[:200])
    return Step("gateway.status", ok, "L1", detail, action="openclaw gateway restart" if not ok else None)


def inspect_dist(package_root: Path | None) -> tuple[Step, Path | None]:
    droot = dist_root(package_root)
    if not droot or not droot.exists():
        return Step("controlui.dist", False, "L2", "Control UI dist directory not found", data={"packageRoot": str(package_root) if package_root else None}), droot
    index = droot / "index.html"
    assets = droot / "assets"
    js_count = len(list(assets.glob("index-*.js"))) if assets.exists() else 0
    css_count = len(list(assets.glob("index-*.css"))) if assets.exists() else 0
    ok = index.exists() and assets.exists() and js_count > 0 and css_count > 0
    return Step("controlui.dist", ok, "L2", f"dist={droot} index={index.exists()} js={js_count} css={css_count}", data={"distRoot": str(droot), "index": str(index)}), droot


def inspect_branding(droot: Path | None) -> Step:
    if not droot:
        return Step("controlui.branding", False, "L3", "no dist root")
    index = droot / "index.html"
    script = droot / BRANDING_SCRIPT_NAME
    html = index.read_text(encoding="utf-8", errors="replace") if index.exists() else ""
    inject = BRANDING_START in html and BRANDING_END in html
    script_exists = script.exists()
    size = script.stat().st_size if script_exists else 0
    script_text = script.read_text(encoding="utf-8", errors="replace") if script_exists and size < 2_000_000 else ""
    key_markers = ["const BRAND", "normalizeFrontstageSnapshot", "connectHealthDockSse"]
    markers_ok = all(marker in script_text for marker in key_markers) if script_text else script_exists and size > 10_000
    ok = inject and script_exists and size > 1000 and markers_ok
    action = "rerun apply-openclaw-control-ui-branding.py" if not ok else None
    return Step("controlui.branding", ok, "L3", f"inject={inject} script={script_exists} size={size} markers={markers_ok}", action=action, data={"script": str(script), "index": str(index)})


def inspect_model_selector(droot: Path | None) -> Step:
    if not droot:
        return Step("controlui.modelSelector", False, "L3", "no dist root")
    assets = droot / "assets"
    candidates = list(assets.glob("index-*.js")) if assets.exists() else []
    hit = False
    resolved_marker = False
    refresh_marker = False
    for path in candidates:
        text = path.read_text(encoding="utf-8", errors="replace")
        if 'data-chat-model-select="true"' in text:
            hit = True
            resolved_marker = "resolved?.modelProvider" in text or "s?.resolved?.modelProvider" in text
            refresh_marker = "refresh-tools-effective" in text
            break
    ok = hit and resolved_marker and refresh_marker
    return Step("controlui.modelSelector", ok, "L3", f"select={hit} resolvedMarker={resolved_marker} refreshTools={refresh_marker}", action="rerun apply-openclaw-session-model-selector-fix.py" if not ok else None)


def inspect_frontstage() -> list[Step]:
    steps: list[Step] = []
    broker_views = Path.home() / ".local" / "state" / "openclaw" / "broker" / "views"
    required = ["snapshot.json", "frontstage.json", "health.json", "tasks.json", "recovery.json", "overview.json"]
    missing = [name for name in required if not (broker_views / name).exists() or (broker_views / name).stat().st_size <= 0]
    steps.append(Step("frontstage.brokerViews", not missing, "L4", "all broker views present" if not missing else f"missing/empty: {missing}", action="rebuild broker views" if missing else None, data={"viewsDir": str(broker_views)}))
    sidecar = fetch_url("http://127.0.0.1:18790/healthz", timeout=5, max_bytes=20_000)
    steps.append(Step("frontstage.sidecar", sidecar["ok"], "L4", f"sidecar healthz status={sidecar.get('status')}" if sidecar["ok"] else f"sidecar failed: {sidecar.get('error')}", action="restart infos-handle sidecar" if not sidecar["ok"] else None))
    proxy = fetch_url("http://127.0.0.1:18788/healthz", timeout=5, max_bytes=20_000)
    steps.append(Step("frontstage.unifiedProxy", proxy["ok"], "L4", f"proxy healthz status={proxy.get('status')}" if proxy["ok"] else f"proxy failed: {proxy.get('error')}", action="restart unified proxy" if not proxy["ok"] else None))
    return steps


def remove_branding_injection(droot: Path, dry_run: bool) -> Step:
    index = droot / "index.html"
    if not index.exists():
        return Step("safeMode.disableBranding", False, "SAFE", "index.html not found")
    html = index.read_text(encoding="utf-8", errors="replace")
    pattern = re.compile(r"\s*" + re.escape(BRANDING_START) + r".*?" + re.escape(BRANDING_END), re.S)
    if not pattern.search(html):
        return Step("safeMode.disableBranding", True, "SAFE", "branding injection already absent")
    backup = index.with_name(f"index.html.bak-control-ui-emergency-{now_label()}")
    script = droot / BRANDING_SCRIPT_NAME
    disabled_script = droot / f"{BRANDING_SCRIPT_NAME}.disabled-{now_label()}"
    if not dry_run:
        shutil.copy2(index, backup)
        index.write_text(pattern.sub("", html, count=1), encoding="utf-8")
        if script.exists() and not disabled_script.exists():
            shutil.copy2(script, disabled_script)
    return Step("safeMode.disableBranding", True, "SAFE", "branding injection removed from index.html" + (" (dry-run)" if dry_run else f"; backup={backup.name}"), data={"backup": str(backup), "disabledScriptCopy": str(disabled_script)})


def perform_repair(steps: list[Step], droot: Path | None, dry_run: bool) -> list[Step]:
    actions: list[Step] = []
    by_name = {step.name: step for step in steps}

    if not by_name.get("gateway.status", Step("", True, "", "")).ok:
        res = run(["openclaw", "gateway", "restart"], timeout=120, dry_run=dry_run)
        actions.append(Step("repair.gatewayRestart", bool(res["ok"]), "REPAIR", "openclaw gateway restart" + (" (dry-run)" if dry_run else ""), data={"exitCode": res.get("exitCode"), "stderr": str(res.get("stderr", ""))[:300]}))

    if any(not by_name.get(name, Step("", True, "", "")).ok for name in ["controlui.branding", "browser.http.assets"]):
        res = run([sys.executable, str(SCRIPTS / "apply-openclaw-control-ui-branding.py")], timeout=120, dry_run=dry_run)
        actions.append(Step("repair.branding", bool(res["ok"]), "REPAIR", "rerun branding patch" + (" (dry-run)" if dry_run else ""), data={"exitCode": res.get("exitCode"), "stderr": str(res.get("stderr", ""))[:300]}))

    if not by_name.get("controlui.modelSelector", Step("", True, "", "")).ok:
        res = run([sys.executable, str(SCRIPTS / "apply-openclaw-session-model-selector-fix.py")], timeout=120, dry_run=dry_run)
        actions.append(Step("repair.modelSelector", bool(res["ok"]), "REPAIR", "rerun model selector patch" + (" (dry-run)" if dry_run else ""), data={"exitCode": res.get("exitCode"), "stderr": str(res.get("stderr", ""))[:300]}))

    if not by_name.get("frontstage.brokerViews", Step("", True, "", "")).ok:
        res = run([sys.executable, str(SCRIPTS / "openclaw-frontstage-broker.py"), "rebuild-views", "--print-json"], timeout=120, dry_run=dry_run)
        actions.append(Step("repair.brokerViews", bool(res["ok"]), "REPAIR", "rebuild broker views" + (" (dry-run)" if dry_run else ""), data={"exitCode": res.get("exitCode"), "stderr": str(res.get("stderr", ""))[:300]}))

    if not by_name.get("frontstage.sidecar", Step("", True, "", "")).ok:
        res = run(["systemctl", "--user", "restart", "openclaw-infos-handle-sidecar.service"], timeout=60, dry_run=dry_run)
        actions.append(Step("repair.sidecarRestart", bool(res["ok"]), "REPAIR", "restart infos-handle sidecar" + (" (dry-run)" if dry_run else ""), data={"exitCode": res.get("exitCode"), "stderr": str(res.get("stderr", ""))[:300]}))

    if not by_name.get("frontstage.unifiedProxy", Step("", True, "", "")).ok:
        res = run([sys.executable, str(SCRIPTS / "apply-openclaw-infos-handle-gateway-proxy.py"), "--install-user-systemd", "--enable", "--restart", "--verify", "--print-json"], timeout=120, dry_run=dry_run)
        actions.append(Step("repair.unifiedProxy", bool(res["ok"]), "REPAIR", "repair unified proxy" + (" (dry-run)" if dry_run else ""), data={"exitCode": res.get("exitCode"), "stderr": str(res.get("stderr", ""))[:300]}))

    return actions


def browser_advice(base_url: str) -> list[str]:
    host = urllib.parse.urlparse(base_url).netloc or "127.0.0.1:18789"
    return [
        f"打开/刷新：{base_url}",
        "先按 Ctrl+F5 / Cmd+Shift+R 强制刷新。",
        "若仍黑屏，用无痕窗口打开，排除缓存和登录态污染。",
        "临时禁用会注入脚本的浏览器扩展，尤其是脚本管理器、广告拦截、翻译/暗色模式插件。",
        f"清理站点数据：浏览器设置里删除 {host} 的缓存、LocalStorage、IndexedDB、Service Worker。",
        "如果出现错误页，打开开发者工具 Console / Network，记录第一条红色 JS 错误和失败资源 URL。",
    ]


def collect(base_url: str) -> tuple[list[Step], Path | None, str, list[str]]:
    package_root = resolve_package_root()
    steps: list[Step] = []
    gateway = inspect_gateway()
    steps.append(gateway)
    dist_step, droot = inspect_dist(package_root)
    steps.append(dist_step)
    index_step, html, assets = inspect_index(base_url)
    steps.append(index_step)
    if assets:
        steps.append(inspect_assets(assets))
    else:
        steps.append(Step("browser.http.assets", False, "L2", "no assets discovered from index.html"))
    steps.append(inspect_branding(droot))
    steps.append(inspect_model_selector(droot))
    steps.extend(inspect_frontstage())
    return steps, droot, html, assets


def print_human(report: dict[str, Any]) -> None:
    icon = "✅" if report["ok"] else "⚠️"
    print(f"{icon} Control UI 应急检查 — {'OK' if report['ok'] else '需要关注'}")
    print(f"地址：{report['baseUrl']}")
    for item in report["steps"]:
        sicon = "✅" if item["ok"] else "❌"
        action = f" ｜建议：{item['action']}" if item.get("action") else ""
        print(f"{sicon} {item['level']:<6} {item['name']:<28} {item['detail']}{action}")
    if report.get("actions"):
        print("\n执行动作：")
        for item in report["actions"]:
            sicon = "✅" if item["ok"] else "❌"
            print(f"{sicon} {item['name']:<28} {item['detail']}")
    print("\n浏览器侧应急步骤：")
    for line in report["browserAdvice"]:
        print(f"- {line}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Control UI 黑屏/打不开应急诊断与低侵入修复")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--check", action="store_true", help="只诊断，不修改（默认）")
    mode.add_argument("--repair", action="store_true", help="低风险自动修复：重打补丁/重建视图/重启相关服务")
    mode.add_argument("--safe-mode", action="store_true", help="安全模式：临时禁用 Control UI 自定义 branding 注入以优先恢复页面")
    parser.add_argument("--dry-run", action="store_true", help="只展示会执行的修复动作，不落盘/不重启")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL, help="Control UI URL，默认 http://127.0.0.1:18789/")
    parser.add_argument("--print-json", action="store_true")
    parser.add_argument("--print-human", action="store_true")
    args = parser.parse_args()

    if not args.check and not args.repair and not args.safe_mode:
        args.check = True

    steps, droot, _html, _assets = collect(args.base_url)
    actions: list[Step] = []

    if args.repair:
        actions.extend(perform_repair(steps, droot, args.dry_run))
        if not args.dry_run:
            # 重新检查一次，让输出反映修复后的状态。
            steps, droot, _html, _assets = collect(args.base_url)
    elif args.safe_mode:
        if droot:
            actions.append(remove_branding_injection(droot, args.dry_run))
        else:
            actions.append(Step("safeMode.disableBranding", False, "SAFE", "no Control UI dist root"))
        if not args.dry_run:
            steps, droot, _html, _assets = collect(args.base_url)

    ok = all(step.ok for step in steps)
    if actions:
        ok = ok and all(step.ok for step in actions)
    report = {
        "ok": ok,
        "mode": "repair" if args.repair else "safe-mode" if args.safe_mode else "check",
        "dryRun": args.dry_run,
        "baseUrl": args.base_url,
        "packageRoot": str(resolve_package_root()) if resolve_package_root() else None,
        "steps": [step.as_dict() for step in steps],
        "actions": [step.as_dict() for step in actions],
        "browserAdvice": browser_advice(args.base_url),
    }

    if args.print_json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print_human(report)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
