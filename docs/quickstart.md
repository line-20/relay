# Quickstart — from install to your first loop

Ten minutes. By the end you'll have shaped a piece of work, started it, reviewed it, merged it,
and handed it off to a fresh session — the full Relay loop, once.

## 0. Prerequisites

- Claude Code, in a repo that's a **git repository** with a remote (`origin`) you can push to.
- The `gh` CLI authenticated (`gh auth status`) — the review and merge steps use it.
- A `main` (or `master`) branch you're allowed to push to. If `main` is protected against
  direct pushes, Relay still works — `/handover` will tell you when it can't push and hand
  you the two files to commit yourself.

## 1. Install the plugin

```
/plugin marketplace add line-20/relay
/plugin install relay
```

Restart Claude Code if prompted. You should now see `/relay-init`, `/explore`, `/whats-next`,
`/continue`, `/wrapup`, and the rest in your command list.

> **Command names collide?** If your setup already has a `/continue` or `/whats-next`, Claude Code
> namespaces plugin commands — invoke them as `/relay:continue`, `/relay:whats-next`, etc.

## 2. Scaffold the convention

```
/relay-init
```

This inspects your repo and creates:

```
relay/
  board.md          ← the front door (seeded with tracks that fit your repo)
  roadmap.md        ← the narrative behind each board item
  briefs/           ← one brief per unit of pending work
  handover/         ← cold-start handovers live here
  reference/        ← reference frames from /cross-check (how others solve a problem)
  pr-reviews/       ← merged review reports
  README.md         ← a short note explaining the convention to teammates
```

Everything the workflow owns lives under one `relay/` folder — it stays out of your repo's
own `docs/`, and a teammate can see the whole convention at a glance.

It commits these but does **not** push — review the seeded tracks, edit them to match how
you actually think about the work, then push when you're happy. The tracks are a starting
guess, not a verdict.

## 3. Shape your first piece of work with `/explore`

Give a rough idea and let Relay turn it into a proper board item:

```
/explore let users export their account data
```

`/explore` interrogates the idea one question at a time — the real problem, who it's for,
what's explicitly out of scope, the constraints — then puts up a couple of approaches, cross-
checks the one you pick against prior art, and writes it up as a **brief** in `relay/briefs/`
with a matching **row on the board**. It *never* writes code: shaping the work and doing it are
deliberately separate. When it's done you have a startable item, not a half-built feature.

> **Prefer to write it yourself?** You can always open `relay/board.md`, add a row to **Open
> threads**, and drop a one-paragraph brief in `relay/briefs/` by hand. `/explore` is the
> assisted path, not the only one.

## 4. Start it

```
/whats-next
```

Relay reads the board, ranks what's startable, and shows you a short table with a ⭐
recommendation. Pick one. It creates an **isolated git worktree** for that item and starts
the first slice — you're now working on a branch, in its own directory, without touching
`main` or any other session's work.

## 5. Wrap it up

When the slice is done and committed:

```
/wrapup
```

This runs the whole end-of-session loop in order, stopping at any gate that needs you:

1. **Test** — runs your suite; stops if anything's red.
2. **PR** — opens a draft PR for the branch.
3. **Review** — fans out the applicable specialists (security always runs), merged into one
   report in `relay/pr-reviews/`.
4. **Fix** — re-verifies each finding and fixes the real ones.
5. **Merge** — only on a clean green path (no blockers, checks passing, no conflicts).
6. **Handover** — writes a cold-start note to `relay/handover/`, updates the board, commits
   both to `main`, and prints a compact summary.

## 6. See the magic

Run `/clear` to wipe the session's memory. Then, in the fresh session:

```
/continue
```

It fetches the board from `main`, finds the thread you just handed off, tells you in plain
English what it is and what's next — and waits for your go-ahead. The new session knows
nothing about your last one, and it doesn't need to. That's the point.

---

## The daily rhythm, once you're going

- **Got a rough idea?** `/explore` — shape it into a brief on the board before you build.
- **Unsure if you're reinventing something?** `/cross-check` — see how others solve it first.
- **Starting fresh?** `/whats-next` — pick from the board.
- **Picking up a thread?** `/continue` — resume from its handover.
- **Done for now?** `/wrapup` (to ship) or `/handover` (to hand off mid-thread).
- **Cleaning up?** Nothing to run — `/wrapup` archives old notes and prunes dead worktrees as
  part of its handover step.

Next: **[the-board-model.md](the-board-model.md)** — the one mental model that makes all of
this hang together.
