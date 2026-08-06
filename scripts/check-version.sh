#!/usr/bin/env bash
#
# Version-sync guard.
#
# The Relay version is hardcoded in several places (plugin.json is the source of truth;
# the marketplace manifest and the two command banners mirror it, because a command can't
# read its own version at runtime — ${CLAUDE_PLUGIN_ROOT} doesn't expand in command bash).
# This script fails if any mirror has drifted, and if the current version has no CHANGELOG
# entry. Run it before a release; it also runs in CI (.github/workflows/version-sync.yml).
#
set -euo pipefail
cd "$(dirname "$0")/.."

canonical="$(jq -r '.version' plugins/relay/.claude-plugin/plugin.json)"
[ -n "$canonical" ] && [ "$canonical" != "null" ] \
  || { echo "✗ could not read .version from plugins/relay/.claude-plugin/plugin.json"; exit 1; }

echo "Source of truth — plugin.json: $canonical"
echo

fail=0
check() { # <label> <actual-version>
  if [ "${2:-}" != "$canonical" ]; then
    printf '  ✗ %-46s %s\n' "$1" "found '${2:-<none>}', expected '$canonical'"
    fail=1
  else
    printf '  ✓ %-46s %s\n' "$1" "$2"
  fi
}

# Mirror 1: marketplace manifest
check ".claude-plugin/marketplace.json" \
  "$(jq -r '.metadata.version' .claude-plugin/marketplace.json 2>/dev/null)"

# Mirrors 2..n: the hardcoded banner version on the "SSDLC workbench" line of each command
for f in plugins/relay/commands/relay-init.md plugins/relay/commands/version.md; do
  banner_v="$(grep 'SSDLC workbench' "$f" 2>/dev/null | grep -oE 'v[0-9]+\.[0-9]+\.[0-9]+' | head -1 | sed 's/^v//')"
  check "$f (banner)" "$banner_v"
done

# Pre-release extra: the current version must be documented in the CHANGELOG.
if grep -qE "^## +${canonical//./\\.}( |\$)" CHANGELOG.md; then
  printf '  ✓ %-46s %s\n' "CHANGELOG.md entry" "## $canonical present"
else
  printf '  ✗ %-46s %s\n' "CHANGELOG.md entry" "no '## $canonical' section found"
  fail=1
fi

echo
if [ "$fail" -ne 0 ]; then
  echo "✗ version drift — bring every location in line with plugin.json ($canonical), then re-run."
  exit 1
fi
echo "✓ all version strings match $canonical"
