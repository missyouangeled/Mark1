#!/bin/bash
# 适用机器：公司（Linux）
# 系统 / OS：Linux
# 用途：定期清理过期临时文件（语音回复、infos-handle 输出、通用 tmp）
# 触发：systemd timer，默认每 30 分钟一次

set -euo pipefail

WORKSPACE="${HOME}/.openclaw/workspace"
STATE_DIR="${HOME}/.local/state/openclaw/cleanup"
LOG_FILE="${STATE_DIR}/cleanup.log"

mkdir -p "${STATE_DIR}"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S %z')] $*" | tee -a "${LOG_FILE}"
}

cleaned_count=0
cleaned_bytes=0

# ── 语音回复：超过 4 小时的 mp3/wav ──
VOICE_DIR="${WORKSPACE}/tmp/voice-replies"
if [ -d "${VOICE_DIR}" ]; then
    while IFS= read -r -d '' f; do
        sz=$(stat -c%s "$f" 2>/dev/null || echo 0)
        rm -f "$f"
        cleaned_count=$((cleaned_count + 1))
        cleaned_bytes=$((cleaned_bytes + sz))
    done < <(find "${VOICE_DIR}" -maxdepth 1 \( -name '*.mp3' -o -name '*.wav' \) -mmin +240 -print0 2>/dev/null || true)
fi

# ── infos-handle 输出：超过 4 小时 ──
INFO_OUT="${WORKSPACE}/tmp/infos-handle/outputs"
if [ -d "${INFO_OUT}" ]; then
    while IFS= read -r -d '' f; do
        sz=$(stat -c%s "$f" 2>/dev/null || echo 0)
        rm -f "$f"
        cleaned_count=$((cleaned_count + 1))
        cleaned_bytes=$((cleaned_bytes + sz))
    done < <(find "${INFO_OUT}" -type f -mmin +240 -print0 2>/dev/null || true)
fi

# ── secret-uploads 临时上传页：超过 24 小时 ──
SECRET_DIR="${WORKSPACE}/tmp/secret-uploads"
if [ -d "${SECRET_DIR}" ]; then
    while IFS= read -r -d '' f; do
        sz=$(stat -c%s "$f" 2>/dev/null || echo 0)
        rm -f "$f"
        cleaned_count=$((cleaned_count + 1))
        cleaned_bytes=$((cleaned_bytes + sz))
    done < <(find "${SECRET_DIR}" -type f -mmin +1440 -print0 2>/dev/null || true)
    # 清空后删除空目录
    find "${SECRET_DIR}" -type d -empty -delete 2>/dev/null || true
fi

# ── 通用 tmp 旧文件：超过 24 小时（保守，避免误删正在用的） ──
GENERAL_TMP="${WORKSPACE}/tmp"
if [ -d "${GENERAL_TMP}" ]; then
    while IFS= read -r -d '' f; do
        sz=$(stat -c%s "$f" 2>/dev/null || echo 0)
        rm -f "$f"
        cleaned_count=$((cleaned_count + 1))
        cleaned_bytes=$((cleaned_bytes + sz))
    done < <(find "${GENERAL_TMP}" -maxdepth 1 -type f -mmin +1440 -print0 2>/dev/null || true)
fi

# ── 空目录清理 ──
find "${WORKSPACE}/tmp" -type d -empty -delete 2>/dev/null || true

# ── 汇报 ──
cleaned_mb=$(echo "scale=2; ${cleaned_bytes} / 1048576" | bc 2>/dev/null || echo "0")
if [ "${cleaned_count}" -gt 0 ]; then
    log "cleaned ${cleaned_count} files (${cleaned_mb} MB)"
else
    log "nothing to clean"
fi
