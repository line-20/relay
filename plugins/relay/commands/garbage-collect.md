---
name: garbage-collect
description: Reclaim orphaned git worktrees left by sessions that skipped the happy path — auto-remove only the provably-finished ones, report the risky ones, prune dead entries. Not needed in normal use; run from the main checkout when orphans pile up.
argument-hint: "(no arguments)"
---

The garbage collector. **On the happy path you never need this** — every `/wrapup` ends by
releasing its own thread's worktree and pruning dead entries, so a session that runs to
completion cleans up after itself. This command exists for the times it *doesn't*: a session
`/clear`ed without a handover, one that crashed, or a worktree abandoned mid-experiment. It
sweeps those orphans from the **main checkout**. Archival of old handovers/reviews is NOT here
— that happens in `/handover`; this is worktrees only.

## The one hard rule
**Multiple sessions share this one checkout, each may own a live worktree with uncommitted
work.** `git worktree remove --force` destroys tracked *and* untracked changes with no undo. So
this **auto-removes only provably-safe worktrees** and asks before anything else. Never
force-remove just because the user said "clean them all" — surface the risky ones first.

Run this from the **main checkout**. If `git rev-parse --show-toplevel` is itself a worktree,
stop and tell the user to run it from the main checkout instead.

## Step 1 — Take inventory
```bash
git worktree list --porcelain
git branch --merged main --format='%(refname:short)'   # branches already merged into main
```
For **each** worktree (skip the main checkout):
- **branch** — its checked-out branch
- **locked?** — a `locked` line means a session marked it in-use; treat as untouchable
- **dirty?** — `git -C <path> status --porcelain` non-empty → uncommitted work
- **merged?** — is its branch in the `--merged main` list
- **age** — `git -C <path> log -1 --format=%cr`

## Step 2 — Classify
- **SAFE to auto-remove** — `merged` **AND** not `dirty` **AND** not `locked`.
- **RISKY — ask first** — anything `dirty`, `locked`, or `unmerged`.

## Step 3 — Report before acting
Print a plain-language table, one row per worktree with its verdict — **"remove (merged &
clean)"**, **"keep — uncommitted changes"**, **"keep — locked"**, **"keep — not yet merged"**.
Don't bury it; this is where the user catches a mistake.

## Step 4 — Remove the safe ones
```bash
git worktree remove <path>    # no --force; it refuses if actually dirty (belt-and-braces)
```
If a bare `remove` refuses, do **not** reach for `--force` — reclassify as RISKY and report it.
Optionally delete the orphaned merged branch: `git branch -d <branch>` (lowercase -d refuses
unmerged branches).

## Step 5 — Prune orphans
```bash
git worktree prune -v   # drops entries for dirs already deleted by hand
```

## Step 6 — Ask about the risky ones
List the RISKY worktrees and ask, one decision at a time, whether to remove any. Only use
`git worktree remove --force` / `git branch -D` on a worktree the user **explicitly** names. If
they say "all of them", still name each back and confirm — the clobber hazard is real.

## Step 7 — Report
One line: how many removed, how many pruned, how many kept and why. If nothing qualified, say so
— don't invent work.
