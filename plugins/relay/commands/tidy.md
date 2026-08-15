---
description: Keep Relay's VOLATILE layer lean — prune spent handovers/reviews, trim done rows off the board, merge same-unit briefs — recurring, idempotent, and parallel-worktree-safe. Never touches durable output (code, ADRs, guides). Prune and trim already run per-lap inside /handover at the same `tidy.level`, so run this by hand for the rest (merges, brief archival) or for a deliberate sweep; a no-op when nothing's stale.
argument-hint: "[optional: a single op — prune|trim|merge — else all enabled; add 'dry-run' to report without writing]"
allowed-tools: Bash(git log:*), Bash(git status:*), Bash(git diff:*), Bash(git branch:*), Bash(git fetch:*), Bash(git read-tree:*), Bash(git add:*), Bash(git write-tree:*), Bash(git commit-tree:*), Bash(git push:*), Bash(git show:*), Bash(git ls-tree:*), Bash(git ls-files:*), Bash(git checkout:*), Bash(git rev-parse:*), Bash(git worktree:*), Bash(git mv:*), Bash(date:*), Bash(mktemp:*), Bash(rm:*), Bash(ls:*), Bash(grep:*), Bash(jq:*), Read, Write, Edit
---

## Usage
`/relay:tidy [prune|trim|merge] [dry-run]`

| Argument | Effect |
|---|---|
| `prune` / `trim` / `merge` | Run a single op instead of every enabled one |
| `dry-run` | Report what would change, write nothing |
| *(empty)* | Every op `tidy.level` enables |

**Any command also takes** `small`·`medium`·`large` (session size) · `terse`·`verbose` (how much Relay narrates) · `plain`·`informed`·`expert` (terminal depth) · `ask`·`challenge`·`solo` (who decides) — per-call, winning over `relay.config.local.json` ([[conventions]]). **Reads config:** `tidy.level`, `tidy.ops`, `tidy.retention`.

> **`?` prints this and stops.** If `$ARGUMENTS` is exactly `?`, `help`, `--help` or `-h`, print the
> signature line, the argument table and the words/config line above — verbatim, nothing else, not
> even this note — then **STOP**: no tools, no preamble, no action. `/relay:help <command>` prints
> the same thing.

> **Output** ([[conventions]]): honour `verbosity` (a per-call `terse`/`verbose` word in `$ARGUMENTS`, else `relay.config.local.json` `.verbosity`, else `normal`) — at **terse**, emit only STOP-gate questions and the final landing, no narration or intermediate recaps. Honour `audience` (a per-call `plain`/`informed`/`expert` word in `$ARGUMENTS`, else `relay.config.local.json` `.audience`, else unset) — how much depth surfaces in your **terminal** output; it never thins a **written artifact** (brief, report, ADR, handover), which always keeps full depth. `plain` = executive summary: the decisions and what you need from the user, minimal jargon; `informed` = lead with the decisions and what changed, keep the corrections and open questions that need the user, defer exhaustive evidence/`file:line` tables to the artifact; `expert` = full depth in the terminal too; unset ⇒ today’s default (no shaping). Never drop a STOP-gate question or the decision itself. Render every list (candidates / plan rows) as a **GFM markdown table**, never stacked `Field: value` records or ASCII-rule separators; keep cells terse, overflow to numbered footnotes.

The housekeeper for Relay's **volatile** layer. Working knowledge — briefs, plans, reviews, handovers,
the board — accretes as you ship; `/tidy` keeps it lean so the next session starts on a clean index.
It's built to run **often** (on demand, per-lap, or daily) and to be **cheap and idempotent** — when
nothing's stale it does nothing and says so.

> **Scope — volatile only, never durable.** `/tidy` operates on `<root>/` (briefs, handover, reviews,
> board) and **never** touches durable OUTPUT — code, ADRs, guides, procedures, how-tos, or anything a
> `paths.*` points at. Durable knowledge is moved out by `/persist`; this only keeps the input side
> tidy. It is the *content* counterpart to `/gc` (which reclaims orphaned git **worktrees**) — different
> job, don't conflate them.

> **You don't have to remember to run this.** PRUNE and TRIM both have a **per-lap trigger** in
> `/handover` Step 4.5 (and so in `/ship`), gated by the same `tidy.level` — a policy with no trigger
> is a policy that never fires. Running `/tidy` by hand is for the ops handover doesn't carry (MERGE,
> brief archival), for a repo that ships rarely, or for a deliberate sweep.

## The hard invariants (get these right)
- **Distil before prune.** Never archive/merge a brief whose durable content isn't harvested yet. A
  brief is *spent* only if it carries a **Distilled marker** (`**Distilled:** …`, stamped by `/persist`)
  **or** distillation is disabled for this repo (`persist.cadence: never` or `persist.level: none`).
  Otherwise **defer it to `/persist` and report** — don't touch it ([[conventions]] → *Persistence*).
- **Never touch live work.** A brief/topic is off-limits if its topic is **live** — the board `Owner`
  names a live worktree, status is ⚙/🔍, the worktree is `locked`, or the topic is still open/queued.
- **Parallel-worktree-safe.** ~10 sessions share one `main`. Write to main with the temp-index
  primitive and a **retry-replay loop** (Step 5); never clobber a sibling's commit.
- **Link-integrity is a hard gate.** Every move rewrites inbound **path** links and a repo-wide
  no-dangling-path-link check passes **before** commit (Step 4.5).
- **Conservative + reported.** Unsure whether something is spent ⇒ **keep it and report**, don't prune.

**Run from the main checkout.** If `git rev-parse --show-toplevel` is a worktree, stop and say so —
tidy edits shared main-owned files and must not run from inside a feature worktree.

## Step 0 — Resolve config
```bash
ROOT="$(jq -r '.root // "relay"' relay.config.json 2>/dev/null || echo relay)"
LEVEL="$(jq -r '.tidy.level // "standard"' relay.config.json 2>/dev/null || echo standard)"
PRUNE="$(jq -r '.tidy.ops.prune // true'  relay.config.json 2>/dev/null || echo true)"
TRIM="$(jq -r  '.tidy.ops.trim  // true'  relay.config.json 2>/dev/null || echo true)"
MERGE="$(jq -r '.tidy.ops.merge // "report"' relay.config.json 2>/dev/null || echo report)"
KEEP_REVIEWS="$(jq -r '.tidy.retention.reviews // 20' relay.config.json 2>/dev/null || echo 20)"
# distillation on? (governs whether a spent brief needs a Distilled marker before pruning)
PCADENCE="$(jq -r 'if (.persist|type)=="object" then .persist.cadence else .persist end // "ask"' relay.config.json 2>/dev/null || echo ask)"
PLEVEL="$(jq -r 'if (.persist|type)=="object" then .persist.level else null end // "standard"' relay.config.json 2>/dev/null || echo standard)"
```
`LEVEL` sets the op defaults when `tidy.ops.*` are absent — `none` ⇒ a no-op (report and stop);
`lean` ⇒ prune only (and, at the per-lap trigger, *report* what trim would clear); `standard` ⇒
prune + trim, merge report-only; `full` ⇒ prune + trim + merge with auto-apply allowed. Explicit
`tidy.ops.*` win over the preset — which is also how the per-lap trim gate records its one-time
answer (`tidy.ops.trim: true|false`), so an owner is asked once per repo and never again. A single-op arg (`prune`/`trim`/`merge`)
or `dry-run` in `$ARGUMENTS` narrows this run. **Distillation is disabled** when `PCADENCE = never` or
`PLEVEL = none` — in that case a shipped brief counts as spent without a marker.

## Step 1 — Take inventory (refresh from main first)
```bash
git fetch origin main
git show FETCH_HEAD:$ROOT/board.md > /tmp/relay-board.md 2>/dev/null   # authoritative board
git worktree list --porcelain                                          # live/locked topics
```
Gather the candidates each enabled op works on:
- **Handovers** — `$ROOT/handover/next-*.md` **not** linked from the board's *Open threads* / *Latest
  handover* column (a linked handover is live; keep it).
- **Reviews** — `$ROOT/reviews/*.md` beyond the newest `$KEEP_REVIEWS`.
- **Done rows** — *Open threads* rows whose status is ✅ done (shipped, left in flight).
- **Briefs** — `$ROOT/briefs/*.md`: same-unit pairs (one topic split across files) for MERGE, and
  shipped-and-spent briefs for archival.

## Step 2 — Classify every candidate against the guards
For each candidate decide **PRUNE / TRIM / MERGE / KEEP**, applying the invariants:
- A brief is **KEEP (deferred)** if it lacks a Distilled marker **and** distillation is enabled — note
  "→ run `/persist` first".
- A brief/row is **KEEP (live)** if its topic is owned by a live worktree, is ⚙/🔍, locked, or still
  open/queued on the board.
- Otherwise it's eligible for its op. **MERGE is the riskiest** (briefs can be mid-edit): default it to
  **report-only** — propose the merge, don't apply — and auto-apply only when `MERGE` is not `report`
  **and** both briefs are provably not-live.
- Anything ambiguous ⇒ **KEEP + report**.

## Step 3 — Report the plan, and STOP if anything is non-trivial
Print one table, a row per candidate with its verdict and reason — **"prune (handover, unlinked)"**,
**"prune (review, past retention)"**, **"trim (row done → ✅ line)"**, **"merge? (same unit — needs
approval)"**, **"keep (undistilled — persist first)"**, **"keep (live topic)"**. Pruning unlinked
handovers and windowing reviews is safe and may proceed without a gate; **any MERGE, any brief
archival, or a `dry-run` run STOPs here for approval** before touching a file. Nothing to do ⇒ say
"nothing to tidy" and stop.

## Step 4 — Apply the approved operations
Compute all moves first (so Step 5 commits them atomically). Never edit another worktree's files —
only main-owned content under `<root>/`.
- **PRUNE** — `git mv` unlinked handovers into `$ROOT/handover/archive/` and over-retention reviews
  into `$ROOT/reviews/archive/`. Nothing is deleted; git keeps full history. (This is the canonical
  home of `/handover` Step 4.5's archival logic.)
- **TRIM** — remove each done row from *Open threads* and collapse it to a one-line `✅ Done: <slug>`
  entry on its track (the `/next` compaction shape). A **near-done tail** (shipped, one loose end) is
  **not** trimmed away — it **stays an Open-threads row** (🔜/⏸) linking back to its source brief, so
  the board remains the single tracker (no separate residue file). (This is also the canonical home of
  `/handover` Step 4.5's per-lap trim.)
- **MERGE** (approved) — fold the same-unit briefs into one, de-duplicating overlap while **preserving
  all content**, then rewrite every inbound link (Step 4.5) and archive the emptied file.
- **COMPACT** — Relay's board keeps "done" as terse inline `✅ Done:` lines, so there's no growing
  done-log to compact; this op is a no-op unless a repo maintains such an artifact. Report it as skipped.
Archiving a **brief** additionally requires the Distilled invariant (Step 2) to have passed.

## Step 4.5 — Link-integrity gate (hard, before any commit)
Every move above may orphan an inbound reference. Rewrite **path** links to each moved file — the
board's `Detail` and `Latest handover` columns, `<root>/briefs/*.md` cross-links, `CLAUDE.md`
references — to their new location. Then scan the repo for any remaining **path** link that resolves to
nothing:
```bash
grep -rEno '\]\(([^)]+\.md)\)|`[^`]+\.md`' "$ROOT" 2>/dev/null   # candidate path links to verify
```
Verify each resolves to an existing file; **zero dangling path links is a hard gate** — if any remains,
do **not** commit: fix it or back the offending move out, and report. Name-based `[[wikilinks]]` are
stable under moves by design — **exempt** them from the check.

## Step 5 — Commit atomically on main, with a retry-replay loop
All moves land as **one** archival commit on `main`, using the temp-index primitive (no branch switch)
`/handover` uses — wrapped so a sibling push that landed mid-run is **merged, not clobbered**:
```bash
for attempt in 1 2 3; do
  git fetch origin main
  # recompute the moves against FETCH_HEAD's tree here (re-read the board, re-stage the renames)
  TMPIDX="$(mktemp)"; GIT_INDEX_FILE="$TMPIDX" git read-tree FETCH_HEAD
  # ... GIT_INDEX_FILE="$TMPIDX" git add <the moved/rewritten paths> ...
  TREE="$(GIT_INDEX_FILE="$TMPIDX" git write-tree)"
  COMMIT="$(git commit-tree "$TREE" -p FETCH_HEAD -m "chore(tidy): prune/trim <counts>")"
  rm -f "$TMPIDX"
  if git push origin "$COMMIT:main"; then break; fi     # rejected ⇒ main moved; loop re-integrates
  [ "$attempt" = 3 ] && { echo "main kept moving — STOP, files correct locally, retry later"; break; }
done
```
Re-derive the moves inside the loop against the **freshly fetched** board so a sibling's changes are
carried forward. After three rejected pushes, **STOP and report** (the moves are correct locally;
nothing is lost) rather than forcing.

## Step 6 — Report
One compact landing: counts pruned / trimmed / merged, how many **kept** and why (undistilled → persist,
or live topic), and that link-integrity passed. If it was a clean no-op, say **"nothing to tidy"** — a
valid, common outcome, not a failure. If any brief was **deferred for distillation**, name it and point
at `/persist`. To run this automatically, note the cadence is wired via the harness scheduler
(`/schedule` / cron) or `/loop` — `/tidy` doesn't schedule itself.
