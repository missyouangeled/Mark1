#!/usr/bin/env bash
set -euo pipefail

WORKSPACE_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
HOME_DIR="${HOME}"
DESKTOP_DIR="${HOME_DIR}/Desktop"
CLI_ANYTHING_REPO="${DESKTOP_DIR}/CLI-Anything"
OPENCLAW_SKILLS_DIR="${HOME_DIR}/.openclaw/skills/cli-anything"
LOCAL_BIN_DIR="${HOME_DIR}/.local/bin"
HELPER_DST="${LOCAL_BIN_DIR}/cli-anything"
HELPER_TEMPLATE="${WORKSPACE_DIR}/openclaw-env/templates/cli-anything-helper.sh"

mkdir -p "${DESKTOP_DIR}"
mkdir -p "${OPENCLAW_SKILLS_DIR}"
mkdir -p "${LOCAL_BIN_DIR}"

if [ ! -d "${CLI_ANYTHING_REPO}/.git" ]; then
  git clone https://github.com/HKUDS/CLI-Anything.git "${CLI_ANYTHING_REPO}"
  echo "Cloned CLI-Anything to ${CLI_ANYTHING_REPO}"
else
  echo "CLI-Anything repo already exists: ${CLI_ANYTHING_REPO}"
fi

if [ -f "${CLI_ANYTHING_REPO}/openclaw-skill/SKILL.md" ]; then
  cp "${CLI_ANYTHING_REPO}/openclaw-skill/SKILL.md" "${OPENCLAW_SKILLS_DIR}/SKILL.md"
  echo "Installed CLI-Anything OpenClaw skill -> ${OPENCLAW_SKILLS_DIR}/SKILL.md"
else
  echo "WARN: CLI-Anything OpenClaw skill source not found in repo" >&2
fi

sed \
  -e "s#__HOME__#${HOME_DIR//\/\\}#g" \
  -e "s#__WORKSPACE__#${WORKSPACE_DIR//\/\\}#g" \
  "${HELPER_TEMPLATE}" > "${HELPER_DST}"
chmod +x "${HELPER_DST}"

echo
printf '%s\n' 'Tooling restore complete.'
echo 'Recommended checks:'
echo '  command -v cli-anything'
echo '  cli-anything help'
echo '  cli-anything skill'
echo '  test -f ~/.openclaw/skills/cli-anything/SKILL.md && echo OK'
