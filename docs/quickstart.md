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

Restart Claude Code if prompted. You should now see `/init`, `/explore`, `/next`,
`/continue`, `/ship`, and the rest in your command list.

> **Command names collide?** If your setup already has a `/continue` or `/next`, Claude Code
> namespaces plugin commands — invoke them as `/relay:continue`, `/relay:next`, etc.

## 2. Scaffold the convention

```
/init
```

This inspects your repo and creates **one folder — the Relay root** — holding every durable file
the workflow reads and writes. This is the exact structure every command builds and looks for:

```
relay/                ← the Relay root (default name; see "point it elsewhere" below)
  board.md            ← the front door: the Open-threads table + tracks. Every command reads this first.
  roadmap.md          ← the longer narrative behind each board item
  briefs/             ← one brief per unit of pending work (what /explore writes, /next starts from)
  handover/           ← cold-start handovers (next-*.md); what /handover writes and /continue resumes from
    archive/          ← superseded handovers, moved here by housekeeping (never deleted)
  pr-reviews/         ← one merged review report per PR (what /review + /ship write)
    archive/          ← review reports past the newest 20, moved here by housekeeping
  reference/          ← reference frames from /cross-check (how others solve a problem)
  archive/            ← shipped briefs, moved here when the board is compacted
  board-audit/        ← dated whole-board reconciliation reports from /next audit
  README.md           ← a short note explaining the convention to teammates
```

Everything the workflow owns lives under this **one root**, so a teammate sees the whole convention
at a glance and it stays cleanly separated from the rest of your repo.

> **Already keep this state somewhere else? Point Relay at it instead of migrating.** The root is
> configurable per repo — drop a `relay.config.json` at the repo root with `{ "root": "docs" }` and
> every command reads/writes `docs/board.md`, `docs/handover/…`, etc. No config (the default) means
> the root is `relay/`. This is how a repo that already runs a board/handover convention under its
> own folder adopts the `relay:*` commands **without moving a single file**.

It commits these but does **not** push — review the seeded tracks, edit them to match how
you actually think about the work, then push when you're happy. The tracks are a starting
guess, not a verdict.

## 3. Shape your first piece of work with `/explore`

Give a rough idea and let Relay turn it into a proper board item:

```
/explore let users export their account data
```

`/explore` interrogates the idea one question at a time — the real problem, who it's for,
what's explicitly out of scope, the constraints — then puts up a couple of approaches and writes
the one you pick up as a **brief** in `relay/briefs/` with a matching **row on the board**. (It
*offers* to cross-check your pick against prior art first — skippable, and skipped for small
ideas.) It *never* writes code: shaping the work and doing it are
deliberately separate. When it's done you have a startable item, not a half-built feature.

> **Prefer to write it yourself?** You can always open `relay/board.md`, add a row to **Open
> threads**, and drop a one-paragraph brief in `relay/briefs/` by hand. `/explore` is the
> assisted path, not the only one.

## 4. Start it

```
/next
```

Relay reads the board, ranks what's startable, and shows you a short table with a ⭐
recommendation. Pick one. It puts you in that item's **topic worktree** — created if this is the
topic's first slice, otherwise reused and re-baselined off `main` — and cuts a fresh branch for
the slice. You're now working in an isolated directory, without touching `main` or any other
session's work.

## 5. Wrap it up

When the slice is done and committed:

```
/ship
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
- **Starting fresh?** `/next` — pick from the board.
- **Picking up a thread?** `/continue` — resume from its handover.
- **Want to try it before merging?** `/test` — a draft PR with a structured test plan
  (happy path + the edge/error/tenant-isolation cases); add `drive` to run the happy path in the
  browser. Never merges.
- **Blocked on a sibling session's unlanded work?** `/watch` — park it, auto-resume when it lands.
- **Done for now?** `/ship` (to ship) or `/handover` (to hand off mid-thread).
- **Cleaning up?** Nothing to run — `/ship` archives old notes and prunes dead worktree entries
  as part of its handover step, and keeps your topic worktrees for their next slice.

Next: **[the-board-model.md](the-board-model.md)** — the one mental model that makes all of
this hang together.
