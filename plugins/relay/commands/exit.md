---
description: Cleanly remove Relay from a repo — restore adopted content to where it came from, export your Relay-created briefs, discard Relay's own bookkeeping, remove config. Your code stays untouched. The graceful exit.
argument-hint: "[--dry-run to preview only; omit to preview then confirm]"
---

> **Output** ([[conventions]]): honour `verbosity` (a per-call `terse`/`verbose` word in `$ARGUMENTS`, else `relay.config.local.json` `.verbosity`, else `normal`) — at **terse**, emit only STOP-gate questions and the final landing, no narration or intermediate recaps. Honour `audience` (a per-call `plain`/`informed`/`expert` word in `$ARGUMENTS`, else `relay.config.local.json` `.audience`, else unset) — the technical register of your prose: `plain` = non-technical, no jargon; `informed` = architecture, trade-offs and named patterns, no code/syntax/flags unless they are the point or asked; `expert` = full implementation depth; unset ⇒ today’s default (no register shaping). Render every list (candidates / findings / plan rows) as a **GFM markdown table**, never stacked `Field: value` records or ASCII-rule separators; keep cells terse, overflow to numbered footnotes.

Remove Relay from this repo **without trapping anything you brought or made.** This is the counterpart
to `/adopt`: adoption pulled content *in*; `/exit` puts it *back* and takes Relay out of the way. The
whole promise is that leaving is clean and **reversible** — your code is never touched, your content is
restored or exported, and only Relay's own bookkeeping is discarded (git keeps it anyway).

**The round-trip that makes this work:** every adopted brief carries a `_Adopted from `<path>`_`
provenance line (written by `/adopt` / `/refine`), so `/exit` knows exactly where to put each one back.

## Step 0 — Resolve the root and inventory Relay's footprint
```bash
ROOT="$(jq -r '.root // "relay"' relay.config.json 2>/dev/null || echo relay)"
```
List what Relay put here: `<root>/` (board, roadmap, briefs, handover, reviews, audits, reference,
archive, and — in legacy repos — `knowledge`), `relay.config.json`, `relay.config.local.json`, the
`.gitignore` line, and any Relay-created git worktrees (`git worktree list`). If there's no
`<root>/board.md`, there's nothing to exit — say so and stop.

**Note where durable output lives.** Durable knowledge — ADRs, procedures, how-tos, guardrails
house-rules, the design system, release notes — lives **outside `<root>/`** by default (in your docs
tree, via `paths.*`); those are **your deliverables and stay put**. Only a legacy repo still holds them
under `<root>/knowledge/` — read `paths.*` to tell which surfaces are external (preserve) vs internal
(discard with the rest of the bookkeeping, they're in git history).

## Step 1 — Classify every brief (this is what protects your content)
For each `<root>/briefs/*.md`, decide where it goes on the way out:
- **Adopted** — has an `_Adopted from `<original path>`_` line ⇒ **restore** it to that original path.
  (It carries the *actualised* content `/adopt`/`/refine` tidied — the improved version goes back, not
  the old fossil; git still has the pre-adoption original if you ever want it.)
- **Relay-created** — no provenance line (shaped by `/explore`) ⇒ still **your plan**, so **export** it,
  don't discard it. Default target `ideas/` (ask for a different folder if the user prefers).

## Step 2 — Present the exit plan and confirm — **STOP**
Show exactly what will happen and **wait for approval before touching anything** (this removes Relay):

> | Item | Action |
> |---|---|
> | `relay/briefs/tms.md` (adopted) | → restore to `ideas/tms-project.md` |
> | `relay/briefs/catalogue.md` (created) | → export to `ideas/catalogue.md` |
> | `relay/board.md`, roadmap, handover, reviews, audits, reference | discard (Relay bookkeeping; in git history) |
> | `relay.config.json`, `relay.config.local.json`, `.gitignore` line | remove (un-wire Relay) |
> | ADRs / procedures / how-tos / guardrails / release notes (outside `<root>/`) | **left in place** — your deliverables, never moved |
> | design guide / conventions docs | **left in place** — yours, never moved |
> | legacy `<root>/knowledge/` (if any) | discard (in git history) — offer to externalise first |
> | your code | **untouched** |
> | Relay worktrees (clean) | remove |

**With `--dry-run`, stop here** — print the plan and change nothing. Otherwise STOP for the go-ahead.

## Step 3 — On approval, exit (safely, content first)
**Safety net** (see [[conventions]]): the whole exit lands as one commit you can `git revert`; in a git
repo that *is* the backup. Refuse to proceed on **uncommitted/in-flight** work — a dirty worktree, a
live Relay worktree with unmerged commits → STOP and surface it, never discard it.

1. **Restore adopted briefs** to their `_Adopted from_` path — history-preserving where there's git:
   ```bash
   restore() { mkdir -p "$(dirname "$2")"
     if git rev-parse --is-inside-work-tree >/dev/null 2>&1 && git ls-files --error-unmatch "$1" >/dev/null 2>&1
     then git mv "$1" "$2"; else mv "$1" "$2"; fi; }
   ```
   Strip the provenance line from the restored file, and **reverse any path references** `/adopt`
   rewrote (best-effort — point them back at the restored path).
2. **Export Relay-created briefs** to the chosen folder (default `ideas/`), same move mechanics.
3. **Discard Relay's bookkeeping** — remove the rest of `<root>/` (board, roadmap, handover, reviews,
   audits, reference, archive). It's all in git history; nothing durable is lost. **Durable output
   already lives outside `<root>/`** (ADRs, procedures, how-tos, guardrails, design system, release
   notes via `paths.*`) — leave it exactly where it is. A **legacy** `<root>/knowledge/` is the one
   exception: it's inside the discard bucket, but **offer to externalise it first** (move it to your
   docs tree, as `/init`'s migration does) so the knowledge survives outside git history too; only
   discard it if the user declines.
4. **Un-wire config** — delete `relay.config.json` and `relay.config.local.json`, and drop the
   `relay.config.local.json` line from `.gitignore`. Removing config leaves the **deliverable docs it
   pointed at exactly where they are** — only the Relay wiring goes.
5. **Remove clean Relay worktrees** (never one with uncommitted or unmerged work — that's the Step 3
   refusal above). Prune dead worktree entries.
6. **Commit the exit** as one revertible commit (`chore: exit Relay — restore content, remove workflow`),
   staging only what exit touched (never `git add -A`). Skip the commit if not a git repo, and say so.

## Step 4 — Report
State, outcome-first: **how many briefs were restored** (to where) **and exported** (to where), what
Relay bookkeeping was discarded, that config + the `.gitignore` line are gone, and that **your code and
deliverable docs are untouched**. End with the reassurance that matters: the exit is **one
`git revert` away** if you change your mind, and re-adopting later is just `/init` + `/adopt`.
