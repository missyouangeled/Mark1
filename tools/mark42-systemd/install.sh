#!/usr/bin/env bash
# Mark42 user-systemd installer
# 用途：把 repo 内 4 个 service 模板渲染到 ~/.config/systemd/user/，并安装 watchdog timer。
# 默认 dry-run；传 --apply 才真正写入并执行 daemon-reload / enable。

set -euo pipefail

usage() {
  cat <<'EOF'
用法：
  tools/mark42-systemd/install.sh [--apply] [--workspace PATH] [--python PATH] [--state-dir PATH] [--scratch PATH] [--user-unit-dir PATH]

默认行为：dry-run，只打印将要渲染/写入的目标，不修改 systemd。
加 --apply：真正写入 ~/.config/systemd/user/ 并执行 daemon-reload。

建议顺序：
  1. tools/mark42-systemd/preflight.sh
  2. tools/mark42-systemd/install.sh
  3. tools/mark42-systemd/install.sh --apply
  4. 如需恢复旧 unit：tools/mark42-systemd/restore.sh --backup-dir <备份目录>
  5. 安装后验收：tools/mark42-systemd/verify.sh

可选参数：
  --workspace PATH      Mark42 工作区根目录（默认：脚本自动推断）
  --python PATH         Python 可执行文件（默认：python3）
  --state-dir PATH      Mark42 状态目录（默认：$XDG_STATE_HOME/openclaw/mark42）
  --scratch PATH        OpenClaw scratch 根目录（默认：/mnt/data/openclaw/scratch）
  --user-unit-dir PATH  user systemd 单元目录（默认：$HOME/.config/systemd/user）
  --apply               真正写入并安装
  --help                显示帮助
EOF
}

APPLY=0
WORKSPACE=""
PYTHON_BIN="python3"
STATE_DIR=""
SCRATCH_ROOT="/mnt/data/openclaw/scratch"
USER_UNIT_DIR="${HOME}/.config/systemd/user"

while [ "$#" -gt 0 ]; do
  case "$1" in
    --apply)
      APPLY=1
      shift
      ;;
    --workspace)
      WORKSPACE="$2"
      shift 2
      ;;
    --python)
      PYTHON_BIN="$2"
      shift 2
      ;;
    --state-dir)
      STATE_DIR="$2"
      shift 2
      ;;
    --scratch)
      SCRATCH_ROOT="$2"
      shift 2
      ;;
    --user-unit-dir)
      USER_UNIT_DIR="$2"
      shift 2
      ;;
    --help|-h)
      usage
      exit 0
      ;;
    *)
      echo "未知参数: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [ -z "$WORKSPACE" ]; then
  WORKSPACE="$(cd "$SCRIPT_DIR/../.." && pwd)"
fi

if [ -z "$STATE_DIR" ]; then
  XDG_STATE_HOME="${XDG_STATE_HOME:-$HOME/.local/state}"
  STATE_DIR="$XDG_STATE_HOME/openclaw/mark42"
else
  XDG_STATE_HOME="$(dirname "$(dirname "$STATE_DIR")")"
fi

MARK42_CLI="$WORKSPACE/scripts/mark42.py"
LOG_DIR="$STATE_DIR/logs"
BOOTSTRAP_SERVICE_SRC="$WORKSPACE/tools/mark42-bootstrap/mark42-bootstrap.service"
ARMOR_SERVICE_SRC="$WORKSPACE/tools/mark42-armor-guard/mark42-armor-guard.service"
ENGINE_SERVICE_SRC="$WORKSPACE/tools/mark42-engine-daemon/mark42-engine-daemon.service"
WATCHDOG_SERVICE_SRC="$WORKSPACE/tools/mark42-watchdog/mark42-watchdog.service"
WATCHDOG_TIMER_SRC="$WORKSPACE/tools/mark42-watchdog/mark42-watchdog.timer"
UNIT_FILES=(
  "mark42-bootstrap.service"
  "mark42-engine-daemon.service"
  "mark42-armor-guard.service"
  "mark42-watchdog.service"
  "mark42-watchdog.timer"
)

need_cmd() {
  command -v "$1" >/dev/null 2>&1 || {
    echo "缺少命令: $1" >&2
    exit 1
  }
}

need_file() {
  [ -f "$1" ] || {
    echo "缺少文件: $1" >&2
    exit 1
  }
}

need_cmd "$PYTHON_BIN"
need_cmd systemctl
need_cmd sed
need_cmd install
need_file "$MARK42_CLI"
need_file "$BOOTSTRAP_SERVICE_SRC"
need_file "$ARMOR_SERVICE_SRC"
need_file "$ENGINE_SERVICE_SRC"
need_file "$WATCHDOG_SERVICE_SRC"
need_file "$WATCHDOG_TIMER_SRC"

if ! command -v openclaw >/dev/null 2>&1; then
  echo "警告：未找到 openclaw 命令；install.sh 仍可渲染 unit，但运行前需补齐 openclaw。" >&2
fi

if ! systemctl --user status openclaw-gateway.service >/dev/null 2>&1; then
  echo "提示：当前未确认 openclaw-gateway.service 处于 active；安装可以继续，但启用后是否正常依赖运行需你再验。" >&2
fi

render_template() {
  local src="$1"
  local dest="$2"
  sed \
    -e "s#__MARK42_WORKSPACE__#$WORKSPACE#g" \
    -e "s#__MARK42_CLI__#$MARK42_CLI#g" \
    -e "s#__MARK42_PYTHON__#$PYTHON_BIN#g" \
    -e "s#__XDG_STATE_HOME__#$XDG_STATE_HOME#g" \
    -e "s#__MARK42_STATE_DIR__#$STATE_DIR#g" \
    -e "s#__MARK42_LOG_DIR__#$LOG_DIR#g" \
    -e "s#__MARK42_OPENCLAW_SCRATCH_ROOT__#$SCRATCH_ROOT#g" \
    "$src" > "$dest"
}

TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT

render_template "$BOOTSTRAP_SERVICE_SRC" "$TMP_DIR/mark42-bootstrap.service"
render_template "$ARMOR_SERVICE_SRC" "$TMP_DIR/mark42-armor-guard.service"
render_template "$ENGINE_SERVICE_SRC" "$TMP_DIR/mark42-engine-daemon.service"
render_template "$WATCHDOG_SERVICE_SRC" "$TMP_DIR/mark42-watchdog.service"
cp "$WATCHDOG_TIMER_SRC" "$TMP_DIR/mark42-watchdog.timer"

printf '== Mark42 install preview ==\n'
printf 'workspace      : %s\n' "$WORKSPACE"
printf 'python         : %s\n' "$PYTHON_BIN"
printf 'state_dir      : %s\n' "$STATE_DIR"
printf 'log_dir        : %s\n' "$LOG_DIR"
printf 'scratch_root   : %s\n' "$SCRATCH_ROOT"
printf 'user_unit_dir  : %s\n' "$USER_UNIT_DIR"
printf 'mode           : %s\n' "$( [ "$APPLY" -eq 1 ] && echo apply || echo dry-run )"
printf '\n渲染结果：\n'
for f in "$TMP_DIR"/*; do
  echo "----- $(basename "$f") -----"
  sed -n '1,80p' "$f"
  echo
Done_loop_marker=1
done
unset Done_loop_marker

if [ "$APPLY" -ne 1 ]; then
  echo "建议先执行：tools/mark42-systemd/preflight.sh"
  echo "dry-run 完成。加 --apply 才会真正写入 $USER_UNIT_DIR 并执行 systemctl --user daemon-reload。"
  exit 0
fi

echo "应用 Mark42 context safety 基线..."
"$PYTHON_BIN" "$MARK42_CLI" context-safety apply

install -d "$USER_UNIT_DIR" "$STATE_DIR" "$LOG_DIR" "$SCRATCH_ROOT" "$STATE_DIR/engine"
BACKUP_DIR=""
BACKUP_COUNT=0

for unit in "${UNIT_FILES[@]}"; do
  if [ -f "$USER_UNIT_DIR/$unit" ]; then
    if [ -z "$BACKUP_DIR" ]; then
      BACKUP_DIR="$USER_UNIT_DIR/mark42-backup-$(date +%Y%m%d-%H%M%S)"
      install -d "$BACKUP_DIR"
    fi
    install -m 0644 "$USER_UNIT_DIR/$unit" "$BACKUP_DIR/$unit"
    BACKUP_COUNT=$((BACKUP_COUNT + 1))
  fi
done

install -m 0644 "$TMP_DIR/mark42-bootstrap.service" "$USER_UNIT_DIR/mark42-bootstrap.service"
install -m 0644 "$TMP_DIR/mark42-armor-guard.service" "$USER_UNIT_DIR/mark42-armor-guard.service"
install -m 0644 "$TMP_DIR/mark42-engine-daemon.service" "$USER_UNIT_DIR/mark42-engine-daemon.service"
install -m 0644 "$TMP_DIR/mark42-watchdog.service" "$USER_UNIT_DIR/mark42-watchdog.service"
install -m 0644 "$TMP_DIR/mark42-watchdog.timer" "$USER_UNIT_DIR/mark42-watchdog.timer"

systemctl --user daemon-reload
systemctl --user enable mark42-watchdog.timer >/dev/null

echo "已写入: $USER_UNIT_DIR"
if [ "$BACKUP_COUNT" -gt 0 ]; then
  echo "已备份旧 unit: $BACKUP_DIR （共 $BACKUP_COUNT 个）"
  echo "如需恢复，可执行："
  echo "  tools/mark42-systemd/restore.sh --backup-dir $BACKUP_DIR"
else
  echo "未发现旧的 Mark42 unit；本次未生成备份目录。"
fi
echo "下一步建议："
echo "  tools/mark42-systemd/verify.sh"
echo "  systemctl --user start mark42-bootstrap.service"
echo "  systemctl --user start mark42-engine-daemon.service"
echo "  systemctl --user start mark42-armor-guard.service"
echo "  systemctl --user enable --now mark42-watchdog.timer"
echo "  systemctl --user status mark42-bootstrap.service mark42-engine-daemon.service mark42-armor-guard.service mark42-watchdog.timer"
