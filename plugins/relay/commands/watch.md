---
description: Park the current thread on a dependency and watch it land in the background — a PR, another board item, or a sibling branch — then auto-resume this work once it's on main.
argument-hint: "[what to wait for: a PR number (#434), a board item (track/slug), or a branch name]"
---

> **Output** ([[conventions]]): honour `verbosity` (a per-call `terse`/`verbose` word in `$ARGUMENTS`, else `relay.config.local.json` `.verbosity`, else `normal`) — at **terse**, emit only STOP-gate questions and the final landing, no narration or intermediate recaps. Honour `audience` (a per-call `plain`/`informed`/`expert` word in `$ARGUMENTS`, else `relay.config.local.json` `.audience`, else unset) — the technical register of your prose: `plain` = non-technical, no jargon; `informed` = architecture, trade-offs and named patterns, no code/syntax/flags unless they are the point or asked; `expert` = full implementation depth; unset ⇒ today’s default (no register shaping). Render every list (candidates / findings / plan rows) as a **GFM markdown table**, never stacked `Field: value` records or ASCII-rule separators; keep cells terse, overflow to numbered footnotes.

You've hit a dependency: this thread can't sensibly go further until something *another* session
is doing lands on `main`. Rather than sit and poll, or forget and build on sand, `/watch` parks
this thread, watches the dependency in the background, and **auto-resumes** the moment it lands.

`$ARGUMENTS` names what to wait for. If empty, ask.

> **Resolve the root first:** durable state lives under the per-repo root (default `relay/`; a
> `relay.config.json` `{ "root": "docs" }` at the repo root overrides). Resolve once —
> `ROOT="$(jq -r '.root // "relay"' relay.config.json 2>/dev/null || echo relay)"` — and read every
> `<root>/…` path below relative to it.

## Step 1 — Resolve the dependency and its "landed" signal
Work out *what* you're waiting for and *how you'll know it landed* — pick by what `$ARGUMENTS`
looks like:
- **A PR number** (`#434` / `434`) → landed when `gh pr view <n> --json state,mergedAt` reports
  **MERGED**.
- **A board item** (`track/slug`) → landed when that item's row on `<root>/board.md` (on
  `origin/main`) reaches **✅ / done**. **This is the signal to prefer when no PR exists yet** —
  a sibling that's still committing locally has no PR to watch, but when it eventually ships via
  its own `/ship`, its board row flips. Watch the board, not the PR.
- **A branch** (`some-feature`) → landed when it's merged into main
  (`git branch --merged origin/main` lists it, or `git ls-remote` shows it gone after a
  delete-on-merge).
- **Uncommitted sibling work with no branch/PR/board item yet** → there is nothing durable to
  watch. Say so: tell the user this dependency isn't trackable yet, suggest they ask the other
  session to at least push a branch or add a board item, and offer to watch *that* once it exists.

## Step 2 — Park this thread (durably, so the wait survives /clear)
Record the block on the board so it's not just in this session's head:
- Refresh the board from main and set this item's row to **⏸ parked**, `Owner = —`, with a
  `blocked-on: <#PR | track/slug | branch>` note (in the row or the item's brief). Commit it to
  `main` with the temp-index push `/handover` uses — no branch switch.
- **Keep the worktree and its work exactly as-is** — you're pausing, not handing off. Don't
  release it; you'll resume in place.
- Write a one-line local marker of where to pick up (the next action you were about to take), so
  the resume in Step 4 doesn't have to reconstruct it.

## Step 3 — Watch in the background (don't block the foreground)
Poll the landed-signal from Step 1 **in the background** using whatever scheduling/background
capability you have — a background shell loop, a scheduled wake-up, a monitor — re-checking on a
sensible cadence (every few minutes; match it to how long the dependency realistically takes,
not every 30 seconds). **Do not freeze the session waiting** — the user keeps working elsewhere,
and you surface only when something changes. If you have no background mechanism at all, tell the
user you'll re-check whenever they nudge you, and stop there.

While watching, if the dependency's state goes somewhere terminal-but-not-merged (PR **closed
unmerged**, branch deleted without merging, board item **parked/abandoned**), **stop watching and
tell the user** — the thing they were waiting for isn't coming, and that's a decision for them.

## Step 4 — On landing: auto-resume
When the dependency lands:
1. Announce it: "✅ `<dependency>` landed — resuming `<this item>`."
2. Bring it in: `git fetch origin main` and merge (or rebase) `main` into this worktree's branch
   so the just-landed work is present. If that conflicts, **STOP and surface the conflict** — a
   merge conflict is a judgment call, not something to auto-resolve.
3. Flip this item's board row back to **⚙ in-progress**, `Owner = <this branch>` (reclaiming it),
   committed to main.
4. **Continue the held work** from the marker in Step 2 — pick up exactly where you paused, now
   that the dependency is satisfied.

## Step 5 — Report
Say what you waited for, that it landed (with the merge SHA / PR link), and that this thread is
live again and resuming — plus anything the merge changed that affects the plan.
