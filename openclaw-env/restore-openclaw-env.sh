#!/usr/bin/env bash
set -euo pipefail

WORKSPACE_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
HOME_DIR="${HOME}"
SYSTEMD_USER_DIR="${HOME_DIR}/.config/systemd/user"
OPENCLAW_DIR="${HOME_DIR}/.openclaw"
HOOKS_DIR="${OPENCLAW_DIR}/hooks"

mkdir -p "${SYSTEMD_USER_DIR}"
mkdir -p "${HOOKS_DIR}"
mkdir -p "${OPENCLAW_DIR}"
mkdir -p "${WORKSPACE_DIR}/.run"
mkdir -p "${WORKSPACE_DIR}/.learnings"
mkdir -p "${WORKSPACE_DIR}/memory"

render_template() {
  local src="$1"
  local dst="$2"
  sed \
    -e "s#__HOME__#${HOME_DIR//\/\\}#g" \
    -e "s#__WORKSPACE__#${WORKSPACE_DIR//\/\\}#g" \
    "$src" > "$dst"
}

render_template "${WORKSPACE_DIR}/openclaw-env/templates/pulsenest-preview.service" \
  "${SYSTEMD_USER_DIR}/pulsenest-preview.service"
render_template "${WORKSPACE_DIR}/openclaw-env/templates/openclaw-resume-watch.service" \
  "${SYSTEMD_USER_DIR}/openclaw-resume-watch.service"
render_template "${WORKSPACE_DIR}/openclaw-env/templates/openclaw-resume-watch.timer" \
  "${SYSTEMD_USER_DIR}/openclaw-resume-watch.timer"

chmod +x "${WORKSPACE_DIR}/scripts/pulsenest-preview.sh"
chmod +x "${WORKSPACE_DIR}/scripts/openclaw-resume-watch.sh"

if [ -d "${WORKSPACE_DIR}/skills/self-improving-agent/hooks/openclaw" ]; then
  rm -rf "${HOOKS_DIR}/self-improvement"
  cp -r "${WORKSPACE_DIR}/skills/self-improving-agent/hooks/openclaw" "${HOOKS_DIR}/self-improvement"
fi

echo
echo "Environment restore files installed."
echo
echo "Next recommended commands:"
echo "  systemctl --user daemon-reload"
echo "  systemctl --user enable --now pulsenest-preview.service"
echo "  systemctl --user enable --now openclaw-resume-watch.timer"
echo "  openclaw hooks enable self-improvement"
echo
echo "Before pushing or using providers, manually restore:"
echo "  - ~/.ssh keys / GitHub auth"
echo "  - ~/.openclaw/openclaw.json private fields / tokens"
echo "  - provider login state"
