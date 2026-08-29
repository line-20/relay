#!/usr/bin/env bash
#
# reflect-gather.sh — pool the Relay trail across your dogfooding repos into ONE file.
#
# The maintainer half of /reflect (phase 1). Relay is improved today from memory — someone
# recalls a friction. This gathers the evidence instead: every repo's durable Relay trail
# (board, decisions, handovers, reviews, audits, movements log, session telemetry, CHANGELOG)
# plus its git history, concatenated into a single pooled markdown file a session can analyse.
#
# It reads OTHER repos on your disk. The output is LOCAL maintainer data — gitignored, never
# committed (it contains your cross-project work).
#
# Usage:
#   ./scripts/reflect-gather.sh [out-file] [repo-path ...]
#     out-file    where to write the pooled file (default: reflect/pooled/<date>.md)
#     repo-path…  the repos to pool. If none given, read ./reflect.repos (one path per line,
#                 '#' comments and '~' allowed). cp reflect.repos.example reflect.repos to start.
#
set -euo pipefail
cd "$(dirname "$0")/.."

command -v jq >/dev/null || { echo "✗ jq is required" >&2; exit 1; }

out="${1:-reflect/pooled/$(date +%Y-%m-%d-%H%M).md}"
[ $# -gt 0 ] && shift || true
repos=("$@")

# Phase-2 movement log — central, outside all repos (see reflect-log.sh).
central="${RELAY_MOVEMENTS:-$HOME/.relay/movements.jsonl}"

# Session telemetry — central, outside all repos (see reflect-sessions.sh). Refresh it from the
# on-disk transcripts before pooling so the report carries this lap's model/cost/duration.
sessions="${RELAY_SESSIONS:-$HOME/.relay/sessions.jsonl}"
if [ -x "scripts/reflect-sessions.sh" ]; then
  ./scripts/reflect-sessions.sh >/dev/null 2>&1 || true
fi

# Per-command (per-stage) telemetry — the segmented companion (see reflect-commands.py).
commands="${RELAY_COMMANDS:-$HOME/.relay/commands.jsonl}"
if [ -x "scripts/reflect-commands.py" ]; then
  ./scripts/reflect-commands.py >/dev/null 2>&1 || true
fi

if [ ${#repos[@]} -eq 0 ]; then
  if [ ! -f reflect.repos ]; then
    echo "✗ no repos given and no ./reflect.repos file." >&2
    echo "  cp reflect.repos.example reflect.repos  and list the repos you dogfood Relay in." >&2
    exit 1
  fi
  while IFS= read -r line; do
    line="${line%%#*}"                      # strip comment
    line="$(printf '%s' "$line" | xargs)"   # trim whitespace
    [ -n "$line" ] && repos+=("$line")
  done < reflect.repos
fi

mkdir -p "$(dirname "$out")"
{
  echo "# Relay pooled trail"
  echo
  echo "_Gathered $(date '+%Y-%m-%d %H:%M') from ${#repos[@]} repo(s). Local maintainer data — do not commit._"
} > "$out"

emit_file() { # <label> <path>
  [ -f "$2" ] || return 0
  { echo; echo "#### $1 — \`$2\`"; echo '```'; cat "$2"; echo '```'; } >> "$out"
}
emit_glob() { # <label> <dir> <glob>
  [ -d "$2" ] || return 0
  local f
  for f in "$2"/$3; do
    [ -f "$f" ] || continue
    emit_file "$1: $(basename "$f")" "$f"
  done
}

for repo in "${repos[@]}"; do
  repo="${repo/#\~/$HOME}"
  if [ ! -d "$repo" ]; then echo "  ⚠ skip (not found): $repo" >&2; continue; fi
  root="$(jq -r '.root // "relay"' "$repo/relay.config.json" 2>/dev/null || echo relay)"
  R="$repo/$root"
  name="$(basename "$repo")"
  {
    echo; echo "---"; echo
    echo "## Repo: $name"
    echo "_Path: \`$repo\` · Relay root: \`$root\`_"
  } >> "$out"
  emit_file  "Board"            "$R/board.md"
  emit_file  "Decisions"        "$R/decisions.md"
  emit_glob  "Handover"         "$R/handover"          "*.md"
  emit_glob  "Handover archive" "$R/handover/archive"  "*.md"
  emit_glob  "Review"           "$R/reviews"           "*.md"
  emit_glob  "Audit"            "$R/audits"            "*.md"
  if [ -f "$central" ]; then
    moves="$(jq -c --arg r "$repo" 'select(.cwd | startswith($r))' "$central" 2>/dev/null || true)"
    if [ -n "$moves" ]; then
      { echo; echo "#### Movements (central log, this repo) — \`$name\`"; echo '```'; printf '%s\n' "$moves"; echo '```'; } >> "$out"
    fi
  fi
  if [ -f "$sessions" ]; then
    sess="$(jq -c --arg r "$repo" 'select((.cwd // "") | startswith($r))' "$sessions" 2>/dev/null || true)"
    if [ -n "$sess" ]; then
      { echo; echo "#### Session telemetry (central, this repo) — \`$name\`"; echo '```'; printf '%s\n' "$sess"; echo '```'; } >> "$out"
    fi
  fi
  if [ -f "$commands" ]; then
    cmds="$(jq -c --arg r "$repo" 'select((.cwd // "") | startswith($r))' "$commands" 2>/dev/null || true)"
    if [ -n "$cmds" ]; then
      { echo; echo "#### Command/stage telemetry (central, this repo) — \`$name\`"; echo '```'; printf '%s\n' "$cmds"; echo '```'; } >> "$out"
    fi
  fi
  emit_file  "Changelog"        "$repo/CHANGELOG.md"
  {
    echo; echo "#### Git log (last 100) — \`$name\`"; echo '```'
    git -C "$repo" log --oneline -100 2>/dev/null || echo "(no git history)"
    echo '```'
  } >> "$out"
  echo "  ✓ $name" >&2
done

echo >&2
echo "Pooled → $out  ($(wc -l < "$out" | tr -d ' ') lines)" >&2
echo "$out"
