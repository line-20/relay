---
description: Scaffold the Relay convention in this repo — the board, handover/roadmap/brief dirs, and relay/pr-reviews — so /continue, /next, /handover and /wrapup work on turn one
argument-hint: "(no arguments)"
---

Set up the durable files Relay's commands read and write, so a fresh repo can run the loop
immediately. This is **idempotent** — safe to run again; it never overwrites an existing
board or handover.

## Step 1 — Check what already exists
```bash
ls relay/board.md relay/roadmap.md 2>/dev/null
ls -d relay/handover relay/briefs relay/archive relay/pr-reviews 2>/dev/null
```
If `relay/board.md` already exists, **do not overwrite it** — report that Relay is already
set up and stop (unless the user explicitly asks to re-scaffold). Otherwise continue.

## Step 2 — Create the directories
```bash
mkdir -p relay/handover/archive relay/briefs relay/archive relay/board-audit relay/pr-reviews/archive
```

## Step 3 — Write the board (the front door)
Write `relay/board.md`. The board has two parts: **Tracks** (stable, long-lived lanes of
work) and **Open threads** (the authoritative table of what's in flight *right now*).
Seed it with the tracks that fit this repo — inspect the repo first (its `CLAUDE.md`,
top-level packages/apps, README) and name 2–4 real tracks rather than inventing generic
ones. Use this shape:

```markdown
# Board

The front door. **Open threads** is the source of truth for what's in flight — never
"newest handover wins". Each item has a stable `track/slug`. Detail lives in
`relay/roadmap.md` and per-item briefs under `relay/briefs/`.

Status glyphs: 💡 idea (icebox) · 🔜 next (queued) · ⚙ in-progress · 🔍 in-review · ⏸ parked · ✅ done

## Open threads

| Item | Status | Owner | Latest handover | Detail |
|---|---|---|---|---|
| `<track>/<slug>` | 🔜 | — | — | `relay/briefs/<slug>.md` |

> `Owner` = the live branch/worktree actively on it, or `—` when it's free for `/continue`
> to pick up. `Latest handover` links the `relay/handover/next-*.md` a cold session resumes from.

## Tracks

### <track-name>
<one line on what this track is about>
- 🔜 `<track>/<slug>` — <one-line summary>
- ✅ Done: <slug>, <slug>
```

## Step 4 — Write the roadmap and a first brief stub
Write `relay/roadmap.md` — the narrative behind each board item (the board stays terse; the
roadmap carries the "why" and the sequencing):

```markdown
# Roadmap

The detailed narrative behind each board item. The board (`relay/board.md`) is the terse
index; this is where the reasoning, sequencing, and open decisions live.

## <track-name>
### <track>/<slug>
<what it is, why it matters, the rough sequence of slices>
```

Write one placeholder brief so the pattern is visible, `relay/briefs/<slug>.md`:

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
Create `relay/README.md` (or append to it) a short note so a newcomer to the repo
understands the convention:

```markdown
# Working in this repo with Relay

- **`board.md`** — the front door. `Open threads` is what's in flight now.
- **`roadmap.md`** — the narrative behind each board item.
- **`briefs/`** — one brief per unit of pending work.
- **`handover/`** — cold-start handovers; `/continue` resumes from the newest per thread.
- **`relay/pr-reviews/`** — one merged review report per PR.

Commands: `/brainstorm` (shape an idea) · `/next` (what to work on) · `/continue` (resume a thread) · `/review-pr` ·
`/wrapup` (test→review→merge→handover→tidy). `/review-pr`, `/fix-pr-review`, `/handover` are
run by `/wrapup` — call them standalone only when you need one on its own.
```

## Step 6 — Commit and report
```bash
git add relay/board.md relay/roadmap.md relay/briefs relay/README.md
git commit -m "chore: scaffold Relay workflow (board + handover + briefs)"
```
Do NOT push automatically — let the user review first. Then report, in plain language:
what was created, the tracks you seeded (and that they're a starting guess to edit), and
that they can now run `/next` to pick the first thing to work on.
