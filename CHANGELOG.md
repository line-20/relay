# Changelog

All notable changes to Relay. Versions follow [semver](https://semver.org); the plugin's
version lives in `plugins/relay/.claude-plugin/plugin.json`.

To pick up a new version, colleagues refresh via the `/plugin` manager — `/plugin marketplace
update line-20` then update the `relay` plugin. Their repos' `relay/` folders are their own
data and are never touched by an update.

## 0.12.1

**Fixed**
- **`/relay-init` no longer invents work from a folder name.** On a truly empty repo it was seeding
  speculative tracks, a roadmap narrative, and a placeholder brief guessed from the directory name
  (a `todo-app/` folder became a fabricated `foundation`/`tasks`/`ui` board) — content the user then
  had to delete, and which left them unsure what was real. Init now **detects greenfield vs
  populated**: a populated repo is inspected and seeded with real tracks as before; a **greenfield**
  repo gets the **structure only** — an empty board, a roadmap header stub, no brief — and the report
  points at **`/explore <idea>`** as the first move (not `/whats-next`, which would survey an empty
  board). The report is also **more compact** (output discipline: no per-step narration, no
  file-content recaps) and now prints the one-line lifecycle so the next move is obvious.

## 0.12.0

**Added**
- **`/deploy` — orchestrate and verify a PR preview, then hand it to `/test-drive`.** Fifth increment
  of the Secure-SDLC arc, and phase (h). It turns "a preview might be building somewhere" into "here
  is a verified, security-gated URL to click through" — and it's deliberately **thin: it never
  deploys anything itself.** It only drives the **project's own pipeline**: discover how the repo
  previews a PR (a documented URL pattern, a `gh pr checks` deploy check, a CI job), ensure the build
  ran (nudging only through the project's own trigger), wait for it (bounded, non-thrashing), then:
  - **health-check** the resolved preview URL actually responds — a green check can still front a
    broken app;
  - **security-gate** it — require the project's own security checks (SAST/dep/secret scan) green for
    the SHA and confirm the target is an ephemeral **preview** env, never prod. A failing security
    check stops the flow; no security checks configured is reported as a gap (a `/persist` candidate).

  No preview mechanism ⇒ it says so and stops (testing falls back to a local run) — it never invents
  infrastructure. That "use the pipeline, never replace it" boundary is what lets one command span
  Vercel previews, review-env containers, and beyond without special-casing a vendor. `/test-drive`
  now points at `/deploy` to gate a preview before driving it.

See [docs/ssdlc-roadmap.md](docs/ssdlc-roadmap.md) — this is increment #5 of the additive 0.x arc.

## 0.11.0

**Added**
- **`/persist` — harvest what a lap taught back into the living knowledge.** Fourth increment of the
  Secure-SDLC arc, and phase (j): the step that makes the spiral *compound* instead of leaking each
  session. After a lap (a merged PR / a slug), `/persist` reads the diff, its review report, the
  brief's threat model, and the handovers, and extracts only the **durable, non-obvious** lessons —
  applying memory's "was it non-obvious, and will it recur?" test so the knowledge layer stays sharp,
  not bloated. It routes each lesson to a surface:
  - **Guardrails** — a recurring review finding or security bar becomes a rule in the dimension's
    **`extends` overlay** (the project's house rules). It **never mutates a shipped baseline** —
    establishing a dimension stays `/guardrails`' job; `/persist` only grows the overlay, wiring a new
    house-rules file into the config's `extends` array surgically when one doesn't exist yet.
  - **Design system** — a new pattern/token/component joins the design-system doc, generalising the
    stewarding `ui-ux-designer` already does for one guide.
  - **AI memory** — a non-obvious decision + its why, one fact each.
  - **Release notes** — a human-readable, user-benefit summary of what the lap shipped, in the
    project's copy voice (British English), grouped by release. This is the *outward* deliverable and
    is **not** filtered by the non-obvious test: every user-visible change earns a note (gated on
    "would a user notice?"), while a purely internal lap gets none. Distinct from a dev CHANGELOG —
    it's the human companion, not a copy. Lives at `<root>/knowledge/release-notes.md`, relocatable
    via `paths["release-notes"]`.

  Architecture/ADR/ops/manual targets are **captured as deferred** (later persist slices), never
  silently dropped. `/persist` offers before it writes (the knowledge layer is shared, main-owned
  project truth) and **never writes code**. "Nothing to persist" is a valid, sprawl-respecting outcome.
- **`/wrapup` now offers `/persist`** after the merge, before handover (Phase 5.7) — a non-fatal
  offer, skipped for a routine change. (At 1.0 this becomes a first-class phase of `ship`.)

See [docs/ssdlc-roadmap.md](docs/ssdlc-roadmap.md) — this is increment #4 of the additive 0.x arc.

## 0.10.0

**Added**
- **`/refine` — groom a shaped idea against THIS project.** Third increment of the Secure-SDLC arc,
  and phase (c) of the spiral: the bridge between `/explore` (which shapes an idea *in the abstract*)
  and `/whats-next` (which builds it). `/refine` takes an existing brief and grounds it in the
  project — reading the actual **code** (what to reuse, what not to break), the **guardrails** from
  `/guardrails` (turning each active dimension's bar into an explicit slice requirement), and the
  project's **memory/knowledge** (so settled decisions aren't re-litigated). It then does two
  distinctive things:
  - **A threat model, content-gated** — whenever the change has a security/privacy surface, it walks
    assets → trust boundaries → threats → mitigations against the `security`/`privacy` guardrail bar,
    and folds each mitigation into a slice as a requirement. Security is designed in, not bolted on.
    A change with no threat surface says so and skips.
  - **Budget-aware slicing** — it re-cuts the slices to the `tier` from increment #2: `free` → small,
    sequential, one-at-a-time; `pro` → moderate, parallel where independent; `max` → may decompose
    into an epic of parallel threads. Each slice carries its acceptance criteria (guardrail
    requirements + threat mitigations).

  It **never writes code** and **never writes guardrails** (that's `/guardrails`/`/persist`) — it
  grooms the brief in place and STOPs for approval before writing. Fully back-compatible: no
  guardrails ⇒ it skips that layer; `unset` tier ⇒ it slices by natural seams.

See [docs/ssdlc-roadmap.md](docs/ssdlc-roadmap.md) — this is increment #3 of the additive 0.x arc.

## 0.9.0

**Added**
- **Budget tier — one signal that scales fan-out to the driver's Claude plan.** Second increment of
  the Secure-SDLC arc. `/relay-init` now asks once for a **`tier`** — `free` / `pro` / `max` — and
  writes it to `relay.config.json`. Two commands read it today:
  - **`/review-pr`** caps how many specialists fan out. A **safety core** — `security-specialist`
    (always), `test-engineer` (runs the suite), `dbms-specialist` (migration safety) — is *never*
    capped; the remaining content-selected specialists fill the budget by risk (`free` → +2, `pro` →
    +4, `max` → no cap). Anything the budget defers is logged in the report's *Skipped specialists*
    with a "re-run standalone for full coverage" note — never a silent drop.
  - **`/whats-next`** scales the verify/audit research fan-out (`free` → ~4 contenders, `pro` → ~8,
    `max` → ~10); an L3 audit stays exhaustive but warns and offers to scope on `free`.
- **Fully back-compatible.** Absent `tier` ⇒ **no cap anywhere** — every command behaves exactly as
  in 0.8.0. Budget shaping is opt-in: a repo that never sets a tier sees no difference. Later
  increments (`/refine`, `/test`) will read the same signal for slice size and test depth.

See [docs/ssdlc-roadmap.md](docs/ssdlc-roadmap.md) — this is increment #2 of the additive 0.x arc.

## 0.8.0

**Added**
- **`/guardrails` — establish what "good" means for a project, as layered guardrails.** First
  increment of the Secure-SDLC arc. Guardrails are **per-dimension** (`api`, `ui`, `security`,
  `privacy`, `testing`, …), **opt-in** (a dimension applies only if the project has it — a simple
  site runs fewer than a full ERP), and each resolves in three layers: **`extends` (the project's
  house rules — local file or URL, win on conflict) > a named `baseline` > Relay's default**. So the
  same command is opinionated (every active dimension ships a real default), adaptable
  (`api.baseline: zalando` swaps the ruleset), and extensible (overlay your own). `/guardrails` runs
  a discover-then-ask interview, writes a `guardrails` block to `relay.config.json` and prose docs
  under `<root>/knowledge/`, and STOPs for approval before writing.
- **Review specialists resolve guardrails.** `api-architect`, `ui-ux-designer`,
  `security-specialist`, and `privacy-specialist` now judge against the *resolved* guardrails for
  their dimension (`extends` > baseline > default) instead of ad-hoc defaulting — with a fully
  back-compatible fallback: no config / no dimension / no doc ⇒ their existing default behaviour,
  unchanged. A repo that never runs `/guardrails` sees no difference.

Shipped default API baseline is **`vendor-neutral-rest`**; Zalando / Microsoft / Google-AIP are
selectable adaptations (bundled rulesets land in a later slice — until then, point a baseline at a
ruleset path you supply). See [docs/ssdlc-roadmap.md](docs/ssdlc-roadmap.md) for the full arc.

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
