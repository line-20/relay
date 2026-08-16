# Relay conventions — prefs, persistence, output, hooks

The shared contracts every Relay command honours. Two config surfaces, one output style, one
extension mechanism, and one input/output split (volatile working state vs durable output).
Commands reference this doc so behaviour is consistent across the whole set.

> Commands are namespaced `/relay:<name>` — written bare here (`/refine`, `/adopt`, …) for
> readability; add the `/relay:` prefix when you type. `/relay:help` prints the whole map.

> **The config principle: opt-in depth, never a gate.** You can go from zero to shipping without ever
> opening a config file — absent keys *are* sensible defaults. Config is there the moment you want more,
> three ways: **just-in-time** (a phase offers the one knob it needs), **`/relay:config`** (a guided
> pass that proposes what's worth setting for this repo and walks it as Q&A), or **by hand** (the
> documented schema below). Nothing about configuring is ever in the way of getting to work.

## Two config surfaces — project vs driver

Relay separates **what the project is** from **how the driver wants to work right now**. They live in
different files because they have different owners and lifetimes.

| | `relay.config.json` (committed) | `relay.config.local.json` (gitignored) |
|---|---|---|
| Owns | project truth — shared by everyone | the driver's here-and-now preferences |
| Holds | `root`, `paths`, `guardrails`, `hooks`, `test`, `review`, `persist`, `tidy`, `autonomy.escalate`/`.log` | `session`, `verbosity`, `audience`, `autonomy.decide`/`.budget` |
| Lifetime | stable; changes rarely | switch-often; personal, per-machine |
| Committed? | yes | **no** (`/init` adds it to `.gitignore`) |

A teammate on a different Claude plan, or in a different mood about session size, must not inherit
yours — so those signals are **local, never committed**.

### The full schema (for reference — you never write this by hand)
No key is scaffolded at `/init`; **absent = default**, and each key is added by the command that owns it
when you use that feature. A fully-configured repo *could* look like this — but a minimal repo has no
config file at all:
```jsonc
// relay.config.json  (committed — project truth; written incrementally, never all at once)
{
  "root": "relay",                                   // /init, only if non-default (else absent)
  "paths": { "knowledge": "docs",                    // /guardrails, /adopt, /config — per-path overrides
             "design-system": "packages/ui/DESIGN.md",
             "adr": "docs/decisions",                // /persist, /init — where ADRs land (OUTSIDE root)
             "procedures": "docs/procedures",        // durable "how WE work" docs
             "how-tos": "docs/how-tos",              // durable "how to operate" docs
             "guardrails": "docs/guardrails" },      // where extends house-rules default
  "guardrails": {                                     // /guardrails, /adopt — per-dimension bars
    "api": { "baseline": "vendor-neutral-rest", "extends": ["docs/api-house.md"] },
    "ui":  { "baseline": "tokens-a11y", "extends": ["packages/ui/DESIGN.md"] }
  },
  "persist": {                                        // /config — how much /persist harvests (see below)
    "cadence": "ask",                                //   ask | always | never  (does /ship auto-run it)
    "level": "standard",                             //   none | lean | standard | full  (the preset)
    "kinds": { "adr": true }                         //   optional per-kind override of the preset
  },
  "tidy": {                                           // /config — how /tidy keeps the volatile layer lean
    "level": "standard",                             //   none | lean | standard | full
    "ops": { "prune": true, "trim": true, "merge": "report" },
    "retention": { "reviews": 20, "handovers": "board-linked" }
  },
  "test": { "target": "preview" },                    // /test, /config — preview | local | ask
                                                      //   absent ⇒ auto (preview if the project has one)
  "hooks": {                                          // /adopt, /test, /deploy — dispatch project automation
    "test": "test-stack",                             //   run the suite (+ its fixture stack)
    "commit": "commit",                               //   how this project commits
    "env": { "up": "stack-up",                        //   bring a LOCAL test environment up …
             "down": "stack-down" },                  //   … and take it down (sibling-safe: the project's call)
    "deploy": "deploy-preview",                       //   trigger the project's PR preview
    "release": "release"                              //   cut a release post-merge — one per lap
  },
  "autonomy": {                                       // /config autonomy — who decides without the driver
    "escalate": ["user-visible", "commercial",        //   categories that ALWAYS come back to the user,
                 "copy", "consequential"],            //     whatever `decide` says (project truth)
    "log": "relay/decisions.md",                      //   one line per call made without the user
    "decide": "ask",                                  //   project DEFAULT only — local + per-call win
    "budget": 4                                       //   idem (see relay.config.local.json below)
  },
  "review": {                                          // /adopt — project-declared review agents
    "verify": false,                                   //   /review Step 2.5 — refute every 🔴/🟡
                                                       //     before reporting (~2× cost); per-call
                                                       //     `audit` turns it on regardless
    "agents": [
      { "name": "a11y-auditor",                        //   a .claude/agents/*.md the project ships
        "gate": "copy-relevant",                       //   built-in signal, or { "paths": ["packages/ui/**"] }
        "tier": "cappable",                            //   safety (uncapped) | cappable (fills budget) — default cappable
        "scope": "frontend",                           //   frontend | backend | full — default full
        "priority": 50 }                               //   tie-break within the cappable pool — default 0
    ]
  }
}
```
```jsonc
// relay.config.local.json  (gitignored — driver preferences; or set per-call)
{ "session": "large", "verbosity": "terse", "audience": "informed",
  "autonomy": { "decide": "challenge", "budget": 4 } }   // per-driver, per-session — see below
```
**Defaults when a key is absent:** `root` → `relay`; no `paths` overrides; no `guardrails` (reviewers
use their built-in defaults); no `hooks` (commands use their built-in discovery); `test.target` → unset
(auto — preview if the project has one, else local); no `review.agents`
(just the built-in ten specialists); `review.verify` → `false` (findings are reported as the
specialists raised them — no refutation pass unless `/review audit` asks for one); `persist` → `cadence:
ask`, `level: standard` (today's harvest); `tidy` → `level: standard`; `autonomy` → `decide: ask`
(today's behaviour — every outliving decision goes to the user), `escalate` → the four categories
above, `budget` → 4, `log` → `<root>/decisions.md`; `session` → unset (no shaping,
full fan-out); `verbosity` → `normal`; `audience` → unset (no register shaping — today's prose). A
committed `tier` is still read where `session` is absent
(back-compat), and a flat `persist: "ask"|"always"|"never"` is still read as `persist.cadence`
(back-compat).

### `session` — how big a bite per slice
`small | medium | large`. This is **context-appetite, not plan**: it sizes the work so building a
slice completes within the *healthy* part of a session's context window (the rule of thumb: finish
before ~50% of the window is used, then start fresh). Bigger window ⇒ `large` is safe; smaller ⇒
`small`.
- **`/refine` reads it to size slices** (the primary job): `small` → many bite-size slices + more
  handovers; `large` → fewer, meatier slices.
- Fan-out (`/review` specialists, `/next` verify/audit width) follows it as a secondary effect (a
  small session ⇒ leaner sprawl).
- **Absent ⇒ no shaping** — natural-seam slices, full fan-out. Fully back-compatible.

### `verbosity` — how much Relay says
`terse | normal | verbose` (default `normal`).
- **terse** — the banner (where a command has one), the STOP-gate questions, and the final landing.
  **No narration between tool calls, no intermediate recaps.** For someone who reads the landing.
- **normal** — today's behaviour.
- **verbose** — also show the reasoning and intermediate findings as they happen.

### `audience` — how much depth Relay surfaces (terminal only)
`plain | informed | expert` (absent ⇒ no shaping — today's output). Governs two things at once — the
**technical register** of the prose *and* **how much supporting detail surfaces in the terminal**. The
invariant that makes it safe: it shapes **terminal output only**. A **written artifact** — a brief, a
review report, an ADR, a handover — always carries full depth, whatever the audience. So dropping to
`informed` doesn't lose the grounding; it moves it out of the chat into the file where it belongs.
- **plain** — executive summary: the decisions and what's needed from the driver, minimal jargon.
  Supporting evidence lives in the artifact, not the terminal.
- **informed** — assume deep, broad IT literacy but not current hands-on coding. Lead with the
  decisions and *what changed*; keep the corrections and open questions that need the driver's
  judgement; defer exhaustive evidence, `file:line` tables, and step-by-step detail to the artifact.
- **expert** — full depth in the terminal too: the complete tables, evidence, and implementation
  specifics (today's behaviour).
- **absent** — no shaping; today's behaviour. Fully back-compatible.

Never drops a STOP-gate question or the decision itself — those are the landing, at every level.

### `autonomy` — who decides when the driver isn't asked
How much a session settles **alone** at a technical decision that outlives the current lap (the shape
of stored data, a new seam, a name that becomes public API, two project rules pointing opposite ways).
Set it deliberately via `/relay:config autonomy` — it is kept out of the guided pass on purpose.

**Split across both surfaces, on purpose:**
- **`decide`** (`ask` | `challenge` | `solo`, default `ask`) and **`budget`** (integer, default `4`
  challenges per lap) are **per-driver, per-session** — `relay.config.local.json`, with a per-call word
  winning, exactly like `session`. "How much *this tab* decides alone" is a property of what the tab is
  doing, so one window can run `/next solo` on plumbing while another runs `/next ask` beside it. A
  committed `decide`/`budget` still reads as the project's **default**.
- **`escalate`** (categories that come back to the driver whatever `decide` says — default
  `["user-visible", "commercial", "copy", "consequential"]`) and **`log`** (default
  `<root>/decisions.md`, one line per call made without the driver) are **project truth**, committed:
  what counts as a product decision, and where calls are recorded, are facts every driver shares.

`challenge` dispatches the `challenger` agent with the options and acts on its ruling; `solo` decides
alone. Both **record the call** in `log` — turning `decide` up without a log is the one combination to
talk a project out of.

**Asked once, at the first real decision.** A policy about who decides can't be answered before a
decision exists, so it is deliberately absent from `/relay:config`'s guided pass. Instead **`/next`
and `/continue`** offer it **once per repo** at the first outliving decision — after putting that
decision to the driver, never instead of it — and record the answer (all three, `ask` included) to
`relay.config.local.json`, so the offer never repeats. Whichever fires first silences the other:
one gate per repo, not one per command. Setting `decide` ahead of time, or passing a
per-call word, means it never fires. Same shape as the per-lap trim gate: ask at the moment it's
answerable, with the real thing on screen, then remember. **This governs judgment gates only, never safety gates:** a dirty tree, a red
suite, an unresolved 🔴 blocker, a stale merge base or a destructive operation stays a STOP at every
level.

### Per-call overrides (the "case by case")
Any command accepts these words in its arguments and they win over the files, for that one run:
`small` / `medium` / `large` (session), `terse` / `quiet` / `verbose` (verbosity),
`plain` / `informed` / `expert` (audience), and `ask` / `challenge` / `solo` (autonomy). E.g.
`/refine large informed`, `/next small terse`, `/next solo`, `/review verbose`.

**Resolution order (both signals):** per-call word → `relay.config.local.json` → (`relay.config.json`
`tier`, back-compat only) → default. Resolve once at a command's Step 0:
```bash
LOCAL=relay.config.local.json
SESSION="$(jq -r '.session // empty' "$LOCAL" 2>/dev/null)"; : "${SESSION:=$(jq -r '.tier // empty' relay.config.json 2>/dev/null)}"
VERBOSITY="$(jq -r '.verbosity // "normal"' "$LOCAL" 2>/dev/null || echo normal)"
AUDIENCE="$(jq -r '.audience // empty' "$LOCAL" 2>/dev/null)"   # empty ⇒ no register shaping
DECIDE="$(jq -r '.autonomy.decide // empty' "$LOCAL" 2>/dev/null)"
: "${DECIDE:=$(jq -r '.autonomy.decide // empty' relay.config.json 2>/dev/null)}"; : "${DECIDE:=ask}"
# then let any per-call word in $ARGUMENTS override SESSION / VERBOSITY / AUDIENCE / DECIDE
```
> **Migration note:** `session` supersedes the old `tier` (`free`/`pro`/`max`). A committed `tier` is
> still read as a fallback so nothing breaks; new setups write `session` to the local file instead.

## Typing a command — usage on demand, and short names

**Every command carries its own usage.** Each command file opens with a `## Usage` block — the
arguments it takes, one row each, plus the per-call words above and the config keys it reads. Two
ways to see it, both printing the same block verbatim and doing nothing else:

| | |
|---|---|
| `/relay:<command> ?` | Also `help`, `--help`, `-h`. The command stops there — no tools, no side effects |
| `/relay:help <command>` | The same block, without leaving the help surface |

`/relay:help` with no argument still prints the whole map. Authors: keep the `## Usage` table in step
with the command's `argument-hint` frontmatter — the hint is what the picker shows *before* you run
it, the block is what `?` shows *instead of* running it. See [authoring-skills](authoring-skills.md).

**The ten commands in the loop answer to a short name too** — two extra ways to reach the same
instructions: a bare form that needs no prefix at all, and the prefixed equivalent. Nothing is
dispatched or forwarded: every name lands directly on a command file.

| Bare | Prefixed | Full |
|---|---|---|
| `/rle` | `/relay:rle` | `/relay:explore` |
| `/rlrf` | `/relay:rlrf` | `/relay:refine` |
| `/rln` | `/relay:rln` | `/relay:next` |
| `/rlc` | `/relay:rlc` | `/relay:continue` |
| `/rlt` | `/relay:rlt` | `/relay:test` |
| `/rls` | `/relay:rls` | `/relay:ship` |
| `/rlrv` | `/relay:rlrv` | `/relay:review` |
| `/rlf` | `/relay:rlf` | `/relay:fix` |
| `/rlh` | `/relay:rlh` | `/relay:handover` |
| `/rlp` | `/relay:rlp` | `/relay:persist` |

Same arguments either way, `?` included. The **`rl` prefix on the bare form is deliberate**: a bare
name is global across every plugin you have installed, and Claude Code silently drops one that
collides with a name something else already owns — `/rlt` won't collide, `/t` might. All three
columns are listed in the `/` menu, so either name is there to be picked or autocompleted.

> **Authors: two names, two files — one of them generated.** A plugin command takes its name from its
> filename, and a frontmatter `name:` *replaces* that name rather than adding to it. So the short
> names live in generated twins: `commands/rlt.md` mirrors `commands/test.md` body-for-body, carries
> `name: rlt` (which is what registers the bare `/rlt`), and is written by
> `./scripts/gen-short-names.sh`. **Edit the source; never the twin** — the pre-push hook and CI both
> fail on a twin that has fallen out of step. Two routes that avoid the duplication don't work: a
> symlink is ignored by the loader, and a stub that injects the real body registers but then produces
> nothing — the same failure as the forwarding stub tried in 1.10.0, which had to be *executed* to
> reach its target and failed more often than it worked.

## Persistence — volatile input, durable output

Relay separates the knowledge it *works through* from the knowledge it *produces*, and treats them
with opposite lifetimes:

- **Volatile working knowledge** — briefs, plans, concepts, reviews, handovers — lives **inside
  `<root>/`**. It exists to get work done and is **expected to be pruned and eventually deleted**;
  git is its only long-term safety net. `/tidy` keeps this side lean.
- **Durable knowledge is OUTPUT**, exactly like code, and lives **OUTSIDE `<root>/`** in the project's
  own docs tree, so it **outlives Relay itself** (remove the tool and the knowledge stays). `/persist`
  distils it out of the volatile inputs:

  | durable kind | what it is | default destination |
  |---|---|---|
  | rules in force | guardrails / house-rules | `paths.guardrails` → `docs/guardrails` |
  | why we chose X over Y | ADRs (decision records) | `paths.adr` → `docs/decisions` |
  | how to operate/run | how-tos | `paths["how-tos"]` → `docs/how-tos` |
  | how WE work (process) | procedures | `paths.procedures` → `docs/procedures` |
  | design patterns/tokens | design system | `paths["design-system"]` |
  | for end users | release notes | `paths["release-notes"]` → `docs/release-notes.md` |

  Config holds only **pointers** to these out-of-`root` destinations; Relay writes there but doesn't
  own the folders. (Existing repos that predate this keep durable knowledge under `<root>/knowledge/`
  until `/init`'s migration offer moves it outward — nothing is forced.)

**How much is persisted is a config-driven spectrum** (`persist.level`), from the *same* mechanism:
`none` (nothing — the codebase is the only deliverable) · `lean` (memory + release-notes) · `standard`
(today's harvest: guardrails overlay + design-system + memory + release-notes) · `full` (+ ADRs +
procedures + how-tos). A one-pager site and a multi-year ERP differ only by this setting.

**ADR convention** (parallel-worktree-native — Relay's reason to exist): filename
`YYYY-MM-DD-<slug>.md`, **no sequential counter** (concurrent worktrees would fight over the next
number); refer by slug, never number; status `Accepted` / `Superseded-by-<slug>` / `Reversed`; **never
delete — supersede**.

**The Distilled marker.** When `/persist` harvests a brief, it stamps the brief with a line
`**Distilled:** <date> · pr-<n>` (or `· nothing-durable` when the lap taught nothing durable) — the same
shape as `/refine`'s `**Refined:**` stamp. This is the contract between `/persist` and `/tidy`: tidy may
archive or merge a spent brief **only** when it is not live **and** either the marker is present **or**
distillation is disabled (`persist.cadence: never` or `persist.level: none`). So "never prune
un-distilled knowledge" is a data invariant, not a matter of running order.

## Output — consistent, predictable, terse-by-default

- **Tables are always GFM markdown tables.** Any list of candidates/findings/plan-rows renders as a
  real table — **never** a stacked record list (`Field: value` lines) and **never** ASCII separators.
  Do not "helpfully" reformat when a table looks wide.
- **Keep cells terse so the table renders** — one short clause per cell (~≤8 words). Anything longer
  becomes a numbered footnote **under** the table, never a wider cell and never a fallback layout.
- **Every moving/destructive action is stated explicitly.** When a command moves or deletes a user
  file — adoption especially — it says so plainly: *"moved `ideas/x.md` → `relay/briefs/x.md`; the
  original is gone."* Never buried in a summary.
- **Adopted artifacts carry provenance.** A brief pulled in from a legacy doc gets a line
  `_Adopted from `ideas/x.md` (moved) · <date>_` so its origin is readable from the file itself,
  without `git` archaeology. A freshly-created brief has no such line — so "adopted vs created" is
  answerable at a glance.
- **Honour `verbosity`** for everything that isn't a table, a STOP gate, or the final landing.
- **Honour `audience`** (`plain` / `informed` / `expert`; absent ⇒ no shaping) — how much depth
  surfaces in the **terminal**: `plain` = executive summary; `informed` = decisions + what changed +
  what needs the driver, with exhaustive evidence deferred to the artifact; `expert` = full depth. It
  **never thins a written artifact** (brief, report, ADR, handover) and never drops a STOP-gate
  question or the decision itself.
- **No fabricated familiarity.** Describe options and defaults **neutrally** — say what an option *does*,
  not who it's for. A recommendation must rest on a **concrete, current** signal and be phrased as a
  tentative suggestion; never assert the user's preferences, style, or habits as fact, and never address
  a fresh session as if you already know them ("Fits *your* … style"). `CLAUDE.md` and memory are
  background context to *serve* the user, not material to characterise them back at themselves.

## Safety net — never leave a destructive move unrecoverable

Relay moves and rewrites the user's own files (adoption pulls a doc into `briefs/`; compaction rewrites
a design guide; migration renames dirs). None of that may be unrecoverable. The rule scales to whether
there's version control:

- **In a git repo, git *is* the backup — so lean on it.** Before a destructive op, make sure the
  affected files' current state is **committed** (a `git mv` + the adoption commit means the
  before-state is one `git revert`/`git checkout <sha> -- <path>` away). If the target has *uncommitted*
  changes, **STOP** — don't bury the user's in-flight work inside the adoption; ask them to commit or
  stash first. Always **report the undo path** in the result ("revert with `git revert <sha>`").
- **No git (or the file is untracked and staying that way) — make an explicit backup first.** Copy the
  original to `<root>/archive/pre-adopt/<name>.<timestamp>` *before* the move/rewrite, and **report
  where the backup is**. A plain `mv`/rewrite with no VC and no backup is the one thing never to do.
- **The STOP gate is the first line of defence** — every destructive op shows its plan and waits for
  approval before touching a file (see the explicit-reporting rules above). Backups are the *second*
  line, for when something was approved but later regretted.

## Housekeeping & link-integrity — keeping the volatile layer lean, safely

`/tidy` prunes, trims, and merges the volatile `<root>/` layer on a recurring basis. Because it edits
**shared, main-owned files** (the board especially) while ~10 sessions run concurrent worktrees against
one main, it honours these invariants:

- **Volatile-only.** It touches `<root>/` (briefs, handover, reviews, board) and **never** durable
  output (code, ADRs, guides, procedures, how-tos, anything a `paths.*` points at).
- **Distil-before-prune.** It defers any un-distilled brief to `/persist` and reports it, rather than
  dropping knowledge that was never harvested (the Distilled-marker invariant above).
- **Never touch live work.** A brief is off-limits if its topic is live — the board `Owner` names a
  live worktree, its status is ⚙/🔍, its worktree is `locked`, or its topic is still open/queued.
  Ambiguous ⇒ **keep and report**, never prune.
- **Parallel-worktree-safe commits.** It writes to `main` with the temp-index primitive (the pattern
  `/handover` uses: `read-tree FETCH_HEAD` → stage → `write-tree` → `commit-tree -p FETCH_HEAD` →
  push), wrapped in a **bounded retry-replay loop** — if main moved and the push is rejected, it
  re-fetches, recomputes the moves against the new tree, and re-pushes; it never clobbers a sibling's
  commit.
- **Link-integrity is a hard gate.** Any move rewrites inbound **path** references (the board's
  `Detail`/`Latest handover` columns, `<root>/briefs/*.md` cross-links) and a repo-wide
  no-dangling-path-link check must pass **before** the commit. Name-based `[[wikilinks]]` are stable
  under moves by design, so they're exempt.
- **Idempotent + reported.** A clean repo is a no-op (no commit, "nothing to tidy"); every run reports
  what was pruned / trimmed / merged / kept.

`daily`/`per-lap` cadence is wired via the harness scheduler (`/schedule`, cron) or `/loop` — a plugin
command can't schedule itself. (Worktree GC is a *different* job — `/gc` reclaims orphaned git
worktrees; `/tidy` is content only.)

## Hooks — plug the project's own automation into Relay's phases

A brownfield repo often already has commands/skills (a `test-stack` skill, a `commit` command). Relay
**dispatches them at the matching phase** instead of reinventing them, via a `hooks` map in
`relay.config.json` (this *is* project truth):
```json
{ "hooks": { "test": "test-stack",
             "commit": "commit",
             "env": { "up": "stack-up", "down": "stack-down" },
             "deploy": "deploy-preview",
             "release": "release" } }
```
- A command that has a hook for its phase **runs the hooked command/skill** at that point.
- No hook ⇒ the command's built-in behaviour (discover the test command from `CLAUDE.md`, etc.).
- `/adopt` populates this map when it reconciles an existing `.claude/` setup (keep-and-hook).

| Hook | Dispatched by | What it's for |
|---|---|---|
| `test` | `/ship` (Phase 1) | Run the suite, bringing its fixture stack up if it needs one |
| `commit` | `/ship`, `/handover` | This project's way of committing |
| `env.up` / `env.down` | `/test` (local target) · `/ship` (teardown) | Bring a **local test environment** up / take it down |
| `deploy` | `/deploy` | Trigger the project's **PR preview** |
| `release` | `/ship` (Phase 5.6, post-merge) | Cut a release for what just landed — one release per lap |

**Relay never owns an environment.** This is the same boundary `/deploy` states for deployment,
generalised: Relay names the *verify* phase and sequences it, the project owns the *mechanics*. That
matters most locally, where a stack is routinely shared with a sibling session — so:
- `/test` brings a local environment up **only** through `env.up`, never by hand;
- `/ship` calls `env.down` **only for an environment this session started**, and never touches one it
  found already running;
- **the `down` command is the project's place to be sibling-safe** — to refuse, or no-op, when
  something else is still using the stack. Relay can't know that; the project can.
- **No hook? Relay offers to write one.** `/test` (local) and `/deploy` (preview) each offer once to
  draft the project's command via the `authoring-skills` skill and wire it into this map. Decline and
  they fall back to printing the run command from `CLAUDE.md` as a manual precondition — never to
  starting or stopping things themselves.

## Custom review agents — extend the `/review` fan-out with your own

Where the `hooks` map plugs the project's *commands* into a phase, `review.agents` plugs the
project's *review agents* into `/review`. A declared agent is a `.claude/agents/*.md` the project
ships; `/review` folds it into the exact same machinery as the built-in ten — gate → session cap →
merged report — so it needs no new step, just a config entry:
```json
{ "review": { "agents": [
  { "name": "a11y-auditor", "gate": "copy-relevant", "tier": "cappable", "scope": "frontend", "priority": 50 }
] } }
```
- **`gate`** decides whether it runs for a given diff — either a built-in signal name (`frontend`,
  `backend`, `privacy-relevant`, `architecture-relevant`, `copy-relevant`) or a `{ "paths": [glob…] }`
  object matched against the changed files. Absent ⇒ always runs.
- **`tier`** decides whether the session-size cap applies: `safety` runs uncapped (like security /
  test / dbms); `cappable` (default) fills the budget after the built-ins, ordered by `priority`.
- **`scope`** (`frontend` | `backend` | `full`, default `full`) is the path scope handed to it.
- **The contract:** a declared agent MUST be a **findings-only reviewer** — severity-graded findings,
  each with a `file:line`, and nothing else. No report file, no verdict, no merge to main (the same
  "one specialist among several" contract every shipped agent honours). An agent that writes its own
  report or emits a pass/fail verdict breaks `/review`'s merge. The `authoring-skills` skill authors
  to this contract.
- `/adopt` populates this list when it reconciles an existing `.claude/agents/` (register-as-review-agent).
  Otherwise it's a small hand-edit — one entry per agent, project truth, committed.
