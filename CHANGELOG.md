# Changelog

All notable changes to Relay. Versions follow [semver](https://semver.org); the plugin's
version lives in `plugins/relay/.claude-plugin/plugin.json`.

To pick up a new version, colleagues refresh via the `/plugin` manager — `/plugin marketplace
update line-20` then update the `relay` plugin. Their repos' `relay/` folders are their own
data and are never touched by an update.

## 0.7.0

**Added**
- **Configurable root — adopt Relay without moving a file.** Relay's durable state (board,
  roadmap, briefs, handover, archive, board-audit, pr-reviews, reference) used to be hardcoded
  under `relay/`; a repo that already keeps this state elsewhere couldn't use the commands at all.
  Now the root is **configurable per repo**: drop a `relay.config.json` at the repo root with
  `{ "root": "docs" }` and every command reads and writes `docs/board.md`, `docs/handover/…`, etc.
  Every command resolves the root once at the top (a "resolve the Relay root" step) and interpolates
  `<root>/…` throughout; `continue`/`whats-next` add a soft existence check that points at
  `/relay-init` if the configured root has no board. **Fully back-compatible** — no config ⇒ root is
  `relay/`, so existing repos are unchanged. `/relay-init` gained `--root <dir>`: it writes the
  config (when non-default), scaffolds under the chosen root, or — if a board already exists there —
  **adopts** the existing structure by writing only the config, wiring a bespoke predecessor to the
  `relay:*` commands with zero migration. Docs (quickstart, the-board-model) document the root and
  the override.

## 0.6.0

**Added**
- **`/test-drive`.** After a chunk of work, open (or reuse) a draft PR and write a
  **consistent, structured test plan** into it — preconditions, happy path, and the
  edge/error/tenant-isolation cases an LLM skips by default — always the same shape, so testing a
  Relay PR is muscle memory. Grounds every step in the real diff and the project's `CLAUDE.md`
  invariants. Where the project publishes a **preview deploy** per PR, the plan targets that URL;
  otherwise it falls back to local-run steps. It can then **drive the happy path in the browser**
  against the preview (`drive`, or it asks once), running the fail-closed non-happy checks, capturing
  a GIF, and posting pass/fail back to the PR — with guardrails (no destructive actions unless
  authorised, isolation probes stay read-only). `plan-only` prints the checklist without touching a
  PR. It never merges — that's still `/wrapup`.

**Changed**
- **Worktrees are now keyed to the topic, not the slice.** One stable git worktree per topic/brief;
  the slice-branch rotates inside it. This ends the per-slice worktree pile-up and keeps a topic in
  one editor tab across `wrapup → clear → continue`. `/whats-next` reuses + re-baselines an existing
  topic tree (`reset --hard origin/main`) when clean, else creates one; `/continue` forks on whether
  the handover's slice already merged — resume the in-flight branch as-is, or (shipped) re-baseline
  and cut the next slice-branch; `/handover` now **keeps** the topic tree on loop-close (removes only
  when the topic itself is done); `/garbage-collect` treats a clean, merged tree whose topic is still
  live as a keepable resting tree, not an orphan. Exact `EnterWorktree`/`ExitWorktree` calls are
  spelled out in each command.

## 0.5.0

**Added**
- **`/watch` + cross-worktree dependency awareness.** `/whats-next` and `/continue` now run a
  **dependency pre-flight** before building: they scan the other live sessions (worktrees on
  disk + the board's in-flight rows), and if your work depends on a sibling thread's change
  that isn't on `main` yet — **PR or not; local and uncommitted work counts** — they surface it
  and offer to hold. `/watch` then parks the thread (⏸ `blocked-on: …`), watches the dependency
  land in the background (a PR merge, a board item reaching ✅, or a branch merging), and
  **auto-resumes** the work once it's on `main`. Detection is conservative + file-overlap by
  default (flags the clear cases, doesn't cry wolf).

**Changed**
- **`/brainstorm` renamed to `/explore`**, and upgraded: it now asks **one question at a time**,
  **offers a visual** (diagram/mockup) when a question needs one, **splits** an idea that's
  really several independent briefs, and **self-reviews** the finished brief for placeholders,
  contradictions, ambiguity, and scope creep before handing off. (Update any alias on
  `/brainstorm`.)
- **Docs surface Relay's strong points better** — a new **Token economics** section (how cold
  handovers, the tiny board index, and scoped/gated review keep context cheap, and where it can
  still improve), sharper parallel-safety and design-before-code framing, and a **realigned**
  "idea in one picture" diagram.

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
