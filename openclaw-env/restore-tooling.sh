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
QMD_PACKAGE="@tobilu/qmd"
OPENCLAW_JSON="${HOME_DIR}/.openclaw/openclaw.json"
SYSTEMD_DROPIN_DIR="${HOME_DIR}/.config/systemd/user/openclaw-gateway.service.d"
QMD_CPU_TEMPLATE="${WORKSPACE_DIR}/openclaw-env/templates/openclaw-gateway.qmd-cpu.conf"
QMD_HF_TEMPLATE="${WORKSPACE_DIR}/openclaw-env/templates/openclaw-gateway.qmd-hf-mirror.conf"

mkdir -p "${DESKTOP_DIR}"
mkdir -p "${OPENCLAW_SKILLS_DIR}"
mkdir -p "${LOCAL_BIN_DIR}"
mkdir -p "${SYSTEMD_DROPIN_DIR}"

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

if command -v qmd >/dev/null 2>&1; then
  echo "QMD already available: $(command -v qmd)"
else
  npm install -g "${QMD_PACKAGE}"
  echo "Installed QMD globally via npm"
fi

if [ -f "${OPENCLAW_JSON}" ]; then
  python3 - <<'PY'
import json, os
p = os.path.expanduser('~/.openclaw/openclaw.json')
with open(p, 'r', encoding='utf-8') as f:
    cfg = json.load(f)
memory = cfg.setdefault('memory', {})
memory['backend'] = 'qmd'
memory['citations'] = memory.get('citations', 'auto')
qmd = memory.setdefault('qmd', {})
qmd['command'] = qmd.get('command') or os.path.expanduser('~/.npm-global/bin/qmd')
qmd['includeDefaultMemory'] = False
qmd['paths'] = [
    {'name': 'memory-root', 'path': '.', 'pattern': 'MEMORY.md'},
    {'name': 'memory-dir', 'path': 'memory', 'pattern': '**/*.md'},
]
qmd['searchMode'] = 'search'
update = qmd.setdefault('update', {})
update['interval'] = update.get('interval', '5m')
update['debounceMs'] = update.get('debounceMs', 15000)
update['onBoot'] = True
update['waitForBootSync'] = False
update['embedInterval'] = '0'
update['commandTimeoutMs'] = 30000
update['updateTimeoutMs'] = 120000
update['embedTimeoutMs'] = 15000
limits = qmd.setdefault('limits', {})
limits['maxResults'] = limits.get('maxResults', 6)
limits['timeoutMs'] = limits.get('timeoutMs', 120000)
scope = qmd.setdefault('scope', {})
scope['default'] = 'deny'
scope['rules'] = [{ 'action': 'allow', 'match': { 'chatType': 'direct' } }]
with open(p, 'w', encoding='utf-8') as f:
    json.dump(cfg, f, ensure_ascii=False, indent=2)
    f.write('\n')
PY
  echo "Applied stable local QMD config to ${OPENCLAW_JSON}"
fi

if [ -f "${QMD_CPU_TEMPLATE}" ]; then
  cp "${QMD_CPU_TEMPLATE}" "${SYSTEMD_DROPIN_DIR}/qmd-cpu.conf"
  echo "Installed gateway QMD CPU-only drop-in -> ${SYSTEMD_DROPIN_DIR}/qmd-cpu.conf"
fi

if [ -f "${QMD_HF_TEMPLATE}" ]; then
  cp "${QMD_HF_TEMPLATE}" "${SYSTEMD_DROPIN_DIR}/qmd-hf-mirror.conf"
  echo "Installed gateway HF mirror drop-in -> ${SYSTEMD_DROPIN_DIR}/qmd-hf-mirror.conf"
fi

echo
printf '%s\n' 'Tooling restore complete.'
echo 'Recommended checks:'
echo '  command -v cli-anything'
echo '  cli-anything help'
echo '  cli-anything skill'
echo '  test -f ~/.openclaw/skills/cli-anything/SKILL.md && echo OK'
echo '  command -v qmd && qmd --version'
echo '  bash openclaw-env/qmd-agent-status.sh main'
echo '  systemctl --user daemon-reload && systemctl --user restart openclaw-gateway.service'
echo
echo 'Optional model prefetch (keeps stable search-only default, only seeds cache):'
echo '  bash openclaw-env/qmd-prefetch-models-via-mirror.sh check all'
echo '  bash openclaw-env/qmd-prefetch-models-via-mirror.sh download embed'
echo
echo 'Important: HF_ENDPOINT is installed for the gateway service, but QMD 2.1.0 still hardcodes'
echo 'huggingface.co in parts of its download path. Mirror-based prefetch is the safer way to prepare'
echo 'embedding / rerank / query-expansion models without leaving stable search-only mode.'
