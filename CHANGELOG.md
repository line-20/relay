# Changelog

All notable changes to Relay. Versions follow [semver](https://semver.org); the plugin's
version lives in `plugins/relay/.claude-plugin/plugin.json`.

To pick up a new version, colleagues refresh via the `/plugin` manager — `/plugin marketplace
update line-20` then update the `relay` plugin. Their repos' `relay/` folders are their own
data and are never touched by an update.

## 1.0.9 — brownfield guardrails sweep

**Added**
- **`/config` offers a guardrails *sweep* on a brownfield repo.** When it detects an established
  project, Layer 2 scans for real standards material and **names what it found** — a design guide /
  design-system package (`ui`), an OpenAPI/GraphQL schema or spectral ruleset (`api`), ESLint/Prettier/
  tsconfig (code style), a `SECURITY.md`/auth layer (`security`), a test runner (`testing`) — and offers
  to "sweep this repo for guardrails" from what's actually there, handing off to `/guardrails`.
- **`/guardrails` discovery is now an explicit repo sweep** — it inventories existing config/standards
  *files* (lint/format/tsconfig, OpenAPI/spectral, `SECURITY.md`, design guide, test config), not just
  which dimensions exist, and cites the artifact seeding each dimension's baseline/`extends`. Grounded
  in real files, evidence-cited — never a guess about the user (per the 1.0.8 principle).

## 1.0.8 — no fabricated familiarity

**Fixed**
- **`/relay:config` no longer characterises the user back at themselves.** On a fresh session it was
  synthesising a working "style" from the global `CLAUDE.md` and presenting option descriptions as
  "Fits *your* … style" — presumptuous, and wrong to assert about someone it doesn't know. Option
  descriptions are now **neutral** (what each does), and any suggested default must rest on a concrete,
  current signal and be phrased tentatively. Stated as a cross-cutting principle ("No fabricated
  familiarity") in `conventions.md`, so it binds every command, not just `/config`.

## 1.0.7 — namespace note on the remaining docs

**Changed**
- Added the `/relay:`-namespace one-liner to `docs/the-board-model.md` and `docs/conventions.md` (they name commands in prose but lacked it), so the whole doc set is consistent.

## 1.0.6 — copy-able docs + new-user nudges

**Changed**
- **Runnable command examples now carry the `/relay:` prefix** across README, quickstart, and
  day-in-the-loop — so they're exact copy-paste (a bare `/init` isn't a command and tab-completes to a
  built-in). Prose keeps the bare names for readability, and each doc now says so up front.
- **New-user nudges.** Since Claude Code controls the `/relay` autocomplete order (it can surface `/gc`
  or `/fix` first — not plugin-influenceable), the README and quickstart now point a new user's first
  keystroke at **`/relay:help`** (the one-screen map) rather than the picker.
- **`/refine` is now a real beat in the day-in-the-loop walk** (shape → **ground** → build), not a
  skippable sidebar, and it's in the flow diagram.

## 1.0.5 — docs refresh + `/help` links

**Changed**
- **`/relay:help` links to the GitHub repo docs** (quickstart, board model, day-in-the-loop,
  conventions, CHANGELOG) instead of local file paths — so "more info" is one click away.
- **Full docs pass to 1.0.4.** Swept the last `budget/tier`→`session` leftovers (README, board-model,
  day-in-the-loop); added `/help` to the README command tables and `/config` · `/help` · `/exit` to the
  quickstart daily rhythm; and re-based `docs/ssdlc-roadmap.md` from "1.0 in progress" to "1.0 shipped,
  now on 1.0.x" (its arc is fully delivered — the CHANGELOG is the authoritative record; Reach R1–R3 is
  the live next). Config's `tier` note marked superseded by `session`.

## 1.0.4 — layered config

**Changed**
- **`/relay:config` is now layered gentlest-first**, instead of opening with a flat "here's all six
  areas, pick" table (which was the questionnaire the command was meant to avoid). It now: **leads with
  the two cheap driver prefs** (session + verbosity, one brief question each) and STOPs — most users are
  done there; then, only on a yes, gives a **compact, evidence-based offer** for the project knobs
  (guardrails → `/guardrails`, hooks → `/adopt`), offered only when the repo shows evidence for them;
  and keeps the **structural knobs (`root`, `paths`) out of the guided flow entirely** — reachable on
  demand via `/relay:config paths` / `root` for someone who's read the docs. The full current-vs-default
  table is now a reference (`/relay:config show`), not the opening menu.

## 1.0.3 — the config front door

**Added**
- **`/relay:config` — guided config, opt-in depth never a gate.** The config principle stated plainly
  and given a home: you can go from zero to shipping without ever opening a config file (absent keys are
  defaults), and this command is the *"now I want more"* surface. It **shows what's set vs available**
  (the discoverability an empty default file can't give), **proposes only what's worth setting for this
  repo** (not a blank questionnaire), and **walks the agreed ones as Q&A** — delegating the deep parts
  (`guardrails` → `/guardrails`, `hooks` → `/adopt`). Declining anything is a first-class answer.
  `/init` now offers it in one line rather than interrogating; `/help` and the README list it. The
  "opt-in depth, never a gate" rule is now the stated spine of the config system in `conventions.md`.

## 1.0.2 — the graceful exit

**Added**
- **`/relay:exit` — leave cleanly, the round-trip for `/adopt`.** Removes Relay from a repo without
  trapping anything: it **restores each adopted brief to where it came from** (the 1.0.1 provenance line
  records the origin), **exports** your Relay-created briefs (default `ideas/`), **discards** Relay's own
  bookkeeping (board, handovers, reviews, audits — all in git history), and **removes** config +
  the `.gitignore` line — leaving your **code and deliverable docs untouched**. Previews the full plan
  and STOPs before touching a file (`--dry-run` to preview only); lands as one `git revert`-able commit;
  refuses to proceed on uncommitted/in-flight work. So adoption is fully reversible — no lock-in.
- **Complete config reference in `docs/conventions.md`.** Because `/init` scaffolds no placeholder
  config (absent = default, each key added by the command that owns it), the full `relay.config.json` /
  `relay.config.local.json` schema is now documented in one annotated block, with the default for every
  absent key.

## 1.0.1 — the interaction layer

Additive polish from dogfooding 1.0 on a real repo — how Relay *talks to you* and *handles your
files*. New shared contracts live in [docs/conventions.md](docs/conventions.md).

**Added**
- **Session size replaces the budget tier.** The signal that sizes work isn't "which Claude plan" —
  it's **context appetite**: slice so a build finishes within the healthy part of a context window
  (~first half). `tier (free/pro/max)` → **`session (small/medium/large)`**, and it moves out of shared
  `relay.config.json` into a **gitignored `relay.config.local.json`** (a driver preference, switch-often,
  never inherited by teammates), with **per-call overrides** on every consumer (`/refine large`,
  `/next small`). A committed `tier` is still read as a back-compat fallback. `/refine` uses it to size
  slices; `/review`/`/next` fan-out follows.
- **Verbosity control.** `verbosity` = `terse | normal | verbose` in the same local prefs file, or a
  per-call word (`/next terse`). `terse` = banner + STOP gates + the landing, no narration.
- **`/relay:help`** — an on-demand capability map (lifecycle + every command, one line each), so the
  command set is discoverable and re-findable.
- **`/adopt` reconciles the existing `.claude/` setup.** Beyond docs, it triages a repo's existing
  commands/skills — **keep** (not covered) / **offer-remove** (redundant with Relay) / **keep-and-hook**
  — and writes an explicit **`hooks`** map so Relay phases dispatch the project's own automation
  (`{ "hooks": { "test": "test-stack" } }` → `/ship`/`/test` bring the fixture stack up via it).
- **Safety net for destructive ops.** Adoption/compaction/migration never leave a move unrecoverable:
  in git, git *is* the backup (commit-first, report the undo path); with no git, the original is copied
  to `<root>/archive/pre-adopt/` first. Every move is stated explicitly, and adopted briefs carry an
  `_Adopted from … (moved)_` **provenance line** so "adopted vs created" is answerable at a glance.

**Changed**
- **Consistent tabular output** — lists (shortlists, findings, plans) always render as GFM tables,
  never stacked `Field: value` records or ASCII separators (the `/next` shortlist regression), with
  terse cells + footnotes.
- **`/init` records nothing switch-often** — session/verbosity are no longer asked or written at init;
  it just gitignores the local prefs file.

## 1.0.0

The breaking cut, tagged **once**. Assembled on branch `1.0`; main stays on 0.14.0 until the
`1.0`→`main` merge. The whole additive 0.x arc (guardrails · budget/tier · `/refine` · `/persist` ·
`/deploy` · brownfield adopt) now sits under one stable major, with the lifecycle finally reading as
its verbs. Every additive 0.x feature carries forward unchanged.

**Changed (breaking)**
- **Command renames** — the lifecycle reads as its verbs; the `relay:` namespace already says "relay",
  so redundant prefixes/plumbing names are gone: `relay-init`→`init`, `whats-next`→`next`,
  `review-pr`→`review`, `fix-pr-review`→`fix`, `test-drive`→`test`, `wrapup`→`ship`,
  `garbage-collect`→`gc`. Unchanged: `explore`, `refine`, `continue`, `deploy`, `persist`,
  `guardrails`, `handover`, `cross-check`, `watch`, `version`.
- **Durable-state dir renames** — `pr-reviews/`→`reviews/` and `board-audit/`→`audits/` (the `pr-`/
  `board-` prefixes were historical). Every reference across commands, agents, and docs swept to match.
- **`/explore` is now purely context-free (explore→refine split)** — it shapes the idea *in the
  abstract* and never inspects the project; the pre-build **fit check** and all code-grounding moved to
  `/refine`. Three clean stages: `/explore` shapes → `/refine` grounds → `/next`/`/continue` builds.

**Added**
- **Progressive setup — `/init` is now minimal, and adoption is gradual.** Onboarding was too heavy:
  init front-loaded a budget-tier question, a full dir tree, seeded stubs, and (in 0.14.0) a
  destructive import of your idea docs. Now `/init` does the *minimum* — a board and the two dirs the
  first commands write — and **nothing destructive**. On a brownfield repo it surfaces your existing
  idea/plan docs on the board **by reference** (left in place); on greenfield, an empty board → `/explore`.
  Everything heavier is **deferred and offered by the phase that needs it**: the budget tier is asked
  the first time a command fans out (`/review`/`/refine`/`/next`), guardrails is offered when `/refine`
  or `/review` finds none, and pulling legacy docs *into* Relay happens on touch or on demand (below).
- **`/adopt [area]` — gradual brownfield migration, with cleanup.** A dedicated, area-scoped command
  that brings existing material under Relay management: **work-inputs** (ideas/plans/todos) are **moved**
  into `briefs/` and **actualised** on the way in (cut what shipped, fix drift, tighten); **deliverable
  knowledge** (design guide, conventions) is **registered** as a guardrails `extends` overlay *in place*
  and **compacted** by its domain steward (e.g. `ui-ux-designer` trims an accreted design guide). Code
  is left untouched. Always previews a triage table and STOPs before touching a file; scope narrows the
  blast radius (`/adopt ui`, `/adopt ideas/finance*`, `/adopt --all`). `/refine` does the same pull-in
  **on touch** for a single idea, so a brownfield repo becomes pristine as you work; `/adopt` is the
  bulk fast-forward. (This is where 0.14.0's destructive import moved — from an init default to a
  deliberate, scoped, non-destructive-by-surprise command.)
- **Per-path config** — `root` generalises to a uniform `paths` resolver: relocate any single logical
  path independently (`{ "paths": { "knowledge": "docs" } }`), resolving `paths[name]` else
  `<root>/<name>`. List only what you move; no config ⇒ everything under `relay/` as before.
- **Epic modelling** — a slug convention (`track/epic/slice`) + a grouping view in `/next`; no board
  schema change. `/refine` slices a large item into an epic; `/next` recommends the next unstarted slice.
- **Reflect loop** — the spiral's return edge, formalised in `/test`, `/ship`, and `/persist`: after a
  result is seen, re-enter `/explore` (new idea) or `/refine` (same idea, changed) with what you learnt.
- **Security shift-left, end to end** — `/test` now turns a `/refine` threat model into scenarios that
  prove each mitigation holds; combined with the always-on security review and `/deploy`'s security
  gate, a modelled threat is verified, not assumed.
- **1.0 migration path** — `/init` detects a pre-1.0 layout (`pr-reviews/`/`board-audit/`) and offers
  to rename it (history-preserving where there's git), the only file-level migration a consumer repo
  needs.

**Migrating from 0.x:** commands are just what you type — use the new names. In each repo, run
`/relay:init` once; it offers the dir rename. The destructive brownfield-adopt introduced in 0.14.0
rides along in this major.

## 0.14.0

**Changed**
- **`/relay-init` now *adopts* a brownfield repo's existing work instead of just pointing at it.**
  0.12.8 surfaced pre-existing idea docs on the board by reference — which left two homes (a mostly
  empty `relay/briefs/` beside the real `ideas/`). Init now **triages** existing docs by intent and
  acts on each:
  - **Work-inputs** (ideas, specs, plans, TODOs — *volatile*, spent once shipped) are **imported into
    `<root>/briefs/`** and put on the board. This is Relay's job: track them to done, then archive.
  - **Deliverable knowledge** (design guide, DB conventions, architecture, tone-of-voice, runbooks —
    *durable*, still true after shipping) is **left with the code** to feed the knowledge layer
    (`/guardrails` reads it, `/persist` grows it).
  - **Code/content/assets** are left untouched.

  Init presents the triage table and **STOPs for approval before moving anything**. The import
  **preserves git history** (`git mv` for tracked files) and rewrites path references to moved files;
  name-based `[[wikilinks]]` survive. A doc that's both a plan and a decided model is imported as a
  brief now — `/persist` lifts its durable decision into the knowledge layer when the work ships.
- **`/relay-init` no longer assumes git.** Not every project is a git repo: the adoption move falls
  back to a plain `mv` when there's no git (or the file is untracked), and the final commit is skipped
  (init never force-`git init`s a project that isn't under version control) — the files are just
  written in place and the report says so.

## 0.13.0

**Added**
- **`/relay:version` — a CLI-style `--version`.** Prints the Relay banner + version, so you can
  confirm which plugin version is actually loaded in a session. Like the init banner, the version is
  hardcoded in the command file (no runtime read is possible — `${CLAUDE_PLUGIN_ROOT}` doesn't expand
  in command bash), which is the more useful behaviour anyway: it certifies the *loaded* command file,
  so a stale cached command shows an old version. (Maintainers bump the string in `plugin.json`,
  `/relay:version`, and the `/relay-init` banner together.)

**Tooling**
- **Version-sync guard** (`scripts/check-version.sh` + a `version-sync` GitHub Action). Because the
  version is mirrored across `plugin.json`, `marketplace.json`, and the two command banners, the guard
  fails the build on any drift — and also if the current version has no CHANGELOG entry. Runs in CI on
  push/PR; run it locally before a release.

## 0.12.8

**Fixed**
- **`/relay-init` (populated repo) now surfaces pre-existing idea/plan docs on the board.** It seeded
  tracks from the *code* but ignored docs where the user had already written down intended work — on
  a real brownfield repo (an `ideas/` folder of project baselines) that silently dropped every one of
  them from the board. Init now scans for intended-work docs (`ideas/`, `briefs/`, `rfcs/`,
  `docs/*-project.md`, `HANDOFF.md`, …), adds each as a 💡 icebox item whose `Detail` **points at the
  doc in place** (adopt, never move/rewrite), and reports how many it surfaced. Pure reference/
  convention docs (design guide, DB conventions) are correctly left off the board.

## 0.12.7

**Fixed**
- **Next-step suggestions now show the full `/relay:` prefix.** `/relay-init` and `/explore` handed
  users bare command names (`/explore`, `/whats-next`, `/refine`) that can't be invoked by copy-paste
  — a bare `/explore` isn't a command and tab-completes to the built-in `/export`. The actionable
  "next move" lines now show `/relay:<name>` and note to tab-complete after the colon.

## 0.12.6

**Fixed**
- **`/relay-init` banner is now unskippable.** It was phrased as a soft note and competed with the
  "run quietly / compact" output discipline, so the model could drop it — defeating its whole
  version-certification purpose. It's now a non-negotiable directive that explicitly overrides the
  quiet-mode discipline (which is scoped to "everything after the banner").

## 0.12.5

**Changed**
- **`/relay-init` banner gains a byline** — `by Line20 · @eriklenaerts` under the tagline.

## 0.12.4

**Changed**
- **`/relay-init` opens with an ASCII `Relay` wordmark banner** (tagline + version) instead of a plain
  version line — a proper CLI-app header. Same version-certification purpose as 0.12.3: the version is
  baked into the banner, so a stale cached command prints an old banner (or none at all).

## 0.12.3

**Added**
- **`/relay-init` prints the running version first** (`⏺ Relay v0.12.3 · /relay-init`). Because the
  version is hardcoded into the command file, it certifies *which command file actually executed* — so
  if it shows an older number than the installed plugin, the session is running a **cached** command
  and needs a reload. This directly surfaces the "am I running the version I think I am?" trap.
  (`${CLAUDE_PLUGIN_ROOT}` doesn't expand in a command's bash, so a runtime read isn't possible;
  hardcoding is both the only option and the more correct one here — a runtime lookup could read a
  different cached copy than the file that's running. Maintainers bump the one string per release.)

## 0.12.2

**Fixed**
- **`/relay-init` greenfield detection now counts untracked files too.** It read only *tracked*
  files, so a freshly-scaffolded-but-uncommitted project (untracked files only) wrongly looked
  greenfield. Now checks tracked + untracked (`git ls-files --others --exclude-standard`), so an
  uncommitted real project is correctly treated as populated.

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
