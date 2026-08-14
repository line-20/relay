#!/usr/bin/env bash
#
# Cut a release: write the version into every place that mirrors it, then verify.
#
# The version is hardcoded in four files because a command can't read its own version at
# runtime (the banner is what certifies which command file a session actually loaded).
# Hand-editing four files is how 1.0.9 drifted while plugin.json climbed to 1.4.0, failing
# CI on every push for five releases without anyone noticing. This script is the only
# supported way to move the number, so that class of drift can't recur.
#
# Usage:  ./scripts/release.sh 1.6.0
#
# Writes:  plugins/relay/.claude-plugin/plugin.json   (source of truth)
#          .claude-plugin/marketplace.json            (.metadata.version)
#          plugins/relay/commands/init.md             (banner)
#          plugins/relay/commands/version.md          (banner)
#
# Does NOT commit, tag or push — that stays a deliberate act. It prints the next steps.
#
set -euo pipefail
cd "$(dirname "$0")/.."

new="${1:-}"
if ! [[ "$new" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
  echo "usage: ./scripts/release.sh <major.minor.patch>   e.g. ./scripts/release.sh 1.6.0" >&2
  exit 1
fi

command -v jq >/dev/null || { echo "✗ jq is required" >&2; exit 1; }

current="$(jq -r '.version' plugins/relay/.claude-plugin/plugin.json)"
echo "  $current  →  $new"
echo

# The CHANGELOG entry is written by a human, before the bump — it's the one part of a
# release that can't be generated, so it gates rather than being filled in with a stub.
if ! grep -qE "^## +${new//./\\.}( |\$)" CHANGELOG.md; then
  cat >&2 <<EOF
✗ CHANGELOG.md has no '## $new' section.

  Write the entry first — what changed and why, in the shape the previous entries use —
  then re-run. Nothing has been modified.
EOF
  exit 1
fi

write_json() { # <file> <jq-path>
  local f="$1" path="$2" tmp
  tmp="$(mktemp)"
  jq --arg v "$new" "$path = \$v" "$f" > "$tmp" && mv "$tmp" "$f"
  echo "  ✓ $f"
}

write_banner() { # <file>  — the 'SSDLC workbench' line carries vX.Y.Z
  local f="$1" tmp
  tmp="$(mktemp)"
  # Portable across BSD/GNU sed: rewrite via a temp file rather than -i.
  sed "/SSDLC workbench/s/v[0-9][0-9]*\.[0-9][0-9]*\.[0-9][0-9]*/v$new/" "$f" > "$tmp" && mv "$tmp" "$f"
  echo "  ✓ $f (banner)"
}

write_json plugins/relay/.claude-plugin/plugin.json '.version'
write_json .claude-plugin/marketplace.json '.metadata.version'
write_banner plugins/relay/commands/init.md
write_banner plugins/relay/commands/version.md

echo
bash scripts/check-version.sh

cat <<EOF

Next:
  git checkout -b release/$new && git add -A && git commit -m "chore: release $new"
  git push -u origin release/\$(echo $new) && gh pr create --fill
  # after the PR merges, on main:
  git tag -a v$new -m "$new" && git push origin v$new
EOF
