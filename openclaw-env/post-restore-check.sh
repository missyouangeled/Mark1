#!/usr/bin/env bash
set -euo pipefail

WORKSPACE_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"

pass() { printf '[PASS] %s\n' "$1"; }
warn() { printf '[WARN] %s\n' "$1"; }
check_cmd() {
  local cmd="$1"
  if command -v "$cmd" >/dev/null 2>&1; then
    pass "command available: $cmd"
  else
    warn "missing command: $cmd"
  fi
}

printf '== command checks ==\n'
check_cmd git
check_cmd node
check_cmd npm
check_cmd php
check_cmd systemctl
check_cmd openclaw
check_cmd qmd

printf '\n== workspace checks ==\n'
for path in \
  "$WORKSPACE_DIR/pulsenest-php" \
  "$WORKSPACE_DIR/PROJECT_VERSIONS.md" \
  "$WORKSPACE_DIR/HANDOFF.md" \
  "$WORKSPACE_DIR/memory" \
  "$WORKSPACE_DIR/.learnings" \
  "$WORKSPACE_DIR/.learnings/INBOX.md" \
  "$WORKSPACE_DIR/openclaw-env/skill-overlays/self-improving-agent/hooks/openclaw/handler.js" \
  "$WORKSPACE_DIR/openclaw-env/plugins/self-improvement-tool-errors/openclaw.plugin.json" \
  "$WORKSPACE_DIR/openclaw-env/plugins/self-improvement-tool-errors/index.js" \
  "$WORKSPACE_DIR/scripts/pulsenest-preview.sh" \
  "$WORKSPACE_DIR/scripts/openclaw-resume-watch.sh" \
  "$WORKSPACE_DIR/openclaw-env/openclaw.local.example.json" \
  "$WORKSPACE_DIR/openclaw-env/restore-tooling.sh" \
  "$WORKSPACE_DIR/openclaw-env/qmd-agent-status.sh" \
  "$WORKSPACE_DIR/openclaw-env/qmd-prefetch-models-via-mirror.sh" \
  "$WORKSPACE_DIR/openclaw-env/templates/openclaw-gateway.qmd-cpu.conf" \
  "$WORKSPACE_DIR/openclaw-env/templates/openclaw-gateway.qmd-hf-mirror.conf"
do
  if [ -e "$path" ]; then
    pass "exists: $path"
  else
    warn "missing: $path"
  fi
done

printf '\n== user systemd checks ==\n'
for unit in \
  "$HOME/.config/systemd/user/pulsenest-preview.service" \
  "$HOME/.config/systemd/user/openclaw-resume-watch.service" \
  "$HOME/.config/systemd/user/openclaw-resume-watch.timer"
do
  if [ -f "$unit" ]; then
    pass "exists: $unit"
  else
    warn "missing: $unit"
  fi
done

printf '\n== openclaw checks ==\n'
if [ -f "$HOME/.openclaw/openclaw.json" ]; then
  pass 'exists: ~/.openclaw/openclaw.json'
else
  warn 'missing: ~/.openclaw/openclaw.json'
fi

if [ -d "$HOME/.openclaw/hooks/self-improvement" ]; then
  pass 'exists: ~/.openclaw/hooks/self-improvement'
else
  warn 'missing: ~/.openclaw/hooks/self-improvement'
fi

if [ -f "$HOME/.openclaw/hooks/self-improvement/handler.js" ]; then
  pass 'exists: ~/.openclaw/hooks/self-improvement/handler.js'
else
  warn 'missing: ~/.openclaw/hooks/self-improvement/handler.js'
fi

if openclaw plugins inspect self-improvement-tool-errors --json >/tmp/self-improvement-tool-errors.inspect.json 2>/dev/null; then
  pass 'visible: self-improvement-tool-errors'
else
  warn 'missing plugin: self-improvement-tool-errors'
fi

if [ -f "$HOME/.openclaw/skills/cli-anything/SKILL.md" ]; then
  pass 'exists: ~/.openclaw/skills/cli-anything/SKILL.md'
else
  warn 'missing: ~/.openclaw/skills/cli-anything/SKILL.md'
fi

if command -v cli-anything >/dev/null 2>&1; then
  pass 'command available: cli-anything'
else
  warn 'missing command: cli-anything'
fi

if python3 - <<'PY'
import json, os, sys
p=os.path.expanduser('~/.openclaw/openclaw.json')
with open(p,'r',encoding='utf-8') as f:
    cfg=json.load(f)
sys.exit(0 if ((cfg.get('memory') or {}).get('backend') == 'qmd') else 1)
PY
then
  pass 'memory backend configured: qmd'
else
  warn 'memory backend not configured as qmd'
fi

if python3 - <<'PY'
import json, os, sys
p=os.path.expanduser('~/.openclaw/openclaw.json')
with open(p,'r',encoding='utf-8') as f:
    cfg=json.load(f)
qmd=((cfg.get('memory') or {}).get('qmd') or {})
update=qmd.get('update') or {}
paths=qmd.get('paths') or []
want_root={'name':'memory-root','path':'.','pattern':'MEMORY.md'}
want_dir={'name':'memory-dir','path':'memory','pattern':'**/*.md'}
ok=(qmd.get('searchMode')=='search' and str(update.get('embedInterval'))=='0' and qmd.get('includeDefaultMemory') is False and want_root in paths and want_dir in paths)
sys.exit(0 if ok else 1)
PY
then
  pass 'stable local QMD mode configured (search-only + embedInterval=0 + explicit memory paths)'
else
  warn 'stable local QMD mode not fully configured'
fi

for dropin in \
  "$HOME/.config/systemd/user/openclaw-gateway.service.d/qmd-cpu.conf" \
  "$HOME/.config/systemd/user/openclaw-gateway.service.d/qmd-hf-mirror.conf"
do
  if [ -f "$dropin" ]; then
    pass "exists: $dropin"
  else
    warn "missing: $dropin"
  fi
done

if systemctl --user cat openclaw-gateway.service 2>/dev/null | grep -q 'QMD_LLAMA_GPU=false'; then
  pass 'gateway service configured: QMD_LLAMA_GPU=false'
else
  warn 'gateway service missing QMD_LLAMA_GPU=false'
fi

if systemctl --user cat openclaw-gateway.service 2>/dev/null | grep -q 'HF_ENDPOINT=https://hf-mirror.com'; then
  pass 'gateway service configured: HF_ENDPOINT=https://hf-mirror.com'
else
  warn 'gateway service missing HF_ENDPOINT=https://hf-mirror.com'
fi

GATEWAY_PID="$(systemctl --user show -p MainPID --value openclaw-gateway.service 2>/dev/null || true)"
if [ -n "$GATEWAY_PID" ] && [ "$GATEWAY_PID" != "0" ] && [ -r "/proc/$GATEWAY_PID/environ" ]; then
  if tr '\0' '\n' < "/proc/$GATEWAY_PID/environ" | grep -q '^QMD_LLAMA_GPU=false$'; then
    pass 'gateway runtime env active: QMD_LLAMA_GPU=false'
  else
    warn 'gateway runtime env missing QMD_LLAMA_GPU=false'
  fi
  if tr '\0' '\n' < "/proc/$GATEWAY_PID/environ" | grep -q '^HF_ENDPOINT=https://hf-mirror.com$'; then
    pass 'gateway runtime env active: HF_ENDPOINT=https://hf-mirror.com'
  else
    warn 'gateway runtime env missing HF_ENDPOINT=https://hf-mirror.com'
  fi
else
  warn 'gateway runtime env not inspectable (service may be stopped)'
fi

QMD_AGENT_XDG_CONFIG_HOME="$HOME/.openclaw/agents/main/qmd/xdg-config"
QMD_AGENT_XDG_CACHE_HOME="$HOME/.openclaw/agents/main/qmd/xdg-cache"
QMD_AGENT_INDEX_YML="$QMD_AGENT_XDG_CONFIG_HOME/qmd/index.yml"
QMD_AGENT_INDEX_DB="$QMD_AGENT_XDG_CACHE_HOME/qmd/index.sqlite"

if [ -f "$QMD_AGENT_INDEX_YML" ]; then
  pass 'agent-scoped QMD config exists'
else
  warn 'agent-scoped QMD config missing'
fi

if [ -f "$QMD_AGENT_INDEX_DB" ]; then
  pass 'agent-scoped QMD index exists'
else
  warn 'agent-scoped QMD index missing'
fi

if command -v qmd >/dev/null 2>&1 && [ -d "$QMD_AGENT_XDG_CACHE_HOME" ]; then
  if XDG_CONFIG_HOME="$QMD_AGENT_XDG_CONFIG_HOME" XDG_CACHE_HOME="$QMD_AGENT_XDG_CACHE_HOME" qmd collection list >/tmp/openclaw-qmd-collections.txt 2>/dev/null; then
    if grep -q 'memory-root-main' /tmp/openclaw-qmd-collections.txt && grep -q 'memory-dir-main' /tmp/openclaw-qmd-collections.txt; then
      pass 'agent-scoped QMD collections visible (memory-root-main + memory-dir-main)'
    else
      warn 'agent-scoped QMD collections do not look complete yet'
    fi
  else
    warn 'agent-scoped QMD collection list failed'
  fi
  if XDG_CONFIG_HOME="$QMD_AGENT_XDG_CONFIG_HOME" XDG_CACHE_HOME="$QMD_AGENT_XDG_CACHE_HOME" qmd status >/tmp/openclaw-qmd-status.txt 2>/dev/null; then
    if grep -q 'Vectors:  0 embedded' /tmp/openclaw-qmd-status.txt; then
      pass 'agent-scoped QMD currently stays on lexical-only/no-vectors state'
    else
      warn 'agent-scoped QMD vectors state differs from expected stable search-only default'
    fi
  else
    warn 'agent-scoped QMD status failed'
  fi
fi

printf '\nDone. Warnings usually mean: restore script not run yet, gateway not restarted yet, software not installed, or secrets not restored.\n'
