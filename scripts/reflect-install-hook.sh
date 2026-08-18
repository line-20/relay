#!/usr/bin/env bash
#
# reflect-install-hook.sh — wire the movement logger (reflect-log.sh) into a repo's Claude Code
# settings as a UserPromptSubmit hook, so Relay commands run there get logged (phase 2).
#
# Idempotent: skips if the hook is already present. Merges into <repo>/.claude/settings.json,
# preserving every other setting. Pass '-' as the repo to target ~/.claude/settings.json
# (user-global — logs Relay commands in EVERY repo at once).
#
# Usage:
#   ./scripts/reflect-install-hook.sh <repo-path> [repo-path ...]
#   ./scripts/reflect-install-hook.sh -                 # user-global
#   ./scripts/reflect-install-hook.sh --print           # print the snippet, install nothing
#
set -euo pipefail
cd "$(dirname "$0")/.."

command -v jq >/dev/null || { echo "✗ jq is required" >&2; exit 1; }
logger="$(cd scripts && pwd)/reflect-log.sh"

snippet="$(jq -n --arg cmd "$logger" \
  '{hooks:{UserPromptSubmit:[{hooks:[{type:"command", command:$cmd}]}]}}')"

if [ "${1:-}" = "--print" ]; then
  echo "# Add to .claude/settings.json (this repo, or ~/.claude for all repos):"
  echo "$snippet"
  exit 0
fi

[ $# -ge 1 ] || { echo "usage: ./scripts/reflect-install-hook.sh <repo-path>... | - | --print" >&2; exit 1; }

for target in "$@"; do
  if [ "$target" = "-" ]; then
    settings="$HOME/.claude/settings.json"; label="~/.claude (user-global)"
  else
    target="${target/#\~/$HOME}"
    [ -d "$target" ] || { echo "  ⚠ skip (not found): $target" >&2; continue; }
    settings="$target/.claude/settings.json"; label="$(basename "$target")"
  fi
  mkdir -p "$(dirname "$settings")"
  [ -f "$settings" ] || echo '{}' > "$settings"

  if jq -e --arg cmd "$logger" \
      'any((.hooks.UserPromptSubmit // [])[]?.hooks[]?; .command == $cmd)' \
      "$settings" >/dev/null 2>&1; then
    echo "  = already installed: $label"
    continue
  fi

  tmp="$(mktemp)"
  jq --arg cmd "$logger" '
    .hooks //= {} |
    .hooks.UserPromptSubmit //= [] |
    .hooks.UserPromptSubmit += [ { hooks: [ { type: "command", command: $cmd } ] } ]
  ' "$settings" > "$tmp" && mv "$tmp" "$settings"
  echo "  ✓ installed: $label  →  $settings"
done

echo
echo "Movements will log to <repo>/<root>/movements.jsonl. Add that to each repo's .gitignore."
