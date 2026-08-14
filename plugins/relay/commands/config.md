---
description: Set Relay's optional config, layered gentlest-first — lead with session + verbosity + audience, then a compact offer for guardrails/hooks, with root/paths on demand only. Opt-in depth, never a gate.
argument-hint: "[jump to one area: session|verbosity|audience|autonomy|persist|tidy|guardrails|hooks|paths|root|show; omit for the layered pass]"
---

> **Output** ([[conventions]]): honour `verbosity` (a per-call `terse`/`verbose` word in `$ARGUMENTS`, else `relay.config.local.json` `.verbosity`, else `normal`) — at **terse**, emit only STOP-gate questions and the final landing, no narration or intermediate recaps. Honour `audience` (a per-call `plain`/`informed`/`expert` word in `$ARGUMENTS`, else `relay.config.local.json` `.audience`, else unset) — how much depth surfaces in your **terminal** output; it never thins a **written artifact** (brief, report, ADR, handover), which always keeps full depth. `plain` = executive summary: the decisions and what you need from the user, minimal jargon; `informed` = lead with the decisions and what changed, keep the corrections and open questions that need the user, defer exhaustive evidence/`file:line` tables to the artifact; `expert` = full depth in the terminal too; unset ⇒ today’s default (no shaping). Never drop a STOP-gate question or the decision itself. Render every list as a **GFM markdown table**, never stacked `Field: value` records or ASCII-rule separators; keep cells terse, overflow to numbered footnotes.

The config front door — **opt-in depth, never a gate** ([[conventions]]). It is **layered
gentlest-first** so it never dumps "here's everything, have a pick": it leads with the cheap driver
prefs, then *compactly* offers the project knobs only if they're relevant, and keeps the structural ones
out of the way unless you ask for them. Decline anything and defaults stand — you can stop after the
first few questions.

## Step 0 — Resolve state (and honour a jump)
```bash
ROOT="$(jq -r '.root // "relay"' relay.config.json 2>/dev/null || echo relay)"
```
Read both surfaces: `relay.config.json` (committed) and `relay.config.local.json` (gitignored).
- If `$ARGUMENTS` names **one area** (`session`/`verbosity`/`audience`/`persist`/`tidy`/`autonomy`/`guardrails`/`hooks`/`paths`/`root`),
  skip the layering and go straight to that area's step.
- If `$ARGUMENTS` is **`show`**, print the reference table (bottom) and stop — no questions.

## Layer 1 — the cheap driver prefs (start here; one brief question each)
These are per-driver, benefit everyone, and cost one question — so always lead with them. **Describe
the options neutrally — say what each does, never who it's for** (see [[conventions]] → *No fabricated
familiarity*). On a fresh session you don't know the user; present the choices plainly and let them pick.
1. **Session size** (`small`/`medium`/`large`) — how big a slice `/refine` cuts and how wide `/review`/
   `/next` fan out. Describe them factually: **small** = narrow slices, tighter fan-out; **medium** =
   balanced; **large** = big slices, wide fan-out (full review panels). You *may* mark one as a
   suggestion **only from a concrete, current signal**, phrased tentatively — never "fits your … style".
   Write the answer to `relay.config.local.json`. Skip ⇒ unset (full fan-out).
2. **Verbosity** (`terse`/`normal`/`verbose`) — how much Relay narrates: **terse** = STOP gates + the
   landing only; **normal** = today's default; **verbose** = also the reasoning. Same rule — neutral
   descriptions; suggest `terse` only if something concrete points that way, and as a light suggestion,
   not a claim about them. Skip ⇒ `normal`.
3. **Audience** (`plain`/`informed`/`expert`) — how much depth Relay surfaces **in the terminal** (a
   written brief/report always keeps full depth): **plain** = executive summary; **informed** =
   decisions + what changed + what needs you, exhaustive evidence deferred to the artifact; **expert**
   = full depth. Same rule — neutral descriptions, no claim about who they are. Write to
   `relay.config.local.json`. Skip ⇒ unset (no shaping — today's output).

**Then STOP** — many users are done here. Ask a single line: *"That's the essentials. Want to set up
project standards or wire in your tooling too? (both optional)"* — only continue to Layer 2 on a yes.

## Layer 2 — offer the project knobs (compact, evidence-based, delegated)
Only if the user opted in above. **Offer only what this repo shows evidence for** — never a blank menu:
- **Guardrails — on a brownfield, offer a *sweep*.** If this is an established repo (real code, not
  greenfield), do a quick scan for existing standards material and **name what you actually found**,
  then offer: *"Want me to sweep this repo for guardrails? I found &lt;a design guide, an OpenAPI spec,
  ESLint + Prettier, DB conventions&gt; — I can set up guardrails from what's really here."* Scan for:
  a design-guide/UX doc or design-system package (`ui`); an OpenAPI/GraphQL schema or `routes/`
  (`api`); `.eslintrc`/`.prettierrc`/`biome`/`tsconfig` strictness (code style); a spectral ruleset
  (`api`); a `SECURITY.md`/auth layer (`security`); a privacy/data-handling doc (`privacy`); a test
  runner/suite (`testing`). On **yes, hand off to `/guardrails`** — its discover-then-ask sweep is the
  real thing; don't reimplement it. If it's greenfield or you found nothing concrete, say so and skip —
  **name the repo, never guess the user** (see [[conventions]] → *No fabricated familiarity*).
- **Hooks** — if there are existing `.claude/commands` or skills (a `test-stack`, a `commit`): name them
  and **hand off to `/adopt`**'s `.claude/` reconciliation (keep / remove-redundant / keep-and-hook),
  which writes the `hooks` map. **Include the verify hooks** if the repo shows evidence for them — a
  compose file / dev-server script / Makefile target ⇒ `hooks.env` (`{ up, down }`, how `/test` gets a
  **local** environment); a preview/deploy CI job ⇒ `hooks.deploy` (how `/deploy` triggers the
  **preview**). Relay never starts or stops an environment itself — these hooks are how the project
  keeps that job. If the repo has one side and not the other, mention that `test.target`
  (`preview`/`local`/`ask`) picks which `/test` defaults to; absent ⇒ auto. **Include `hooks.release`**
  if the repo shows evidence of one — a release-bot PR/workflow (release-please, changesets,
  semantic-release), a `release` script, or version tags — so `/ship` cuts a release per lap instead of
  leaving the version describing a past that no longer exists. Absent ⇒ `/ship` skips it silently and
  never invents a version scheme.
If the repo shows **no** evidence for either, say so plainly and skip — don't manufacture an offer.

## Persist policy (jump-only: `/relay:config persist`, NOT in the layered pass)
A **project-wide** block in `relay.config.json` (committed), with two independent knobs — describe both
neutrally, presets factually:
- **`cadence`** (`ask`/`always`/`never`, default `ask`) — what `/ship`'s persist phase does **once it
  has decided the lap taught something durable** (the gate always runs first): **ask** = offer
  `/persist`, run on a yes; **always** = run without asking; **never** = skip the offer.
- **`level`** (`none`/`lean`/`standard`/`full`, default `standard`) — how much `/persist` harvests:
  **none** = nothing (the codebase is the only deliverable); **lean** = AI memory + release notes;
  **standard** = today's harvest (guardrails overlay + design system + memory + release notes);
  **full** = also ADRs + procedures + how-tos. A per-kind `kinds` map (e.g. `{ "adr": true }`) overrides
  the preset for one kind.

A flat `persist: "ask"` from an earlier version is still read as `persist.cadence` (back-compat). Skip ⇒
`cadence: ask`, `level: standard`. Remember durable output lands **outside `<root>/`** via `paths.*`
(below) — see [[conventions]] → *Persistence*.

## Tidy policy (jump-only: `/relay:config tidy`, NOT in the layered pass)
Also project-wide in `relay.config.json` — how `/tidy` keeps the volatile layer lean:
- **`level`** (`none`/`lean`/`standard`/`full`, default `standard`) — **none** = off; **lean** = prune
  only (the per-lap trigger reports what trim would clear, without applying it); **standard** = prune +
  trim, merge report-only; **full** = also auto-apply merges. The same level governs `/handover`'s
  per-lap Step 4.5, so this is the dial between *housekeeping happens by convention* (`standard`) and
  *tell me and I'll decide* (`lean`).
- **`ops`** — per-op override: `prune`/`trim` (`true`/`false`), `merge` (`report`/`auto`/`false`).
  Setting `trim` here up front also skips the one-time "trim done rows from now on?" question the
  first per-lap trim asks.
- **`retention`** — `reviews` (keep newest N, default 20), `handovers` (`board-linked` — keep those the
  board still points at). Describe factually; a bigger project runs `/tidy` more aggressively, a tiny
  one barely at all. Recurring runs are wired via the harness scheduler, not here (`/tidy` can't
  schedule itself). Skip ⇒ `level: standard`.

## Autonomy policy (jump-only: `/relay:config autonomy`, NOT in the layered pass)
How much a session decides **without the user**. Deliberately
out of the layered pass: this is a trust decision, and it should be made on purpose rather than
answered in passing. Default is today's behaviour, so a project that never visits it loses nothing.

**Two surfaces, on purpose.** `decide` and `budget` are **per-driver and per-session** — they live in
`relay.config.local.json` (gitignored) with a **per-call word in `$ARGUMENTS` winning**, exactly like
`session`, because "how much this tab decides alone" is a property of what *this tab is doing*, not of
the repo: one session runs `/next solo` on plumbing while another runs `/next ask` beside it.
`escalate` and `log` are **project-wide** in `relay.config.json` (committed) — what counts as a product
decision, and where calls get recorded, are facts about the project that every driver should share.
A `decide`/`budget` in the committed file still reads as the project's **default**; local and per-call
override it.

- **`decide`** (`ask`/`challenge`/`solo`, default `ask`) — what a session does at a **technical**
  decision that will outlive the current lap (the shape of stored data, a new seam or boundary, a name
  that becomes public API, two project rules pointing opposite ways): **ask** = STOP and put it to the
  user, today's behaviour; **challenge** = dispatch the `challenger` agent with the options and act on
  its ruling; **solo** = decide alone. `challenge` and `solo` both record the call (see `log`).
- **`escalate`** — categories that come back to the user **whatever `decide` says**. Default
  `["user-visible", "commercial", "copy", "consequential"]`: anything that changes what a user sees or
  can do; anything touching pricing/packaging/licensing; product wording; and anything with legal,
  financial, safety or security weight. These aren't engineering calls, so no agent settles them —
  the session parks them and keeps building around them. Set `[]` only with eyes open.
- **`budget`** (integer, default `4`) — challenges per lap. Hitting it is a signal the slice is too
  big; the session says so and re-slices rather than asking a fifth time.
- **`log`** (path, default `<root>/decisions.md`) — one line per call made without the user: date, the
  question, the ruling, why. This is what makes `challenge`/`solo` reviewable after the fact, and what
  stops the next lap quietly reversing this one. **Turning `decide` up without a log is the one
  combination to talk the user out of.**

**This governs judgment gates only — never safety gates.** A STOP for a dirty tree, a red suite, an
unresolved 🔴 blocker, a stale merge base or a destructive/irreversible operation stays a STOP at every
level. Autonomy is about who picks between two defensible designs, not about merging something broken.

**You don't have to come here first.** Because a policy about who decides is hard to answer before any
decision has happened, `/next` asks **once per repo**, at the *first* outliving decision — after
putting that decision to the user, with it still on screen as the example (Step 5.4) — and records the
answer to `relay.config.local.json`. Setting `decide` here up front means that gate never fires. This
is why autonomy stays out of the layered pass: the question has a better moment than setup.

Skip ⇒ `decide: ask` (nothing changes; the first-decision gate will offer once).

## Advanced — root & paths (on demand only, NOT in the layered pass)
**Do not surface these in the guided flow.** They're structural, for someone who's read the docs, and
reached only via an explicit arg:
- `/relay:config paths` — relocate a logical path so `/persist`/`/guardrails` write where your durable
  docs actually live. Covers `knowledge`, `design-system`, `release-notes`, and the durable-output
  destinations `adr` (default `docs/decisions`), `procedures` (`docs/procedures`), `how-tos`
  (`docs/how-tos`), `guardrails` (`docs/guardrails`) — all **outside `<root>/`** by default. Confirm the
  target, merge surgically.
- `/relay:config root` — move where all durable state lives (a real move — safety net, see
  [[conventions]]).
In the layered pass, mention them at most as **one closing line**: *"Advanced: `root`/`paths` on demand
— `/relay:config paths`, or see `docs/conventions.md`."*

## Reference — current vs default (shown on `show`, or if the user asks)
A single table of every area, its current value (or `default: …`), and one line on what it does — the
discoverability an empty default file can't give. Don't lead with this; it's a reference, not the menu.

## Report
State what changed and in which file (nothing if they only looked), that everything else stays at its
sensible default, and that `/relay:config` is safe to re-run anytime to review or adjust.
