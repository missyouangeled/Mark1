#!/usr/bin/env bash
set -euo pipefail

REPO="__HOME__/Desktop/CLI-Anything"
README="$REPO/README.md"
SKILL="$HOME/.openclaw/skills/cli-anything/SKILL.md"

usage() {
  cat <<'EOF'
cli-anything (local helper)

This machine currently has the CLI-Anything repository and OpenClaw skill installed,
but not a standalone official global executable from the project itself.

Available helper actions:
  cli-anything repo         Print repository path
  cli-anything readme       Print README path
  cli-anything skill        Print OpenClaw skill path
  cli-anything openclaw     Print OpenClaw usage hint
  cli-anything help         Show this help
EOF
}

cmd="${1:-help}"
case "$cmd" in
  repo)
    printf '%s\n' "$REPO"
    ;;
  readme)
    printf '%s\n' "$README"
    ;;
  skill)
    printf '%s\n' "$SKILL"
    ;;
  openclaw)
    cat <<EOF
OpenClaw skill installed at:
$SKILL

Suggested usage in chat:
@cli-anything build a CLI for /path/to/software
@cli-anything refine /path/to/software
@cli-anything validate /path/to/software
@cli-anything test /path/to/software
EOF
    ;;
  help|--help|-h)
    usage
    ;;
  *)
    echo "Unknown subcommand: $cmd" >&2
    echo >&2
    usage >&2
    exit 2
    ;;
esac
