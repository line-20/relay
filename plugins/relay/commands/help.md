---
description: Show what Relay can do — the lifecycle map and every command, one line each. The "what can this do again?" surface.
argument-hint: "(no arguments)"
---

Print a compact overview of Relay's capabilities so the user can discover or be reminded of them.
Your reply is **just the overview below** — no preamble, no tool calls. Render every list as a **GFM
markdown table** (never stacked records — see [[conventions]]). Keep it tight.

Open with the one-line lifecycle, then the tables:

**The spiral:** `guardrails → explore → refine → next/continue → test → deploy → review/fix → ship → persist`
— each phase optional, results loop back to `explore`/`refine`.

## The loop (what you type most)

| Command | Phase | What it does |
|---|---|---|
| `/relay:explore` | shape | Turn a rough idea into a brief on the board (context-free) |
| `/relay:refine` | ground | Fit a brief to the project: code, guardrails, threat model, session-sized slices |
| `/relay:next` | build | Ranked shortlist from the board → start a pick in a worktree |
| `/relay:continue` | build | Resume an in-flight thread from its handover |
| `/relay:test` | verify | Draft PR + structured test plan; can drive it in the browser |
| `/relay:ship` | ship | test → review → fix → merge → handover → (persist, per `persist` policy) |

## Setup & knowledge (occasional)

| Command | What it does |
|---|---|
| `/relay:init` | Minimal scaffold — board + dirs; greenfield or brownfield, never destructive |
| `/relay:config` | Guided config front door — shows/sets optional config; opt-in depth, never a gate |
| `/relay:guardrails` | Establish per-dimension project standards (API/UI/security/…) |
| `/relay:adopt` | Bulk-adopt a brownfield area: pull idea docs in, register + compact convention docs, reconcile `.claude/` |
| `/relay:exit` | Cleanly remove Relay: restore adopted content to where it came from, export your briefs, un-wire config. Code untouched |
| `/relay:persist` | After a lap: harvest lessons into guardrails/design-system/memory + ADRs + release notes — durable output lands outside `<root>/` (config-driven: `none`→`full`) |
| `/relay:deploy` | Orchestrate + security-gate a PR preview via your own CI |

## Support (as needed)

| Command | What it does |
|---|---|
| `/relay:cross-check` | Check an approach against prior art / standards |
| `/relay:watch` | Park on a dependency, auto-resume when it lands |
| `/relay:review` · `/relay:fix` · `/relay:handover` | The pieces `/ship` composes — run standalone when needed |
| `/relay:tidy` | Keep the volatile layer lean — prune spent handovers/reviews, trim done rows, merge briefs (content) |
| `/relay:gc` | Reclaim orphaned worktrees (git worktrees, not content) |
| `/relay:help` · `/relay:version` | This overview · the version banner |

## Tuning (per-call or in `relay.config.local.json`)

| Word (in any command's args) | Effect |
|---|---|
| `small` · `medium` · `large` | Session size — how big a slice (`/refine`), how wide the fan-out |
| `terse` · `verbose` | How much Relay narrates |

**More** → **github.com/line-20/relay** · [quickstart](https://github.com/line-20/relay/blob/main/docs/quickstart.md) · [the board model](https://github.com/line-20/relay/blob/main/docs/the-board-model.md) · [a day in the loop](https://github.com/line-20/relay/blob/main/docs/a-day-in-the-loop.md) · [conventions](https://github.com/line-20/relay/blob/main/docs/conventions.md) · [CHANGELOG](https://github.com/line-20/relay/blob/main/CHANGELOG.md)
