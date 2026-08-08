# The board model

This is the one mental model everything in Relay rests on. If you read only one doc, read
this one.

> Commands are namespaced `/relay:<name>` — this doc writes them bare (`/next`, `/refine`, …) for
> readability; add the `/relay:` prefix when you type (tab-complete after the colon). `/relay:help`
> prints the whole map.

## The problem it solves

You run several Claude sessions at once. Each one works on something different. You check
back on them when work has landed, not while it's in flight. Days pass. Sessions get
`/clear`ed. New sessions start cold.

In that world, **"what's the current state of the project?" has no answer you can get from a
chat history** — there are five chat histories, they interleave, and most are gone. The
naive fix — "just read the newest handover file" — is actively wrong: the newest file by
timestamp belongs to whichever session happened to finish last, which tells you nothing
about the thread *you* care about. Threads don't take turns.

Relay's answer: **one durable, curated index, on `main`, that every session reads and
writes.** That's the board.

> **A note on paths.** This doc writes the durable files as `relay/…`, the default. Paths are
> **configurable per repo** via `relay.config.json`. Two layers, one uniform rule:
> - `{ "root": "docs" }` relocates the whole root — every `relay/…` becomes `docs/…`.
> - a `paths` block relocates any *single* logical path independently, e.g.
>   `{ "paths": { "knowledge": "docs", "design-system": "packages/ui/DESIGN.md" } }`.
>
> Resolution: a command maps a logical name to `paths[name]` if set, else `<root>/<name>`. **List only
> what you move**; with no config, everything sits under `relay/` exactly as shown. Process state
> (board, briefs, handover, reviews, audits) usually stays under the root; deliverable knowledge
> (design system, docs) often lives with the code — which is why each path is independently movable.
> Read every `relay/…` below as "the resolved path".

## The three concepts

### 1. The board (`relay/board.md`)

The front door. It has two parts:

- **Open threads** — a table of what is in flight *right now*. This is the **source of
  truth**. Not the newest file; not your memory; this table.
- **Tracks** — the stable, long-lived lanes the work is grouped into (e.g. "auth",
  "billing", "platform"). Tracks barely change. Items move through them.

Every item has a stable slug, `track/slug`, that never changes even as its status does. You
refer to work by its slug, everywhere — in briefs, handovers, reviews, and to Claude.

**Epics** are the one grouping between a track and a slice, for work too big for a single session.
An epic is a **pure slug convention plus a grouping view — no new board columns**: its slices share a
slug stem, `track/epic/slice` (e.g. `backend/goods-value-chain/purchase`, `…/production`, `…/sales`),
and the board lists them together under the epic. `/refine` produces the slices; `/next` groups them
and recommends the next unstarted one. Nothing else changes — an epic is just how related slices are
named and shown, so it stays weightless until the work actually earns it.

### 2. Threads and their status

An **item** on the board is a unit of work. Its **status glyph** says where it is:

| Glyph | Meaning | Who owns it |
|---|---|---|
| 💡 | idea (icebox) | nobody — a maybe-someday |
| 🔜 | next (queued) | nobody — free to start with `/next` |
| ⚙ | in-progress | a live session in a worktree |
| 🔍 | in-review | a live session (PR open) |
| ⏸ | parked | nobody — blocked on something; note what |
| ✅ | done | shipped; leaves Open threads |

The **Owner** column names the live branch/worktree actively on an item, or `—` when it's
free. This is what keeps parallel sessions from colliding: `/next` and `/continue` skip
anything a live owner holds, and `/handover` sets `Owner = —` when it relinquishes a thread
so a cold session can pick it up.

A shipped item **leaves Open threads** and collapses to a one-line `✅ Done: <slug>` on its
track — `/tidy` does this trimming in bulk. A shipped item with **one loose end** stays an
Open-threads row (🔜/⏸) linking back to its brief: the board *is* the residue tracker, so
near-done tails live here, never in a separate file.

### 3. The handover (`relay/handover/next-*.md`)

When a session ends or hands off, it writes a **cold-start handover**: a self-contained
prompt a fresh session can act on with zero chat history. Where we are, what just landed,
what's in flight, the next objective, the context you'd otherwise have to re-research, where
to start, and what "done" means. The board's row for that item links its **latest**
handover, so `/continue` resumes *that thread's* note — never "whatever's newest".

## Why it's committed to `main`

The board and the handovers land directly on `main` — not on a feature branch, not in a PR.
Three reasons:

1. **Every session can see them.** A brand-new worktree, before it has merged anything, can
   still `git fetch origin main` and read the current board. State that lived on a branch
   would be invisible to siblings.
2. **They outlive the work.** The feature branch gets deleted at merge; the durable record
   shouldn't die with it.
3. **They're not code.** They don't need review; they need to be *available*. A PR round-trip
   would just add latency to the one thing every session depends on being current.

`/handover` does this without switching your working branch — it builds a commit against
`main` with a temporary git index and pushes just those two files. Your feature branch and
working tree are never disturbed.

## The one discipline: the board is shared, so never clobber it

Because the board is main-owned and several sessions write to it, every Relay command that
touches it follows the same rule: **start from `main`'s copy, make one surgical edit, commit
just that.** Never overwrite the whole board from stale local state — you'd wipe a parallel
session's row. `/handover` refreshes from `FETCH_HEAD` before editing for exactly this reason.

The same care extends to worktrees, which are keyed to the **topic**, not the slice: when the
loop closes `/handover` **keeps** its own topic tree for the next slice (removing it only once the
topic itself is done), and prunes dead worktree entries — but it only ever *reports* a sibling
worktree for removal when it's merged, clean, **and** its topic is no longer live on the board
(never a resting topic tree), and never force-removes another session's tree. When in doubt, Relay
reports and waits rather than deleting.

## How the commands map onto the model

- `/explore` **writes** a new item: it interrogates a rough idea (purely context-free), weighs
  alternatives, and adds a brief + a board row (🔜/💡) — the front of the loop that feeds everything.
- `/refine` **grooms** an item's brief against the project (code, guardrails, threat model, budget-
  sized slices) — the bridge from a shaped idea to a buildable one; may slice a large item into an epic.
  On a brownfield repo it also **pulls a referenced legacy doc into `briefs/`** as it grooms it
  (adopt-on-touch), so the board row flips from "referenced outside `relay/`" to Relay-owned.
- `/adopt [area]` **bulk-adopts** a brownfield area: moves its work-inputs into `briefs/` (tidying
  them) and registers + compacts its deliverable docs in place. The fast-forward for what `/refine`
  and `/guardrails` otherwise do gradually; scoped, and never touches a file without approval.
- `/cross-check` **writes** a reference frame under `relay/reference/` (how others solve the
  problem) and checks an approach against it — offered at the end of `/explore`, or on its own.
- `/next` **reads** Open threads, filters to what's startable (🔜/⏸/💡, no live owner),
  ranks it, and starts your pick in the topic's worktree (created once, reused each slice).
- `/continue` **reads** Open threads, finds your thread (by slug or current branch), and
  resumes from its linked handover.
- `/watch` **parks** an item (⏸, `blocked-on: …`) when it depends on a sibling's unlanded work,
  watches the dependency reach `main` in the background, and flips the row back to ⚙ (reclaiming
  `Owner`) when it lands — the only command that drives the ⏸ state programmatically.
- `/test` touches the **PR, not the board**: it opens a draft PR for the thread's branch and
  writes a structured test plan into it (and can drive it in the browser) — a pre-merge checkpoint
  that never merges.
- `/handover` **writes** a handover and **updates** the item's row (status, owner → `—`,
  latest handover), both onto `main`.
- `/ship` runs the ship loop and ends by calling `/handover`.
- `/handover`, as it commits, also **archives** superseded handovers/reviews the board no
  longer references and **prunes** dead worktree entries — the end-of-session housekeeping,
  folded into the step that already touches those records.
- `/gc` is the off-happy-path escape hatch: it **reclaims** orphaned worktrees a
  crashed or un-handed-over session left behind. You don't need it in normal use.
- **Reflect** is not a command but a **loop edge**: after a lap's result is seen (`/test`, `/ship`,
  `/persist`), you re-enter with what you learnt — `/explore` for a genuinely new idea, `/refine` for
  the same idea changed. That re-entry is what makes the board a spiral, not a queue.

That's the whole system. Everything else is detail.

Next: **[a-day-in-the-loop.md](a-day-in-the-loop.md)** — one item walked end to end.
