---
name: gc
description: Reclaim orphaned git worktrees left by sessions that skipped the happy path — auto-remove only the provably-finished ones, report the risky ones, prune dead entries. Not needed in normal use; run from the main checkout when orphans pile up.
argument-hint: "(no arguments)"
---

The garbage collector. **On the happy path you never need this** — every `/ship` ends by
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

> **Resolve the root first:** durable state lives under the per-repo root (default `relay/`; a
> `relay.config.json` `{ "root": "docs" }` at the repo root overrides). Resolve once —
> `ROOT="$(jq -r '.root // "relay"' relay.config.json 2>/dev/null || echo relay)"` — the board read
> below uses `<root>/board.md`.

## Step 1 — Take inventory
```bash
git worktree list --porcelain
git branch --merged main --format='%(refname:short)'   # branches already merged into main
```
For **each** worktree (skip the main checkout):
- **branch** — its checked-out branch
- **topic** — worktrees are keyed to a topic (its dir name), not a slice; a clean topic tree on
  a merged branch is the **normal resting state between slices**, not garbage
- **topic still live?** — does an **open or queued** board item share this topic (i.e. will the
  next `/next`/`/continue` re-baseline and reuse this tree)? Refresh with `git fetch origin
  main` + read `git show FETCH_HEAD:<root>/board.md` if the board exists
- **locked?** — a `locked` line means a session marked it in-use; treat as untouchable
- **dirty?** — `git -C <path> status --porcelain` non-empty → uncommitted work
- **merged?** — is its branch in the `--merged main` list
- **age** — `git -C <path> log -1 --format=%cr`

## Step 2 — Classify
- **KEEP — live topic tree** — clean and its **topic is still live** on the board (open/queued
  work will reuse it). A merged branch here is expected, NOT a reason to remove — this is the
  whole point of topic-scoped worktrees. Leave it be.
- **SAFE to auto-remove** — `merged` **AND** not `dirty` **AND** not `locked` **AND** its topic
  is *not* live (nothing queued will reuse it — a genuine orphan or a shipped-and-done topic).
- **RISKY — ask first** — anything `dirty`, `locked`, or `unmerged`.

## Step 3 — Report before acting
Print a plain-language table, one row per worktree with its verdict — **"remove (merged &
clean, topic done)"**, **"keep — live topic tree"**, **"keep — uncommitted changes"**, **"keep
— locked"**, **"keep — not yet merged"**. Don't bury it; this is where the user catches a
mistake — especially a live topic tree that used to look like removable garbage.

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
