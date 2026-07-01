#!/usr/bin/env bash
# Mark42 user-systemd restore helper
# 用途：把 install.sh 产生的备份目录恢复回 ~/.config/systemd/user/。

set -euo pipefail

usage() {
  cat <<'EOF'
用法：
  tools/mark42-systemd/restore.sh --backup-dir PATH [--user-unit-dir PATH] [--apply]

默认行为：dry-run，只预览将要恢复的 unit，不真正覆盖当前 user systemd unit。
加 --apply：真正把备份目录中的 Mark42 unit 恢复到 user systemd 目录，并执行 daemon-reload。

可选参数：
  --backup-dir PATH     install.sh 生成的备份目录（必填）
  --user-unit-dir PATH  user systemd 单元目录（默认：$HOME/.config/systemd/user）
  --apply               真正执行恢复
  --help                显示帮助

说明：
  - 本脚本只恢复 Mark42 的 user systemd unit / timer
  - 不删除 workspace 代码
  - 不删除 ~/.local/state/openclaw/mark42/
  - 不删除 /mnt/data/openclaw/scratch
EOF
}

APPLY=0
BACKUP_DIR=""
USER_UNIT_DIR="${HOME}/.config/systemd/user"
UNIT_FILES=(
  "mark42-bootstrap.service"
  "mark42-engine-daemon.service"
  "mark42-armor-guard.service"
  "mark42-watchdog.service"
  "mark42-watchdog.timer"
)

while [ "$#" -gt 0 ]; do
  case "$1" in
    --backup-dir)
      BACKUP_DIR="$2"
      shift 2
      ;;
    --user-unit-dir)
      USER_UNIT_DIR="$2"
      shift 2
      ;;
    --apply)
      APPLY=1
      shift
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

if [ -z "$BACKUP_DIR" ]; then
  echo "缺少参数: --backup-dir PATH" >&2
  usage >&2
  exit 2
fi

if [ ! -d "$BACKUP_DIR" ]; then
  echo "备份目录不存在: $BACKUP_DIR" >&2
  exit 1
fi

printf '== Mark42 restore preview ==\n'
printf 'backup_dir     : %s\n' "$BACKUP_DIR"
printf 'user_unit_dir  : %s\n' "$USER_UNIT_DIR"
printf 'mode           : %s\n' "$( [ "$APPLY" -eq 1 ] && echo apply || echo dry-run )"
printf '\n备份内容：\n'

FOUND=0
for unit in "${UNIT_FILES[@]}"; do
  if [ -f "$BACKUP_DIR/$unit" ]; then
    printf '  - %s\n' "$BACKUP_DIR/$unit"
    FOUND=1
  else
    printf '  - %s (missing)\n' "$BACKUP_DIR/$unit"
  fi
done

if [ "$FOUND" -ne 1 ]; then
  echo "备份目录里未找到任何 Mark42 unit：$BACKUP_DIR" >&2
  exit 1
fi

printf '\n将执行：\n'
printf '  systemctl --user stop mark42-engine-daemon.service mark42-armor-guard.service mark42-bootstrap.service || true\n'
printf '  systemctl --user disable --now mark42-watchdog.timer || true\n'
printf '  cp -f %s/{mark42-bootstrap.service,mark42-engine-daemon.service,mark42-armor-guard.service,mark42-watchdog.service,mark42-watchdog.timer} %s/\n' "$BACKUP_DIR" "$USER_UNIT_DIR"
printf '  systemctl --user daemon-reload\n'
printf '  systemctl --user reset-failed\n'
printf '\n'

if [ "$APPLY" -ne 1 ]; then
  echo "dry-run 完成。加 --apply 才会真正恢复备份 unit。"
  exit 0
fi

if ! command -v systemctl >/dev/null 2>&1; then
  echo "缺少命令: systemctl" >&2
  exit 1
fi

install -d "$USER_UNIT_DIR"
systemctl --user stop mark42-engine-daemon.service mark42-armor-guard.service mark42-bootstrap.service >/dev/null 2>&1 || true
systemctl --user disable --now mark42-watchdog.timer >/dev/null 2>&1 || true

for unit in "${UNIT_FILES[@]}"; do
  if [ -f "$BACKUP_DIR/$unit" ]; then
    install -m 0644 "$BACKUP_DIR/$unit" "$USER_UNIT_DIR/$unit"
  fi
done

systemctl --user daemon-reload
systemctl --user reset-failed >/dev/null 2>&1 || true

echo "已恢复备份 unit 到：$USER_UNIT_DIR"
echo "下一步建议："
echo "  tools/mark42-systemd/verify.sh"
echo "  systemctl --user start mark42-bootstrap.service"
echo "  systemctl --user start mark42-engine-daemon.service"
echo "  systemctl --user start mark42-armor-guard.service"
echo "  systemctl --user enable --now mark42-watchdog.timer"
echo "  systemctl --user status mark42-bootstrap.service mark42-engine-daemon.service mark42-armor-guard.service mark42-watchdog.timer"
