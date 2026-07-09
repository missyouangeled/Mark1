#!/usr/bin/env bash
# Mark42 user-systemd verify helper
# 用途：把安装后 / 恢复后的最小验收流程标准化。

set -euo pipefail

usage() {
  cat <<'EOF'
用法：
  tools/mark42-systemd/verify.sh [--workspace PATH] [--python PATH]

默认行为：
  - 只读验证，不修改 systemd，不写入任何 unit
  - 汇总 PASS/WARN/FAIL，帮助维护者判断 Mark42 是否已回到“可继续运行”的最低状态

可选参数：
  --workspace PATH      Mark42 工作区根目录（默认：脚本自动推断）
  --python PATH         Python 可执行文件（默认：python3）
  --help                显示帮助

说明：
  - FAIL：关键依赖缺失、unit 丢失、Gateway / status 面不可读
  - WARN：unit 已安装但尚未启动，或运行态未达到预期
  - PASS：状态可读且关键运行态正常
EOF
}

WORKSPACE=""
PYTHON_BIN="python3"
USER_UNIT_DIR="${HOME}/.config/systemd/user"

PASS_COUNT=0
WARN_COUNT=0
FAIL_COUNT=0
STATUS_TMP=""

UNIT_FILES=(
  "mark42-bootstrap.service"
  "mark42-engine-daemon.service"
  "mark42-armor-guard.service"
  "mark42-watchdog.service"
  "mark42-watchdog.timer"
)

while [ "$#" -gt 0 ]; do
  case "$1" in
    --workspace)
      WORKSPACE="$2"
      shift 2
      ;;
    --python)
      PYTHON_BIN="$2"
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

MARK42_CLI="$WORKSPACE/scripts/mark42.py"

pass() {
  PASS_COUNT=$((PASS_COUNT + 1))
  printf '[PASS] %s\n' "$1"
}

warn() {
  WARN_COUNT=$((WARN_COUNT + 1))
  printf '[WARN] %s\n' "$1"
}

fail() {
  FAIL_COUNT=$((FAIL_COUNT + 1))
  printf '[FAIL] %s\n' "$1"
}

cleanup() {
  rm -f "${STATUS_TMP:-}"
}
trap cleanup EXIT

printf '== Mark42 verify ==\n'
printf 'workspace      : %s\n' "$WORKSPACE"
printf 'python         : %s\n' "$PYTHON_BIN"
printf 'user_unit_dir  : %s\n' "$USER_UNIT_DIR"
printf '\n'

if command -v systemctl >/dev/null 2>&1; then
  pass "systemctl 命令可用"
else
  fail "缺少命令：systemctl"
fi

if command -v "$PYTHON_BIN" >/dev/null 2>&1; then
  pass "Python 命令可用：$PYTHON_BIN"
else
  fail "缺少 Python 命令：$PYTHON_BIN"
fi

if [ -d "$WORKSPACE" ]; then
  pass "workspace 目录存在：$WORKSPACE"
else
  fail "workspace 目录不存在：$WORKSPACE"
fi

if [ -f "$MARK42_CLI" ]; then
  pass "Mark42 CLI 存在：$MARK42_CLI"
else
  fail "缺少 Mark42 CLI：$MARK42_CLI"
fi

if systemctl --user show-environment >/dev/null 2>&1; then
  pass "user systemd 会话可访问"
else
  fail "user systemd 会话不可访问；请先确认当前登录环境支持 systemctl --user"
fi

for unit in "${UNIT_FILES[@]}"; do
  if [ -f "$USER_UNIT_DIR/$unit" ]; then
    pass "unit 文件存在：$USER_UNIT_DIR/$unit"
  else
    fail "缺少 unit 文件：$USER_UNIT_DIR/$unit"
  fi

done

GATEWAY_LOAD_STATE="$(systemctl --user show -p LoadState --value openclaw-gateway.service 2>/dev/null || true)"
if [ "$GATEWAY_LOAD_STATE" = "loaded" ]; then
  pass "openclaw-gateway.service 已安装"
else
  fail "openclaw-gateway.service 未安装或当前用户不可见（LoadState=${GATEWAY_LOAD_STATE:-unknown}）"
fi

GATEWAY_ACTIVE_STATE="$(systemctl --user show -p ActiveState --value openclaw-gateway.service 2>/dev/null || true)"
if [ "$GATEWAY_ACTIVE_STATE" = "active" ]; then
  pass "openclaw-gateway.service 当前 active"
else
  fail "openclaw-gateway.service 当前不是 active（ActiveState=${GATEWAY_ACTIVE_STATE:-unknown}）"
fi

check_unit_state() {
  local unit="$1"
  local expected_hint="$2"
  local load_state=""
  local active_state=""
  local sub_state=""

  load_state="$(systemctl --user show -p LoadState --value "$unit" 2>/dev/null || true)"
  active_state="$(systemctl --user show -p ActiveState --value "$unit" 2>/dev/null || true)"
  sub_state="$(systemctl --user show -p SubState --value "$unit" 2>/dev/null || true)"

  if [ "$load_state" != "loaded" ]; then
    fail "$unit 未加载（LoadState=${load_state:-unknown}）"
    return
  fi

  case "$unit" in
    mark42-bootstrap.service)
      if [ "$active_state" = "active" ]; then
        pass "$unit 当前 active（SubState=${sub_state:-unknown}）"
      else
        warn "$unit 已安装但当前不是 active（ActiveState=${active_state:-unknown}，建议先执行：systemctl --user start mark42-bootstrap.service）"
      fi
      ;;
    mark42-watchdog.timer)
      if [ "$active_state" = "active" ]; then
        pass "$unit 当前 active（SubState=${sub_state:-unknown}）"
      else
        warn "$unit 已安装但当前不是 active（ActiveState=${active_state:-unknown}，建议先执行：systemctl --user enable --now mark42-watchdog.timer）"
      fi
      ;;
    *)
      if [ "$active_state" = "active" ]; then
        pass "$unit 当前 active（SubState=${sub_state:-unknown}）"
      else
        warn "$unit 已安装但当前不是 active（ActiveState=${active_state:-unknown}，建议先执行：$expected_hint）"
      fi
      ;;
  esac
}

check_unit_state "mark42-bootstrap.service" "systemctl --user start mark42-bootstrap.service"
check_unit_state "mark42-engine-daemon.service" "systemctl --user start mark42-engine-daemon.service"
check_unit_state "mark42-armor-guard.service" "systemctl --user start mark42-armor-guard.service"
check_unit_state "mark42-watchdog.timer" "systemctl --user enable --now mark42-watchdog.timer"

if command -v openclaw >/dev/null 2>&1; then
  if openclaw status >/dev/null 2>&1; then
    pass "openclaw status 可运行：Gateway 本地状态可读取"
  else
    fail "openclaw status 失败：请先确认 Gateway 本地可达与 CLI 配置是否正常"
  fi
else
  warn "未找到 openclaw 命令；无法补充读取 Gateway 状态面"
fi

if "$PYTHON_BIN" "$MARK42_CLI" context-safety verify >/dev/null 2>&1; then
  pass "Mark42 context safety verify 通过"
else
  fail "Mark42 context safety verify 未通过"
fi

STATUS_TMP="$(mktemp)"
if "$PYTHON_BIN" "$MARK42_CLI" status --json >"$STATUS_TMP" 2>&1; then
  pass "mark42.py status --json 可运行"

  if SUMMARY="$($PYTHON_BIN -c 'import json,sys; data=json.load(open(sys.argv[1], encoding="utf-8")); engine=data.get("engine") or {}; armor=data.get("armor") or {}; logs=data.get("logs") or {}; print(f"activeLoops={engine.get('"'"'activeLoops'"'"','"'"'unknown'"'"')} totalLoops={engine.get('"'"'totalLoops'"'"','"'"'unknown'"'"')} armorStatus={armor.get('"'"'status'"'"','"'"'unknown'"'"')} rotationCount={logs.get('"'"'rotationCount'"'"','"'"'unknown'"'"')}")' "$STATUS_TMP")"; then
    pass "Mark42 状态摘要：$SUMMARY"
  else
    warn "mark42.py status --json 可运行，但摘要提取失败；建议人工复核"
  fi

  if "$PYTHON_BIN" -c 'import json,sys; data=json.load(open(sys.argv[1], encoding="utf-8")); engine=data.get("engine") or {}; loops=engine.get("activeLoops"); raise SystemExit(0 if isinstance(loops, int) and loops > 0 else 1)' "$STATUS_TMP" >/dev/null 2>&1; then
    pass "Mark42 activeLoops > 0"
  else
    warn "Mark42 activeLoops 目前不是正数；如刚完成安装/恢复，可能还需要先启动 bootstrap/engine/armor"
  fi

  if "$PYTHON_BIN" -c 'import json,sys; data=json.load(open(sys.argv[1], encoding="utf-8")); armor=data.get("armor") or {}; status=armor.get("status"); raise SystemExit(0 if status in {"ok", "warn"} else 1)' "$STATUS_TMP" >/dev/null 2>&1; then
    pass "Armor 状态可读"
  else
    warn "Armor 状态暂未达到预期；建议人工复核 mark42.py status --json"
  fi
else
  fail "mark42.py status --json 失败：当前无法读取 Mark42 运行状态"
fi

printf '\n== summary ==\n'
printf 'pass=%s warn=%s fail=%s\n' "$PASS_COUNT" "$WARN_COUNT" "$FAIL_COUNT"

if [ "$FAIL_COUNT" -gt 0 ]; then
  echo "verify 未通过：请先处理 FAIL 项，再判断是否已经恢复到可继续运行状态。" >&2
  exit 1
fi

if [ "$WARN_COUNT" -gt 0 ]; then
  echo "verify 通过，但还有 WARN 项建议继续人工确认。"
else
  echo "verify 通过：当前已满足安装后 / 恢复后的最低验收条件。"
fi
