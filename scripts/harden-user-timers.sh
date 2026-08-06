#!/usr/bin/env bash
# 适用机器：公司（Linux）
# 系统 / OS：Linux
# 建立日期：2026-08-06
#
# 用途：为所有 openclaw/mark42 的 user 级 timer 统一加固，根治
#      「OnBootSec 语义错误导致 timer 永久卡死」的隐患。
#
# ── 根因（systemd 官方文档证实）──
# 1. OnBootSec= 相对【机器开机】计时。
# 2. 本批 timer 属 per-user manager（systemd --user）。man systemd.timer 原文：
#    用户级 manager「通常在首次登录时才启动，而非开机时」→ 应使用 OnStartupSec=。
# 3. Persistent= 官方原文："this setting only has an effect on timers
#    configured with OnCalendar=" → 无 OnCalendar 时它完全无效，错过无法补回。
#
# ── 实测（2026-08-06）──
#   开机 07:30:51 → user manager 07:32:17（+86s）→ timer 07:32:25（+94s）
#   OnBootSec=90s 的触发点 07:32:21 已过去 4 秒 → 触发被跳过
#   → service 从未激活 → OnUnitActiveSec 无锚点 → timer 永久卡死
#   （enabled + active，但 list-timers 的 NEXT 列为 `-`，永不触发）
#
#   实际后果：frontstage-guardian 与 health-collector 自 08-05 17:54 起
#   完全停摆，前台假死检测 + CPU 过载自动响应两道防线长期为空。
#   与 CASE-20260803-014 同一种病：看起来在工作，实际救不了任何东西。
#
#   其余 timer 今天只是「赶上了」：余量仅 34-94 秒。开机稍慢即会成批阵亡，
#   其中包含 mark42-watchdog —— 自愈机制本身。
#
# ── 加固方案（三重保障，不依赖任何单一锚点）──
#   OnStartupSec=  相对 user manager 启动（官方为 user timer 指定的正确选项）
#   OnUnitActiveSec= 显式重申周期（必须显式写，见下方警告）
#   OnCalendar=    绝对时间兜底，同时让 Persistent=true 真正生效
#
# ⚠️ 关键坑（2026-08-06 实测）：`OnBootSec=` 空串会重置【整个 monotonic
#    timer 列表】，不只清 OnBootSec 一项 —— 主文件里的 OnUnitActiveSec 会被
#    一起清掉，表现为 list-timers 的 NEXT 列显示 `-`。故必须在 drop-in 里
#    显式重申 OnUnitActiveSec，不能依赖主文件继承。
#
# 用法：
#   bash harden-user-timers.sh --dry-run   # 只打印将要做什么（默认）
#   bash harden-user-timers.sh --apply     # 真正写入并 reload
#
set -euo pipefail

UNIT_DIR="$HOME/.config/systemd/user"
DROPIN_NAME="fix-onboot-deadlock.conf"
MODE="${1:---dry-run}"

# timer 名 : OnUnitActiveSec 周期 : OnCalendar 兜底
TARGETS=(
  "openclaw-task-scheduler:60s:*:0/5"
  "openclaw-resume-watch:5min:*:0/10"
  "openclaw-session-backup:10min:*:0/15"
  "openclaw-lifecycle-maintainer:15min:*:0/20"
  "mark42-watchdog:5min:*:0/10"
  "mark42-autonomy:5min:*:0/10"
)

echo "模式: $MODE"
echo "目标: ${#TARGETS[@]} 个 timer"
echo

changed=0
for entry in "${TARGETS[@]}"; do
  name="${entry%%:*}"
  rest="${entry#*:}"
  period="${rest%%:*}"
  calendar="${rest#*:}"

  timer_file="$UNIT_DIR/${name}.timer"
  if [ ! -f "$timer_file" ]; then
    echo "⏭️  $name: 主文件不存在，跳过"
    continue
  fi

  dropin_dir="$UNIT_DIR/${name}.timer.d"
  dropin="$dropin_dir/$DROPIN_NAME"

  if [ -f "$dropin" ]; then
    echo "⏭️  $name: 已有加固 drop-in，跳过"
    continue
  fi

  echo "🔧 $name: OnStartupSec=90s OnUnitActiveSec=$period OnCalendar=$calendar"

  if [ "$MODE" = "--apply" ]; then
    mkdir -p "$dropin_dir"
    cat > "$dropin" <<EOF
# 适用机器：公司（Linux）
# 系统 / OS：Linux
# 建立日期：2026-08-06（由 harden-user-timers.sh 生成）
#
# 根治「OnBootSec 语义错误导致 user timer 永久卡死」。
# 详细根因与实测证据见 scripts/harden-user-timers.sh 文件头注释，
# 以及 docs/对系统操作必须要参考的崩坏案例.md 的 CASE-20260806-017。
#
# ⚠️ OnBootSec= 空串会重置整个 monotonic timer 列表，
#    因此下面必须显式重申 OnUnitActiveSec，不能依赖主文件继承。

[Timer]
OnBootSec=
OnStartupSec=90s
OnUnitActiveSec=$period
OnCalendar=$calendar
Persistent=true
AccuracySec=10s
EOF
    changed=$((changed + 1))
  fi
done

echo
if [ "$MODE" = "--apply" ]; then
  if [ "$changed" -gt 0 ]; then
    echo "校验 unit 合法性..."
    for entry in "${TARGETS[@]}"; do
      name="${entry%%:*}"
      [ -f "$UNIT_DIR/${name}.timer" ] || continue
      systemd-analyze --user verify "$UNIT_DIR/${name}.timer" || {
        echo "❌ $name verify 失败，中止"; exit 1; }
    done
    echo "✅ 全部 verify 通过"
    systemctl --user daemon-reload
    echo "✅ daemon-reload 完成"
    echo
    echo "⚠️ 尚需 restart 各 timer 使新配置生效（本脚本不自动 restart，"
    echo "   避免在不合适的时机打断正在执行的 service）："
    for entry in "${TARGETS[@]}"; do
      name="${entry%%:*}"
      [ -f "$UNIT_DIR/${name}.timer" ] || continue
      echo "   systemctl --user restart ${name}.timer"
    done
  else
    echo "无需改动（全部已加固）"
  fi
else
  echo "这是 dry-run，未做任何修改。确认无误后加 --apply 执行。"
fi
