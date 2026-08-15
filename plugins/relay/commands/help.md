---
description: Show what Relay can do — the lifecycle map and every command, one line each, or one command's usage. The "what can this do again?" surface.
argument-hint: "[a command name for its usage, e.g. 'test'; omit for the whole map]"
---

Print a compact overview of Relay's capabilities so the user can discover or be reminded of them.
Your reply is **just the overview below** — no preamble, and (empty `$ARGUMENTS`) no tool calls.
Render every list as a **GFM markdown table** (never stacked records — see [[conventions]]). Keep it
tight.

## One command's usage — `$ARGUMENTS` names a command

If `$ARGUMENTS` names a Relay command (with or without the `/relay:` prefix, and accepting the short
aliases below — `rlt` → `test`), **don't print the map**. Locate that command's file — glob
`**/relay/commands/<name>.md` (installed plugins live under `~/.claude/plugins/`; in the Relay repo
itself it's `plugins/relay/commands/<name>.md`) — print its `## Usage` block **verbatim** and stop.
Never reconstruct a usage block from memory: if you can't read the file, say so in one line and tell
the user to type `/relay:<name> ?` instead. An unknown name ⇒ say so in one line, then print the map.

## The whole map — `$ARGUMENTS` is empty

Open with the one-line lifecycle, then the tables:

**The spiral:** `guardrails → explore → refine → next/continue → test → review/fix → ship → persist`
— results loop back to `explore`/`refine`. **Build → verify → ship** is the main line: `/test` sits
between them so the review fan-out is spent on something that's actually been exercised.

## The loop (what you type most)

| Command | Short | Phase | What it does |
|---|---|---|---|
| `/relay:explore` | `/rle` | shape | Turn a rough idea into a brief on the board (context-free) |
| `/relay:refine` | `/rlrf` | ground | Fit a brief to the project: code, guardrails, threat model, session-sized slices |
| `/relay:next` | `/rln` | build | Ranked shortlist from the board → start a pick in a worktree |
| `/relay:continue` | `/rlc` | build | Resume an in-flight thread from its handover |
| `/relay:test` | `/rlt` | verify | Draft PR + structured test plan; can drive it against a preview or a local env |
| `/relay:ship` | `/rls` | ship | test → verify gate → review → fix → merge → handover → (persist, per `persist` policy) |

## Setup & knowledge (occasional)

| Command | What it does |
|---|---|
| `/relay:init` | Minimal scaffold — board + dirs; greenfield or brownfield, never destructive |
| `/relay:config` | Guided config front door — shows/sets optional config; opt-in depth, never a gate |
| `/relay:guardrails` | Establish per-dimension project standards (API/UI/security/…) |
| `/relay:adopt` | Bulk-adopt a brownfield area: pull idea docs in, register + compact convention docs, reconcile `.claude/` |
| `/relay:exit` | Cleanly remove Relay: restore adopted content to where it came from, export your briefs, un-wire config. Code untouched |
| `/relay:persist` (`/rlp`) | After a lap: harvest lessons into guardrails/design-system/memory + ADRs + release notes — durable output lands outside `<root>/` (config-driven: `none`→`full`) |

## Support (as needed)

| Command | What it does |
|---|---|
| `/relay:review` (`/rlrv`) · `/relay:fix` (`/rlf`) · `/relay:handover` (`/rlh`) | The pieces `/ship` composes — run standalone when needed |
| `/relay:deploy` | Get a trustworthy PR preview to test against — via the project's own CI. Only if your project builds PR previews; `/test preview` leans on it |
| `/relay:cross-check` | Check an approach against prior art / standards |
| `/relay:watch` | Park on a dependency, auto-resume when it lands |
| `/relay:tidy` | Keep the volatile layer lean — merge briefs, archive spent ones, deliberate sweeps. Prune + trim already ride every `/handover` |
| `/relay:gc` | Reclaim orphaned worktrees (git worktrees, not content) |
| `/relay:help` · `/relay:version` | This overview · the version banner |

## Typing less

| | |
|---|---|
| `/rlt`, `/rln`, `/rls`, … | Bare shortcuts — no prefix, work anywhere. Also `/relay:rlt`, `/relay:rln`, … |
| `/relay:test ?` | Any command's own usage — every argument it takes. `--help` and `-h` work too |
| `/relay:help test` | The same usage, from here |

## Tuning (per-call or in `relay.config.local.json`)

| Word (in any command's args) | Effect |
|---|---|
| `small` · `medium` · `large` | Session size — how big a slice (`/refine`), how wide the fan-out |
| `terse` · `verbose` | How much Relay narrates |
| `plain` · `informed` · `expert` | How much depth surfaces in the terminal (never thins a written artifact) |
| `ask` · `challenge` · `solo` | Who decides at a decision that outlives the lap |
| `preview` · `local` | (`/test`) which environment to verify against — else `test.target`, else auto |

**More** → **github.com/line-20/relay** · [quickstart](https://github.com/line-20/relay/blob/main/docs/quickstart.md) · [the board model](https://github.com/line-20/relay/blob/main/docs/the-board-model.md) · [a day in the loop](https://github.com/line-20/relay/blob/main/docs/a-day-in-the-loop.md) · [conventions](https://github.com/line-20/relay/blob/main/docs/conventions.md) · [CHANGELOG](https://github.com/line-20/relay/blob/main/CHANGELOG.md)
