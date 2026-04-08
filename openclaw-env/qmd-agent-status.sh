#!/usr/bin/env bash
set -euo pipefail

AGENT_ID="${1:-main}"
QUERY="${2:-}"
OPENCLAW_JSON="${HOME}/.openclaw/openclaw.json"
QMD_BIN="${HOME}/.npm-global/bin/qmd"
[ -x "${QMD_BIN}" ] || QMD_BIN="$(command -v qmd || true)"
QMD_XDG_CONFIG_HOME="${HOME}/.openclaw/agents/${AGENT_ID}/qmd/xdg-config"
QMD_XDG_CACHE_HOME="${HOME}/.openclaw/agents/${AGENT_ID}/qmd/xdg-cache"
QMD_INDEX_YML="${QMD_XDG_CONFIG_HOME}/qmd/index.yml"
QMD_INDEX_DB="${QMD_XDG_CACHE_HOME}/qmd/index.sqlite"

printf '== OpenClaw QMD runtime summary ==\n'
printf 'agent: %s\n' "$AGENT_ID"
printf 'config: %s\n' "$OPENCLAW_JSON"
printf 'agent qmd config: %s\n' "$QMD_INDEX_YML"
printf 'agent qmd index: %s\n' "$QMD_INDEX_DB"

printf '\n== OpenClaw memory config ==\n'
python3 - <<'PY'
import json, os
p=os.path.expanduser('~/.openclaw/openclaw.json')
with open(p,'r',encoding='utf-8') as f:
    cfg=json.load(f)
mem=(cfg.get('memory') or {})
qmd=(mem.get('qmd') or {})
print(json.dumps({
  'backend': mem.get('backend'),
  'citations': mem.get('citations'),
  'searchMode': qmd.get('searchMode'),
  'includeDefaultMemory': qmd.get('includeDefaultMemory'),
  'paths': qmd.get('paths'),
  'update': qmd.get('update'),
  'limits': qmd.get('limits'),
  'scope': qmd.get('scope')
}, ensure_ascii=False, indent=2))
PY

printf '\n== Gateway service env (configured) ==\n'
systemctl --user cat openclaw-gateway.service 2>/dev/null | grep -E 'HF_ENDPOINT=|QMD_LLAMA_GPU=' || echo 'No QMD gateway env drop-ins found.'

PID="$(systemctl --user show -p MainPID --value openclaw-gateway.service 2>/dev/null || true)"
printf '\n== Gateway process env (runtime) ==\n'
if [ -n "$PID" ] && [ "$PID" != "0" ] && [ -r "/proc/$PID/environ" ]; then
  tr '\0' '\n' < "/proc/$PID/environ" | grep -E '^(HF_ENDPOINT|QMD_LLAMA_GPU|OPENCLAW_)=' | sort || true
else
  echo 'Gateway process not running or /proc access unavailable.'
fi

printf '\n== Agent-scoped QMD index ==\n'
if [ -f "$QMD_INDEX_YML" ]; then
  sed -n '1,200p' "$QMD_INDEX_YML"
else
  echo 'Agent-scoped QMD config not found yet.'
fi

if [ -n "$QMD_BIN" ] && [ -x "$QMD_BIN" ] && [ -d "$QMD_XDG_CACHE_HOME" ]; then
  export XDG_CONFIG_HOME="$QMD_XDG_CONFIG_HOME"
  export XDG_CACHE_HOME="$QMD_XDG_CACHE_HOME"
  printf '\n== qmd status (agent-scoped) ==\n'
  "$QMD_BIN" status || true
  printf '\n== qmd collections (agent-scoped) ==\n'
  "$QMD_BIN" collection list || true
  if [ -n "$QUERY" ]; then
    printf '\n== qmd search sample ==\n'
    printf 'query: %s\n' "$QUERY"
    "$QMD_BIN" search "$QUERY" --json -n 5 || true
  fi
else
  printf '\nqmd binary or agent-scoped cache not available yet.\n'
fi
