---
description: Scaffold the MINIMAL Relay convention — a board and the dirs to start — so /explore, /next and /continue work on turn one. Works on greenfield and brownfield; deepens progressively; never destructive.
argument-hint: "[--root <dir>  (where durable state lives; default 'relay')]"
---

Get a repo ready to run the Relay loop **with the least possible ceremony**. This does the *minimum*
to start — a board and the dirs the first commands write — and **nothing else up front**. Everything
heavier (session size, verbosity, guardrails, pulling legacy docs into Relay) is **deferred** and
offered by the phase that needs it, so onboarding is a few seconds, not a setup wizard. It's
**idempotent** (safe to
re-run) and **never destructive** — it never moves your files or overwrites an existing board.

It handles **both kinds of repo**:
- **Greenfield** (empty repo) → an empty board + a pointer to `/explore`. Nothing invented.
- **Brownfield** (existing project) → a board with real tracks from your code and your existing
  idea/plan docs **surfaced by reference** (left exactly where they are). Pulling them *into* Relay is
  a later, opt-in step (`/refine` does it on touch; `/adopt` does it in bulk) — never at init.

**Always begin with the banner — non-negotiable, and it OVERRIDES the "run quietly" discipline
below.** Your reply MUST start, before any other text, thinking, or tool call, with this banner
printed **verbatim inside a fenced code block** (monospace keeps it aligned). Never skip it, never
compress it to a plain line, never treat it as optional decoration — it is the first thing the user
sees and the one signal that certifies which command file ran:

```
 ____      _
|  _ \ ___| | __ _ _   _
| |_) / _ \ |/ _` | | | |
|  _ <  __/ | (_| | |_| |
|_| \_\___|_|\__,_|\__, |
                   |___/
  continuity-first SSDLC workbench                          v1.0.9
  by Line20 · @eriklenaerts
```

The version is **hardcoded in this banner on purpose** — it certifies which command file actually
ran, so if it shows an older number than the installed plugin, the session is running a **cached**
command and needs a reload (a pre-banner cached command prints no banner at all — an instant tell).
`${CLAUDE_PLUGIN_ROOT}` doesn't expand in command bash, so there's no runtime read.
**Maintainers: bump the version in this banner on every release.**

> **Output discipline (everything AFTER the banner).** Scaffolding is routine — run it quietly. Don't
> narrate between writes, don't echo file contents back to the terminal, and **don't seed speculative
> content**. End with **one compact report** (Step 6), not a play-by-play.

## Step 0 — Choose the root (don't ask for anything you don't need yet)
Relay keeps its durable state under one **root** folder (default `relay/`).
1. Use `relay` unless `$ARGUMENTS` passes `--root <dir>`, or the repo already keeps this kind of state
   somewhere (a `docs/board.md`, an existing handover convention) — then propose that dir so nothing
   has to move. Set `ROOT` to the chosen dir (`<root>` below = this value).
2. **Ask for nothing else here.** Session size and verbosity are **driver preferences**, not project
   config — they live in a gitignored `relay.config.local.json` and are offered just-in-time by the
   phase that needs them (see [[conventions]]). Don't interrogate them at init.

**Write `relay.config.json`** only if the root is non-default; the plain default needs no file. Merge
surgically — preserve existing keys (e.g. a `guardrails` block):
```bash
if [ "$ROOT" != "relay" ]; then
  base='{}'; [ -f relay.config.json ] && base="$(cat relay.config.json)"
  printf '%s' "$base" | jq --arg root "$ROOT" '.root = $root' > relay.config.json.tmp && mv relay.config.json.tmp relay.config.json
fi
```

**Keep local prefs out of git.** Ensure `.gitignore` ignores the driver-preferences file (create/append):
```bash
grep -qxF 'relay.config.local.json' .gitignore 2>/dev/null || echo 'relay.config.local.json' >> .gitignore
```

3. **Already have a board under `<root>`?** Then you're *adopting*, not scaffolding — write only the
   config block above (if anything), skip the scaffold, and report the existing structure is wired to
   `relay:*`. Zero-migration path for a repo with a bespoke predecessor.

## Step 1 — Check what already exists (and migrate a pre-1.0 layout)
```bash
ls <root>/board.md <root>/roadmap.md 2>/dev/null
ls -d <root>/handover <root>/briefs <root>/archive <root>/reviews 2>/dev/null
ls -d <root>/pr-reviews <root>/board-audit 2>/dev/null   # pre-1.0 dir names
```
If `<root>/board.md` already exists, **do not overwrite it** — report that Relay is already set up and
stop (unless the user asks to re-scaffold) — **except** for the migration below.

**Migrate a pre-1.0 layout.** If `<root>/pr-reviews/` or `<root>/board-audit/` exists, this repo was
set up before the 1.0 dir renames. **Offer to migrate** (the only file-level 1.0 migration): rename
`pr-reviews/`→`reviews/` and `board-audit/`→`audits/`, and fix references in the repo's own
`<root>/*.md` (board, README). Nothing else in a consumer repo changes — the command renames are just
what you type, not stored. Use a history-preserving move where there's git, plain `mv` otherwise:
```bash
mig() { [ -d "$1" ] || return 0
  if git rev-parse --is-inside-work-tree >/dev/null 2>&1 && git ls-files --error-unmatch "$1" >/dev/null 2>&1
  then git mv "$1" "$2"; else mv "$1" "$2"; fi; }
mig <root>/pr-reviews <root>/reviews
mig <root>/board-audit <root>/audits
# then: perl -pi -e 's/\bpr-reviews\b/reviews/g; s/\bboard-audit\b/audits/g' <root>/*.md
```
**STOP for approval before migrating** (it moves files), then report what was renamed. Otherwise continue.

## Step 2 — Create the minimal directories
Create only what the first commands write — the rest (`reference/`, `reviews/`, `audits/`, `archive/`)
are made lazily by the command that first needs them, so init stays light:
```bash
mkdir -p <root>/briefs <root>/handover/archive
```

## Step 2.5 — Greenfield or populated? (never invent work from a folder name)
Whether to seed real tracks depends on whether there's actually a project here yet:
```bash
# tracked AND untracked (so a scaffolded-but-uncommitted project still reads as populated)
POPULATED="$( { git ls-files; git ls-files --others --exclude-standard; } 2>/dev/null \
  | grep -vE '^(relay/|README|LICENSE|\.)' | head -1)"
```
- **Populated** (`POPULATED` non-empty, or there's obvious source/config on disk) — there's a real
  codebase to describe, so inspect it (`CLAUDE.md`, packages/apps, README) and seed **2–4 real
  tracks** (Step 3). **Also surface any existing idea/plan docs on the board — by reference (Step
  3.5)**, so nothing the user wrote down is invisible. Init **references** them in place; it never
  moves or rewrites them.
- **Greenfield** (empty repo, or nothing but the folder name and maybe a README) — **seed nothing
  speculative.** A folder called `todo-app` is not a spec; guessing tracks from the name just makes
  work the user has to delete. Scaffold the **structure only**: an **empty board** and a **roadmap
  header stub**. The first real item arrives via `/explore` (Step 6 says so).

## Step 3 — Write the board (the front door)
Write `<root>/board.md`. The board has two parts: **Tracks** (stable, long-lived lanes of
work) and **Open threads** (the authoritative table of what's in flight *right now*).

- **Populated** — seed the tracks that fit this repo (2–4 **real** ones from the Step 2.5 inspection,
  never generic filler), each with a queued item where one is obvious.
- **Greenfield** — write the board with the shape below but an **empty Open threads table** (the
  header row only) and a Tracks section holding a single line: `_No tracks yet — run `/explore` to
  shape the first item._` **Invent nothing.**

Use this shape:

```markdown
# Board

The front door. **Open threads** is the source of truth for what's in flight — never
"newest handover wins". Each item has a stable `track/slug`. Detail lives in
`<root>/roadmap.md` and per-item briefs under `<root>/briefs/`.

Status glyphs: 💡 idea (icebox) · 🔜 next (queued) · ⚙ in-progress · 🔍 in-review · ⏸ parked · ✅ done

## Open threads

| Item | Status | Owner | Latest handover | Detail |
|---|---|---|---|---|
| `<track>/<slug>` | 🔜 | — | — | `<root>/briefs/<slug>.md` |

> `Owner` = the live branch/worktree actively on it, or `—` when it's free for `/continue`
> to pick up. `Latest handover` links the `<root>/handover/next-*.md` a cold session resumes from.

## Tracks

### <track-name>
<one line on what this track is about>
- 🔜 `<track>/<slug>` — <one-line summary>
- ✅ Done: <slug>, <slug>
```

> **Epics** (optional grouping): work too big for one session is an epic — a slug convention, not a
> schema. Its slices share a stem `track/epic/slice` and list together under the epic. Don't create
> epics at scaffold time; they emerge when `/refine` slices something large.

## Step 3.5 — Populated only: surface existing work-inputs BY REFERENCE (non-destructive)
A real repo usually already holds intended work written down — and init's job is to make sure **none
of it is invisible on the board**, without touching a single file. **Discover** the work-input docs
(the "something to build" kind — `ideas/`, `briefs/`, `rfcs/`, `proposals/`, `todo/`, `notes/`,
`docs/*-project.md` / `*-baseline.md`, `HANDOFF.md`). For each, add a board **Open-threads** row:
- **💡** by default (🔜 if the doc plainly says it's next/active), `Owner` = —, and **`Detail` = the
  doc's existing path** — pointed at **in place**. **Do NOT move, copy, or rewrite it.**
- Slot each under the best-fit track.

That's it — init only *references*. A `Detail` that points **outside `<root>/`** is the board's own
signal for "referenced legacy, not yet pulled in". Pulling a work-input *into* Relay (moving it into
`<root>/briefs/` and actualising it) is deliberately deferred:
- **`/refine`** pulls one in the moment you groom it (per-idea, as you work);
- **`/adopt [area]`** pulls a whole area in at once (the bulk escape hatch) and can compact deliverable
  docs too.

**Deliverable-knowledge docs** (design guide, conventions, architecture — the "how we work" kind) are
**not** board items and are **left entirely alone** here; they're adopted by `/guardrails` (registered
as `extends`, in place) when a dimension first matters. Just **note** in the report that they exist.

**Completeness beats tidiness:** reference every work-input doc — the board must never silently omit
work the user already wrote down.

## Step 4 — Write a roadmap header stub (keep it minimal)
Write `<root>/roadmap.md` — the narrative behind board items. At init, write **only the header** on
both greenfield and populated; the narrative grows as `/explore` and `/refine` add and shape items.
Don't invent per-item roadmap prose, and don't write brief stubs — briefs come from `/explore` (new
ideas) or the referenced legacy docs (pulled in later by `/refine`/`/adopt`).

```markdown
# Roadmap

The detailed narrative behind each board item. The board (`<root>/board.md`) is the terse
index; this is where the reasoning, sequencing, and open decisions live.
```

## Step 5 — Add a README pointer to the docs dir
Create `<root>/README.md` (or append to it) a short note so a newcomer to the repo
understands the convention:

```markdown
# Working in this repo with Relay

- **`board.md`** — the front door. `Open threads` is what's in flight now.
- **`roadmap.md`** — the narrative behind each board item.
- **`briefs/`** — one brief per unit of pending work.
- **`handover/`** — cold-start handovers; `/continue` resumes from the handover the board links
  for a thread (not "newest wins").
- **`reference/`** — reference frames from `/cross-check` (how others solve a problem).
- **`reviews/`** — one merged review report per PR (created on first review).

The loop: `/explore` (shape an idea) → `/refine` (ground it against the code + guardrails) →
`/next` / `/continue` (build) → `/test` (draft PR + test plan; can drive it) → `/deploy` (verify +
security-gate a PR preview) → `/review` → `/ship` (test→review→merge→handover) → `/persist` (harvest
lessons + release notes). Setup/support: `/guardrails` (project standards), `/adopt` (pull legacy docs
into Relay, by area), `/cross-check` (prior art), `/watch` (park on a dependency), `/handover`,
`/gc` (reclaim orphaned worktrees), `/version`. Each is optional — invoke what the work needs.
```

## Step 6 — Commit and report (compact)
**Only if this is a git repo** — commit the scaffold and adoption. **Do not `git init` a project that
isn't under version control** (not every project is in git); just leave the files in place and say so.
Stage **only what init touched** — never `git add -A` (that would sweep the user's unrelated
uncommitted work into the scaffold commit):
Init only *creates* files (and, if you accepted it, the Step 1 migration renames) — it never moves the
user's docs. Stage **only what init touched** — never `git add -A`:
```bash
if git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  git add <root> relay.config.json 2>/dev/null   # scaffold + config (+ any migration renames/rewrites)
  git commit -m "chore: scaffold Relay (board + dirs)"
else
  : # not a git repo — files written in place, nothing to commit (report this)
fi
```
Do NOT push automatically — let the user review first. Then give **one compact report** (a few lines,
no file-content recaps):
- **What was created** — the `<root>/` structure, in one line. If not a git repo, say the files were
  written but **not committed** (no git).
- **Populated only** — the tracks you seeded (a guess to edit) and **how many existing idea/plan docs
  you referenced** on the board (from where, e.g. "6 from `ideas/`, left in place"), plus a note of any
  deliverable-knowledge docs you spotted. Nothing was moved.
- **The next move** — differs by what Step 2.5 found:
  - **Greenfield** → the board is intentionally **empty**. Next: **`/relay:explore <your first idea>`**.
    Don't point at `/relay:next` yet — nothing's on the board.
  - **Populated** → **`/relay:next`** to start something, or **`/relay:refine <slug>`** to ground a
    referenced idea (which also pulls it into Relay).
- **Deepen when you need it (not now)** — **config is opt-in depth, never a gate.** One line: run
  **`/relay:config`** anytime for a guided pass (it proposes what's worth setting for this repo —
  session size, guardrails, hooks — and walks it), or just keep working and each phase offers the one
  knob it needs. Don't set anything up now unless the user asks. (If the repo already has
  `.claude/commands` or skills, mention `/relay:adopt` reconciles them.)
- **Write commands with the `/relay:` prefix** (a bare `/explore` tab-completes to the built-in
  `/export`) — show the full `/relay:<name>`; tab-complete after the colon.
- **The loop, one line** (each a `/relay:` command, optional — invoke what the work needs):
  `explore → refine → next/continue → test → deploy → review → ship → persist`.
