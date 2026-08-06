---
description: Scaffold the Relay convention in this repo — pick the root and budget tier, then the board, handover/roadmap/brief dirs, and pr-reviews — so /continue, /whats-next, /handover and /wrapup work on turn one
argument-hint: "[--root <dir>  (where durable state lives; default 'relay')] [--tier free|pro|max]"
---

Set up the durable files Relay's commands read and write, so a fresh repo can run the loop
immediately. This is **idempotent** — safe to run again; it never overwrites an existing
board or handover.

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
  continuity-first SSDLC workbench                          v0.13.0
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

## Step 0 — Choose the root and the budget tier, and record them
Relay keeps all its durable state under one **root** folder, and shapes how hard it fans out to a
per-repo **budget tier**. Decide both before scaffolding:

**Root:**
1. **Default `relay`.** Use it unless `$ARGUMENTS` passes `--root <dir>`, or the repo already keeps
   this kind of state somewhere (a `docs/board.md`, an existing handover convention) — in that case
   propose that dir as the root so nothing has to move.
2. Set `ROOT` to the chosen dir (`<root>` below = this value).

**Budget tier** (asked once, here — it drives how many review agents `/review-pr` fans out and how
wide `/whats-next` researches; later increments read it in `/refine` and `/test`):
3. If `$ARGUMENTS` passes `--tier free|pro|max`, take that. Otherwise **ask once**, plainly — it
   tracks the driver's Claude plan, not the project:
   - **`free`** — lean fan-out: a safety core (security · tests · migrations) plus a couple of
     specialists; verify/audit sweeps stay narrow. For a free Claude Code setup.
   - **`pro`** — moderate fan-out. The sensible middle if unsure.
   - **`max`** — full fan-out, every applicable specialist, widest sweeps. For a max plan.
   Set `TIER` to the answer. **If the user has no preference, leave `TIER` empty** — Relay then
   behaves exactly as it does today (full fan-out, no cap); the tier can be set later by re-running
   this command or editing `relay.config.json`. Never block setup on this.

**Write the config** — only when it carries something (a non-default root, or a tier); the plain
default (root `relay`, no tier) needs no file, so existing repos stay file-free. **Merge
surgically** — preserve any keys already there (e.g. a `guardrails` block from `/guardrails`):
```bash
if [ "$ROOT" != "relay" ] || [ -n "$TIER" ]; then
  base='{}'; [ -f relay.config.json ] && base="$(cat relay.config.json)"
  printf '%s' "$base" | jq --arg root "$ROOT" --arg tier "$TIER" '
      (if $root != "relay" then .root = $root else . end)
    | (if $tier != ""      then .tier = $tier else . end)
  ' > relay.config.json.tmp && mv relay.config.json.tmp relay.config.json
fi
```

4. **Already have a board under `<root>`?** Then you're *adopting*, not scaffolding — write only
   `relay.config.json` (the block above), skip the scaffold below, and report that the existing
   structure is now wired to the `relay:*` commands. This is the zero-migration path for a repo with
   a bespoke predecessor.

## Step 1 — Check what already exists
```bash
ls <root>/board.md <root>/roadmap.md 2>/dev/null
ls -d <root>/handover <root>/briefs <root>/archive <root>/pr-reviews 2>/dev/null
```
If `<root>/board.md` already exists, **do not overwrite it** — report that Relay is already
set up and stop (unless the user explicitly asks to re-scaffold). Otherwise continue.

## Step 2 — Create the directories
```bash
mkdir -p <root>/handover/archive <root>/briefs <root>/reference <root>/archive <root>/board-audit <root>/pr-reviews/archive
```
(`<root>/reference/` holds reference frames from `/cross-check` — how other systems and standards
solve a problem. It starts empty; `/cross-check` and `/explore` fill it over time.)

## Step 2.5 — Greenfield or populated? (never invent work from a folder name)
Whether to seed real tracks depends on whether there's actually a project here yet:
```bash
# tracked AND untracked (so a scaffolded-but-uncommitted project still reads as populated)
POPULATED="$( { git ls-files; git ls-files --others --exclude-standard; } 2>/dev/null \
  | grep -vE '^(relay/|README|LICENSE|\.)' | head -1)"
```
- **Populated** (`POPULATED` non-empty, or there's obvious source/config on disk) — there's a real
  codebase to describe, so inspect it (`CLAUDE.md`, packages/apps, README) and seed **2–4 real
  tracks** (Step 3) with a roadmap narrative and one brief stub (Step 4). **Also scan for
  pre-existing idea/plan docs and surface them on the board (Step 3.5)** — a real repo often already
  has intended work written down, and dropping it is the failure mode to avoid.
- **Greenfield** (empty repo, or nothing but the folder name and maybe a README) — **seed nothing
  speculative.** A folder called `todo-app` is not a spec; guessing tracks from the name just makes
  work the user has to delete. Scaffold the **structure only**: an **empty board**, a **roadmap
  header stub**, and **no brief**. The first real item arrives via `/explore` (Step 6 says so).

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

## Step 3.5 — Populated only: surface pre-existing idea/plan docs (NEVER drop them)
A real repo often already collects intended work as docs — the code tells you what *exists*, but
these tell you what the user *means to build*, and inspecting only the code misses them entirely.
**Discover them** (don't assume a folder name — look for anything that reads as "a thing we intend to
build"): an `ideas/`, `briefs/`, `rfcs/`, `proposals/`, `docs/*-project.md` / `*-baseline.md`, a
`HANDOFF.md`, and similar. Skip pure reference/convention docs (a design guide, DB conventions, an
architecture doc that's context, not a work item).

For **each** intended-work doc found, add a board **Open threads** row:
- **Status 💡** by default (icebox — it's captured, not committed), or **🔜** if the doc plainly says
  it's next/active.
- `Owner` = —, `Latest handover` = —, and **`Detail` = the doc's existing path** — point at it **in
  place**. Do **not** move, copy, or rewrite the user's docs into `<root>/briefs/`; Relay **adopts**,
  never migrates.
- Slot each under the best-fitting seeded track; add a track only if a cluster of ideas needs one.

**Completeness beats tidiness:** list every intended-work doc, even a dozen 💡 rows. A board that
silently omits work the user already wrote down is worse than a long one — the whole point of the
board is that nothing in flight or intended is invisible. In the report (Step 6), say **how many** you
surfaced and from where.

## Step 4 — Write the roadmap (and, only if populated, a first brief stub)
Write `<root>/roadmap.md` — the narrative behind each board item (the board stays terse; the
roadmap carries the "why" and the sequencing). **Greenfield → write the header only** (no invented
sections); the narrative grows as `/explore` adds items.

```markdown
# Roadmap

The detailed narrative behind each board item. The board (`<root>/board.md`) is the terse
index; this is where the reasoning, sequencing, and open decisions live.

## <track-name>          ← populated only; omit on greenfield
### <track>/<slug>
<what it is, why it matters, the rough sequence of slices>
```

**Populated only** — write one real brief stub so the pattern is visible, `<root>/briefs/<slug>.md`.
**Greenfield → skip this entirely** (there's no work to brief yet — `/explore` writes the first brief):

```markdown
# <slug>

**Status:** 🔜 queued

## What & why
<the unit of work, in plain language>

## Slices
1. <first shippable slice>
2. <next>

## Open questions
- <anything unresolved>
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
- **`pr-reviews/`** — one merged review report per PR.

Commands: `/explore` (shape an idea) · `/whats-next` (what to work on) · `/continue` (resume a
thread) · `/cross-check` (check against prior art) · `/test-drive` (draft PR + structured test
plan; can drive it in the browser) · `/watch` (park on a dependency, auto-resume when it lands) ·
`/wrapup` (test→review→merge→handover→tidy). `/review-pr`, `/fix-pr-review`, `/handover` are run
by `/wrapup` — call them standalone only when you need one on its own. `/garbage-collect` reclaims
orphaned worktrees when needed.
```

## Step 6 — Commit and report (compact)
```bash
git add <root> && [ -f relay.config.json ] && git add relay.config.json
git commit -m "chore: scaffold Relay workflow"
```
Do NOT push automatically — let the user review first. Then give **one compact report** (a few lines,
no file-content recaps):
- **What was created** — the `<root>/` structure, in one line; and the **tier** recorded (or "none —
  full fan-out").
- **Populated only** — the tracks you seeded (a guess to edit) and **how many pre-existing idea/plan
  docs you surfaced** as 💡 items, and from where (e.g. "6 ideas from `ideas/` added as icebox items").
  So the user can see nothing they'd written down was dropped.
- **The next move** — the important part, and it differs by what you found in Step 2.5:
  - **Greenfield** → the board is intentionally **empty**. Next: **`/relay:explore <your first idea>`**
    to shape the first feature into a brief. Do NOT tell them to run `/relay:whats-next` yet — there's
    nothing on the board to pick.
  - **Populated** → **`/relay:whats-next`** to pick from the seeded tracks (edit them first — a guess).
- **Write commands with the `/relay:` prefix** — they're plugin-namespaced, so a bare `/explore` isn't
  a command (it tab-completes to the built-in `/export`). Always show the full `/relay:<name>` so the
  user can copy it straight; tell them to tab-complete *after* the colon.
- **The loop, one line** so they see the shape (each is a `/relay:` command, optional — invoke what the
  work needs): `explore → refine → whats-next/continue → test-drive → deploy → review-pr → wrapup → persist`.
