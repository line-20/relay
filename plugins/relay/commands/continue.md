---
description: Continue the next phase from a handover (prefers the shared copy on main) — verify the branch, then execute
argument-hint: "[optional item slug or handover path; defaults to the thread matching this branch]"
---

> **Output** ([[conventions]]): honour `verbosity` (a per-call `terse`/`verbose` word in `$ARGUMENTS`, else `relay.config.local.json` `.verbosity`, else `normal`) — at **terse**, emit only STOP-gate questions and the final landing, no narration or intermediate recaps. Honour `audience` (a per-call `plain`/`informed`/`expert` word in `$ARGUMENTS`, else `relay.config.local.json` `.audience`, else unset) — the technical register of your prose: `plain` = non-technical, no jargon; `informed` = architecture, trade-offs and named patterns, no code/syntax/flags unless they are the point or asked; `expert` = full implementation depth; unset ⇒ today’s default (no register shaping). Render every list (candidates / findings / plan rows) as a **GFM markdown table**, never stacked `Field: value` records or ASCII-rule separators; keep cells terse, overflow to numbered footnotes.

Continue the next phase of work from a handover file and carry it out.

> **Relay convention.** This command reads durable state from `<root>/board.md`
> (the front-door index) and `<root>/handover/next-*.md` (cold-start handovers),
> both committed to `main`. If your repo doesn't have them yet, run
> `/init` once to scaffold them.

## Step 0 — Resolve the Relay root
Durable state lives under a per-repo root — default `relay/`, overridable via a `relay.config.json`
at the repo root (`{ "root": "docs" }`). Resolve it once; read every `<root>/…` path below relative
to it. Absent config (or no `root` key) ⇒ `<root>` = `relay`, so existing repos are unchanged.
```bash
ROOT="$(jq -r '.root // "relay"' relay.config.json 2>/dev/null || echo relay)"
```
**Soft check:** if the resolved `<root>/board.md` is nowhere to be found (not on `origin/main`, not
local), STOP and say so plainly — e.g. *"root `docs` configured but `docs/board.md` missing — run
`/init`?"* — rather than failing deep in a later step.

## Step 1 — Find the thread to continue (board first, then its handover)
Under parallel worktree sessions there is **no single newest handover** — threads
interleave. So resolve the *thread* via the board, then open *that thread's* handover.
Board + handovers are committed to main, so a fresh worktree picks them up even before
main is merged in locally.

1. `git fetch origin main` to refresh the shared board + handovers.
2. Read the board: `git show FETCH_HEAD:<root>/board.md` — the **Open threads** table is
   the authoritative index of what's in flight.
3. **Pick the thread:**
   - If `$ARGUMENTS` names an **item slug** (`track/slug`) or a handover timestamp/path,
     use that exact one.
   - Else match the **current branch** (`git branch --show-current`) to an Open-threads
     row's `Owner` — that's this worktree's thread.
   - Else, if exactly one thread is `⚙ in-progress`, use it. If several are, or none is,
     **list the Open-threads rows and ask which** rather than guessing.
4. **Open its handover:** read the row's `Latest handover` path via
   `git show FETCH_HEAD:<root>/handover/<...>` (no checkout needed). If the row has no
   handover (`—`), work from its detail/brief doc instead.
5. Fallback (no board, or empty): newest handover on main —
   `git ls-tree -r --name-only FETCH_HEAD <root>/handover/ | grep -E 'next-.*\.md$' | sort | tail -1`
   — or newest local `ls -t <root>/handover/next-*.md 2>/dev/null | head -1`. If neither
   exists, STOP — nothing to continue.
6. Remember the item slug, source, and filename you used; report them in Step 4.

## Step 1.5 — Get into the thread's topic worktree (ALWAYS — don't ask)
`/continue` **always works in a git worktree** — never directly on `main` in the shared
checkout. Do NOT ask worktree-or-main; just do it. Worktrees are **keyed to the topic, not
the slice**: one stable tree per topic, the slice-branch inside it rotates. So resuming a
thread means getting into its *topic* tree and checking out its branch there.

1. The handover's `branch:` frontmatter is the thread's *last* branch; the **topic** is the
   item's track — the `<track>/` prefix of its slug (`pricing/increment-h` → `pricing`), or the
   slug's first hyphen-segment if it has no `/`.
2. **Shipped-or-resume — decide which branch you're checking out.** A handover written by a
   mid-thread `/handover` pause hands back an **in-flight** slice; one written by `/ship` hands
   back a thread whose slice **already shipped** and whose "Next objective" is the *next* slice.
   Tell them apart, then pick the **target branch**:
   ```
   git fetch origin main
   # SHIPPED if the branch is gone (deleted on merge) OR already folded into main:
   git rev-parse --verify --quiet <handover-branch> || git rev-parse --verify --quiet origin/<handover-branch> \
     || echo "branch absent → shipped"
   git merge-base --is-ancestor <handover-branch> origin/main 2>/dev/null && echo "merged → shipped"
   ```
   - **Branch missing, or an ancestor of `origin/main` → shipped.** The old branch is done (`/ship`
     merged its PR and `--delete-branch` removed it — so on the shipped path the ref is usually
     *gone*, which is why a bare `merge-base` would error rather than answer; the absence IS the
     signal). Confirm with `gh pr view <handover-branch> --json state` (MERGED) if unsure. You are
     **starting the next slice**: target branch = a fresh slice-branch named from the handover's
     **Next-objective item slug** (flat last segment, status-quo style — `pricing/slice-c` →
     `slice-c`), cut off fresh `origin/main`. This is the `/next` re-baseline path, reached via
     `/continue` because the thread is ⚙ in-progress with a handover.
   - **Branch exists and is not yet merged → in-flight.** Target branch = the handover's `<branch>`;
     you resume it as-is.
   - **No handover at all** (Step 1.4's brief-only thread) → treat as **shipped-shape**: no branch to
     resume, so cut a fresh slice-branch named from the item slug off `origin/main`.
3. If this session is **already inside the topic worktree with the target branch checked out**
   (`git branch --show-current` matches and the cwd is under the worktree dir), you're done.
4. Otherwise **get into the topic worktree**, then check out the target branch per the case above:
   - Find the topic's worktree in `git worktree list` (dir ending in `/<topic>`). If it exists,
     **enter it**; else **create it** named for the topic:
     ```
     EnterWorktree({ path: "<that path>" })          # reuse — switching in is allowed even mid-worktree
     # — or, if none exists —
     EnterWorktree({ name: "<topic>" })              # create .claude/worktrees/<topic> (branch <topic>, off origin/main)
     ```
     **If an existing tree is dirty with someone else's in-flight work, STOP and surface it** —
     never `reset --hard` or discard it; ask how to proceed.
   - **Check out the target branch:**
     ```
     # in-flight — resume the existing branch as-is (do NOT re-baseline; that would nuke the WIP):
     git switch <target>                              # or `git switch -c <target> origin/<target>` if it's only on the remote

     # shipped — re-baseline the tree to fresh main, then cut the next slice-branch:
     git reset --hard origin/main && git switch -C <target> origin/main
     ```
     (On the **create** path the tool leaves a branch named `<topic>`; `switch -C <target>` above
     rotates you onto the slice-branch, so the `<topic>` branch is just an unused ref — harmless.)
   - Never `git checkout`/`git switch` in the main checkout — that risks clobbering another
     session's tree.
5. **Capture the worktree root and hold it for the whole session.** Run
   `git rev-parse --show-toplevel` — the result is the worktree dir, NOT the main checkout.
   **Every** Edit/Write/Read `file_path` for the rest of this thread MUST begin with that
   worktree root. The file tools require *absolute* paths, so "use relative paths" does NOT
   protect you here — muscle-memory main-checkout paths (and every handover's `file:line`
   citation) all point at the WRONG tree. When you open a file a handover cites, rewrite
   the path onto the worktree root before Reading it.
6. Fresh worktrees lack untracked files (e.g. `.env`) — if you'll run the app, copy any
   the app needs from the main checkout first.

## Step 2 — Verify we're in the right place (the one gate)
1. `git branch --show-current`, compare to the **target branch** from Step 1.5.2 — the handover's
   `branch:` in the **in-flight** case, or the fresh next-slice branch in the **shipped** case
   (NOT the frontmatter branch, which is the merged predecessor).
   - After Step 1.5 these should match by construction. **If they still differ, STOP** —
     show both branches and ask to confirm; something is off with the worktree.
2. `git status` — in the **in-flight** case, if the working tree doesn't match the handover's
   "In flight" section, note it briefly and keep going. In the **shipped** case the tree is a
   clean re-baseline off `origin/main` (In flight was "None") — expect it clean.

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
`git -C <worktree-root> status --porcelain` (the root from Step 1.5.5) — the files you just
changed MUST appear. **If it's empty, you edited the main checkout by absolute-path
mistake — STOP.** Move those files onto the worktree root and revert the main checkout;
leave any *other* session's in-flight files in main untouched. A green typecheck/test over
an empty worktree diff is a false green — it exercised the unchanged baseline, not your change.

## Step 5 — Report
State which **board item** (`track/slug`) and which handover you continued (origin/main
or local, plus the filename). When you reach the done-criteria (or get blocked),
summarise what you changed (files + commits), what's left, and anything the user should
know. `/handover` will fold the outcome back into `<root>/board.md` at the end of the session.
