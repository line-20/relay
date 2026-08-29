# Manual real-work recovery test (harvest slice 1)

_How to validate the slice against a **real** Relay work item by hand:
active worker → durable checkpoint → destroy the session → rediscover → fresh Continue,
with **no** Claude `/resume` and **no** transcript lookup. Read `docs/harvest-design.md` for the design._

Everything runs through `scripts/relay_harvest.py`. Substitute `$REPO` for the real repo (e.g. `~/Documents/castles-erp`) and `$RH=<this-repo>/scripts/relay_harvest.py`.

## 0. Pick a real in-flight item

```bash
python3 "$RH" --repo "$REPO" discover
```

Choose an item whose row shows a resolved `worktree` (a live topic worktree), e.g. `pricing/document-model`. Note its `branch` and `worktree`.

## 1. Active worker does its work

In a normal Claude Code session, work the item in its topic worktree as usual. Nothing new here.

## 2. Make it durable (checkpoint + harvest) — before you stop

**a. Local checkpoint** (offline-safe; commits WIP, no network):
```bash
python3 "$RH" --repo "$REPO" checkpoint "$WORKTREE" "$LAP_ID"   # -> a commit SHA
```

**b. Emit the structured harvest result** (the worker builds this from what it did — references to already-durable state + disposition + resume delta):
```bash
cat <<JSON | python3 "$RH" --repo "$REPO" emit
{"harvest_version":1,"lap_id":"$LAP_ID","work_item":"pricing/document-model",
 "disposition":"stopped:needs-judgment",
 "references":{"branch":"$BRANCH","head_sha":"$SHA","brief":"relay/briefs/…-brief.md","pr":719},
 "resume_delta":{"stage":"build","next_slice":"…the next concrete slice…",
   "in_flight":"clean","scope_edges":["…"],"open_questions":["…"]}}
JSON
```

**c. Runtime persists it** (idempotent; writes the canonical checkpoint + a projected handover):
```bash
python3 "$RH" --repo "$REPO" apply
```

After this the durable state exists at `$REPO/relay/harvest/pricing__document-model/checkpoint.json`.

## 3. Destroy the Claude session

Close the terminal, force-quit VS Code, or kill the session. **Do not record the Claude session id.** This is the "worker disappears" step — forced loss, the normal case.

## 4. Rediscover — fresh Relay, zero session knowledge

```bash
python3 "$RH" --repo "$REPO" discover                     # the item is listed, worktree resolved
python3 "$RH" --repo "$REPO" bootstrap pricing/document-model   # provider-neutral resume payload
```

`bootstrap` returns the worktree, branch, brief path and resume delta with `requires_transcript:false`, `requires_session_id:false`. No `/resume`, no transcript, no session id was used.

## 5. Fresh Continue — a brand-new worker

Open a **new** Claude Code session and run:
```
/relay:continue pricing/document-model
```
Continue's checkpoint-first step (see `continue.md` Step 1) reads
`relay/harvest/<slug>/checkpoint.json` as the authoritative resume state — the Markdown
handover is only a projection/fallback. The new worker lands in the right worktree on the
right branch and continues from `resume_delta`.

*(Provider-neutral variant: hand the `bootstrap` JSON to any coding agent — it has everything to `cd` into the worktree, read the brief, inspect the repo with git, and continue, without the previous transcript.)*

## Pass criteria

- The item is rediscovered from durable state alone (board + git worktree + checkpoint).
- The fresh worker resumes in the correct worktree/branch from the resume delta.
- `/resume` was never used; no transcript or session id was located.
- Re-running `apply` changes nothing (idempotent); works with no network.

## What this exercised on real data (2026-08-29)

- `discover` parsed the **real** castles-erp board and matched the genuinely in-flight items
  (`pricing/document-model`, `finance/money-evidence`, `platform/deploy-reconcilers`) to their
  real worktrees.
- `bootstrap` produced a correct provider-neutral payload for a real worktree
  (`.claude/worktrees/pricing+document-model`, branch `documents-allowance-enforce`) **without
  writing anything into the real repo** (a scratch relay-root held the checkpoint; worktree
  discovery used real git).
- Real validation caught and fixed a branch-parsing bug (free-text `branch:` frontmatter →
  malformed `(none`) the synthetic fixture had hidden.
