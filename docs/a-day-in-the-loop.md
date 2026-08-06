# A day in the loop

One item, walked from a rough idea to a shipped change, annotated. Follow it once and the
commands stop feeling like separate tricks and start feeling like one motion.

The example: adding a rate limit to a login endpoint. Track `auth`, slug `auth/rate-limit`.

---

## The day before: shape the idea

It starts as a one-liner — "we should throttle repeated login attempts." Before it's worth
anyone's session, you shape it:

```
/explore throttle repeated login attempts
```

Relay doesn't jump to a design. It interrogates the idea one theme at a time, stopping for
your answers: *what's the real problem* (credential-stuffing, not user typos), *who hits it*
(every login, so it's hot-path), *what's explicitly out* (no CAPTCHA, no account lockout this
round), *what constrains it* (must work across multiple app instances). Then it puts up two or
three approaches — in-memory counter, shared store, gateway-level — with trade-offs, and
recommends the smallest one that actually solves it.

You agree. It writes `relay/briefs/rate-limit.md` — problem, chosen approach, the
alternatives it beat, a first slice, and what's out of scope — and adds a `🔜` row to the
board. **It stops there. No code.** The idea is now a startable item; shaping it and building
it are two separate acts.

> **Why separate them?** Because the questions worth asking about an idea are cheapest to ask
> before any code exists. `/explore` is where a wrong assumption costs a sentence, not a
> rewrite.

## Morning: pick something

Next day, fresh session, no memory of yesterday's `/explore` — but the brief is on the board.
You've no idea what's most worth doing, so you ask:

```
/next
```

Relay fetches the board from `main`, filters to what's actually startable (skipping anything
a live session already owns), ranks it, and shows you:

> | # | Item | What it is | Why now | Size |
> |---|---|---|---|---|
> | **1** ⭐ | `auth/rate-limit` | Throttle repeated login attempts | Closes an open security gap | **S–M** |
> | **2** | `billing/invoice-pdf` | Generate invoice PDFs | Unblocks the billing epic | **M** |
>
> ⭐ = my pick.

You pick 1. Relay puts you in the `auth` **topic worktree** — an isolated directory, created now
and reused for every later `auth` slice — on a new `rate-limit` branch, reads the brief, scopes
the first slice, and starts building. **You never touched `main`, and no other session's work is
anywhere near yours.**

> **Why a worktree, not just a branch?** So five sessions can each have a working tree
> checked out at once without fighting over one directory. Relay always works in one — and keys
> it to the **topic**, not the slice, so tomorrow's `auth` work reuses this same directory (same
> editor tab), re-baselined onto fresh `main`, instead of spawning a new tree per slice.

## Midday: something comes up

You get pulled away before the slice is finished — but it's at a natural pause. Rather than
lose the thread, hand it off:

```
/handover
```

Relay writes `relay/handover/next-2026-08-04-1330.md`: what you were doing, what's committed,
what's half-done, the next objective, and the exact first step to resume. It updates the
`auth/rate-limit` row on the board — status `⚙`, owner `—` (relinquished), latest handover
linked — and commits both to `main`. It prints a four-line summary and any open questions.

Then `/clear`. The session's memory is gone. The thread is not — it's on `main`.

> **The handover is the product.** Everything else exists to produce and consume this file.
> A good handover is one a stranger could act on. Cold-start is the design target, not an
> edge case.

## Afternoon: pick it back up

New session, hours later, no memory of the morning:

```
/continue
```

Relay fetches the board, sees `auth/rate-limit` waiting with a handover, enters its worktree,
and — before doing anything — tells you in plain English what the thread is and what's next.
It **waits for your go-ahead**, then describes the approach and **waits again**. Only then
does it build. Two pauses, because picking up cold is exactly when a wrong assumption is
cheapest to catch.

You confirm, it finishes the slice, commits.

## Late afternoon: kick the tyres (optional)

Not ready to merge on trust? Before `/ship`, hand the change to a test pass:

```
/test
```

Relay opens a draft PR and writes a **structured test plan** into it — preconditions, the happy
path, and the cases an LLM skips by default: invalid input, wrong-role, tenant-isolation. Add
`drive` and it clicks through the happy path in the browser against the preview and posts pass/fail
with a GIF. It **never merges** — it stops at a tested-but-unmerged PR; `/ship` still owns the
merge. (On a project with per-PR preview deploys this is where it shines; without one it falls back
to local-run steps.)

## Evening: ship it

```
/ship
```

The end-of-session loop, in order, stopping at any gate that needs you:

1. **Test** — runs your suite. Green, so it continues. (Red would stop here.)
2. **PR** — opens a draft PR for the branch.
3. **Review** — the diff touches backend + a security-sensitive path, so it fans out
   **backend-developer**, **security-specialist** (always on), and **test-engineer** in
   parallel, merged into one report at `relay/reviews/pr-142-2026-08-04.md`. One 🔴: the limit
   is per-process, not shared across instances.
4. **Fix** — Relay re-verifies that finding against the code (real), fixes it, keeps the
   typecheck green, ticks the box.
5. **Merge** — verdict is now clean, checks pass, no conflicts → merges with
   `--delete-branch`.
6. **Handover** — the PR is merged, so it writes the next handover (what shipped, what's next
   on the `auth` track), updates the board (`auth/rate-limit` → ✅, off Open threads), commits
   to `main`, prints the summary.

`auth/rate-limit` is done. The board shows the next `auth` item as 🔜. Tomorrow's `/next`
will surface it — and start it in the same `auth` worktree, re-baselined onto fresh `main`.

## Housekeeping happens on its own

Notice there was no "clean up" step. That's deliberate: the `/ship` you just ran archived
`auth/rate-limit`'s now-superseded handover, trimmed old PR reviews past the newest 20, and
pruned dead worktree entries — all folded into its handover step, on `main`, nothing deleted
(git keeps it all). It **kept** the `auth` worktree — the topic still has queued work, so
tomorrow's slice reuses it (a tree is only removed once its topic has nothing left on the board).
The one thing it *won't* do is force-remove a **sibling** session's worktree; it names one for
removal only when it's merged, clean, **and** its topic is no longer live — never a resting topic
tree, never by force — so it can never clobber a session that's still live. There's no separate
cleanup command to remember.

---

## The shape of it

The ship path is three commands — explore the idea, start it, wrap it up (`/ship` runs
the review, the merge, the handover, **and the tidy-up** for you at the end):

```
/explore ──► /next ──► build in worktree ──► /ship ──► merged, handed off & tidied
   idea →                                        test → review → merge → handover → archive
   brief on board
```

`/handover` and `/continue` are the **mid-thread pair** — you only reach for them when you
stop *without* shipping:

```
build ──► /handover ──► /clear     (pause: hand the thread off unfinished)
              │
   (cold session, later)
              │
              ▼
        /continue ──► build ──► /ship   (resume, then ship)
```

Every arrow that crosses a session boundary crosses through a file on `main`. That's the
whole reason the loop survives parallelism, `/clear`, and the passage of time.
