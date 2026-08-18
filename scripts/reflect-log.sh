#!/usr/bin/env bash
#
# reflect-log.sh — the Relay movement logger (phase 2). A Claude Code UserPromptSubmit hook target.
#
# The trail records outcomes (a merged PR, a review's blockers, a logged decision) but NOT the
# movement stream: which Relay command ran, when, in what order — and so it can't see a flow you
# abandoned, or how long a lap took. This appends ONE JSON line per Relay command submitted. It is
# the reliable half; /reflect reconstructs the richer signals (an overridden /next pick, a gate you
# pushed past) by CORRELATING this stream against the durable trail, rather than trusting a command
# to remember to record its own outcome.
#
# Install it per dogfooding repo (or user-global) — see .claude/commands/reflect.md. It writes to
# <repo>/<root>/movements.jsonl, which reflect-gather.sh then pools. Never fails the prompt: any
# problem just exits 0 so a logging hiccup never blocks your work.
#
set -uo pipefail

payload="$(cat 2>/dev/null || true)"
command -v jq >/dev/null 2>&1 || exit 0

prompt="$(printf '%s' "$payload" | jq -r '.prompt // empty' 2>/dev/null || true)"
cwd="$(printf '%s'    "$payload" | jq -r '.cwd // empty'    2>/dev/null || true)"
[ -n "$prompt" ] || exit 0

# Only Relay commands: the /relay:* namespace and the short-name twins (/rle, /rln, /rls, …).
case "$prompt" in
  /relay:*|/rl*) : ;;
  *) exit 0 ;;
esac

[ -n "$cwd" ] || cwd="$PWD"
root="$(jq -r '.root // "relay"' "$cwd/relay.config.json" 2>/dev/null || echo relay)"
log="$cwd/$root/movements.jsonl"
mkdir -p "$(dirname "$log")" 2>/dev/null || exit 0

cmd="$(printf '%s' "$prompt" | awk '{print $1}')"
args="$(printf '%s' "$prompt" | cut -s -d' ' -f2-)"
ts="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

jq -cn --arg ts "$ts" --arg cmd "$cmd" --arg args "$args" --arg cwd "$cwd" \
  '{ts:$ts, cmd:$cmd, args:$args, cwd:$cwd}' >> "$log" 2>/dev/null || exit 0
exit 0
