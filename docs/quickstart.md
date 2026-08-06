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

`/init` is deliberately **minimal** — it does the least needed to start and defers everything else.
On a **greenfield** repo it writes an empty board and points you at `/explore`. On a **brownfield**
repo it also seeds a few real tracks from your code and **references your existing idea/plan docs on
the board — leaving them exactly where they are** (see the reassurance box below). It never asks for a
session size, never runs guardrails, and never moves a file; those come later, when a phase needs them.

Over time the Relay root fills out to this full shape (most sub-dirs are created lazily, by the first
command that writes them — `/init` itself only makes `board.md`, `briefs/`, and `handover/`):

```
relay/                ← the Relay root (default name; see "point it elsewhere" below)
  board.md            ← the front door: the Open-threads table + tracks. Every command reads this first.
  roadmap.md          ← the longer narrative behind each board item
  briefs/             ← one brief per unit of pending work (what /explore writes, /next starts from)
  handover/           ← cold-start handovers (next-*.md); what /handover writes and /continue resumes from
    archive/          ← superseded handovers, moved here by housekeeping (never deleted)
  reviews/            ← one merged review report per PR (what /review + /ship write)
    archive/          ← review reports past the newest 20, moved here by housekeeping
  reference/          ← reference frames from /cross-check (how others solve a problem)
  archive/            ← shipped briefs, moved here when the board is compacted
  audits/             ← dated whole-board reconciliation reports from /next audit
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

> ### Pointing Relay at an existing project — what happens, and what doesn't
> Relay is built to move **into** a repo that already has history, docs, and half-formed plans —
> greenfield and brownfield are both first-class. The worry is always "will it rearrange my stuff?"
> The answer is **no, not without you asking**:
> - **`/init` moves nothing.** Your `ideas/`, `docs/`, RFCs, notes stay exactly where they are. Init
>   only *references* your idea/plan docs on the board (a row whose `Detail` points at the original
>   file) so none of them is invisible — nothing is copied, moved, or rewritten.
> - **Adoption is progressive and opt-in.** A doc is only ever *pulled into* Relay when you choose to
>   work it: `/refine <slug>` moves that one idea into `briefs/` as it grooms it, and — because it's
>   reconciling against your current code anyway — **tidies it on the way in** (cuts what already
>   shipped, fixes what drifted). Over time, as you work, `ideas/` empties and the repo becomes fully
>   Relay-managed. The board's `Detail` column shows the progress: rows still pointing *outside* the
>   root are the not-yet-adopted tail.
> - **Want to sweep an area at once?** `/adopt [area]` is the bulk button — it pulls a whole area's
>   work-inputs in (and can register + **compact** an existing design guide or convention doc in place,
>   via its steward). Scoped, and it always shows a plan and STOPs before touching anything.
> - **Your durable docs stay with your code.** A design guide, DB conventions, architecture notes are
>   never moved into Relay — they're *registered* (pointed at) by `/guardrails` so reviews check
>   against them, and they keep living where they belong.
>
> Net: start Relay on a messy real project today, keep working, and it cleans up *as a side effect of
> the work* — never as a big scary migration.

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

## 3.5 (optional) Ground it with `/refine`

`/explore` shapes the idea in the abstract. On a real project, `/refine` grounds it before you build:

```
/relay:refine <track/slug>
```

It reads the actual code, the guardrails (`/guardrails`), and memory; threat-models the change; and
re-slices the work to your session size — updating the brief in place. Skip it for something small and
obvious; reach for it when the idea needs to fit an existing codebase. Then `/next` starts a grounded,
right-sized slice instead of a raw sketch.

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
   report in `relay/reviews/`.
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

- **Setting "what good means" for the project?** `/guardrails` — establish the layered guardrails
  (API/UI/security/…) that `/refine` and the review specialists then check against.
- **Moving in on a repo full of legacy notes?** `/adopt [area]` — pull an area's idea docs into Relay
  (tidied on the way in) and register + compact its convention docs. The bulk version of what `/refine`
  does per-idea; scoped, and always asks first.
- **Got a rough idea?** `/explore` — shape it into a brief on the board (purely in the abstract).
- **Unsure if you're reinventing something?** `/cross-check` — see how others solve it first.
- **Need it grounded before building?** `/refine` — fit the idea to the code + guardrails, threat-model
  it, and slice it to your session size.
- **Starting fresh?** `/next` — pick from the board.
- **Picking up a thread?** `/continue` — resume from its handover.
- **Want to try it before merging?** `/test` — a draft PR with a structured test plan (happy path +
  edge/error/tenant-isolation + threat-model cases); add `drive` to run it in the browser. Never merges.
- **Need the PR preview ready to test?** `/deploy` — orchestrate + security-gate the PR preview via
  your own CI, then hand a verified URL to `/test`.
- **Blocked on a sibling session's unlanded work?** `/watch` — park it, auto-resume when it lands.
- **Done for now?** `/ship` (to ship) or `/handover` (to hand off mid-thread).
- **Just shipped something worth keeping?** `/persist` — harvest the lesson into guardrails/design
  system/memory and draft a release note, so the next lap starts smarter.
- **Cleaning up?** Nothing to run — `/ship` archives old notes and prunes dead worktree entries as
  part of its handover step, and keeps your topic worktrees for their next slice.

The lifecycle, one line: **`guardrails` → `explore` → `refine` → `next`/`continue` → `test` →
`deploy` → `review`/`fix` → `ship` → `persist`** — a spiral, each phase optional, results loop back to
`explore`/`refine`.

Next: **[the-board-model.md](the-board-model.md)** — the one mental model that makes all of
this hang together.
