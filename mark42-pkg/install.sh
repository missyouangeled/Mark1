#!/usr/bin/env bash
# Mark42 一键安装脚本 (Linux)
# 用法: curl -sSL .../install.sh | bash
#   或: bash install.sh [--user]
set -euo pipefail

# ── 颜色 ──
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

info()  { echo -e "${BLUE}[INFO]${NC} $*"; }
ok()    { echo -e "${GREEN}[OK]${NC} $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC} $*"; }
fail()  { echo -e "${RED}[FAIL]${NC} $*"; exit 1; }

# ── 前置检查 ──
info "检查运行环境..."

[[ "$(uname -s)" == "Linux" ]] || fail "Mark42 仅支持 Linux"
command -v python3 >/dev/null 2>&1 || fail "需要 python3 (>=3.10)"
command -v pip3 >/dev/null 2>&1 || fail "需要 pip3"

PY_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
PY_MAJOR=$(echo "$PY_VERSION" | cut -d. -f1)
PY_MINOR=$(echo "$PY_VERSION" | cut -d. -f2)
[[ "$PY_MAJOR" -ge 3 && "$PY_MINOR" -ge 10 ]] || fail "需要 Python >= 3.10，当前 $PY_VERSION"

# 检查 OpenClaw
OPENCLAW_BIN=""
if command -v openclaw >/dev/null 2>&1; then
    OPENCLAW_BIN="$(command -v openclaw)"
elif [[ -x "$HOME/.npm-global/bin/openclaw" ]]; then
    OPENCLAW_BIN="$HOME/.npm-global/bin/openclaw"
else
    warn "未找到 openclaw CLI，Mark42 需要 OpenClaw 才能完整运行"
    warn "请先安装 OpenClaw: https://docs.openclaw.ai"
    read -p "是否继续安装 Mark42？(y/N) " -n 1 -r
    echo
    [[ $REPLY =~ ^[Yy]$ ]] || exit 0
fi

# 检查 systemd
if ! command -v systemctl >/dev/null 2>&1; then
    warn "未检测到 systemctl，systemd 服务将不可用"
    HAS_SYSTEMD=0
else
    HAS_SYSTEMD=1
fi

# ── 安装 Mark42 ──
info "安装 Mark42..."

# 确定安装方式
if [[ "$EUID" -eq 0 ]]; then
    PIP_INSTALL="pip3 install ."
    SYSTEMD_USER="--system"
    SYSTEMD_DIR="/etc/systemd/system"
else
    PIP_INSTALL="pip3 install --user ."
    SYSTEMD_USER="--user"
    SYSTEMD_DIR="$HOME/.config/systemd/user"
fi

# 执行 pip 安装
info "执行 pip install..."
( cd "$(dirname "$0")" && eval "$PIP_INSTALL" ) || fail "pip install 失败"

# 找到安装后的 mark42 命令
MARK42_BIN=""
if command -v mark42 >/dev/null 2>&1; then
    MARK42_BIN="$(command -v mark42)"
elif [[ -x "$HOME/.local/bin/mark42" ]]; then
    MARK42_BIN="$HOME/.local/bin/mark42"
fi

[[ -n "$MARK42_BIN" ]] || fail "mark42 命令未找到，请检查 pip 安装路径是否在 PATH 中"

ok "Mark42 已安装: $MARK42_BIN"
$MARK42_BIN --version 2>/dev/null || true

# ── 渲染 systemd 服务 ──
if [[ "$HAS_SYSTEMD" -eq 1 ]]; then
    info "配置 systemd 服务..."

    mkdir -p "$SYSTEMD_DIR"

    # 路径变量
    PYTHON_BIN="$(command -v python3)"
    WORKSPACE="${MARK42_WORKSPACE:-$HOME/.openclaw/workspace}"
    XDG_STATE="${XDG_STATE_HOME:-$HOME/.local/state}"
    STATE_DIR="$XDG_STATE/openclaw/mark42"
    LOG_DIR="$STATE_DIR/logs"
    SCRATCH="${MARK42_SCRATCH:-/mnt/data/openclaw/scratch}"

    # 如果 /mnt/data 不存在，回退到 XDG
    if [[ ! -d "/mnt/data" ]]; then
        SCRATCH="$XDG_STATE/openclaw/scratch"
    fi

    mkdir -p "$LOG_DIR" "$SCRATCH"

    # 找 systemd 模板目录
    PKG_DIR="$(python3 -c "import mark42; import pathlib; print(pathlib.Path(mark42.__file__).parent / 'systemd')" 2>/dev/null)"
    if [[ -z "$PKG_DIR" || ! -d "$PKG_DIR" ]]; then
        # 回退：从脚本所在目录找
        SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
        PKG_DIR="$SCRIPT_DIR/mark42/systemd"
    fi

    [[ -d "$PKG_DIR" ]] || fail "找不到 systemd 模板目录: $PKG_DIR"

    # 渲染模板
    for tmpl in "$PKG_DIR"/*.service.tmpl; do
        [[ -f "$tmpl" ]] || continue
        svc_name="$(basename "$tmpl" .tmpl)"  # e.g. mark42-armor-guard.service
        target="$SYSTEMD_DIR/$svc_name"
        info "渲染 $svc_name -> $target"

        sed \
            -e "s|__MARK42_BIN__|$MARK42_BIN|g" \
            -e "s|__MARK42_PYTHON__|$PYTHON_BIN|g" \
            -e "s|__MARK42_WORKSPACE__|$WORKSPACE|g" \
            -e "s|__MARK42_XDG_STATE__|$XDG_STATE|g" \
            -e "s|__MARK42_STATE_DIR__|$STATE_DIR|g" \
            -e "s|__MARK42_LOG_DIR__|$LOG_DIR|g" \
            -e "s|__MARK42_SCRATCH__|$SCRATCH|g" \
            "$tmpl" > "$target"

        ok "  -> $svc_name"
    done

    # watchdog timer（非模板，直接复制）
    if [[ -f "$PKG_DIR/mark42-watchdog.timer" ]]; then
        cp "$PKG_DIR/mark42-watchdog.timer" "$SYSTEMD_DIR/mark42-watchdog.timer"
        ok "  -> mark42-watchdog.timer"
    fi

    # reload + enable
    if [[ "$SYSTEMD_USER" == "--user" ]]; then
        systemctl --user daemon-reload
        systemctl --user enable mark42-bootstrap.service mark42-armor-guard.service mark42-engine-daemon.service 2>/dev/null || true
        ok "systemd 用户服务已启用"
        echo
        info "启动服务:"
        echo "  systemctl --user start mark42-bootstrap"
        echo "  systemctl --user start mark42-armor-guard"
        echo "  systemctl --user start mark42-engine-daemon"
    else
        systemctl daemon-reload
        systemctl enable mark42-bootstrap.service mark42-armor-guard.service mark42-engine-daemon.service 2>/dev/null || true
        ok "systemd 系统服务已启用"
        echo
        info "启动服务:"
        echo "  systemctl start mark42-bootstrap"
        echo "  systemctl start mark42-armor-guard"
        echo "  systemctl start mark42-engine-daemon"
    fi
fi

echo
ok "Mark42 安装完成！"
echo
info "快速验证:"
echo "  mark42 status"
echo "  mark42 armor --check"
echo
info "配置文件:"
echo "  OpenClaw: $HOME/.openclaw/openclaw.json"
echo "  Mark42:   $HOME/.local/state/openclaw/mark42/config.json"
