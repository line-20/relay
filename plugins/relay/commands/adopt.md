---
description: Bring a brownfield repo's existing material under Relay management, scoped by area — move + actualise work-inputs into briefs, register + compact deliverable knowledge in place — the bulk escape hatch for progressive adoption.
argument-hint: "[area/track, a path glob, or --all; omit to preview the whole repo]"
---

## Usage
`/relay:adopt [area | path-glob | --all]`

| Argument | Effect |
|---|---|
| `<area>` / `<track>` | Scope to one area's code + docs — `ui`, `backend` |
| `<path glob>` | Scope to matching files — `ideas/finance*` |
| `--all` | The whole repo |
| *(empty)* | Preview the whole repo; adopts nothing without your go-ahead |

**Any command also takes** `small`·`medium`·`large` (session size) · `terse`·`verbose` (how much Relay narrates) · `plain`·`informed`·`expert` (terminal depth) · `ask`·`challenge`·`solo` (who decides) — per-call, winning over `relay.config.local.json` ([[conventions]]).

> **`?` prints this and stops.** If `$ARGUMENTS` is exactly `?`, `help`, `--help` or `-h`, print the
> signature line, the argument table and the words/config line above — verbatim, nothing else, not
> even this note — then **STOP**: no tools, no preamble, no action. `/relay:help <command>` prints
> the same thing.

> **Output** ([[conventions]]): honour `verbosity` (a per-call `terse`/`verbose` word in `$ARGUMENTS`, else `relay.config.local.json` `.verbosity`, else `normal`) — at **terse**, emit only STOP-gate questions and the final landing, no narration or intermediate recaps. Honour `audience` (a per-call `plain`/`informed`/`expert` word in `$ARGUMENTS`, else `relay.config.local.json` `.audience`, else unset) — how much depth surfaces in your **terminal** output; it never thins a **written artifact** (brief, report, ADR, handover), which always keeps full depth. `plain` = executive summary: the decisions and what you need from the user, minimal jargon; `informed` = lead with the decisions and what changed, keep the corrections and open questions that need the user, defer exhaustive evidence/`file:line` tables to the artifact; `expert` = full depth in the terminal too; unset ⇒ today’s default (no shaping). Never drop a STOP-gate question or the decision itself. Render every list (candidates / findings / plan rows) as a **GFM markdown table**, never stacked `Field: value` records or ASCII-rule separators; keep cells terse, overflow to numbered footnotes.

Fast-forward a repo's adoption into Relay. Relay adopts **progressively by default** — `/init`
*references* existing docs, `/refine` *pulls a work-input in* the moment it's touched, `/guardrails`
*registers* context when a dimension first matters. `/adopt` is the **bulk button** for when you'd
rather sweep a whole area at once instead of waiting for it to happen lap by lap — and, crucially, it
**cleans up as it goes**, so adoption is also the moment stale material gets trimmed.

It handles the **two kinds of existing material differently**, because they have different lifetimes
(see [[the-board-model]] / the guardrails model):

| | Work-inputs (ideas, plans, todos, rfc, specs) | Deliverable knowledge (design guide, conventions, architecture) |
|---|---|---|
| Lifetime | transient — spent once shipped | durable — true after shipping |
| Action | **move** into `<root>/briefs/`, empty the source | **register** as a guardrails `extends` overlay, **in place** (never moved) |
| Cleanup | **actualise** — cut shipped, fix drift, tighten | **compact** — dedupe, de-stale, restructure, shrink (via the domain steward) |

**Scoped by design.** Compaction of a durable deliverable is the highest-stakes thing here, so aim it:
`$ARGUMENTS` is an **area/track** (`ui`, `backend`), a **path glob** (`ideas/finance*`), or `--all`.
Omit it to **preview** the whole repo without changing anything. Everything below is **offered, never
automatic** — `/adopt` STOPs for approval before it moves or rewrites a single file.

## Step 0 — Resolve config and the scope
```bash
ROOT="$(jq -r '.root // "relay"' relay.config.json 2>/dev/null || echo relay)"
GUARDRAILS="$(jq -r '.guardrails // empty | keys | join(",")' relay.config.json 2>/dev/null)"
```
Interpret `$ARGUMENTS` into a concrete **scope set** of files/dirs: a track/area maps to its code +
doc areas and its guardrail dimension; a path glob is literal; `--all` is the whole repo; empty ⇒
preview-only over the whole repo. State the scope you resolved before scanning.

## Step 1 — Discover and triage the material in scope
Find existing material in scope and sort each item into one of three buckets — the signal is **intent**:
- **Work-input** — "describes something to build" (an `ideas/`, `briefs/`, `rfcs/`, `todo/`, `notes/`,
  `docs/*-project.md`/`*-baseline.md`, `HANDOFF.md`). → move + actualise.
- **Deliverable knowledge** — "describes how the system is / how we work" (design guide, DB
  conventions, architecture, tone-of-voice, runbook, API guidelines). → register in place + compact.
- **Code / content / assets** — not a work doc. → leave untouched.

Skip anything already adopted (a work-input already under `<root>/briefs/`; a doc already wired into a
guardrail `extends`). Account for **everything** in scope — a silent omission defeats the point.

## Step 2 — Present the adoption plan and confirm — **STOP**
Show a triage table for the scope and **wait for approval before touching anything**:

> | Item | Kind | Action | Cleanup |
> |---|---|---|---|
> | `ideas/finance-project.md` | work-input | → `<root>/briefs/finance.md` (💡) | actualise vs current code |
> | `docs/design-guide.md` | deliverable (`ui`) | register as `ui` `extends` (in place) | steward compaction (5k→lean) |
> | `apps/**` | code | leave | — |

Note residue left outside the scope, and flag anything ambiguous. **STOP for the go-ahead.**

## Step 3 — Work-inputs: move + actualise
**Safety net first** (see [[conventions]]): in a git repo, ensure the source is committed (git is the
backup — a move is one `git revert` away); if the tree is dirty for it, STOP and ask to commit. **No
git ⇒ copy the original to `<root>/archive/pre-adopt/<name>.<ts>` before moving.** For each in-scope
work-input, on approval:
- **Move** into `<root>/briefs/` — history-preserving where there's git, plain move otherwise (not
  every project is a git repo):
  ```bash
  adopt_mv() { mkdir -p "$(dirname "$2")"
    if git rev-parse --is-inside-work-tree >/dev/null 2>&1 && git ls-files --error-unmatch "$1" >/dev/null 2>&1
    then git mv "$1" "$2"; else mkdir -p "<root>/archive/pre-adopt" && cp "$1" "<root>/archive/pre-adopt/$(basename "$1").$(date +%s)" && mv "$1" "$2"; fi; }
  ```
- **Stamp provenance** — add a line near the top of the moved brief:
  `_Adopted from `<original path>` (moved) · <date>_` — so its origin is readable from the file, no
  `git` archaeology (a freshly-created brief has no such line — that's how you tell them apart).
- **State the move explicitly** in the report: "moved `<src>` → `<root>/briefs/<name>.md`; original gone."
- **Actualise as you import** — don't move a fossil. Reconcile the doc against current reality: cut
  what's already shipped, correct assumptions that drifted, tighten the rest. (This is the same pass
  `/refine` does on pull-on-touch; `/adopt` just does it in bulk.)
- **Rewrite references** to the moved file (`CLAUDE.md`, cross-links); name-based `[[wikilinks]]`
  survive, only explicit paths need fixing.
- **Update the board row** `Detail` to the new `<root>/briefs/<name>.md` — its status stays what it
  was (💡/🔜). The source spot is now empty; that item is fully Relay-owned.

## Step 4 — Deliverable knowledge: register in place + compact (via the steward)
For each in-scope deliverable doc, on approval — **never move it; it lives with the code:**
1. **Register** it as the `extends` overlay for its dimension in `relay.config.json` (surgical merge,
   preserve other keys — the pattern `/guardrails` uses). This is what makes the reviewers and
   `/refine` read it.
2. **Dispatch the domain steward to compact/actualise it** — the same specialist `/review` uses:
   `ui-ux-designer` for a design guide, `api-architect` for API guidelines, etc. The steward
   **dedupes, de-stales, restructures, and shrinks** the doc in place. **Guardrails on this:**
   - **Safety net first** (see [[conventions]]): rewriting a durable doc is high-stakes — ensure it's
     committed (git is the backup), or back it up to `<root>/archive/pre-adopt/` if there's no git.
   - **Preserve every real rule** — dedupe and restructure, never amputate. A rule you'd drop as
     obsolete is called out for confirmation, not silently deleted.
   - The steward **reports what it cut and why** (a summary or a diff, and the before/after size) and
     the change **STOPs for approval** before it's written — it's a real project deliverable.
   - This is a **one-time catch-up**; `/persist` keeps the doc from re-bloating lap to lap afterward.

## Step 4.5 — Reconcile the existing `.claude/` setup (commands + skills)
A brownfield repo often already has its own `.claude/commands/` and `.claude/skills/`. Relay is a
**good citizen** — it discovers them and proposes a disposition per item (show the table, **STOP**):
- **Not covered by Relay → keep.** No Relay equivalent; leave it untouched, no opinion.
- **Covered / redundant → offer removal.** Relay already does this (e.g. a project `release` vs
  `/ship`). Propose deletion, remove **only on confirm**, never silently. Classify **conservatively** —
  if it does something Relay doesn't, it's *not* redundant; keep it.
- **Complementary → keep + hook.** Wire it into the matching Relay phase via the **`hooks` map** in
  `relay.config.json` (surgical merge): `{ "hooks": { "test": "test-stack", "commit": "commit" } }`.
  Then `/test`/`/ship` bring the fixture stack up via the `test` hook, `/ship`/`/handover` commit via
  `commit`, etc. (see [[conventions]] → Hooks). `test-stack` is the poster child: the test phase
  *should* call your fixture skill, not reinvent it.
- **A project review agent → register into `/review`.** A `.claude/agents/*.md` that reviews code
  (a findings-only reviewer) is registered in `relay.config.json` under `review.agents`
  (`{ name, gate, tier, scope, priority }`) so `/review` fans it in alongside the built-in
  specialists — same gate/cap/merge (see [[conventions]] → Custom review agents). Confirm it honours
  the findings-only contract first; if it writes its own report or emits a verdict, keep it standalone
  rather than registering it.
   If a dimension has no steward agent, register it but skip compaction (note it).

## Step 5 — Commit and report
Commit what changed (main-owned; skip the commit if not a git repo, and say so). Then report,
outcome-first:
- **Work-inputs**: how many moved + actualised into `<root>/briefs/`, from where.
- **Deliverable knowledge**: which docs registered as `extends` and which the steward compacted
  (with the before/after size or a one-line "what got cut").
- **Residue**: what in scope you left, and what's still referenced *outside* the scope (the board's
  `Detail` column shows the remaining "outside `relay/`" rows — the repo's not-yet-adopted tail).
- The next move: run `/adopt <another area>` to continue, or let the rest adopt lap-by-lap via
  `/refine` and `/guardrails`.
