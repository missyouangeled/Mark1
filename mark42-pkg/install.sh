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

# 确定安装方式：优先 pipx，回退 venv
if [[ "$EUID" -eq 0 ]]; then
    SYSTEMD_USER="--system"
    SYSTEMD_DIR="/etc/systemd/system"
else
    SYSTEMD_USER="--user"
    SYSTEMD_DIR="$HOME/.config/systemd/user"
fi

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
MARK42_BIN=""

if command -v pipx >/dev/null 2>&1; then
    # pipx 方式
    info "使用 pipx 安装..."
    pipx install --force "$SCRIPT_DIR" || fail "pipx install 失败"
    MARK42_BIN="$(command -v mark42 2>/dev/null || echo "$HOME/.local/bin/mark42")"
elif [[ -x "$HOME/.local/bin/mark42" ]] && mark42 --version >/dev/null 2>&1; then
    # 已安装，跳过
    info "检测到已安装的 mark42，跳过安装步骤"
    MARK42_BIN="$(command -v mark42)"
else
    # venv 方式：先构建 wheel，再从 wheel 安装（可复现）
    VENV_DIR="$HOME/.local/share/mark42-venv"
    info "创建虚拟环境: $VENV_DIR"
    python3 -m venv "$VENV_DIR" || fail "创建 venv 失败"
    info "构建 wheel..."
    "$VENV_DIR/bin/pip" install --upgrade pip setuptools wheel >/dev/null 2>&1 || true
    WHEELHOUSE="$VENV_DIR/wheelhouse"
    "$VENV_DIR/bin/pip" wheel --no-deps -w "$WHEELHOUSE" "$SCRIPT_DIR" || fail "wheel 构建失败"
    info "安装 mark42 (from wheel)..."
    "$VENV_DIR/bin/pip" install "$WHEELHOUSE"/*.whl || fail "pip install 失败"

    # 创建 symlink 到 ~/.local/bin
    mkdir -p "$HOME/.local/bin"
    ln -sf "$VENV_DIR/bin/mark42" "$HOME/.local/bin/mark42"
    MARK42_BIN="$HOME/.local/bin/mark42"
fi

[[ -n "$MARK42_BIN" ]] || fail "mark42 命令未找到"

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

# ── ArcLock 配置初始化 ──
info "初始化 ArcLock 配置..."
ARCLOCK_FILE="$STATE_DIR/arclock.yaml"
if [[ ! -f "$ARCLOCK_FILE" ]]; then
    # 从包内模板复制
    TMPL_DIR="$(python3 -c "import mark42; import pathlib; print(pathlib.Path(mark42.__file__).parent / 'templates')" 2>/dev/null)"
    if [[ -z "$TMPL_DIR" || ! -d "$TMPL_DIR" ]]; then
        SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
        TMPL_DIR="$SCRIPT_DIR/mark42/templates"
    fi
    if [[ -f "$TMPL_DIR/arclock.yaml.tmpl" ]]; then
        cp "$TMPL_DIR/arclock.yaml.tmpl" "$ARCLOCK_FILE"
        ok "ArcLock 配置已初始化: $ARCLOCK_FILE"
    else
        # 创建空配置
        echo "# ArcLock 配置 - 不配则使用默认实现" > "$ARCLOCK_FILE"
        echo "arclock: {}" >> "$ARCLOCK_FILE"
        ok "ArcLock 配置已创建（默认）: $ARCLOCK_FILE"
    fi
else
    ok "ArcLock 配置已存在: $ARCLOCK_FILE"
fi

# ── 调用 mark42 --init ──
info "初始化 Mark42 配置..."
$MARK42_BIN --init 2>/dev/null || true
ok "配置初始化完成"

# ── 配置向导 ──
echo
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}  Mark42 安装完成！接下来：${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo
echo -e "${YELLOW}1. 配置模型路由${NC}"
echo "   编辑 OpenClaw 配置:"
echo "   $HOME/.openclaw/openclaw.json"
echo "   在 models.providers 中配置你的 AI 模型供应商："
echo "   - volcengine-agent (火山方舟, 推荐)"
echo "   - litellm (Agnes AI)"
echo "   - ollama (本地模型)"
echo "   - nvidia (NVIDIA API)"
echo
echo -e "${YELLOW}2. 配置 Mark42 阈值${NC}"
echo "   运行初始化命令:"
echo "   $MARK42_BIN --init"
echo "   然后编辑配置文件:"
echo "   $HOME/.config/mark42/config.toml"
echo "   关键配置项:"
echo "   - armor.warn_threshold  (默认 70%)"
echo "   - armor.alert_threshold (默认 85%)"
echo "   - armor.crit_threshold  (默认 95%)"
echo
echo -e "${YELLOW}3. ArcLock 电磁锁扣（可选）${NC}"
echo "   默认零配置即可使用，如需自定义实现:"
echo "   编辑: $ARCLOCK_FILE"
echo "   可替换的锁扣:"
echo "   - compress / memory / consciousness / archive"
echo "   - breaker / health / engine / chaos / heavy"
echo "   详见: docs/CONFIG-GUIDE.md"
echo
echo -e "${YELLOW}4. 启动服务${NC}"
echo "   一键启动完整战甲:"
echo "   $MARK42_BIN assemble"
echo
echo -e "${YELLOW}5. 验证安装${NC}"
echo "   查看系统状态:"
echo "   $MARK42_BIN status"
echo "   检查上下文健康:"
echo "   $MARK42_BIN armor --check"
echo "   查看 Prometheus 指标:"
echo "   $MARK42_BIN status --metrics"
echo
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo

# ── 自动验证 ──
info "运行安装验证..."
if $MARK42_BIN status >/dev/null 2>&1; then
    ok "✅ Mark42 安装验证通过"
else
    warn "⚠️ Mark42 status 未通过，可能是 OpenClaw 未启动"
    warn "   请先启动 OpenClaw: openclaw gateway restart"
    warn "   然后重新验证: $MARK42_BIN status"
fi

info "配置文件:"
echo "  OpenClaw: $HOME/.openclaw/openclaw.json"
echo "  Mark42:   $HOME/.config/mark42/config.toml"
echo "  ArcLock:  $ARCLOCK_FILE"
