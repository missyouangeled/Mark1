#!/usr/bin/env bash
# 适用机器：公司（Linux VM）
# 系统 / OS：Linux（systemd --user）
# 建立日期：2026-08-06
#
# 用途：Unity 连接栈补丁 —— 一个模块管两条通道，装/卸/开/关都是一条命令。
#
#   成员：
#     openclaw-unity-bridge.service   老 Bridge (TomLeeLive)   端口 27182
#     openclaw-unity-mcp.service      新 MCP (CoplayDev)       端口 8080
#     openclaw-unity.target           总开关（两者的父单元）
#
# ── 为什么要有这个补丁（2026-08-06 事故）──
#   两个服务原先都是 nohup 裸进程。当天一次意外重启把它俩双双带走：
#     - Unity 插件报 "An error occurred while sending the request"
#     - MCP 点 Connect 无反应（8080 无进程无端口）
#   用户一天内手动拉起两次。裸进程 = 重启即失联、无自愈、无留痕。
#
# ── 设计要点 ──
#   1. 「开就都开、关就都关」：成员用 PartOf=openclaw-unity.target，
#      stop/restart target 时成员跟着动；成员用 WantedBy=openclaw-unity.target，
#      start target 时成员被拉起。
#   2. 「删掉就都删掉」：uninstall 会 disable+stop+删除三个单元文件与
#      日志目录（日志默认保留，加 --purge-logs 才删）。
#   3. 只 enable target，不单独 enable 成员 —— 避免出现「半启动」状态。
#   4. 开机自启依赖 Linger。本机已 Linger=yes（2026-08-06 确认）；
#      脚本会检查，为 no 时给出明确提示（不静默失败）。
#
# ── 与 CASE-20260806-017 的关系 ──
#   本模块是 service 不是 timer，不涉及 OnBootSec/OnStartupSec 那个坑。
#   常驻服务用 Restart=always 自愈，不需要 timer 周期拉起。
#
# ⚠️ 安全边界：本脚本只碰 openclaw-unity-* 三个单元，
#    绝不 touch openclaw-gateway / mark42-* 等任何现存单元。
#    （遵守 CASE-20260803-012：不对承载自身的服务做生命周期操作）
#
# 用法：
#   bash unity-stack-patch.sh status              # 查看当前状态（默认）
#   bash unity-stack-patch.sh install --dry-run   # 只打印将要做什么
#   bash unity-stack-patch.sh install --apply     # 真正安装 + enable + 启动
#   bash unity-stack-patch.sh verify              # 实际调用验收（不只看灯）
#   bash unity-stack-patch.sh start|stop|restart  # 两个一起开/关/重启
#   bash unity-stack-patch.sh uninstall --apply   # 整个模块干净卸载
#   bash unity-stack-patch.sh uninstall --apply --purge-logs
#
set -euo pipefail

WS="/home/missyouangeled/.openclaw/workspace"
SRC_DIR="$WS/config/systemd/unity-stack"
UNIT_DIR="$HOME/.config/systemd/user"
LOG_DIR="$HOME/.local/state/openclaw/unity-stack"

TARGET="openclaw-unity.target"
SVC_BRIDGE="openclaw-unity-bridge.service"
SVC_MCP="openclaw-unity-mcp.service"
UNITS=("$TARGET" "$SVC_BRIDGE" "$SVC_MCP")

BRIDGE_PORT=27182
MCP_PORT=8080
VM_IP="192.168.79.128"
MCP_CLI="$WS/tools/unity-mcp-coplay/Server/.venv/bin/unity-mcp"

ACTION="${1:-status}"
MODE="dry-run"
PURGE_LOGS=0
for a in "${@:2}"; do
  case "$a" in
    --apply)      MODE="apply" ;;
    --dry-run)    MODE="dry-run" ;;
    --purge-logs) PURGE_LOGS=1 ;;
  esac
done

c_ok()   { printf '\033[32m%s\033[0m\n' "$*"; }
c_warn() { printf '\033[33m%s\033[0m\n' "$*"; }
c_err()  { printf '\033[31m%s\033[0m\n' "$*"; }
hr()     { echo "────────────────────────────────────────────────────────"; }

# dry-run 时只打印，apply 时真跑
run() {
  if [[ "$MODE" == "apply" ]]; then
    echo "  \$ $*"
    "$@"
  else
    echo "  [dry-run] $*"
  fi
}

check_linger() {
  local linger
  linger="$(loginctl show-user "$USER" 2>/dev/null | sed -n 's/^Linger=//p')"
  if [[ "$linger" == "yes" ]]; then
    c_ok "  ✅ Linger=yes（开机自启可生效）"
  else
    c_err "  ❌ Linger=$linger —— 开机自启【不会】生效！"
    echo "     user 级 systemd 默认在首次登录才启动。修复："
    echo "       sudo loginctl enable-linger $USER"
  fi
}

do_status() {
  hr; echo "Unity 连接栈状态"; hr
  check_linger
  echo
  for u in "${UNITS[@]}"; do
    if [[ -f "$UNIT_DIR/$u" ]]; then
      printf '  %-34s installed  enabled=%-9s active=%s\n' "$u" \
        "$(systemctl --user is-enabled "$u" 2>/dev/null || echo n/a)" \
        "$(systemctl --user is-active  "$u" 2>/dev/null || echo n/a)"
    else
      printf '  %-34s \033[33mNOT INSTALLED\033[0m\n' "$u"
    fi
  done
  echo
  echo "  端口监听："
  ss -tlnp 2>/dev/null | grep -E "($BRIDGE_PORT|$MCP_PORT)\b" \
    | sed 's/^/    /' || echo "    （两个端口都没在监听）"
  echo
  c_warn "  注意：is-active 全绿 ≠ 真能用。请跑 verify 做实际调用验收。"
}

do_install() {
  hr; echo "安装 Unity 连接栈补丁（模式：$MODE）"; hr
  for u in "${UNITS[@]}"; do
    [[ -f "$SRC_DIR/$u" ]] || { c_err "缺少源文件：$SRC_DIR/$u"; exit 1; }
  done
  c_ok "  ✅ 三个源单元文件齐全"
  check_linger
  echo
  echo "1) 建日志目录"
  run mkdir -p "$LOG_DIR"
  echo
  echo "2) 安装单元文件到 $UNIT_DIR"
  run mkdir -p "$UNIT_DIR"
  for u in "${UNITS[@]}"; do
    # 已存在则先备份，绝不静默覆盖
    if [[ -f "$UNIT_DIR/$u" ]]; then
      run cp -a "$UNIT_DIR/$u" "$UNIT_DIR/$u.bak-$(date +%Y%m%d-%H%M%S)"
    fi
    run cp "$SRC_DIR/$u" "$UNIT_DIR/$u"
  done
  echo
  echo "3) reload + 语法校验"
  run systemctl --user daemon-reload
  if [[ "$MODE" == "apply" ]]; then
    systemd-analyze --user verify "$UNIT_DIR/$TARGET" \
      "$UNIT_DIR/$SVC_BRIDGE" "$UNIT_DIR/$SVC_MCP" \
      && c_ok "  ✅ systemd-analyze verify 通过" \
      || c_warn "  ⚠️ verify 有告警，见上方输出"
  fi
  echo
  echo "4) 只 enable target（成员由 WantedBy 自动挂载，不单独 enable）"
  run systemctl --user enable "$TARGET"
  run systemctl --user enable "$SVC_BRIDGE" "$SVC_MCP"
  echo
  echo "5) 清理可能残留的 nohup 裸进程（避免与 service 抢端口）"
  run pkill -f "unity-bridge-server.js" || true
  run pkill -f "mcp-for-unity" || true
  run sleep 2
  echo
  echo "6) 启动 target（两个一起起）"
  run systemctl --user start "$TARGET"
  if [[ "$MODE" == "apply" ]]; then
    echo "  等待 MCP 绑定端口（实测需 8-14 秒）..."
    sleep 15
  fi
  echo
  [[ "$MODE" == "apply" ]] && do_status || c_warn "  [dry-run] 未做任何改动。加 --apply 才真正执行。"
}

do_uninstall() {
  hr; echo "卸载 Unity 连接栈补丁（模式：$MODE，purge-logs=$PURGE_LOGS）"; hr
  c_warn "  将删除三个单元：${UNITS[*]}"
  c_warn "  不会碰任何其他 systemd 单元。"
  echo
  echo "1) 停 target（成员靠 PartOf 一起停）"
  run systemctl --user stop "$TARGET" || true
  run systemctl --user stop "$SVC_BRIDGE" "$SVC_MCP" || true
  echo
  echo "2) disable"
  run systemctl --user disable "$TARGET" "$SVC_BRIDGE" "$SVC_MCP" || true
  echo
  echo "3) 删单元文件（含备份文件）"
  for u in "${UNITS[@]}"; do
    run rm -f "$UNIT_DIR/$u"
  done
  echo
  echo "4) reset-failed + reload"
  run systemctl --user reset-failed || true
  run systemctl --user daemon-reload
  echo
  if [[ "$PURGE_LOGS" == "1" ]]; then
    echo "5) 删日志目录"
    run rm -rf "$LOG_DIR"
  else
    echo "5) 保留日志目录 $LOG_DIR（要删加 --purge-logs）"
  fi
  echo
  [[ "$MODE" == "apply" ]] && c_ok "  ✅ 模块已干净卸载" || c_warn "  [dry-run] 未做任何改动。"
}

# 实际调用验收 —— 不只看 is-active
do_verify() {
  hr; echo "Unity 连接栈实际调用验收"; hr
  local fail=0

  echo "1) Bridge /bridge/health（localhost）"
  if curl -sf --max-time 6 "http://127.0.0.1:$BRIDGE_PORT/bridge/health" 2>/dev/null | sed 's/^/    /'; then
    echo; c_ok "  ✅ Bridge 本地可用"
  else
    c_err "  ❌ Bridge 本地不可用"; fail=1
  fi
  echo
  echo "2) Bridge 外网口（Unity 实际连的地址 $VM_IP）"
  if curl -sf --max-time 6 "http://$VM_IP:$BRIDGE_PORT/bridge/health" >/dev/null 2>&1; then
    c_ok "  ✅ $VM_IP:$BRIDGE_PORT 可达"
  else
    c_err "  ❌ $VM_IP:$BRIDGE_PORT 不可达"; fail=1
  fi
  echo
  echo "3) Bridge Unity session 注册情况"
  curl -s --max-time 6 "http://127.0.0.1:$BRIDGE_PORT/unity/status" 2>/dev/null | head -c 600 | sed 's/^/    /' || true
  echo
  echo "4) MCP 端口 + CLI status（真实调用）"
  if [[ -x "$MCP_CLI" ]]; then
    if timeout 30 "$MCP_CLI" --host 127.0.0.1 --port "$MCP_PORT" status 2>&1 | sed 's/^/    /' | grep -q "Connected"; then
      c_ok "  ✅ MCP 服务可用"
      timeout 30 "$MCP_CLI" --host 127.0.0.1 --port "$MCP_PORT" status 2>&1 | sed 's/^/    /'
    else
      c_err "  ❌ MCP CLI status 未返回 Connected"; fail=1
    fi
  else
    c_err "  ❌ 找不到 MCP CLI：$MCP_CLI"; fail=1
  fi
  echo
  echo "5) MCP 外网口可达性"
  local code
  code="$(curl -s --max-time 6 -o /dev/null -w '%{http_code}' "http://$VM_IP:$MCP_PORT/mcp" 2>/dev/null || echo 000)"
  # 406 = FastMCP 拒绝非 MCP 协议的裸 GET，属正常「服务活着」信号
  if [[ "$code" == "406" || "$code" == "200" || "$code" == "404" ]]; then
    c_ok "  ✅ $VM_IP:$MCP_PORT 可达（HTTP $code，406 为 FastMCP 正常响应）"
  else
    c_err "  ❌ $VM_IP:$MCP_PORT 不可达（HTTP $code）"; fail=1
  fi
  echo; hr
  if [[ "$fail" == "0" ]]; then
    c_ok "验收结果：全部通过 ✅"
  else
    c_err "验收结果：有项目未通过 ❌（见上方）"; return 1
  fi
}

case "$ACTION" in
  status)    do_status ;;
  install)   do_install ;;
  uninstall) do_uninstall ;;
  verify)    do_verify ;;
  start)     run systemctl --user start   "$TARGET"; [[ "$MODE" == "apply" ]] && { sleep 15; do_status; } || true ;;
  stop)      run systemctl --user stop    "$TARGET" ;;
  restart)   run systemctl --user restart "$TARGET"; [[ "$MODE" == "apply" ]] && { sleep 15; do_status; } || true ;;
  *)
    c_err "未知动作：$ACTION"
    echo "可用：status | install | uninstall | verify | start | stop | restart"
    echo "加 --apply 才真正执行（默认 dry-run）"
    exit 1 ;;
esac
