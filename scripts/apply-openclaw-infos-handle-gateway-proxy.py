#!/usr/bin/env python3
# 适用机器：公司（Linux）
# 系统 / OS：Linux
# 用途：安装/重载/验证 infos-handle 统一入口代理（Caddy），并可在 HTTP / HTTPS（域名）配置之间切换。

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[1]
PROXY_DIR = WORKSPACE / "tools" / "openclaw-infos-handle-gateway-proxy"
CADDYFILE_PATH = PROXY_DIR / "Caddyfile"
SERVICE_TEMPLATE_PATH = PROXY_DIR / "openclaw-unified-proxy.service"
USER_SYSTEMD_DIR = Path.home() / ".config" / "systemd" / "user"
USER_SERVICE_PATH = USER_SYSTEMD_DIR / "openclaw-unified-proxy.service"
GATEWAY_CONFIG_PATH = Path.home() / ".openclaw" / "openclaw.json"
DEFAULT_HTTP_PORT = 18788
DEFAULT_GATEWAY_PORT = 18789
DEFAULT_SIDECAR_PORT = 18790


def run(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=WORKSPACE, capture_output=True, text=True, check=False)


def load_gateway_token() -> str | None:
    try:
        raw = GATEWAY_CONFIG_PATH.read_text(encoding="utf-8")
        try:
            import json5  # type: ignore
            config = json5.loads(raw)
        except Exception:
            config = json.loads(raw)
    except Exception:
        return None
    if not isinstance(config, dict):
        return None
    gateway = config.get("gateway") if isinstance(config.get("gateway"), dict) else {}
    auth = gateway.get("auth") if isinstance(gateway.get("auth"), dict) else {}
    token = auth.get("token") or auth.get("password")
    return str(token) if isinstance(token, str) and token.strip() else None


def build_proxy_routes(sidecar_port: int, gateway_port: int, *, commented: bool = False) -> str:
    prefix = "# " if commented else ""
    indent = "# \t" if commented else "\t"
    return "\n".join(
        [
            f"{prefix}\t# infos-handle API → sidecar",
            f"{prefix}\thandle /v1/query/* {{",
            f"{indent}reverse_proxy 127.0.0.1:{sidecar_port} {{",
            f"{indent}\theader_up X-Real-IP {{remote_host}}",
            f"{indent}}}",
            f"{prefix}\t}}",
            f"{prefix}\thandle /v1/handle* {{",
            f"{indent}reverse_proxy 127.0.0.1:{sidecar_port} {{",
            f"{indent}\theader_up X-Real-IP {{remote_host}}",
            f"{indent}}}",
            f"{prefix}\t}}",
            f"{prefix}\thandle /v1/artifacts/* {{",
            f"{indent}reverse_proxy 127.0.0.1:{sidecar_port} {{",
            f"{indent}\theader_up X-Real-IP {{remote_host}}",
            f"{indent}}}",
            f"{prefix}\t}}",
            f"{prefix}\thandle /v1/events/* {{",
            f"{indent}reverse_proxy 127.0.0.1:{sidecar_port} {{",
            f"{indent}\theader_up X-Real-IP {{remote_host}}",
            f"{indent}}}",
            f"{prefix}\t}}",
            f"{prefix}\thandle /healthz* {{",
            f"{indent}reverse_proxy 127.0.0.1:{sidecar_port} {{",
            f"{indent}\theader_up X-Real-IP {{remote_host}}",
            f"{indent}}}",
            f"{prefix}\t}}",
            f"{prefix}",
            f"{prefix}\t# 其余 → Gateway",
            f"{prefix}\thandle {{ reverse_proxy 127.0.0.1:{gateway_port} }}",
        ]
    )


def build_caddyfile(*, mode: str, http_port: int, gateway_port: int, sidecar_port: int, domain: str | None, email: str | None) -> str:
    email_line = f"\temail {email}\n" if email else "\t# email your-email@example.com\n"
    http_block = f"""http://:{http_port} {{
\t# CORS 头（给跨域 consumer 用）
\t@cors_preflight method OPTIONS
\thandle @cors_preflight {{
\t\theader {{
\t\t\tAccess-Control-Allow-Origin *
\t\t\tAccess-Control-Allow-Methods \"GET, POST, OPTIONS\"
\t\t\tAccess-Control-Allow-Headers \"Authorization, Content-Type\"
\t\t\tAccess-Control-Max-Age \"86400\"
\t\t}}
\t\trespond 204
\t}}

\t# CORS 普通请求也加
\theader {{
\t\tAccess-Control-Allow-Origin *
\t\tAccess-Control-Allow-Methods \"GET, POST, OPTIONS\"
\t\tAccess-Control-Allow-Headers \"Authorization, Content-Type\"
\t}}

{build_proxy_routes(sidecar_port, gateway_port)}
}}
"""
    https_domain = domain or "your-domain.com"
    https_block = f"""{https_domain} {{
\t# CORS 头
\t@cors_preflight method OPTIONS
\thandle @cors_preflight {{
\t\theader {{
\t\t\tAccess-Control-Allow-Origin *
\t\t\tAccess-Control-Allow-Methods \"GET, POST, OPTIONS\"
\t\t\tAccess-Control-Allow-Headers \"Authorization, Content-Type\"
\t\t\tAccess-Control-Max-Age \"86400\"
\t\t}}
\t\trespond 204
\t}}
\theader {{
\t\tAccess-Control-Allow-Origin *
\t\tAccess-Control-Allow-Methods \"GET, POST, OPTIONS\"
\t\tAccess-Control-Allow-Headers \"Authorization, Content-Type\"
\t}}

{build_proxy_routes(sidecar_port, gateway_port)}
}}
"""
    commented_https = build_proxy_routes(sidecar_port, gateway_port, commented=True)
    if mode == "https" and not domain:
        raise ValueError("--mode https requires --domain")
    if mode == "https":
        active_block = https_block
        inactive_label = f"# HTTP 入口示例（若要回退到纯 HTTP，可改回下面这块并删除上面的域名块）\n#\n" + "\n".join(f"# {line}" if line else "#" for line in http_block.splitlines())
    else:
        active_block = http_block
        inactive_label = f"# ========== 公网 TLS 配置（填域名后可切到 HTTPS） =========="
        commented_https_block = "\n".join(f"# {line}" if line else "#" for line in https_block.replace(https_domain, "your-domain.com").splitlines())
        inactive_label = inactive_label + "\n" + commented_https_block
    return f"""# Caddyfile — OpenClaw unified Gateway + infos-handle reverse proxy
# 适用机器：公司（Linux）
# 系统 / OS：Linux
# 用途：单端口统一入口，把 Gateway ({gateway_port}) 和 infos-handle sidecar ({sidecar_port}) 合并到一个入口

# 当前模式：{mode}
# - http: 仅本地 / LAN 使用
# - https: 绑定域名，自动申请 Let's Encrypt 证书

{{
{email_line}}}

{active_block}

{inactive_label}
"""


def write_caddyfile(*, mode: str, http_port: int, gateway_port: int, sidecar_port: int, domain: str | None, email: str | None) -> None:
    content = build_caddyfile(
        mode=mode,
        http_port=http_port,
        gateway_port=gateway_port,
        sidecar_port=sidecar_port,
        domain=domain,
        email=email,
    )
    CADDYFILE_PATH.write_text(content, encoding="utf-8")
    run(["/usr/local/bin/caddy", "fmt", "--overwrite", str(CADDYFILE_PATH)])


def install_user_systemd() -> None:
    USER_SYSTEMD_DIR.mkdir(parents=True, exist_ok=True)
    shutil.copy2(SERVICE_TEMPLATE_PATH, USER_SERVICE_PATH)
    result = run(["systemctl", "--user", "daemon-reload"])
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "systemctl --user daemon-reload failed")


def systemctl_user(*args: str) -> None:
    result = run(["systemctl", "--user", *args])
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or f"systemctl --user {' '.join(args)} failed")


def reload_caddy() -> None:
    result = run(["/usr/local/bin/caddy", "reload", "--config", str(CADDYFILE_PATH)])
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "caddy reload failed")


def fetch_json(url: str, *, headers: dict[str, str] | None = None) -> dict[str, object]:
    request = urllib.request.Request(url, headers=headers or {})
    with urllib.request.urlopen(request, timeout=8) as response:
        return json.loads(response.read().decode("utf-8"))


def fetch_status(url: str, *, headers: dict[str, str] | None = None) -> tuple[int, dict[str, str], str]:
    request = urllib.request.Request(url, headers=headers or {})
    try:
        with urllib.request.urlopen(request, timeout=8) as response:
            return response.getcode(), dict(response.headers.items()), response.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        return exc.code, dict(exc.headers.items()), exc.read().decode("utf-8", errors="replace")


def detect_lan_ip() -> str | None:
    result = run(["hostname", "-I"])
    if result.returncode != 0:
        return None
    for part in result.stdout.split():
        if "." in part:
            return part.strip()
    return None


def verify_proxy(*, mode: str, http_port: int) -> dict[str, object]:
    token = load_gateway_token()
    if not token:
        raise RuntimeError("unable to load gateway token from ~/.openclaw/openclaw.json")
    local_health = fetch_json(f"http://127.0.0.1:{http_port}/healthz")
    local_summary_code, _, local_summary = fetch_status(f"http://127.0.0.1:{http_port}/v1/query/snapshot.summary?format=text")
    lan_ip = detect_lan_ip()
    remote_no_auth_code = None
    remote_with_auth_code = None
    if lan_ip and mode == "http":
        remote_no_auth_code, _, _ = fetch_status(f"http://{lan_ip}:{http_port}/v1/query/snapshot.summary?format=text")
        remote_with_auth_code, _, _ = fetch_status(
            f"http://{lan_ip}:{http_port}/v1/query/snapshot.summary?format=text",
            headers={"Authorization": f"Bearer {token}"},
        )
    return {
        "ok": True,
        "configPath": str(CADDYFILE_PATH),
        "mode": mode,
        "port": http_port,
        "localHealthzOk": local_health.get("ok") is True,
        "localSummaryCode": local_summary_code,
        "localSummaryPreview": local_summary[:120],
        "lanIp": lan_ip,
        "remoteNoAuthCode": remote_no_auth_code,
        "remoteWithAuthCode": remote_with_auth_code,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Install / reload / verify infos-handle unified proxy")
    parser.add_argument("--mode", choices=["http", "https"], default="http", help="Render proxy in HTTP or HTTPS mode")
    parser.add_argument("--domain", help="HTTPS domain (required when --mode https)")
    parser.add_argument("--email", help="Email for Caddy/Let's Encrypt")
    parser.add_argument("--http-port", type=int, default=DEFAULT_HTTP_PORT)
    parser.add_argument("--gateway-port", type=int, default=DEFAULT_GATEWAY_PORT)
    parser.add_argument("--sidecar-port", type=int, default=DEFAULT_SIDECAR_PORT)
    parser.add_argument("--install-user-systemd", action="store_true")
    parser.add_argument("--enable", action="store_true", help="Enable and start the user service")
    parser.add_argument("--restart", action="store_true", help="Restart the user service after writing config")
    parser.add_argument("--reload", action="store_true", help="Reload Caddy config via admin API")
    parser.add_argument("--verify", action="store_true")
    parser.add_argument("--print-json", action="store_true")
    args = parser.parse_args()

    write_caddyfile(
        mode=args.mode,
        http_port=args.http_port,
        gateway_port=args.gateway_port,
        sidecar_port=args.sidecar_port,
        domain=args.domain,
        email=args.email,
    )

    if args.install_user_systemd:
        install_user_systemd()
    if args.enable:
        systemctl_user("enable", "--now", USER_SERVICE_PATH.name)
    if args.restart:
        systemctl_user("restart", USER_SERVICE_PATH.name)
    if args.reload:
        reload_caddy()

    payload: dict[str, object] = {
        "ok": True,
        "mode": args.mode,
        "configPath": str(CADDYFILE_PATH),
        "serviceTemplate": str(SERVICE_TEMPLATE_PATH),
        "userService": str(USER_SERVICE_PATH),
    }
    if args.verify:
        payload["verify"] = verify_proxy(mode=args.mode, http_port=args.http_port)

    if args.print_json or args.verify:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(json.dumps(payload, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
