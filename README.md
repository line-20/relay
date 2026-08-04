# Relay

**A continuity-first workflow for Claude Code.** A shared board, cold-start handovers,
worktree-isolated sessions, and a multi-specialist review fan-out — built for the way real
work actually happens: several sessions in parallel, picked up and put down over days, by a
model with no memory of last time.

Most agent workflows assume one focused session that starts a task and finishes it. Relay
assumes the opposite and makes it safe: **any session can be handed off cold, and any session
can pick up where another left off** — because the state that matters lives in the repo, on
`main`, not in a chat history that's about to be cleared.

---

## The idea in one picture

```
        relay/board.md  ← the front door: what's in flight, right now
              │
   ┌──────────┼───────────────────────────────┐
   │          │                                │
 /next     /continue                        /wrapup
 pick a    resume a thread                  test → review → merge
 thread    from its handover                → handover
   │          │                                │
   └──► work in an isolated git worktree ◄──────┘
              │
        /handover  ← writes a cold-start note + updates the board, on main
```

Every command reads and writes two durable files — `relay/board.md` and
`relay/handover/next-*.md` — committed straight to `main`. That's the whole trick: the baton
is in the repo, so it survives `/clear`, survives days, survives a completely fresh session.

## What's in the box

**Commands** (the workflow loop):

| Command | What it does |
|---|---|
| `/relay-init` | Scaffold the board + handover/brief dirs in a repo (run once) |
| `/next` | "What should I work on?" — a ranked shortlist from the board, then starts it in a worktree |
| `/continue` | Resume an in-flight thread from its handover |
| `/review-pr` | Fan out domain specialists over a PR, merged into one report |
| `/fix-pr-review` | Re-verify each review finding against the code, fix, tick off |
| `/wrapup` | End-of-session loop: test → PR + review → fix → merge → handover |
| `/handover` | Write a cold-start handover, update the board, commit both to main |
| `/start-new` | End-of-session reset: tidy worktrees, archive old handovers/reviews |

**Review agents** (dispatched by `/review-pr`): backend, frontend, ui-ux, api-architect,
dbms, test-engineer, security, privacy, i18n, solution-architect. All stack-agnostic — they
read your project's `CLAUDE.md` and code rather than assuming a framework.

**A meta-skill**, `authoring-skills`, for adding your own commands and agents in the same shape.

## Install

Relay is distributed as a Claude Code plugin. From inside Claude Code:

```
/plugin marketplace add line-20/relay
/plugin install relay
```

Then, once, in each repo you want to use it in:

```
/relay-init
```

That scaffolds the board and the handover/brief directories, seeded with tracks that fit
your repo. From there, `/next` picks the first thing to work on.

> New to it? Read **[docs/quickstart.md](docs/quickstart.md)** (10 minutes to your first loop),
> then **[docs/the-board-model.md](docs/the-board-model.md)** for the one mental model
> everything rests on.

## Philosophy

- **Continuity over cleverness.** The hard part of long-running agent work isn't any single
  session — it's not losing the thread between them. Relay optimises the seams.
- **State lives in the repo, not the chat.** If it matters, it's a file on `main`. Chat
  history is disposable by design.
- **Parallel-safe by default.** Every command assumes a sibling session might be working
  right now, and never clobbers its worktree or its board row.
- **Verify, don't trust.** Review findings are claims to re-check against the code, not
  orders. The board is a guess to confirm against ground truth, not gospel.
- **Stop at the right moments.** These commands are as much about where they *pause for you*
  as what they automate.

## Documentation

- **[docs/quickstart.md](docs/quickstart.md)** — install to first loop, in ten minutes.
- **[docs/the-board-model.md](docs/the-board-model.md)** — the board, threads, tracks, and
  why "newest handover wins" is a trap. The core mental model.
- **[docs/a-day-in-the-loop.md](docs/a-day-in-the-loop.md)** — one item walked end to end,
  from `/next` to merged-and-handed-over, annotated.
- **[docs/authoring-skills.md](docs/authoring-skills.md)** — add your own commands and agents.

## License

MIT. See [LICENSE](LICENSE).
