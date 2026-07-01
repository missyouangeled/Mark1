#!/usr/bin/env bash
# Mark42 user-systemd uninstaller
# 用途：把 README/QuickStart 里的 user systemd 卸载步骤脚本化。

set -euo pipefail

usage() {
  cat <<'EOF'
用法：
  tools/mark42-systemd/uninstall.sh [--apply] [--user-unit-dir PATH]

默认行为：dry-run，只预览将要 stop / disable / remove 的 unit，不真正删除。
加 --apply：真正停止并移除 Mark42 的 user systemd unit。

可选参数：
  --user-unit-dir PATH  user systemd 单元目录（默认：$HOME/.config/systemd/user）
  --apply               真正执行卸载
  --help                显示帮助

说明：
  - 本脚本默认只卸载 user systemd unit
  - 不删除 workspace 代码
  - 不删除 ~/.local/state/openclaw/mark42/
  - 不删除 /mnt/data/openclaw/scratch
EOF
}

APPLY=0
USER_UNIT_DIR="${HOME}/.config/systemd/user"

while [ "$#" -gt 0 ]; do
  case "$1" in
    --apply)
      APPLY=1
      shift
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

UNIT_FILES=(
  "mark42-bootstrap.service"
  "mark42-engine-daemon.service"
  "mark42-armor-guard.service"
  "mark42-watchdog.service"
  "mark42-watchdog.timer"
)

printf '== Mark42 uninstall preview ==\n'
printf 'user_unit_dir  : %s\n' "$USER_UNIT_DIR"
printf 'mode           : %s\n' "$( [ "$APPLY" -eq 1 ] && echo apply || echo dry-run )"
printf '\n目标 unit：\n'
for unit in "${UNIT_FILES[@]}"; do
  printf '  - %s\n' "$USER_UNIT_DIR/$unit"
done
printf '\n将执行：\n'
printf '  systemctl --user disable --now mark42-watchdog.timer\n'
printf '  systemctl --user stop mark42-engine-daemon.service mark42-armor-guard.service mark42-bootstrap.service\n'
printf '  rm -f %s/{mark42-bootstrap.service,mark42-engine-daemon.service,mark42-armor-guard.service,mark42-watchdog.service,mark42-watchdog.timer}\n' "$USER_UNIT_DIR"
printf '  systemctl --user daemon-reload\n'
printf '  systemctl --user reset-failed\n\n'

if [ "$APPLY" -ne 1 ]; then
  echo "dry-run 完成。加 --apply 才会真正卸载 user systemd unit。"
  echo "注意：本脚本不会删除 ~/.local/state/openclaw/mark42/ 或 /mnt/data/openclaw/scratch。"
  exit 0
fi

if ! command -v systemctl >/dev/null 2>&1; then
  echo "缺少命令: systemctl" >&2
  exit 1
fi

systemctl --user disable --now mark42-watchdog.timer >/dev/null 2>&1 || true
systemctl --user stop mark42-engine-daemon.service mark42-armor-guard.service mark42-bootstrap.service >/dev/null 2>&1 || true

for unit in "${UNIT_FILES[@]}"; do
  rm -f "$USER_UNIT_DIR/$unit"
done

systemctl --user daemon-reload
systemctl --user reset-failed >/dev/null 2>&1 || true

echo "已卸载 Mark42 user systemd unit：$USER_UNIT_DIR"
echo "未删除的数据："
echo "  - ~/.local/state/openclaw/mark42/"
echo "  - /mnt/data/openclaw/scratch"
echo "如需清这些目录，请先备份，再手动处理。"
