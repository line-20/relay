# Changelog

All notable changes to Relay. Versions follow [semver](https://semver.org); the plugin's
version lives in `plugins/relay/.claude-plugin/plugin.json`.

To pick up a new version, colleagues refresh via the `/plugin` manager — `/plugin marketplace
update line-20` then update the `relay` plugin. Their repos' `relay/` folders are their own
data and are never touched by an update.

## 0.4.0

**Added**
- **`/cross-check`** — build a durable **reference frame** (`relay/reference/<topic>.md`) of how
  other products, standards, and prior art handle a problem, and check your approach against it
  for alignment, divergence, blind spots, and reinvention. Reusable and cumulative; uses web
  search when the environment has it, otherwise the model's own knowledge (flagged as such).
  `/brainstorm` now offers it at the end (Step 3.5) before a design is committed. `relay-init`
  scaffolds `relay/reference/`.
- **`/garbage-collect`** — reclaim orphaned worktrees left by sessions that skipped the happy
  path (crashed, or `/clear`ed without a handover). Not needed in normal use — `/wrapup` cleans
  up after itself; this is the off-happy-path escape hatch. Auto-removes only provably-finished
  sibling worktrees, reports the risky ones, never force-removes another session's tree.

**Changed**
- **Uniform review reports.** `/review-pr` now writes to one fixed template every time — set
  frontmatter (incl. a `counts` block), a standard Verdict line, findings in one identical
  per-finding format (`**ID** · area · file:line — problem. **Fix:** … (specialist)`) ordered
  🔴→🟡→🟢, and always-present section headings (empty ones say `_None._`). No specialist gets
  its own format; the report reads the same regardless of which ones ran.
- **`/next` renamed to `/whats-next`** — clearer about the question it answers, and less
  collision-prone. (If you had a habit or alias on `/next`, update it.)

## 0.3.0

**Changed**
- **Command tiers made explicit.** The README now separates the commands you *drive* the loop
  with (`/relay-init`, `/brainstorm`, `/next`, `/continue`, `/wrapup`) from the ones the loop
  *composes* (`/review-pr`, `/fix-pr-review`, `/handover`) — the latter carry an in-file note
  that they're normally run by `/wrapup` and standalone only when you specifically need one.

**Removed**
- **`/start-new`** is gone. Its jobs were folded into `/handover` (which `/wrapup` runs): a new
  Step 4.5 archives superseded handovers + old PR reviews into `archive/`, and Step 6 now also
  prunes dead worktree entries. End-of-session housekeeping now happens automatically at the
  end of every `/wrapup` — there's no separate cleanup command to remember. The one behaviour
  change: a finished **sibling** worktree is now *reported* for you to remove, never
  force-removed, so the loop can't clobber another live session's tree.

## 0.2.0

**Added**
- **`/brainstorm`** — the front of the loop. Turns a rough idea into a shaped brief on the
  board: it interrogates the idea one theme at a time, weighs two or three real alternatives
  (keeping the product/UX lens separate from the architecture/data-model lens), recommends
  one, and writes `relay/briefs/<slug>.md` + a board row. It never builds — `/next` picks the
  item up when you're ready. The ship loop is now **`/brainstorm → /next → /wrapup`**
  (`/wrapup` runs the review, merge, and handover at the end); `/handover` + `/continue`
  remain the mid-thread pause/resume pair for when you stop without shipping.

## 0.1.0

Initial release.

- **Commands:** `/relay-init`, `/next`, `/continue`, `/review-pr`, `/fix-pr-review`,
  `/wrapup`, `/handover`, `/start-new`.
- **Review agents** (dispatched by `/review-pr`): backend, frontend, ui-ux, api-architect,
  dbms, test-engineer, security, privacy, i18n, solution-architect — all stack-agnostic.
- **Meta-skill:** `authoring-skills`, for adding your own commands and agents.
- **Docs:** quickstart, the board model, a day in the loop, authoring guide.
- All workflow state namespaced under a single `relay/` folder in the target repo.
