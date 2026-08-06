# Relay conventions — prefs, output, hooks

The shared contracts every Relay command honours. Two config surfaces, one output style, one
extension mechanism. Commands reference this doc so behaviour is consistent across the whole set.

## Two config surfaces — project vs driver

Relay separates **what the project is** from **how the driver wants to work right now**. They live in
different files because they have different owners and lifetimes.

| | `relay.config.json` (committed) | `relay.config.local.json` (gitignored) |
|---|---|---|
| Owns | project truth — shared by everyone | the driver's here-and-now preferences |
| Holds | `root`, `paths`, `guardrails`, `hooks` | `session`, `verbosity` |
| Lifetime | stable; changes rarely | switch-often; personal, per-machine |
| Committed? | yes | **no** (`/init` adds it to `.gitignore`) |

A teammate on a different Claude plan, or in a different mood about session size, must not inherit
yours — so those signals are **local, never committed**.

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

### Per-call overrides (the "case by case")
Any command accepts these words in its arguments and they win over the files, for that one run:
`small` / `medium` / `large` (session) and `terse` / `quiet` / `verbose` (verbosity). E.g.
`/refine large`, `/next small terse`, `/review verbose`.

**Resolution order (both signals):** per-call word → `relay.config.local.json` → (`relay.config.json`
`tier`, back-compat only) → default. Resolve once at a command's Step 0:
```bash
LOCAL=relay.config.local.json
SESSION="$(jq -r '.session // empty' "$LOCAL" 2>/dev/null)"; : "${SESSION:=$(jq -r '.tier // empty' relay.config.json 2>/dev/null)}"
VERBOSITY="$(jq -r '.verbosity // "normal"' "$LOCAL" 2>/dev/null || echo normal)"
# then let any per-call word in $ARGUMENTS override SESSION / VERBOSITY
```
> **Migration note:** `session` supersedes the old `tier` (`free`/`pro`/`max`). A committed `tier` is
> still read as a fallback so nothing breaks; new setups write `session` to the local file instead.

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

## Hooks — plug the project's own automation into Relay's phases

A brownfield repo often already has commands/skills (a `test-stack` skill, a `commit` command). Relay
**dispatches them at the matching phase** instead of reinventing them, via a `hooks` map in
`relay.config.json` (this *is* project truth):
```json
{ "hooks": { "test": "test-stack", "commit": "commit", "deploy": "…" } }
```
- A command that has a hook for its phase **runs the hooked command/skill** at that point (e.g. `/test`
  and `/ship` bring the fixture stack up via the `test` hook; `/ship`/`/handover` commit via `commit`).
- No hook ⇒ the command's built-in behaviour (discover the test command from `CLAUDE.md`, etc.).
- `/adopt` populates this map when it reconciles an existing `.claude/` setup (keep-and-hook).
