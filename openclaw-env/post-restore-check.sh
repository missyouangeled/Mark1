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
  "$WORKSPACE_DIR/scripts/pulsenest-preview.sh" \
  "$WORKSPACE_DIR/scripts/openclaw-resume-watch.sh" \
  "$WORKSPACE_DIR/openclaw-env/openclaw.local.example.json"
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

printf '\nDone. Warnings usually mean: restore script not run yet, software not installed, or secrets not restored.\n'
