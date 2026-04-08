#!/usr/bin/env bash
set -euo pipefail

MODE="check"
TARGET="all"
CACHE_DIR="${QMD_MODEL_CACHE_DIR:-${HOME}/.cache/qmd/models}"
BASE_URL="${HF_MIRROR_BASE:-https://hf-mirror.com}"

usage() {
  cat <<'EOF'
Usage:
  bash openclaw-env/qmd-prefetch-models-via-mirror.sh [check|download] [embed|rerank|expand|all]

Examples:
  bash openclaw-env/qmd-prefetch-models-via-mirror.sh
  bash openclaw-env/qmd-prefetch-models-via-mirror.sh check all
  bash openclaw-env/qmd-prefetch-models-via-mirror.sh download embed
  bash openclaw-env/qmd-prefetch-models-via-mirror.sh download all

Notes:
- This only seeds QMD model files into ~/.cache/qmd/models for later reuse.
- It does NOT automatically switch OpenClaw out of stable search-only mode.
- OpenClaw's agent-scoped QMD cache symlinks to ~/.cache/qmd/models when present.
EOF
}

if [ "${1:-}" = "-h" ] || [ "${1:-}" = "--help" ]; then
  usage
  exit 0
fi

if [ -n "${1:-}" ]; then
  MODE="$1"
fi
if [ -n "${2:-}" ]; then
  TARGET="$2"
fi

case "$MODE" in
  check|download) ;;
  *) echo "Unsupported mode: $MODE" >&2; usage; exit 1 ;;
esac
case "$TARGET" in
  embed|rerank|expand|all) ;;
  *) echo "Unsupported target: $TARGET" >&2; usage; exit 1 ;;
esac

mkdir -p "$CACHE_DIR"

url_for() {
  case "$1" in
    embed) echo "$BASE_URL/ggml-org/embeddinggemma-300M-GGUF/resolve/main/embeddinggemma-300M-Q8_0.gguf" ;;
    rerank) echo "$BASE_URL/ggml-org/Qwen3-Reranker-0.6B-Q8_0-GGUF/resolve/main/qwen3-reranker-0.6b-q8_0.gguf" ;;
    expand) echo "$BASE_URL/tobil/qmd-query-expansion-1.7B-gguf/resolve/main/qmd-query-expansion-1.7B-q4_k_m.gguf" ;;
  esac
}

file_for() {
  case "$1" in
    embed) echo "embeddinggemma-300M-Q8_0.gguf" ;;
    rerank) echo "qwen3-reranker-0.6b-q8_0.gguf" ;;
    expand) echo "qmd-query-expansion-1.7B-q4_k_m.gguf" ;;
  esac
}

iter_models() {
  if [ "$TARGET" = "all" ]; then
    printf '%s\n' embed rerank expand
  else
    printf '%s\n' "$TARGET"
  fi
}

check_one() {
  local key="$1" url file dest
  url="$(url_for "$key")"
  file="$(file_for "$key")"
  dest="$CACHE_DIR/$file"
  echo "== $key =="
  echo "url:  $url"
  echo "file: $dest"
  if [ -f "$dest" ]; then
    ls -lh "$dest"
  else
    echo 'local: missing'
  fi
  if python3 - "$url" <<'PY'
import ssl, sys, urllib.request
url=sys.argv[1]
req=urllib.request.Request(url, method='HEAD')
ctx=ssl.create_default_context()
try:
    with urllib.request.urlopen(req, timeout=20, context=ctx) as r:
        print(f"remote: HTTP {r.status}, content-length={r.headers.get('content-length','?')}")
except Exception as e:
    print(f"remote: HEAD failed ({e})")
PY
  then
    :
  else
    echo 'remote: HEAD failed'
  fi
  echo
}

download_one() {
  local key="$1" url file dest tmp
  url="$(url_for "$key")"
  file="$(file_for "$key")"
  dest="$CACHE_DIR/$file"
  tmp="$dest.part"
  echo "== downloading $key =="
  echo "source: $url"
  echo "target: $dest"
  curl -fL --retry 3 --continue-at - -o "$tmp" "$url"
  mv "$tmp" "$dest"
  ls -lh "$dest"
  echo
}

printf 'cache dir: %s\n\n' "$CACHE_DIR"
for key in $(iter_models); do
  check_one "$key"
  if [ "$MODE" = "download" ]; then
    download_one "$key"
  fi
done

if [ "$MODE" = "download" ]; then
  cat <<EOF
Prefetch complete.

Recommended next steps:
  bash openclaw-env/qmd-agent-status.sh main
  # keep stable default unless you intentionally want advanced mode
  # if you later test advanced QMD, enable it deliberately instead of by default
EOF
fi
