---
description: Generate a cold-start handover for the next phase, commit it to main, and print a compact terminal summary
argument-hint: "[optional focus, e.g. 'health monitoring metering']"
allowed-tools: Bash(gh pr view:*), Bash(git log:*), Bash(git status:*), Bash(git diff:*), Bash(git branch:*), Bash(git fetch:*), Bash(git read-tree:*), Bash(git add:*), Bash(git write-tree:*), Bash(git commit-tree:*), Bash(git push:*), Bash(git show:*), Bash(git ls-tree:*), Bash(git checkout:*), Bash(git rev-parse:*), Bash(date:*), Bash(mkdir:*), Bash(mktemp:*), Bash(rm:*), Bash(ls:*), Read, Write
---

Produce a self-contained prompt that a FRESH session — with no access to this
conversation — can act on immediately to begin the next phase, WITHOUT needing to
re-research the state of the project.

`$ARGUMENTS`, if present, is the focus/next target to plan around. If empty, infer the
next item from the roadmap/board.

> **Relay convention.** The durable records are `docs/board.md` and
> `docs/handover/next-*.md`, both on `main`. Run `/relay-init` once if your repo
> doesn't have them yet.

## Step 0 — Finish-the-loop guard
Before generating anything, make sure you're not handing over mid-flow:

```bash
gh pr view --json number,state,reviewDecision,url 2>/dev/null
```

- **No PR** (command empty/errors) → fine: a planning handover, or the work is already merged into main. Proceed.
- **state MERGED** → loop closed. Proceed.
- **state OPEN** → the loop isn't finished. Check `pr-reviews/` for a report on this PR; if none, it's also unreviewed. WARN and STOP:
  `⚠ Handing over with PR #<n> still open (<reviewed | UNREVIEWED>): <url>. The flow expects it merged first.`
  Ask to either finish the loop (`/fix-pr-review`, then merge) or reply "handover anyway" to continue. Wait for the answer.
- **state CLOSED (not merged)** → note it and ask the same way.

## Step 1 — Read the current state
1. `git branch --show-current`.
2. `git log --oneline -20`, then `git log --stat -5` — what landed recently.
3. `git status` and `git diff HEAD` — work in flight (staged, unstaged, untracked).
4. Read `docs/board.md` — the front-door index. Identify **which board item** this session advanced (its `track/slug`) and which item comes next. The board's **Open threads** table, not "newest file", is the source of truth for what's in flight.
5. Read `docs/roadmap.md` (if present) for the detailed narrative behind that item.
6. Read the handover the board links from *this* item (its "Latest handover" cell), if any, so you continue that thread rather than whatever file is newest by timestamp.
7. Draw on what you know from THIS session — decisions made, dead-ends hit, things deliberately deferred, things half-done — that git alone wouldn't reveal. This is the most valuable input. Do not skip it.

## Step 2 — Decide the next objective
- Name the board item (`track/slug`) the next session should pick up — an existing one, or a new slug you add to the right track.
- Ground it in the roadmap/brief: name the specific next phase/task and quote the relevant line(s).
- If `$ARGUMENTS` was given, plan around that, but still locate it on the board.
- If what comes next is ambiguous, say so in Open Questions rather than guessing silently.

## Step 3 — Write the handover (verbose is fine here)
This file is the durable record — be as detailed as it needs to be. It must STAND ALONE:
the next session has the repo's `CLAUDE.md` but no chat history.
- Refer to everything by path (and line where useful), never "the file we just edited".
- State decisions and their rationale explicitly — don't assume they're remembered.
- Front-load the research you just did so the next session doesn't repeat it.
- Pointers over dumps. Concrete.

`mkdir -p docs/handover`, capture the timestamp once with `TS=$(date +%Y-%m-%d-%H%M)`
(reuse it in Steps 4–5), and write to `docs/handover/next-$TS.md` using EXACTLY this
structure:

---
generated: <YYYY-MM-DD HH:MM>
branch: <branch>
item: <track/slug — the board item this thread belongs to>
phase: <roadmap phase/milestone>
---

# Handover: <next objective in a few words>

## Where we are
<2–3 sentences: the project, the current milestone, the immediate goal. Enough to orient cold.>

## What just landed
<Bullets. The last completed unit(s) of work with commit hashes / file paths. Include decisions or trade-offs that aren't obvious from the code.>

## In flight
<Uncommitted / half-done work, by path: what's done, what remains. "None — tree is clean." if so.>

## Next objective
<The next phase/task, grounded in the roadmap/brief (quote the relevant line). A goal, not a vague area.>

## Context you need (so you don't re-research)
<Key files and their roles FOR THIS TASK. Prior decisions, conventions, and gotchas that bear on the next chunk specifically. Not a tour of the repo.>

## Start here
<The first 2–4 concrete actions, specific enough to begin without exploration.>

## Done when
<Crisp done-criteria for this chunk. And the scope edges — what NOT to touch.>

## Open questions
<Anything unresolved the next session should decide or ask the user about. "None." if there are none.>

## Step 4 — Update the board, then commit both to main
The handover AND `docs/board.md` are durable records `/continue` reads from `origin/main`,
so both land on main — no branch, no PR — WITHOUT switching branches or disturbing your
working tree.

First bring the board to main's version and apply this thread's update to it. The board is
**main-owned** — always start from main's copy so you don't clobber a parallel session's edits:

```bash
git fetch origin main
git show FETCH_HEAD:docs/board.md > docs/board.md   # refresh to main's copy
```

Now edit `docs/board.md` for this thread's item (`item:` slug from the frontmatter):
- Update its row in the **Open threads** table — set `Status`, `Owner`, and
  `Latest handover` → `handover/next-$TS.md`. **`Owner` = `—` for a hand-off.**
  Writing a handover means you are RELINQUISHING the thread for a cold session to
  resume, so no live session owns it (the branch is still discoverable via the
  handover's `branch:` frontmatter). Only name a worktree/branch here when a
  *different* live session is actively on it — never your own, which you're ending;
  Owner = your own branch reads to `/continue` as "occupied" and blocks the pickup.
  Add the row if the item is new; if the item is now **done**, remove it from Open
  threads and move it to its track's ✅ Done line.
- Keep edits minimal and surgical — one thread, one item.

Then commit **both files** onto main via a temporary index (no branch switch, working tree untouched):

```bash
TMPIDX="$(mktemp)"
GIT_INDEX_FILE="$TMPIDX" git read-tree FETCH_HEAD
GIT_INDEX_FILE="$TMPIDX" git add "docs/handover/next-$TS.md" docs/board.md
TREE="$(GIT_INDEX_FILE="$TMPIDX" git write-tree)"
COMMIT="$(git commit-tree "$TREE" -p FETCH_HEAD -m "docs(handover+board): $TS — <item>")"
git push origin "$COMMIT:main"
rm -f "$TMPIDX"
git checkout HEAD -- docs/board.md 2>/dev/null || true   # restore branch's board; keep the feature branch clean
```

If the push is rejected (main moved on, or direct pushes to main are blocked), STOP and
say so — both files are already correct locally, so nothing is lost and the user can
commit them. The handover stays untracked on the current feature branch until main
propagates; that's expected.

## Step 5 — Print a COMPACT terminal summary
Do NOT paste the full handover into the terminal. Print only a short summary plus the
open questions:

```
📋 Handover → docs/handover/next-$TS.md   (pushed to main: <short-sha>)
   Item:   <track/slug>  →  <new status on the board>
   Next:   <next objective, one line>
   Landed: <what just landed, one line>
```

Then print the Open Questions IN FULL — these need attention before the next session:

```
❓ Open questions:
   - <question 1>
   - <question 2>
```

If there are none, print `❓ Open questions: none.`
If the push failed in Step 4, replace the `(pushed to main: …)` note with
`(NOT pushed — commit it yourself)` and say why.

Finally, hint the next step:
`→ Next session: /continue picks this up from main.`

## Step 6 — Leave a clean tree and release the worktree
End the session with **nothing stray left behind** — no orphaned handover file, no
half-written board, no worktree lock blocking the next `/continue`. This part regularly
gets skipped, so do it explicitly.

**Only if Step 4's push SUCCEEDED** (main now holds both files — the durable copy
`/continue` reads), clean the local working tree of the now-redundant artifacts:

```bash
rm -f "docs/handover/next-$TS.md"                        # committed to main via the temp index, but still UNTRACKED here
git checkout HEAD -- docs/board.md 2>/dev/null || true    # restore the branch's board (idempotent with Step 4)
git status --porcelain                                    # expect EMPTY
```

If `git status --porcelain` is empty, the tree is clean. **If anything *else* is stray,
report it and STOP — do NOT auto-delete unrelated work** (a parallel session may be mid-flight).

**If the push FAILED, skip the cleanup entirely** — those files are the only copy. Leave
them, keep the worktree, and the user will commit them.

Then release the worktree (if your harness has a native tool that refuses to remove a
dirty/unmerged tree, prefer it — it's self-protecting):
- **Loop closed** (this PR is MERGED, or there was no PR and the work is already on main;
  tree clean) → remove the worktree dir + branch, the clean end of a finished thread.
- **In flight** (unmerged — you handed over mid-thread) → keep the worktree/branch's work
  but drop any lock so the next `/continue` isn't blocked. Board `Owner = —` alone is NOT
  enough — a concurrent-session guard keys off the live process, not the board text.

Then remind the user to `/clear` this session before the cold one runs `/continue`.
