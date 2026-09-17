---
description: Reclaim orphaned git worktrees left by sessions that skipped the happy path — auto-remove only the provably-finished ones, report the risky ones, prune dead entries. Not needed in normal use; run from the main checkout when orphans pile up.
argument-hint: "(no arguments)"
---

## Usage
`/relay:gc`

| Argument | Effect |
|---|---|
| *(no arguments)* | Scans for orphaned worktrees; auto-removes only the provably-finished ones |

**Any command also takes** `small`·`medium`·`large` (session size) · `terse`·`verbose` (how much Relay narrates) · `plain`·`informed`·`expert` (terminal depth) · `ask`·`challenge`·`solo` (who decides) — per-call, winning over `relay.config.local.json` ([[conventions]]).

> **`?` prints this and stops.** If `$ARGUMENTS` is exactly `?`, `help`, `--help` or `-h`, print the
> signature line, the argument table and the words/config line above — verbatim, nothing else, not
> even this note — then **STOP**: no tools, no preamble, no action. `/relay:help <command>` prints
> the same thing.

> **Output** ([[conventions]]): honour `verbosity` (a per-call `terse`/`verbose` word in `$ARGUMENTS`, else `relay.config.local.json` `.verbosity`, else `normal`) — at **terse**, emit only STOP-gate questions and the final landing, no narration or intermediate recaps. Honour `audience` (a per-call `plain`/`informed`/`expert` word in `$ARGUMENTS`, else `relay.config.local.json` `.audience`, else unset) — how much depth surfaces in your **terminal** output; it never thins a **written artifact** (brief, report, ADR, handover), which always keeps full depth. `plain` = executive summary: the decisions and what you need from the user, minimal jargon; `informed` = lead with the decisions and what changed, keep the corrections and open questions that need the user, defer exhaustive evidence/`file:line` tables to the artifact; `expert` = full depth in the terminal too; unset ⇒ today’s default (no shaping). Never drop a STOP-gate question or the decision itself. Render every list (candidates / findings / plan rows) as a **GFM markdown table**, never stacked `Field: value` records or ASCII-rule separators; keep cells terse, overflow to numbered footnotes.

The garbage collector. **On the happy path you never need this** — every `/ship` ends by
releasing its own thread's worktree and pruning dead entries, so a session that runs to
completion cleans up after itself. This command exists for the times it *doesn't*: a session
`/clear`ed without a handover, one that crashed, or a worktree abandoned mid-experiment. It
sweeps those orphans from the **main checkout**. Archival of old handovers/reviews and other
**content** housekeeping is NOT here — that's `/tidy` (per-ship, `/handover` does a subset); this
is git **worktrees** only.

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
Get `origin/main` current **first** — every "merged?" and "ahead" number below is measured against
it, and a stale ref makes both lie (the classic failure: a shipped branch looks unmerged because
your local `origin/main` predates its merge). Then pull the merged-PR list **once**: this repo
**squash-merges**, so a shipped branch's own commits never become ancestors of `main`, and plain
git ancestry (`git branch --merged`, `--is-ancestor`) calls *every* squash-merged branch "unmerged"
— that mislabel is exactly why shipped worktrees used to pile up here. `gh` is optional: offline, we
fall back to the ancestry-free count and let anything uncertain go to the RISKY list rather than
guess.
```bash
git fetch -q origin main               # make origin/main honest before measuring anything
git worktree list --porcelain

# Authoritative "did it ship?" for a squash-merge repo — matched later by branch name.
# Empty when gh is absent/offline; the per-worktree count still runs.
MERGED_PRS=""
command -v gh >/dev/null 2>&1 && \
  MERGED_PRS="$(gh pr list --state merged --limit 500 --json headRefName --jq '.[].headRefName' 2>/dev/null)"
```
For **each** worktree (skip the main checkout):
- **branch** — its checked-out branch
- **topic** — worktrees are keyed to a topic (its dir name), not a slice; a clean topic tree on
  a merged branch is the **normal resting state between slices**, not garbage
- **topic still live?** — does an **open or queued** board item share this topic (i.e. will the
  next `/next`/`/continue` re-baseline and reuse this tree)? Read `git show
  FETCH_HEAD:<root>/board.md` (the fetch above already refreshed `FETCH_HEAD`) if the board exists
- **locked?** — a `locked` line means a session marked it in-use; treat as untouchable
- **dirty?** — `git -C <path> status --porcelain` non-empty → uncommitted work (this **includes**
  untracked `??` files, so an untracked file already forces RISKY on its own)
- **untracked WIP?** — does `git -C <path> status --porcelain` have any `??` line? Track this
  separately: committed work survives on the branch and in the reflog, but an **untracked file
  exists on no branch** — it is the one genuinely-losable thing a worktree can hold. Never a
  candidate for auto-removal, and always named explicitly in the report.
- **ahead** — `git -C <path> rev-list --count origin/main..HEAD` — commits this branch has that
  `origin/main` does not. This is the primary **"does it hold unique work?"** signal, and it
  **replaces the old `git branch --merged` ancestry check**.
- **merged?** — TRUE when **either**: `ahead` is `0` (tip fully on `main` — catches true
  fast-forward / merge-commit merges and rebased-flat branches, no network needed), **or** the
  branch name is in `MERGED_PRS` (its PR is merged — this is the arm that clears a **squash-merged**
  branch, whose `ahead` stays non-zero because its own commits were never replayed onto `main`).
  Offline with no `gh`, only the first arm can fire, so squash-merged branches stay RISKY instead of
  being removed on a guess.
- **age** — `git -C <path> log -1 --format=%cr`

## Step 2 — Classify
- **KEEP — live topic tree** — clean and its **topic is still live** on the board (open/queued
  work will reuse it). A merged branch here is expected, NOT a reason to remove — this is the
  whole point of topic-scoped worktrees. Leave it be.
- **SAFE to auto-remove** — `merged` **AND** not `dirty` **AND** not `locked` **AND** its topic
  is *not* live (nothing queued will reuse it — a genuine orphan or a shipped-and-done topic).
  With the `merged?` rule above, a **squash-merged-and-shipped** tree now lands here instead of
  festering in RISKY forever — the bug this command was rewritten to fix.
- **RISKY — ask first** — anything `dirty` (**including an untracked WIP file**), `locked`, or
  genuinely **unmerged**: `ahead > 0` **and** its PR is not merged — it holds unique commits that
  are on no `main` and in no merged PR. This is the hard floor: unique uncommitted or unmerged work
  is never auto-removed.

## Step 3 — Report before acting
Print a plain-language table, one row per worktree with its verdict — **"remove (merged &
clean, topic done)"**, **"keep — live topic tree"**, **"keep — untracked WIP (on no branch —
unrecoverable)"**, **"keep — uncommitted changes"**, **"keep — locked"**, **"keep — not yet
merged"**. Don't bury it; this is where the user catches a mistake — especially a live topic tree
that used to look like removable garbage, or an untracked file that is the only copy of some work.

## Step 4 — Remove the safe ones
```bash
git worktree remove <path>    # no --force; it refuses if actually dirty (belt-and-braces)
```
If a bare `remove` refuses, do **not** reach for `--force` — reclassify as RISKY and report it.
Optionally delete the orphaned branch afterwards — but mind the same ancestry trap: `git branch -d`
uses the exact `--merged` check that mislabels squash-merges, so it **refuses a squash-merged
branch** even though its PR shipped. For a branch classified `merged` **via its PR** (not via
`ahead == 0`), use `git branch -D`; that is safe here precisely because the merged-PR check already
proved the work is on `main`.

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
