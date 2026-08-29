#!/usr/bin/env bash
#
# reflect-sessions.sh — the Relay session telemetry scanner (Phase 1, Slice 1). Derives the
# "what it cost and how it ran" stream that the movements log (reflect-log.sh) and the durable
# trail don't record: which model ran a lap, how many tokens it burned, how long it took, and
# which Relay commands the session issued.
#
# It is OBSERVATIONAL and runs OUT OF BAND. Claude Code keeps every session transcript on disk
# under ~/.claude/projects/<slug>/<session-id>.jsonl; this reads those files and never touches a
# live session, so it adds zero latency to your work — unlike a Stop hook, which would re-parse a
# growing transcript on every single turn. Run it whenever you want fresh telemetry (reflect-gather
# calls it for you before pooling).
#
# It writes ONE JSON line per Relay session to a central file OUTSIDE all your repos — default
# ~/.relay/sessions.jsonl (override RELAY_SESSIONS). "Relay session" = a transcript that issued at
# least one /relay:* or /rl* command; everything else is skipped. The output is a derived CACHE of
# the transcripts: each run rewrites it in full, so it's idempotent and safe to re-run.
#
# Slice 1 captures only the transcript-derived spine (model / tokens / duration / stages). Git-state
# fields (files changed, durable-artefact references, PR checks) need capture while the worktree
# still exists and are Slice 2 — see relay/briefs/semantic-trail-phase1.md.
#
# Usage:
#   ./scripts/reflect-sessions.sh            # scan ~/.claude/projects, write ~/.relay/sessions.jsonl
#   RELAY_SESSIONS=/tmp/s.jsonl ./scripts/reflect-sessions.sh
#
set -uo pipefail

command -v jq >/dev/null 2>&1 || { echo "✗ jq is required" >&2; exit 1; }

projects="${CLAUDE_PROJECTS:-$HOME/.claude/projects}"
out="${RELAY_SESSIONS:-$HOME/.relay/sessions.jsonl}"
mkdir -p "$(dirname "$out")" 2>/dev/null || { echo "✗ cannot create $(dirname "$out")" >&2; exit 1; }

[ -d "$projects" ] || { echo "✗ no Claude projects dir at $projects" >&2; exit 1; }

# One transcript -> one session object. Streams the file (reduce inputs) so a day-long transcript
# never gets slurped whole into memory. Emits nothing for a file that issued no Relay command.
aggregate() { # <session-id> <transcript-path>
  jq -n -c --arg sid "$1" --arg tp "$2" '
    def bump($u): {
      input:          (.input          + ($u.input_tokens                     // 0)),
      output:         (.output         + ($u.output_tokens                    // 0)),
      cache_read:     (.cache_read     + ($u.cache_read_input_tokens          // 0)),
      cache_creation: (.cache_creation + ($u.cache_creation_input_tokens      // 0)),
      thinking:       (.thinking       + ($u.output_tokens_details.thinking_tokens // 0))
    };
    reduce inputs as $l (
      { v:1, session_id:$sid, transcript_path:$tp, ts_start:null, ts_end:null,
        cwd:null, repo:null, branch:null, stages:[], models:{}, subagents:{},
        tokens:{input:0,output:0,cache_read:0,cache_creation:0,thinking:0},
        files_raw:[], prs:[] };

      ( ($l.timestamp // null) as $t
        | if $t then
            ( if .ts_start==null or $t < .ts_start then .ts_start=$t else . end )
            | ( if .ts_end==null or $t > .ts_end then .ts_end=$t else . end )
          else . end )
      | ( if $l.cwd then .cwd=$l.cwd else . end )
      | ( if $l.gitBranch then .branch=$l.gitBranch else . end )
      | ( if $l.type=="user" and ($l.message.content|type)=="string"
          then .stages += [ $l.message.content
                            | scan("<command-name>(/(?:relay:|rl)[a-z:]*)</command-name>") | .[0] ]
          else . end )
      | ( if $l.type=="assistant"
          then
            # token + model spine for this turn — skip Claude Code injected <synthetic>
            # turns (not real inference; carry no meaningful usage)
            ( if ($l.message.usage != null) and (($l.message.model // "") != "<synthetic>")
              then ($l.message.usage) as $u
                | .tokens |= bump($u)
                | ( ($l.message.model // "unknown") as $m
                    | .models[$m] = ((.models[$m] // 0) + 1) )
              else . end )
            # which specialists this lap spawned (Agent/Task tool_use); per-agent token
            # cost is not exposed in this transcript format — a later refinement.
            | reduce ( ($l.message.content // [])[]?
                       | select(.type=="tool_use" and (.name=="Agent" or .name=="Task"))
                       | (.input.subagent_type // "unknown") ) as $a
                ( . ; .subagents[$a] = ((.subagents[$a] // 0) + 1) )
            # files this lap changed, straight from Edit/Write tool_use (immune to the
            # worktree being gone later — the transcript is the record)
            | .files_raw += [ ($l.message.content // [])[]?
                              | select(.type=="tool_use"
                                       and (.name=="Edit" or .name=="Write"
                                            or .name=="MultiEdit" or .name=="NotebookEdit"))
                              | (.input.file_path // .input.notebook_path // empty) ]
          else . end )
      # PR number, wherever it surfaces (gh output in a tool_result, a URL in prose)
      | .prs += [ ($l.message.content // "" | tostring) | scan("pull/([0-9]+)") | .[0] ]
    )
    # collapse only CONSECUTIVE duplicate stages (two real /rlt runs apart stay two)
    | .stages |= reduce .[] as $s ([]; if .[-1]==$s then . else .+[$s] end)
    | .repo = ( (.cwd // "") | sub("/\\.claude/worktrees/.*$";"") | split("/") | last )
    # normalise changed files to session-root-relative; drop scratchpad/tmp writes outside it
    | ( (.cwd // "") + "/" ) as $base
    | .files = ( .files_raw
                 | map(select(type=="string" and ($base|length)>1 and startswith($base)) | ltrimstr($base))
                 | unique )
    | .artefacts = ( .files | map(select(test("^relay/"))) )   # durable Relay surfaces (default root)
    | .prs = ( .prs | map(tonumber?) | unique )
    | del(.files_raw)
    | select( (.stages|length) > 0 )
  ' < "$2" 2>/dev/null
}

tmp="$(mktemp)"
scanned=0; emitted=0
# glob depth: ~/.claude/projects/<slug>/<uuid>.jsonl
shopt -s nullglob
for tp in "$projects"/*/*.jsonl; do
  scanned=$((scanned+1))
  # cheap pre-filter: skip transcripts that never issued a Relay command
  grep -qE '<command-name>/(relay:|rl)' "$tp" 2>/dev/null || continue
  sid="$(basename "$tp" .jsonl)"
  if line="$(aggregate "$sid" "$tp")" && [ -n "$line" ]; then
    printf '%s\n' "$line" >> "$tmp"
    emitted=$((emitted+1))
  fi
done
shopt -u nullglob

# sort newest-first by ts_end for a stable, readable file
if command -v sort >/dev/null 2>&1; then
  jq -s -c 'sort_by(.ts_end) | reverse | .[]' "$tmp" > "$out" 2>/dev/null || mv "$tmp" "$out"
else
  mv "$tmp" "$out"
fi
rm -f "$tmp" 2>/dev/null || true

echo "Scanned $scanned transcript(s); wrote $emitted Relay session(s) → $out" >&2
echo "$out"
