---
description: Continue the next phase from a handover (prefers the shared copy on main) — verify the branch, then execute
argument-hint: "[optional item slug or handover path; defaults to the thread matching this branch]"
---

Continue the next phase of work from a handover file and carry it out.

> **Relay convention.** This command reads durable state from `relay/board.md`
> (the front-door index) and `relay/handover/next-*.md` (cold-start handovers),
> both committed to `main`. If your repo doesn't have them yet, run
> `/relay-init` once to scaffold them.

## Step 1 — Find the thread to continue (board first, then its handover)
Under parallel worktree sessions there is **no single newest handover** — threads
interleave. So resolve the *thread* via the board, then open *that thread's* handover.
Board + handovers are committed to main, so a fresh worktree picks them up even before
main is merged in locally.

1. `git fetch origin main` to refresh the shared board + handovers.
2. Read the board: `git show FETCH_HEAD:relay/board.md` — the **Open threads** table is
   the authoritative index of what's in flight.
3. **Pick the thread:**
   - If `$ARGUMENTS` names an **item slug** (`track/slug`) or a handover timestamp/path,
     use that exact one.
   - Else match the **current branch** (`git branch --show-current`) to an Open-threads
     row's `Owner` — that's this worktree's thread.
   - Else, if exactly one thread is `⚙ in-progress`, use it. If several are, or none is,
     **list the Open-threads rows and ask which** rather than guessing.
4. **Open its handover:** read the row's `Latest handover` path via
   `git show FETCH_HEAD:relay/handover/<...>` (no checkout needed). If the row has no
   handover (`—`), work from its detail/brief doc instead.
5. Fallback (no board, or empty): newest handover on main —
   `git ls-tree -r --name-only FETCH_HEAD relay/handover/ | grep -E 'next-.*\.md$' | sort | tail -1`
   — or newest local `ls -t relay/handover/next-*.md 2>/dev/null | head -1`. If neither
   exists, STOP — nothing to continue.
6. Remember the item slug, source, and filename you used; report them in Step 4.

## Step 1.5 — Get into the thread's worktree (ALWAYS — don't ask)
`/continue` **always works in a git worktree** — never directly on `main` in the shared
checkout. Do NOT ask worktree-or-main; just do it.

1. The thread's branch is the `branch:` line in the handover frontmatter.
2. If this session is **already inside the worktree for that branch** (`git branch
   --show-current` matches and the cwd is under the worktree dir), you're done — continue.
3. Otherwise **enter/create the worktree for that branch**. If your harness has a native
   worktree tool, use it; otherwise `git worktree add`. If one already exists for the
   branch, enter it. Never `git checkout`/`git switch` in the main checkout — that risks
   clobbering another session's tree.
4. **Capture the worktree root and hold it for the whole session.** Run
   `git rev-parse --show-toplevel` — the result is the worktree dir, NOT the main checkout.
   **Every** Edit/Write/Read `file_path` for the rest of this thread MUST begin with that
   worktree root. The file tools require *absolute* paths, so "use relative paths" does NOT
   protect you here — muscle-memory main-checkout paths (and every handover's `file:line`
   citation) all point at the WRONG tree. When you open a file a handover cites, rewrite
   the path onto the worktree root before Reading it.
5. Fresh worktrees lack untracked files (e.g. `.env`) — if you'll run the app, copy any
   the app needs from the main checkout first.

## Step 2 — Verify we're in the right place (the one gate)
1. `git branch --show-current`, compare to the `branch:` line in the handover frontmatter.
   - After Step 1.5 these should match by construction. **If they still differ, STOP** —
     show both branches and ask to confirm; something is off with the worktree.
2. `git status` — if the working tree doesn't match the handover's "In flight" section,
   note it briefly and keep going.

## Step 2.5 — Run any project setup the handover names
A handover often follows a merge that shipped schema/dependency changes. If the handover
(or your project's `CLAUDE.md`/README) names a setup step to run after a merge — install,
migrate a local database, regenerate something — run it now, **best-effort and non-fatal**.
If it can't run (a service isn't up), note it and continue rather than stopping.

## Step 3 — Say what the next step is, then PAUSE
A handover is often picked up days later, cold. So before doing anything, orient the user:
- In a few plain-English sentences, state **what this thread is** and **what the next
  step is** (the handover's "Next objective") — no jargon or shorthand to decode.
- Then **STOP and wait for the go-ahead on the topic.** Don't propose a solution yet,
  don't touch code. The user might redirect, defer, or confirm.

## Step 3.5 — Describe the solution(s), then PAUSE
Once the topic is OK'd:
- Describe the solution — or a couple of options if there's a real choice — in **short,
  plain, simple English**. What you'd build/change and why, at a level that can be approved
  without reading code. Keep it brief; this is a direction check, not a design doc.
- Then **STOP and wait for direction or approval.** Only start building once told go.

## Step 3.6 — Dependency pre-flight (does this need a sibling thread's work first?)
Before building, check whether resuming this thread depends on something **another live
session** is doing that isn't on `main` yet — the parallel-work trap of building on an API,
component, or schema a sibling is still writing.
1. **Gather what siblings are doing:** `git worktree list` + the board's ⚙/🔍 rows and their
   handovers. For each sibling, collect what it's changing — committed (`git -C <path> diff
   --name-only origin/main...HEAD`) **and** uncommitted (`git -C <path> status --porcelain`).
   A sibling need not have a PR — local or uncommitted work still signals an incoming change.
2. **Flag a dependency — conservative, plus file-overlap:** *explicit* (this thread's
   handover/brief names another item, PR, or branch as needed) or *file-overlap* (files you'll
   touch overlap with what a sibling is introducing). Don't infer deep deps from incidental overlap.
3. **If found, surface it and ask** — start anyway (note the assumption) or **hold**. On hold,
   hand to **`/watch`** (park ⏸ with `blocked-on: …`, watch it land, auto-resume). If nothing
   overlaps, say one line and continue.

## Step 4 — Do the work
With topic and approach approved, carry out the handover's "Start here" steps, then
continue toward the "Next objective" within its "Done when" scope. Stay inside the scope
edges the handover names. If you hit a genuine fork the handover doesn't cover, make the
reasonable call and note it rather than stalling.

**Path gate — after your FIRST batch of edits, before running any check:** confirm the
edits actually landed in the worktree, not the main checkout. Run
`git -C <worktree-root> status --porcelain` (the root from Step 1.5.4) — the files you just
changed MUST appear. **If it's empty, you edited the main checkout by absolute-path
mistake — STOP.** Move those files onto the worktree root and revert the main checkout;
leave any *other* session's in-flight files in main untouched. A green typecheck/test over
an empty worktree diff is a false green — it exercised the unchanged baseline, not your change.

## Step 5 — Report
State which **board item** (`track/slug`) and which handover you continued (origin/main
or local, plus the filename). When you reach the done-criteria (or get blocked),
summarise what you changed (files + commits), what's left, and anything the user should
know. `/handover` will fold the outcome back into `relay/board.md` at the end of the session.
