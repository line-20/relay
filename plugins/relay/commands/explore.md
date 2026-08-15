---
name: rle
description: Turn a rough idea into a well-shaped brief — interrogate it, explore real alternatives, recommend one, and write it to the board as a startable item. Never builds; it shapes the work /next then picks up.
argument-hint: "[a rough idea, e.g. 'let users export their data']"
---

## Usage
`/relay:explore [rough idea]` — also `/rle` (bare, no prefix) and `/relay:rle`

| Argument | Effect |
|---|---|
| `<rough idea>` | The thing to shape — "let users export their data" |
| *(empty)* | Asks what you want to think through |

**Any command also takes** `small`·`medium`·`large` (session size) · `terse`·`verbose` (how much Relay narrates) · `plain`·`informed`·`expert` (terminal depth) · `ask`·`challenge`·`solo` (who decides) — per-call, winning over `relay.config.local.json` ([[conventions]]).

> **`?` prints this and stops.** If `$ARGUMENTS` is exactly `?`, `help`, `--help` or `-h`, print the
> signature line, the argument table and the words/config line above — verbatim, nothing else, not
> even this note — then **STOP**: no tools, no preamble, no action. `/relay:help <command>` prints
> the same thing.

> **Output** ([[conventions]]): honour `verbosity` (a per-call `terse`/`verbose` word in `$ARGUMENTS`, else `relay.config.local.json` `.verbosity`, else `normal`) — at **terse**, emit only STOP-gate questions and the final landing, no narration or intermediate recaps. Honour `audience` (a per-call `plain`/`informed`/`expert` word in `$ARGUMENTS`, else `relay.config.local.json` `.audience`, else unset) — how much depth surfaces in your **terminal** output; it never thins a **written artifact** (brief, report, ADR, handover), which always keeps full depth. `plain` = executive summary: the decisions and what you need from the user, minimal jargon; `informed` = lead with the decisions and what changed, keep the corrections and open questions that need the user, defer exhaustive evidence/`file:line` tables to the artifact; `expert` = full depth in the terminal too; unset ⇒ today’s default (no shaping). Never drop a STOP-gate question or the decision itself. Render every list (candidates / findings / plan rows) as a **GFM markdown table**, never stacked `Field: value` records or ASCII-rule separators; keep cells terse, overflow to numbered footnotes.

Take a fuzzy idea and shape it into something worth building — or decide it isn't. This is
the **front of the loop**: it produces a brief and a board item that `/next` can later start.

It is **purely context-free** — it shapes the idea *in the abstract* and never inspects the
project's code, `CLAUDE.md`, or conventions. Grounding the idea against *this* project — the code it
must fit, the guardrails, the pre-build fit check, budget-sized slices — is **`/refine`'s** job, the
next step. It does **not** write code either. Shaping, grounding, and building are deliberately three
separate stages.

> **Relay convention.** Output lands in `<root>/briefs/<slug>.md` and a new row on
> `<root>/board.md`, so the thing you explored is immediately startable with `/next`.

> **Resolve the root first:** durable state lives under the per-repo root (default `relay/`; a
> `relay.config.json` `{ "root": "docs" }` at the repo root overrides). Resolve once —
> `ROOT="$(jq -r '.root // "relay"' relay.config.json 2>/dev/null || echo relay)"` — and read every
> `<root>/…` path below relative to it.

## Step 1 — Restate the idea, don't shape it yet
`$ARGUMENTS` is the raw idea. If it's empty, ask what the user wants to think through and
wait. Otherwise, **play it back in one or two plain sentences** — "here's what I think you're
asking for" — and confirm you've got the intent right before interrogating it. Getting this
wrong wastes the whole session, so check.

## Step 2 — Interrogate before designing (ONE question at a time, STOP for the answer)
A brief written from an unexamined idea is worthless. Ask the sharp questions — but **ask them
one at a time.** Pose a single question, **STOP and wait for the answer**, then ask the next.
A wall of five questions gets one skimmed reply; one focused question gets a real one. Skip
anything the user already answered; never assume an answer to move faster.

Work through these, roughly in order (one message each):
- **The real problem.** What job is this doing? What's painful *today* without it? (An idea is
  usually a proposed solution — find the problem underneath it.)
- **Who it's for.** Which user/role hits this, how often. A rare edge case and a daily
  workflow deserve very different amounts of machinery.
- **What "good" looks like.** How would you know it worked? The crispest version of done.
- **What's explicitly OUT.** The scope edge. Naming what this is *not* is as valuable as
  naming what it is — it's what keeps the first slice small.
- **Constraints the user can name.** Deadline, data they have or don't, a hard requirement or a
  "must not break" they already know. Take these *from the user* — don't go inspecting the codebase
  to find them; grounding against the actual code is `/refine`'s job, not this step's.

**Offer a visual just-in-time.** When a question is genuinely easier to answer against a
picture — a flow, a state machine, a rough screen layout — offer a quick diagram or ASCII
mockup *at that moment*, not upfront. Skip it when words are enough; don't decorate.

If, partway through, the idea looks like it shouldn't be built (solves a non-problem, or a far
cheaper thing would do), **say so plainly** and stop — killing a bad idea here is a win, not a
failure.

## Step 2.5 — Split it if it's really several things
Before designing, check whether this is **one** unit of work or several independent ones hiding
behind a single sentence ("let users export their data *and* add an audit log *and* a settings
page"). If it decomposes into pieces that could ship separately, **say so and split it** — one
brief and one board item per piece, each with its own slug, sequenced if they depend on each
other. A brief that secretly contains three projects can't be sized, started, or reviewed. One
brief = one shippable thing.

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

## Step 3.5 — Cross-check the concept against prior art (always offer)
Once an approach is chosen, **always offer to `/cross-check` it** before it hardens into a brief —
this is the cheapest moment to catch a reinvented wheel, a missed standard, or a blind spot
everyone else in the space has already solved. This is the **conceptual** cross-check: *is this the
right approach at all*, judged against how others frame and solve the problem — so run it at the
`conceptual` lens. **Make the offer a real, visible line at convergence** — the failure to avoid is
silently skipping it. On accept, run the `/cross-check` flow on the chosen approach (build/extend
`<root>/reference/<topic>.md`, then report Aligns / Diverges / Blind spots / Reinvention) and **fold
its findings into the approach** before Step 4. **Only auto-skip** when the change is genuinely
trivial (a two-line tweak, well-trodden ground with nothing to learn) — and even then, say in one
line that you skipped it and why. `/refine` runs the **technical** counterpart against the
implementation later; this one is about the idea.

## Step 4 — Write the brief and put it on the board
Pick a slug (`<track>/<slug>`) on an existing board track, or propose a new track if none fits.
Write `<root>/briefs/<slug>.md`:

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
git show FETCH_HEAD:<root>/board.md > /tmp/board.md   # main's current copy to edit from
```

Add one row to **Open threads** (`Status` = 🔜 or 💡, `Owner` = —, `Latest handover` = —,
`Detail` = `<root>/briefs/<slug>.md`) and a one-line entry under its track. Commit the brief +
board together onto `main` — if you're on `main` a normal `git add && git commit && git push`
is fine; if you're on a feature branch, use the temp-index push `/handover` uses so you don't
switch branches. If the push is rejected (main moved, or protected), say so — the files are
correct locally and the user can commit them.

## Step 4.5 — Self-review the brief before you rely on it
Re-read what you just wrote as if you were the cold session that has to *build* from it, and
fix it in place before reporting. Check specifically for:
- **Placeholders** — any `<...>`, "TBD", or hand-wave left unfilled.
- **Contradictions** — the Approach promising something the Out-of-scope excludes, or Slices
  that don't add up to the stated problem.
- **Ambiguity** — a step a builder could read two ways. Make it one way.
- **Scope creep** — anything in Slices that isn't needed for the real problem from Step 2.
  Cut it (YAGNI) or move it to a follow-up item.
A brief that survives its own review is one a stranger can execute. This is the difference
between a note and a spec.

## Step 5 — STOP and report
**Do not start building.** Report, in plain language:
- the one-line problem and the approach you landed on,
- the brief path and the board item (`track/slug` + status),
- any open questions still needing a decision,
- and the next move: **`/relay:refine <slug>`** to ground it in the project (code, guardrails, threat
  model, budget-sized slices) before building, or **`/relay:next`** to start it straight away if
  it's small enough not to need grooming. (Commands are `/relay:`-namespaced — a bare `/refine` isn't
  a command; tab-complete after the colon.)

If the idea was killed in Step 2/3, report that instead — what it was, and why it's not worth
building — and write nothing to the board.
