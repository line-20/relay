# The board model

This is the one mental model everything in Relay rests on. If you read only one doc, read
this one.

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

## The three concepts

### 1. The board (`relay/board.md`)

The front door. It has two parts:

- **Open threads** — a table of what is in flight *right now*. This is the **source of
  truth**. Not the newest file; not your memory; this table.
- **Tracks** — the stable, long-lived lanes the work is grouped into (e.g. "auth",
  "billing", "platform"). Tracks barely change. Items move through them.

Every item has a stable slug, `track/slug`, that never changes even as its status does. You
refer to work by its slug, everywhere — in briefs, handovers, reviews, and to Claude.

### 2. Threads and their status

An **item** on the board is a unit of work. Its **status glyph** says where it is:

| Glyph | Meaning | Who owns it |
|---|---|---|
| 💡 | idea (icebox) | nobody — a maybe-someday |
| 🔜 | next (queued) | nobody — free to start with `/whats-next` |
| ⚙ | in-progress | a live session in a worktree |
| 🔍 | in-review | a live session (PR open) |
| ⏸ | parked | nobody — blocked on something; note what |
| ✅ | done | shipped; leaves Open threads |

The **Owner** column names the live branch/worktree actively on an item, or `—` when it's
free. This is what keeps parallel sessions from colliding: `/whats-next` and `/continue` skip
anything a live owner holds, and `/handover` sets `Owner = —` when it relinquishes a thread
so a cold session can pick it up.

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

The same care extends to worktrees: `/handover` releases its **own** thread's worktree when
the loop closes, and prunes dead worktree entries — but it only ever *reports* a finished
sibling worktree (merged + clean) for you to remove, never force-removes another session's
tree. When in doubt, Relay reports and waits rather than deleting.

## How the commands map onto the model

- `/explore` **writes** a new item: it interrogates a rough idea, weighs alternatives, and
  adds a brief + a board row (🔜/💡) — the front of the loop that feeds everything below.
- `/cross-check` **writes** a reference frame under `relay/reference/` (how others solve the
  problem) and checks an approach against it — offered at the end of `/explore`, or on its own.
- `/whats-next` **reads** Open threads, filters to what's startable (🔜/⏸/💡, no live owner),
  ranks it, and starts your pick in a worktree.
- `/continue` **reads** Open threads, finds your thread (by slug or current branch), and
  resumes from its linked handover.
- `/handover` **writes** a handover and **updates** the item's row (status, owner → `—`,
  latest handover), both onto `main`.
- `/wrapup` runs the ship loop and ends by calling `/handover`.
- `/handover`, as it commits, also **archives** superseded handovers/reviews the board no
  longer references and **prunes** dead worktree entries — the end-of-session housekeeping,
  folded into the step that already touches those records.
- `/garbage-collect` is the off-happy-path escape hatch: it **reclaims** orphaned worktrees a
  crashed or un-handed-over session left behind. You don't need it in normal use.

That's the whole system. Everything else is detail.

Next: **[a-day-in-the-loop.md](a-day-in-the-loop.md)** — one item walked end to end.
