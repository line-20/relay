---
description: Scaffold the Relay convention in this repo — pick the root, then the board, handover/roadmap/brief dirs, and pr-reviews — so /continue, /whats-next, /handover and /wrapup work on turn one
argument-hint: "[--root <dir>  (where durable state lives; default 'relay')]"
---

Set up the durable files Relay's commands read and write, so a fresh repo can run the loop
immediately. This is **idempotent** — safe to run again; it never overwrites an existing
board or handover.

## Step 0 — Choose the root and record it
Relay keeps all its durable state under one **root** folder. Decide it before scaffolding:
1. **Default `relay`.** Use it unless `$ARGUMENTS` passes `--root <dir>`, or the repo already keeps
   this kind of state somewhere (a `docs/board.md`, an existing handover convention) — in that case
   propose that dir as the root so nothing has to move.
2. Set `ROOT` to the chosen dir (`<root>` below = this value).
3. **Write `relay.config.json` at the repo root when `ROOT` isn't `relay`** so every command finds
   it (the default needs no file — absent config ⇒ `relay`):
   ```bash
   [ "$ROOT" != "relay" ] && printf '{\n  "root": "%s"\n}\n' "$ROOT" > relay.config.json
   ```
4. **Already have a board under `<root>`?** Then you're *adopting*, not scaffolding — write only
   `relay.config.json` (step 3), skip the scaffold below, and report that the existing structure is
   now wired to the `relay:*` commands. This is the zero-migration path for a repo with a bespoke
   predecessor.

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

## Step 3 — Write the board (the front door)
Write `<root>/board.md`. The board has two parts: **Tracks** (stable, long-lived lanes of
work) and **Open threads** (the authoritative table of what's in flight *right now*).
Seed it with the tracks that fit this repo — inspect the repo first (its `CLAUDE.md`,
top-level packages/apps, README) and name 2–4 real tracks rather than inventing generic
ones. Use this shape:

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

## Step 4 — Write the roadmap and a first brief stub
Write `<root>/roadmap.md` — the narrative behind each board item (the board stays terse; the
roadmap carries the "why" and the sequencing):

```markdown
# Roadmap

The detailed narrative behind each board item. The board (`<root>/board.md`) is the terse
index; this is where the reasoning, sequencing, and open decisions live.

## <track-name>
### <track>/<slug>
<what it is, why it matters, the rough sequence of slices>
```

Write one placeholder brief so the pattern is visible, `<root>/briefs/<slug>.md`:

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

## Step 6 — Commit and report
```bash
git add <root>/board.md <root>/roadmap.md <root>/briefs <root>/README.md
[ -f relay.config.json ] && git add relay.config.json    # only exists when root ≠ relay
git commit -m "chore: scaffold Relay workflow (board + handover + briefs)"
```
Do NOT push automatically — let the user review first. Then report, in plain language:
what was created, the tracks you seeded (and that they're a starting guess to edit), and
that they can now run `/whats-next` to pick the first thing to work on.
