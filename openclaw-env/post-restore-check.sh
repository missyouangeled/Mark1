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
  "$WORKSPACE_DIR/openclaw-env/restore-tooling.sh"
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

printf '\nDone. Warnings usually mean: restore script not run yet, software not installed, or secrets not restored.\n'
