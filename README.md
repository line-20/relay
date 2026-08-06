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
┌────────────────────── the loop · every session cycles through it ────────────────────────┐
│                                                                                          │
▼                                                                                          │
relay/board.md  ──▶ /next   ──▶   ┌ worktree A ┐   ──▶  /ship    ──▶    /handover  ┘
shared · on main    or /continue        │            │        test → review →   writes back
what's in flight                        ├ worktree B ┤        merge → ship      to the board
                                        │            │ 
                                        └ worktree C ┘        

      ↑  many sessions run this loop at once — each in its own worktree,
         all sharing the one board.    /explore feeds new briefs in · handover closes it ↺
```

Read it as a **ring**, not a pipeline: a session picks a thread off the board (`/next`)
or resumes one (`/continue`), works in its own isolated worktree, and `/ship` ships it and
hands the thread back to the board — where the next session picks it up. And it's not one ring
but **many at once**: several sessions run this same loop in parallel, each in its own worktree,
the shared board the only thing between them.

Worktrees are keyed to the **topic**, not the slice: one persistent tree per topic, reused
across slices with the branch rotating inside it. `/ship` keeps it, and the next `/next`
or `/continue` on that topic re-baselines it off `main` and cuts the next branch — same topic,
same directory, same editor tab, instead of a fresh tree per slice.

Every command reads and writes two durable files — `relay/board.md` and
`relay/handover/next-*.md` — committed straight to `main`. That's the whole trick: the baton
is in the repo, so it survives `/clear`, survives days, survives a completely fresh session.

## What's in the box

**Drive the loop with these** — the four commands you actually type, plus one-time setup:

| Command | What it does |
|---|---|
| `/init` | Scaffold the **minimal** board + dirs in a repo (run **once**, at setup) — greenfield or brownfield, never destructive |
| `/explore` | Turn a rough idea into a shaped brief on the board — interrogate it, weigh alternatives, never builds (purely context-free) |
| `/refine` | Ground a shaped brief against **this** project — code, guardrails, threat model, budget-sized slices; pulls a legacy doc into Relay as it grooms it |
| `/next` | "What should I work on?" — a ranked shortlist from the board, then starts it in a worktree |
| `/continue` | Resume an in-flight thread from its handover |
| `/ship` | End-of-session loop: test → PR + review → fix → merge → handover → (offers `/persist`) |

**Run by the loop** — `/ship` composes these for you. You *can* call them standalone, but in
the normal flow you don't:

| Command | Composed by | Standalone only when… |
|---|---|---|
| `/review` | `/ship` Phase 3 | you want a review without shipping |
| `/fix` | `/ship` Phase 4 | you're working an existing review report |
| `/handover` | `/ship` Phase 6 | you're handing off **mid-thread**, without shipping |

> `/ship` also does the end-of-session housekeeping (archiving superseded handovers and old
> reviews, pruning dead worktree entries) as part of its handover step — there's no separate
> cleanup command to remember. It **keeps** the topic's worktree for the next slice (removed only
> when the topic itself is done).

**The SSDLC spiral** — Relay is a **Secure-SDLC workbench**, not just a ship loop. These extend the
loop into a spiral where quality and security *compound* each lap. All optional, invoked when the work
needs them:

| Command | What it does |
|---|---|
| `/guardrails` | Establish **what "good" means** for the project — layered, per-dimension (API/UI/security/privacy/testing…), that `/refine` and the review agents check against |
| `/deploy` | Orchestrate + **security-gate** the PR preview your own CI produces, then hand a verified URL to `/test`. Never owns deployment |
| `/persist` | After a lap, **harvest what it taught** — into guardrails, the design system, AI memory — and draft human-readable **release notes**. The step that makes the spiral compound |
| `/adopt` | **Bulk-adopt a brownfield area**: move its idea docs into Relay (tidying them) and register + compact its convention docs in place. The fast-forward for what `/refine`/`/guardrails` do gradually |

**Also handy:**

| Command | What it does |
|---|---|
| `/test` | After a chunk of work, open (or reuse) a PR and write a **consistent, structured test plan** into it — preconditions, happy path, and the edge/error/tenant-isolation + threat-model cases an LLM skips by default. Can then **drive the happy path in the browser** against the preview and report pass/fail with a GIF. Stops at a **draft** PR (never merges); `plan-only` prints the checklist without a PR. |
| `/cross-check` | Build a **reference frame** — how other products, standards, and prior art handle a problem — and check your approach against it for blind spots and reinvention. Standalone, or offered at the end of `/explore`. |
| `/watch` | Park this thread on a **dependency** (a PR, a sibling board item, or a branch), watch it land in the background, and **auto-resume** once it's on `main`. `/next` and `/continue` offer it automatically when they spot a cross-worktree dependency. |
| `/gc` | Reclaim **orphaned** worktrees left by sessions that skipped the happy path (crashed, or `/clear`ed without a handover). You never need it in normal use — `/ship` cleans up after itself; reach for it only when orphans pile up. |
| `/version` | Print the Relay banner + version (confirms which plugin version is loaded). |

**Review agents** (dispatched by `/review`): backend, frontend, ui-ux, api-architect,
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
/init
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
- **Parallel-safe, and parallel-*aware*, by default.** Every command assumes a sibling session
  might be working right now, so it never clobbers another worktree or board row — *and* it can
  see what the others are doing. Before you start, Relay checks whether your work depends on a
  sibling thread's unlanded change and offers to watch that land and auto-resume. No other agent
  workflow can do this, because none of them keep a cross-session registry. Relay's board is one.
- **Verify, don't trust.** Review findings are claims to re-check against the code, not
  orders. The board is a guess to confirm against ground truth, not gospel.
- **Design before code.** `/explore` interrogates a rough idea, separates the UX and data-model
  questions, cross-checks it against how the rest of the world solves it, and self-reviews the
  brief — *then* stops. The cheapest place to fix a wrong assumption is before any code exists.
- **Stop at the right moments.** These commands are as much about where they *pause for you*
  as what they automate.

## Token economics

Long-running agent work usually dies by context bloat — a session drags an ever-growing chat
history until it's spending most of its budget re-reading itself. Relay is built to avoid that,
and the savings *are* the design, not an add-on:

- **Cold handovers cap the context.** A session starts from a compact, self-contained handover
  and `/clear`s between threads — so tokens go to the task, not to re-reading a transcript that
  grows without bound. The handover front-loads the research the last session did, so the next
  one doesn't pay to re-derive it.
- **The board is a tiny curated index**, read with a cheap `git show` — a few hundred tokens to
  know the whole project's state, versus re-exploring the repo every session.
- **Review fans out, scoped and gated.** `/review` runs specialists in *parallel* subagents,
  each scoped to the area it reviews, and only launches the ones the diff actually touches — you
  don't pay for a privacy or i18n pass on a CSS-only change.
- **Dependency-awareness avoids throwaway work** — catching that you'd be building on unlanded
  code *before* you build it saves the tokens (and the rework) of doing it twice.

- **Session size right-sizes the work.** A driver preference — `session` = `small`/`medium`/`large` in
  a gitignored `relay.config.local.json`, or a per-call word — sizes slices in `/refine` (so a build
  finishes within the healthy part of a context window) and, as a knock-on, how far `/review` and
  `/next` fan out. Offered lazily; absent, Relay runs at full, so nothing is front-loaded.

**Where it can improve — honestly:** the review fan-out is deliberately thorough, so on a tiny
diff it can spend more than the change warranted (gating + session sizing help, but a lightweight
"quick-review" mode for small diffs is still a real future win); and `/cross-check` with live web
search can be token-heavy. These are the next places to sharpen, not solved problems.

## Documentation

- **[docs/quickstart.md](docs/quickstart.md)** — install to first loop, in ten minutes.
- **[docs/the-board-model.md](docs/the-board-model.md)** — the board, threads, tracks, and
  why "newest handover wins" is a trap. The core mental model.
- **[docs/a-day-in-the-loop.md](docs/a-day-in-the-loop.md)** — one item walked end to end,
  from `/next` to merged-and-handed-over, annotated.
- **[docs/authoring-skills.md](docs/authoring-skills.md)** — add your own commands and agents.
- **[docs/ssdlc-roadmap.md](docs/ssdlc-roadmap.md)** — where Relay is heading: the Secure-SDLC
  spiral, the layered guardrails model, and the increment arc to 1.0.

## License

MIT. See [LICENSE](LICENSE).
