# Command-level (per-stage) telemetry model

_Phase 2.5 of the Relay-runtime instrumentation: `observe → **segment**`. Observability only — it derives nothing, changes no Relay behaviour, and introduces no lifecycle contracts._

## Why it exists

Session-level telemetry (`~/.relay/sessions.jsonl`, from `reflect-sessions.sh`) records a whole Claude Code session as one unit. But a session usually runs several Relay commands — a lap is commonly `/rlc → /rlt → /rls` in one sitting (35 sessions do exactly that). So session telemetry can't say which command spent the tokens, changed the files, or spawned the reviewers. **`session ≠ stage`.**

This layer splits each session into **command spans** and records one per Relay command, so tokens/files/artefacts/sub-agents attach to the command that actually did them.

## Where it sits

Three files, one system, all central under `~/.relay/` (outside every repo), all derived from the on-disk Claude Code transcripts (`~/.claude/projects/*/*.jsonl`):

| File | Grain | Producer |
|---|---|---|
| `movements.jsonl` | one line per Relay command *submitted* | `reflect-log.sh` (UserPromptSubmit hook) |
| `sessions.jsonl` | one line per session (rollup) | `reflect-sessions.sh` (batch scan) |
| **`commands.jsonl`** | **one line per Relay command span** | **`reflect-commands.py` (batch scan)** |

`commands.jsonl` is **additive** — it does not replace or alter the other two (backward compatible). Each span carries `session_id`, so it joins back to `sessions.jsonl`. Override its path with `RELAY_COMMANDS`. Each run rewrites the file in full (idempotent) and backfills all history.

## How a span is found

The boundary is the `<command-name>` marker Claude Code writes into a transcript when a slash command is invoked. Walking the transcript in order, every turn belongs to the most recently opened command. A new `<command-name>` closes the current span and opens the next. Spans whose command isn't a Relay command (`/clear`, `/help`, and the pre-command preamble) are dropped — but only *after* they've absorbed their own turns, so their tokens never leak into a Relay span.

## Schema (`v: 1`)

```json
{
  "v": 1,
  "session_id": "0120878a-…", "seq": 2,
  "command": "/relay:rls", "next": null,
  "repo": "castles-erp", "branch": "…", "cwd": "…",
  "ts_start": "…", "ts_end": "…", "duration_s": 3120,
  "models": {"claude-opus-4-8": 88},
  "tokens": {"input": 12, "output": 185217, "cache_read": …, "cache_creation": …, "thinking": …},
  "tools": {"Bash": 40, "Edit": 12, "Agent": 3},
  "subagents": {"relay:security-specialist": 1, "relay:test-engineer": 1},
  "files": ["apps/api/src/routes.ts", "…"],
  "code_write_count": 8,
  "artefacts": ["relay/board.md", "relay/handover/…md"],
  "prs": [774], "errors": 0
}
```

`seq` is the span's 0-based position among the session's Relay commands; `next` is the following Relay command (or `null`) — together they reconstruct sequences and transitions. `artefacts` is the subset of `files` under the relay root — i.e. **writes to shared/global Relay state**, kept distinct from worker-local code writes (`code_write_count`). See "Global vs worker-local" below.

## Attribution honesty

- **observed** (directly in the span's turns): `command`, `models`, `tokens`, `tools`, `subagents` (which specialists), `files`, `prs`, `errors` (count of `is_error` tool results), timestamps.
- **derived**: `duration_s` (end − start), `artefacts` (files under `relay/`), `code_write_count`, `next`.
- **unavailable** (deliberately not invented):
  - *per-sub-agent token cost* — this Claude Code version writes no sidechain usage records; only which specialists ran is knowable, not what each cost.
  - *stage outcome / success* — no reliable deterministic signal; `errors` is a proxy, not a verdict.
  - *questions raised, decisions made* — need transcript-prose mining (a later slice); not captured here.

## Global vs worker-local (the concurrency lens)

Each span separates two kinds of write:
- **worker-local** — code in the isolated worktree (`code_write_count`, and `files` minus `artefacts`).
- **global/shared Relay state** — `artefacts`: `board.md`, `handover/`, `reviews/`, `decisions.md`, `knowledge/`, `briefs/`.

This is the raw material for the longer-term "workers produce results; the runtime owns global state" question — it shows *which stages* mutate shared state and *which surfaces*, without changing anything about how they do it today.

## Testing

`scripts/tests/test_reflect_commands.py` (stdlib `unittest`, no deps) drives a synthetic `/rlc → /rlt → /rls` transcript and asserts three spans with correctly isolated tokens, files, artefacts, sub-agents, errors, PR and transition chain — including that preamble and `/clear` turns don't leak into any Relay span. Run: `python3 scripts/tests/test_reflect_commands.py`.
