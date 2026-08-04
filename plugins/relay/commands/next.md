---
description: Recommend the next best thing to work on — a ranked shortlist from the board, at one of three depths (quick / verify / audit), then start the one you pick in a worktree
argument-hint: "[track/theme/slug; or 'verify' (thorough shortlist) / 'audit' (exhaustive all-items + archival)]"
---

Answer one question in plain, simple English: **what's the next best thing to work on?**
Then, once picked, start it in a worktree.

This is NOT `/continue`. `/continue` **resumes an in-flight thread** from its handover.
`/next` **surveys what's queued** and recommends where to start — an item that has no
handover yet, just a brief. Keep them distinct: `/next` never resumes ⚙/🔍 work (that's
already owned by a live session).

## Three levels — pick by `$ARGUMENTS`
The levels differ ONLY in how hard they verify before ranking. Steps 1–2 (read board, filter to
startable) and Steps 3–6 (rank, present, worktree, start) are shared. What changes is the middle.

- **L1 · Quick (default).** Rank from the board's one-liners; spot-check only the ~5 finalists
  against their briefs (**Step 3.5**). Seconds. Trusts the board. Use for a fast "what's next".
- **L2 · Verify** — `$ARGUMENTS` contains `verify`, `check`, `thorough`, or `deep`. Rebuild the
  ranking from **ground truth for the shortlist**: fan out one research agent per plausible
  contender (~8–10) across its board row + full brief + pr-reviews + handovers + git/code, so the
  recommendation is accurate, not just board-deep (**Step 2.9A** replaces Step 3.5). Minutes.
- **L3 · Audit** — `$ARGUMENTS` contains `audit`, `archive`, `exhaustive`, `compact`, or `full`. A
  **board audit**, not just a recommendation: reconcile **EVERY** startable item against **all
  sources** — board, briefs, pr-reviews, handovers, code, and GitHub history (`gh pr`/`gh issue`).
  Its primary product is a **dated, committed archival report**; the shortlist falls out as a
  byproduct. It can then **compact the board** — archive shipped briefs, slim Open threads to just
  live work — as a confirmed follow-through (**Step 2.9B step 5**). Can take a long time — that's
  expected (**Step 2.9B** replaces Step 3.5). Use to true-up the whole board.

(Any other argument — a track, theme, or exact slug — biases the candidate set at *any* level.)

## Step 1 — Read the board (the curated front door, fetched from main)
Do NOT sweep `docs/briefs/` blindly — the board already distils them.
1. `git fetch origin main` to refresh the shared board.
2. Read it: `git show FETCH_HEAD:docs/board.md`. The **Open threads** table and the
   **Tracks** section are the source of truth for what exists and its status.
3. Glyphs: 💡 idea (icebox) · 🔜 next (queued) · ⚙ in-progress · 🔍 in-review · ⏸ parked · ✅ done.

## Step 2 — Filter to what's actually startable
Keep only items that could be picked up **now**:
- ✅ include **🔜 next**, **⏸ parked** (note what it's waiting on), and the strongest **💡 ideas**.
- ❌ exclude **⚙ in-progress** and **🔍 in-review** — a live worktree already owns those
  (that's `/continue` / `/fix-pr-review` territory, not `/next`).
- ❌ exclude anything whose `Owner` column names a live branch/worktree.
- If `$ARGUMENTS` is given, use it to bias the filter (a track name, a theme, or an exact slug
  to jump straight to Step 4).

## Step 2.9A — L2 (VERIFY) ONLY: research the shortlist from ground truth (fan-out)
Skip unless L2. Replaces Step 3.5 — research the plausible contenders, not just spot-check five,
so the ranking rests on what's actually true rather than the board's one-liner.

1. Take the startable set from Step 2 and keep the **~8–10 most promising** contenders (drop the
   obvious non-starters). Note any you deferred — never silently drop the tail.
2. **Fan out one research agent per contender, in parallel**, in a single message so they run
   concurrently. Give each the item slug and this brief:
   > Research board item `<slug>` for a "what to work on next" decision. Read (a) its board row
   > in `docs/board.md`, (b) its full brief/detail doc, (c) any `pr-reviews/` file naming it and
   > its latest handover, (d) `git log`/`git grep` for its code area. Report: **real current
   > status** (what's actually shipped vs the board's claim), **startable-now?** (yes /
   > blocked-on-what), **staleness** (does the board row or brief disagree with the code? quote
   > the drift), **rough size** (S/S–M/M/L + is it an epic), **leverage** (what it unblocks / what
   > gap it closes), and **2–3 evidence pointers** (commit shas, file:line, brief/PR section).
   > Be concrete; cite, don't assert.
3. Collect the verdicts. Rank from **those**, by the Step 3 criteria — ground truth overrides
   the board wording every time.
4. Gather every **drift** the agents found into a short list to show under the table, and
   **offer to fix them** (offer, don't auto-write — the board is main-owned and shared).

## Step 2.9B — L3 (AUDIT) ONLY: reconcile EVERY item, all sources, then archive
Skip unless L3. This is a **board audit**; the ranked shortlist is a byproduct. Expect a long run
and real token cost — completeness beats speed.

1. **Candidate set = every startable item** from Step 2 — do NOT cap. If it's very large, note the
   count and process in batches; never silently drop items (a silent cap defeats an audit).
2. **Fan out one research agent per item** (or run it as a workflow if your harness has one, so
   it's resumable and progress-visible). Each reconciles the item across all sources:
   > Audit board item `<slug>`. Read: (a) its board row(s) in `docs/board.md`; (b) its full
   > brief/detail doc; (c) every `pr-reviews/` file that names it; (d) every `docs/handover/`
   > (incl. `archive/`) that names it; (e) the actual code (`git log`/`git grep`/read files); (f)
   > GitHub history (`gh pr list --search <slug>`, `gh issue list --search <slug>`, relevant merged
   > PRs). Return STRUCTURED: `{slug, realStatus, boardStatus, startable, blockedOn, staleness:
   > [{source, boardSays, truthIs, evidence}], size, leverage, recommendedNextSlice, evidence:[]}`.
   > Cite every claim (sha / file:line / PR# / handover path). Do not assert without a source.
3. **Write the archival report** to `docs/board-audit/<timestamp>.md` (get `<timestamp>` from a
   `date +%Y-%m-%d-%H%M` Bash call). Structure: a summary (item count, how many rows drifted), a
   per-item table (slug · board status · real status · drift? · size · startable), a **Drift ledger**
   (every board/brief row that disagrees with reality, with the exact fix), and the **ranked
   shortlist**. Commit it to main (it's a durable record the board can't hold).
4. Present the shortlist (Step 3 table) as usual, then point at the committed report and **offer
   to apply the Drift ledger** to the board in one pass (offer, don't auto-write).

### Step 2.9B step 5 — offer to COMPACT the board (the archival half of the audit)
The audit has already located every ✅ done item and every stale row — compaction is the *action*
on that finding. This is the goal: shrink the board back to a short "what's still open" list.

Present a **compaction plan** and, only on explicit go-ahead, apply it in **one confirmed pass**:
- **Archive shipped briefs.** For each ✅ item the audit *verified as actually shipped*, move its
  brief `docs/briefs/<slug>.md` → `docs/archive/`, and drop its row from the **Open threads**
  table, leaving a one-line ✅ trace on its track's Done line. Never a silent delete — the full
  record lives in git + the committed report.
- **A ✅-claimed row the code contradicts does NOT get archived** — it stays put and goes in the
  Drift ledger instead. Only verified-shipped items leave the board.
- **Result:** Open threads holds only 🔜 / ⚙ / 🔍 / ⏸ + the strongest 💡 — the short open list.
- **Write discipline:** offer, don't auto-write; **one atomic pass**; the board is main-owned. Commit
  the board edit + brief moves **together, on main** (via the temp-index pattern `/handover` uses —
  never switch the working branch).
- If declined, leave everything as-is — the report already records what *could* be compacted.

## Step 3 — Rank and present a SHORT shortlist (this is the whole point)
Pick the **best ~5** and rank them. Ranking is **not recency** — it's:
- **Unblocked** — no open decision/dep in its way (a ⏸ item only ranks if its blocker is now cleared).
- **High-leverage** — unblocks other work, or closes a real gap (security/correctness earn a bump).
- **Right-sized** — a slice that fits one session; note if it's a multi-session epic.
- Recency/freshness breaks ties only.

Open a brief (via the board's **Detail** column) only for an item that makes the shortlist and
needs a sentence to explain or size it.

### Step 3.5 — L1 (QUICK) ONLY: sanity-check the shortlist before presenting (the ~5 finalists)
(L2 does this deeper in Step 2.9A; L3 in Step 2.9B — skip 3.5 at those levels.)
The board's one-line status can drift from the brief. Verify ONLY the finalists — cheap because
it's ~5 items, not the whole board:
- Read each shortlisted item's **brief progress header** and a quick `git log --oneline -15 --
  <its area>`. Confirm it isn't already done, already owned by a live worktree, or resting on a
  premise that's since gone stale.
- **If the board and the brief disagree, trust the brief** and flag it: `⚠ board stale — says X,
  brief says Y`. Don't silently rank on the board's word.
- **Offer to fix drift; do NOT auto-write it.** The board is main-owned and shared — surface the
  drift and offer to patch the row/brief as a separate, confirmed step.

Present it as a **markdown table** — no preamble, plain English, one row per item. Mark the
recommended pick with a ⭐. Use **t-shirt sizes** (S / S–M / M / L), and tag an L item as an epic
where only the first slice fits a session.

**Keep cells terse or the table stops rendering.** Hard rules:
- Each cell is **one short clause (~≤8 words)**. If you need more, it goes in a footnote, not the cell.
- **No `⚠`, italics, parentheticals, or drift notes inside cells.** Any caveat becomes a numbered
  footnote `¹²³` under the table.
- Five columns only, in this order. Don't widen it.

> | # | Item | What it is | Why now | Size |
> |---|---|---|---|---|
> | **1** ⭐ | `track/slug` | <one short clause> | <one short clause> | **S–M** |
> | **2** | `track/slug` | … | … ¹ | **L** |
>
> ⭐ = my pick.
> ¹ <the caveat / verify-first / drift note that would otherwise have bloated the cell>
>
> **Parked, not clean to start:** `slug` (<what's blocking it>) · …

Then ask which one — or offer that the user can name a different board item. **Stop here and wait**
unless `$ARGUMENTS` already named an exact item slug.

## Step 4 — On pick: worktree first (ALWAYS — never the shared main checkout)
Like `/continue`, `/next` **always works in a git worktree**. Do NOT ask worktree-or-main.
1. Derive a short branch/worktree name from the item slug (e.g. `pricing/increment-h` → `increment-h`).
2. Create/enter it (a native worktree tool if your harness has one, else `git worktree add`). If one
   already exists for that branch, enter it. **Never** `git checkout`/`git switch` in the main
   checkout (clobbers other sessions).
3. If you'll run the app, copy any untracked files it needs (e.g. `.env`) from the main checkout first.

## Step 5 — Start the first slice from the brief
The item has no handover yet — work from its **brief / roadmap detail**.
1. Read the item's detail doc.
2. Run any **pre-build checklist** the project's `CLAUDE.md` requires for a new feature/module.
3. Scope the first shippable slice, then start building it — don't stop to ask for a full plan;
   make reasonable calls and note them. `/handover` folds the outcome back into the board.

## Step 6 — Report
State the **board item** (`track/slug`) you started, the worktree/branch you're in, and the
first slice you're building.
