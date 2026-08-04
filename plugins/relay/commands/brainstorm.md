---
description: Turn a rough idea into a well-shaped brief — interrogate it, explore real alternatives, recommend one, and write it to the board as a startable item. Never builds; it shapes the work /whats-next then picks up.
argument-hint: "[a rough idea, e.g. 'let users export their data']"
---

Take a fuzzy idea and shape it into something worth building — or decide it isn't. This is
the **front of the loop**: it produces a brief and a board item that `/whats-next` can later start.
It does **not** write code. Shaping the work and doing the work are deliberately separate.

> **Relay convention.** Output lands in `relay/briefs/<slug>.md` and a new row on
> `relay/board.md`, so the thing you brainstormed is immediately startable with `/whats-next`.

## Step 1 — Restate the idea, don't shape it yet
`$ARGUMENTS` is the raw idea. If it's empty, ask what the user wants to think through and
wait. Otherwise, **play it back in one or two plain sentences** — "here's what I think you're
asking for" — and confirm you've got the intent right before interrogating it. Getting this
wrong wastes the whole session, so check.

## Step 2 — Interrogate before designing (one theme at a time, STOP for answers)
A brief written from an unexamined idea is worthless. Ask the sharp questions — but **don't
dump them all at once**. Raise one or two themes, **STOP and wait**, then move on. Skip a
theme the user already answered; never assume an answer to move faster.

Cover, in roughly this order:
- **The real problem.** What job is this doing? What's painful *today* without it? (An idea is
  usually a proposed solution — find the problem underneath it.)
- **Who it's for.** Which user/role hits this, how often. A rare edge case and a daily
  workflow deserve very different amounts of machinery.
- **What "good" looks like.** How would you know it worked? The crispest version of done.
- **What's explicitly OUT.** The scope edge. Naming what this is *not* is as valuable as
  naming what it is — it's what keeps the first slice small.
- **Constraints.** Deadline, data you already have or don't, anything in the codebase this
  must fit, anything it must not break.

If, partway through, the idea looks like it shouldn't be built (solves a non-problem, or a far
cheaper thing would do), **say so plainly** and stop — killing a bad idea here is a win, not a
failure.

## Step 3 — Explore real alternatives, then recommend one
Don't design the first thing that comes to mind. Put up **two or three genuinely different
approaches** and their trade-offs, in plain language the user can weigh without reading code.

Keep two lenses **separate** so one never silently drives the other:
- **Product / UX** — what the user experiences, the flow, the surface.
- **Architecture / data model** — how it's stored and structured underneath.
A slick UX preference must not quietly force a schema decision (or vice versa); when a UX call
*does* have an architecture consequence, name it as its own trade-off rather than smuggling it in.

Then **recommend one, with the reason** — the smallest approach that credibly solves the real
problem from Step 2. Present it, and **STOP for a direction.** The user may pick a different
option, merge two, or redirect.

## Step 3.5 — Cross-check against prior art (offer)
Once an approach is chosen, **offer to `/cross-check` it** before it hardens into a brief —
this is the cheapest moment to catch a reinvented wheel, a missed standard, or a blind spot
everyone else in the space has already solved. If the user accepts, run the `/cross-check` flow
on the chosen approach (build/extend `relay/reference/<topic>.md`, then report Aligns /
Diverges / Blind spots / Reinvention) and **fold its findings into the approach** before Step 5.
If the user declines, or the idea is small/obvious enough that prior art won't teach you
anything, skip it — don't force a landscape study onto a two-line change.

## Step 4 — Fit check (only if the project defines one)
If the project's `CLAUDE.md` has a pre-build checklist for a new feature/module (packaging,
separability, tiering, portability — whatever it requires), run it against the chosen approach
now and fold the answers into the brief. If it defines none, skip this step.

## Step 5 — Write the brief and put it on the board
Pick a slug (`<track>/<slug>`) on an existing board track, or propose a new track if none fits.
Write `relay/briefs/<slug>.md`:

```markdown
# <slug>

**Status:** 🔜 queued   (or 💡 if it's an idea to revisit, not to start yet)

## Problem & why
<the real problem from Step 2, and who it's for — not the solution>

## Approach
<the chosen design, in plain language> — and, in a line each, **the alternatives it beat and
why**, so a future reader (or a cold session) doesn't re-litigate the decision.

## Slices
1. <the first shippable slice — small, end-to-end, demoable>
2. <next>
3. <next>

## Out of scope
<the scope edges named in Step 2 — what this deliberately does NOT do>

## Open questions
<anything still unresolved. "None." if there are none.>
```

Then add the item to the board, keeping it **main-owned** (the board is shared — start from
main's copy, make one surgical edit, never overwrite the whole file):

```bash
git fetch origin main
git show FETCH_HEAD:relay/board.md > /tmp/board.md   # main's current copy to edit from
```

Add one row to **Open threads** (`Status` = 🔜 or 💡, `Owner` = —, `Latest handover` = —,
`Detail` = `relay/briefs/<slug>.md`) and a one-line entry under its track. Commit the brief +
board together onto `main` — if you're on `main` a normal `git add && git commit && git push`
is fine; if you're on a feature branch, use the temp-index push `/handover` uses so you don't
switch branches. If the push is rejected (main moved, or protected), say so — the files are
correct locally and the user can commit them.

## Step 6 — STOP and report
**Do not start building.** Report, in plain language:
- the one-line problem and the approach you landed on,
- the brief path and the board item (`track/slug` + status),
- any open questions still needing a decision,
- and that **`/whats-next` picks it up** when the user's ready to build.

If the idea was killed in Step 2/3, report that instead — what it was, and why it's not worth
building — and write nothing to the board.
