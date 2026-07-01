#!/usr/bin/env bash
# Mark42 user-systemd preflight checker
# 用途：把“陌生机器安装前置条件清单”脚本化，帮助维护者判断是否值得进入 install.sh --apply。

set -euo pipefail

usage() {
  cat <<'EOT'
用法：
  tools/mark42-systemd/preflight.sh [--workspace PATH] [--python PATH] [--state-dir PATH] [--scratch PATH] [--user-unit-dir PATH]

默认行为：执行前置条件检查，不修改 systemd，不写入任何 unit。
输出会汇总 `PASS/WARN/FAIL`，方便判断是否值得进入 `install.sh --apply`。

可选参数：
  --workspace PATH      Mark42 工作区根目录（默认：脚本自动推断）
  --python PATH         Python 可执行文件（默认：python3）
  --state-dir PATH      Mark42 状态目录（默认：$XDG_STATE_HOME/openclaw/mark42）
  --scratch PATH        OpenClaw scratch 根目录（默认：/mnt/data/openclaw/scratch）
  --user-unit-dir PATH  user systemd 单元目录（默认：$HOME/.config/systemd/user）
  --help                显示帮助
EOT
}

WORKSPACE=""
PYTHON_BIN="python3"
STATE_DIR=""
SCRATCH_ROOT="/mnt/data/openclaw/scratch"
USER_UNIT_DIR="${HOME}/.config/systemd/user"

PASS_COUNT=0
WARN_COUNT=0
FAIL_COUNT=0

OPENCLAW_STATUS_TMP=""
OPENCLAW_HEALTH_TMP=""
OPENCLAW_MODELS_TMP=""

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
CONFIG_FILE="$HOME/.openclaw/openclaw.json"

pass() {
  PASS_COUNT=$((PASS_COUNT + 1))
  printf '[PASS] %s
' "$1"
}

warn() {
  WARN_COUNT=$((WARN_COUNT + 1))
  printf '[WARN] %s
' "$1"
}

fail() {
  FAIL_COUNT=$((FAIL_COUNT + 1))
  printf '[FAIL] %s
' "$1"
}

first_existing_parent() {
  local path="$1"
  while [ ! -e "$path" ]; do
    path="$(dirname "$path")"
  done
  printf '%s
' "$path"
}

check_creatable_or_writable() {
  local label="$1"
  local path="$2"
  local parent=""

  if [ -e "$path" ]; then
    if [ -d "$path" ] && [ -w "$path" ]; then
      pass "$label 可写：$path"
    elif [ -d "$path" ]; then
      fail "$label 已存在但不可写：$path"
    else
      fail "$label 已存在但不是目录：$path"
    fi
    return
  fi

  parent="$(first_existing_parent "$path")"
  if [ -w "$parent" ]; then
    pass "$label 当前不存在，但父路径可写，可由安装脚本创建：$path"
  else
    fail "$label 当前不存在，且父路径不可写：$path（最近已存在父路径：$parent）"
  fi
}

cleanup() {
  rm -f "${OPENCLAW_STATUS_TMP:-}" "${OPENCLAW_HEALTH_TMP:-}" "${OPENCLAW_MODELS_TMP:-}"
}

trap cleanup EXIT

printf '== Mark42 preflight ==
'
printf 'workspace      : %s
' "$WORKSPACE"
printf 'python         : %s
' "$PYTHON_BIN"
printf 'state_dir      : %s
' "$STATE_DIR"
printf 'scratch_root   : %s
' "$SCRATCH_ROOT"
printf 'user_unit_dir  : %s
' "$USER_UNIT_DIR"
printf '
'

if [ "$(uname -s)" = "Linux" ]; then
  pass "当前系统是 Linux"
else
  fail "当前系统不是 Linux：$(uname -s)"
fi

if command -v systemctl >/dev/null 2>&1; then
  pass "systemctl 命令可用"
else
  fail "缺少命令：systemctl"
fi

if command -v sed >/dev/null 2>&1; then
  pass "sed 命令可用"
else
  fail "缺少命令：sed"
fi

if command -v install >/dev/null 2>&1; then
  pass "install 命令可用"
else
  fail "缺少命令：install"
fi

if command -v "$PYTHON_BIN" >/dev/null 2>&1; then
  pass "Python 命令可用：$PYTHON_BIN"
  if "$PYTHON_BIN" - <<'PYV' >/dev/null 2>&1
import sys
raise SystemExit(0 if sys.version_info >= (3, 10) else 1)
PYV
  then
    PY_VERSION="$($PYTHON_BIN - <<'PYV'
import sys
print('.'.join(map(str, sys.version_info[:3])))
PYV
)"
    pass "Python 版本满足 3.10+：$PY_VERSION"
  else
    fail "Python 版本低于 3.10：$($PYTHON_BIN --version 2>&1)"
  fi
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

check_creatable_or_writable "user unit 目录" "$USER_UNIT_DIR"
check_creatable_or_writable "Mark42 state 目录" "$STATE_DIR"
check_creatable_or_writable "scratch 根目录" "$SCRATCH_ROOT"

if [ -e "$SCRATCH_ROOT" ]; then
  pass "scratch 根目录已存在：$SCRATCH_ROOT"
else
  warn "scratch 根目录当前不存在；install.sh --apply 会尝试创建：$SCRATCH_ROOT"
fi

if command -v openclaw >/dev/null 2>&1; then
  pass "openclaw 命令可用"

  if openclaw config validate >/dev/null 2>&1; then
    pass "openclaw config validate 通过"
  else
    warn "openclaw config validate 未通过；建议先修配置，再考虑 install.sh --apply"
  fi

  OPENCLAW_STATUS_TMP="$(mktemp)"
  if openclaw status >"$OPENCLAW_STATUS_TMP" 2>&1; then
    pass "openclaw status 可运行：Gateway 本地状态可读取"
  else
    fail "openclaw status 失败：请先确认 Gateway 本地可达与 CLI 配置是否正常"
  fi

  OPENCLAW_HEALTH_TMP="$(mktemp)"
  if openclaw health --json >"$OPENCLAW_HEALTH_TMP" 2>&1; then
    if "$PYTHON_BIN" - "$OPENCLAW_HEALTH_TMP" <<'PYH' >/dev/null 2>&1
import json
import sys
path = sys.argv[1]
with open(path, 'r', encoding='utf-8') as f:
    data = json.load(f)
raise SystemExit(0 if data.get('ok') is True else 1)
PYH
    then
      HEALTH_DURATION="$($PYTHON_BIN - "$OPENCLAW_HEALTH_TMP" <<'PYH'
import json
import sys
path = sys.argv[1]
with open(path, 'r', encoding='utf-8') as f:
    data = json.load(f)
print(data.get('durationMs', 'unknown'))
PYH
)"
      pass "openclaw health --json 通过：Gateway 健康快照 ok=true（durationMs=${HEALTH_DURATION}）"
    else
      fail "openclaw health --json 可执行，但健康快照 ok 不是 true；请先检查 Gateway 健康状态"
    fi
  else
    fail "openclaw health --json 失败：当前无法读取 Gateway 健康快照"
  fi

  OPENCLAW_MODELS_TMP="$(mktemp)"
  if openclaw models status --json >"$OPENCLAW_MODELS_TMP" 2>&1; then
    pass "openclaw models status --json 可运行：provider/auth 状态可读取"

    if MODELS_SUMMARY="$($PYTHON_BIN -c 'import json,sys; data=json.load(open(sys.argv[1], encoding="utf-8")); auth=data.get("auth") or {}; providers=auth.get("providers") or []; pwo=auth.get("providersWithOAuth") or []; oauth=(auth.get("oauth") or {}); profiles=oauth.get("profiles") or []; unusable=auth.get("unusableProfiles") or []; missing=auth.get("missingProvidersInUse") or []; print(f"providers={len(providers)} providersWithOAuth={len(pwo)} oauthProfiles={len(profiles)} unusableProfiles={len(unusable)} missingProvidersInUse={len(missing)}")' "$OPENCLAW_MODELS_TMP")"; then
      pass "openclaw models status 摘要：${MODELS_SUMMARY}"
    else
      warn "openclaw models status --json 可运行，但 provider 摘要提取失败；建议人工复核"
    fi

    if "$PYTHON_BIN" -c 'import json,sys; data=json.load(open(sys.argv[1], encoding="utf-8")); auth=data.get("auth") or {}; providers=auth.get("providers") or []; raise SystemExit(0 if providers else 1)' "$OPENCLAW_MODELS_TMP" >/dev/null 2>&1; then
      pass "openclaw models status 已返回 provider 列表"
    else
      warn "openclaw models status --json 未返回 provider 列表；建议人工复核"
    fi

    if "$PYTHON_BIN" -c 'import json,sys; data=json.load(open(sys.argv[1], encoding="utf-8")); auth=data.get("auth") or {}; oauth=auth.get("oauth") or {}; profiles=oauth.get("profiles") or []; raise SystemExit(0 if profiles else 1)' "$OPENCLAW_MODELS_TMP" >/dev/null 2>&1; then
      pass "openclaw models status 已返回 OAuth/token profile 摘要"
    else
      warn "openclaw models status --json 未返回 OAuth/token profile 摘要；建议人工复核"
    fi

    if "$PYTHON_BIN" -c 'import json,sys; data=json.load(open(sys.argv[1], encoding="utf-8")); auth=data.get("auth") or {}; missing=auth.get("missingProvidersInUse") or []; unusable=auth.get("unusableProfiles") or []; raise SystemExit(1 if (missing or unusable) else 0)' "$OPENCLAW_MODELS_TMP" >/dev/null 2>&1; then
      pass "openclaw models status 未见 missingProvidersInUse / unusableProfiles"
    else
      warn "openclaw models status 提示存在 missingProvidersInUse 或 unusableProfiles；建议人工复核 provider 配置"
    fi
  else
    warn "openclaw models status --json 失败：provider/auth 健康面暂不可读，建议人工排查后再 install.sh --apply"
  fi
else
  warn "未找到 openclaw 命令；这不阻止 preflight，但会影响长期运行链路"
fi

if [ -f "$CONFIG_FILE" ]; then
  pass "OpenClaw 配置文件存在：$CONFIG_FILE"
else
  warn "未找到 OpenClaw 配置文件：$CONFIG_FILE"
fi

if systemctl --user show-environment >/dev/null 2>&1; then
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
    warn "openclaw-gateway.service 当前不是 active（ActiveState=${GATEWAY_ACTIVE_STATE:-unknown}）；安装前建议先确认"
  fi
fi

warn "机器角色仍需人工确认：临时开发机优先用 assemble；长期托管机才建议 install.sh --apply"
warn "回退策略仍需人工确认：陌生机器上 apply 前，至少先准备旧 unit 备份或稳定版本回滚方案"

printf '\n== summary ==\n'
printf 'pass=%s warn=%s fail=%s\n' "$PASS_COUNT" "$WARN_COUNT" "$FAIL_COUNT"

if [ "$FAIL_COUNT" -gt 0 ]; then
  echo "preflight 未通过：请先处理 FAIL 项，再考虑进入 install.sh --apply。" >&2
  exit 1
fi

if [ "$WARN_COUNT" -gt 0 ]; then
  echo "preflight 通过，但还有 WARN 项建议人工确认。"
else
  echo "preflight 通过：当前机器已满足进入 install.sh --apply 的最低前提。"
fi
