---
name: start-new
description: >-
  End-of-session reset: clean up git worktrees safely, archive superseded
  handovers and PR reviews, then remind the user to clear context. Auto-removes
  ONLY the genuinely stale worktrees (branch merged into main AND clean tree AND
  not locked) and REPORTS the risky ones (dirty, locked, or unmerged), asking
  before touching them — a sibling session may be actively working in one.
---

# Start new — end-of-session reset

Run at the end of a session, terminal still open, to tidy the worktrees and hand back a
clean slate for the next piece of work.

Housekeeping for the worktrees this repo uses for isolated work. The goal: drop the
worktrees that are safely done, leave everything with unsaved or in-flight work untouched,
and hand back a clean slate.

## The one hard rule

**Multiple sessions may share this one checkout, each owning a live worktree with
uncommitted work.** A `git worktree remove --force` destroys untracked *and* tracked
uncommitted files — there is no undo. So this **auto-removes only provably-safe worktrees**
and asks before anything else. Never force-remove a worktree just because the user said
"clean them all" — surface the risky ones first.

You are almost certainly **running inside the main checkout**, not a worktree — this
operates on the sibling worktrees, never on the checkout it's invoked from. If
`git rev-parse --show-toplevel` is itself a worktree, stop and tell the user to run this
from the main checkout instead.

## Steps

### 1. Take inventory

```sh
git worktree list --porcelain
git branch --merged main --format='%(refname:short)'   # branches already merged into main
```

For **each** worktree (skip the main checkout):
- **branch** — its checked-out branch
- **locked?** — a `locked` line means a session marked it in-use; treat as untouchable
- **dirty?** — `git -C <worktree_path> status --porcelain` non-empty → uncommitted work
- **merged?** — is its branch in the `--merged main` list above
- **age** — `git -C <worktree_path> log -1 --format=%cr` (last-commit relative time)

### 2. Classify
- **SAFE to auto-remove** — `merged` **AND** not `dirty` **AND** not `locked`.
- **RISKY — ask first** — anything that is `dirty`, `locked`, or `unmerged`.

### 3. Report before acting
Print a plain-language table: one row per worktree with its verdict —
**"remove (merged & clean)"**, **"keep — uncommitted changes"**, **"keep — locked"**,
**"keep — not yet merged"**. Don't bury it; this is the moment the user catches a mistake.

### 4. Remove the safe ones
```sh
git worktree remove <worktree_path>    # no --force; it refuses if actually dirty (belt-and-braces)
```
If a bare `remove` refuses, do **not** reach for `--force` — reclassify it as RISKY and
report it. Optionally delete the orphaned merged branch: `git branch -d <branch>`
(lowercase -d refuses unmerged branches).

### 5. Prune orphans
```sh
git worktree prune -v   # drops administrative entries for dirs already deleted by hand
```

### 6. Ask about the risky ones
List the RISKY worktrees and ask, one decision at a time, whether to remove any. Only use
`git worktree remove --force` / `git branch -D` on a worktree the user **explicitly** names.
If they say "all of them", still name each one back and confirm.

### 7. Archive stale handovers & PR reviews
`/handover` and `/review-pr` mint a new file every session, so `relay/handover/` and
`relay/pr-reviews/` grow without bound. This sweeps the **superseded** ones into `archive/`
subfolders — nothing is deleted, git keeps full history, so it's always safe and reversible.

The rule is "keep only what's still live":
- **Handovers** — the board's *Open threads* table is the source of truth for which
  handovers are still in flight. Archive every loose `relay/handover/next-*.md` whose
  basename is **not** linked from `relay/board.md`; keep the ones the board still points at.
- **PR reviews** — a review doc is a one-shot artifact consumed at merge time. Keep the
  **20 most recent** loose `relay/pr-reviews/*.md` and archive the rest.

Use `git mv` so history follows the file (macOS bash is 3.2 — no `mapfile`; use a plain
counter loop). Then verify no doc's links broke:

```sh
# --- handovers: archive loose ones the board no longer references ---
grep -oE 'handover/next-[0-9-]+\.md' relay/board.md | sed 's#handover/##' | sort -u > /tmp/href.txt
for f in relay/handover/next-*.md; do
  b=$(basename "$f")
  grep -qx "$b" /tmp/href.txt || git mv "$f" "relay/handover/archive/$b"
done

# --- PR reviews: keep newest 20 loose, archive the rest ---
mkdir -p relay/pr-reviews/archive; i=0
for f in $(ls -t relay/pr-reviews/*.md); do
  i=$((i+1)); [ "$i" -le 20 ] && continue
  git mv "$f" "relay/pr-reviews/archive/$(basename "$f")"
done

# --- verify: no tracked doc links to a handover that just moved to archive/ ---
for f in $(git ls-files 'relay/*.md' | grep -v '^relay/handover/'); do
  for link in $(grep -oE 'handover/next-[0-9-]+\.md' "$f" 2>/dev/null | sort -u); do
    [ -f "relay/$link" ] || echo "FIX stale link in $f -> relay/$link"
  done
done
```

If the verify step prints a `FIX` line, repoint that link to `handover/archive/…` before
finishing. Report a one-line count of what was archived. If nothing qualified, say so.

Commit the sweep on `main` with the worktree cleanup (these are main-owned records):
`git add -A relay/ && git commit`.

### 8. Remind about context
A command runs *inside* the current conversation and **cannot clear its own context**.
Finish with this literal reminder line:

> Worktrees tidied. To start fresh, type **`/clear`** (or **`/compact`** to keep a
> summary) — I can't do that step for you.

## Notes
- Never touch the main checkout or the `main` branch.
- Never `--force` without an explicit per-worktree yes.
- If `git worktree list` shows a path that no longer exists, that's what `prune` (step 5)
  is for — don't try to `remove` it.
