# A day in the loop

One item, walked from "what should I do?" to "merged and handed off," annotated. Follow it
once and the commands stop feeling like separate tricks and start feeling like one motion.

The example: adding a rate limit to a login endpoint. Track `auth`, slug `auth/rate-limit`.

---

## Morning: pick something

You sit down with a fresh session and no idea what's most worth doing.

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

You pick 1. Relay creates a git worktree for `auth/rate-limit` — an isolated directory on a
new branch — reads the brief, scopes the first slice, and starts building. **You never touched
`main`, and no other session's work is anywhere near yours.**

> **Why a worktree, not just a branch?** So five sessions can each have a working tree
> checked out at once without fighting over one directory. Relay always works in one.

## Midday: something comes up

You get pulled away before the slice is finished — but it's at a natural pause. Rather than
lose the thread, hand it off:

```
/handover
```

Relay writes `docs/handover/next-2026-08-04-1330.md`: what you were doing, what's committed,
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

## Evening: ship it

```
/wrapup
```

The end-of-session loop, in order, stopping at any gate that needs you:

1. **Test** — runs your suite. Green, so it continues. (Red would stop here.)
2. **PR** — opens a draft PR for the branch.
3. **Review** — the diff touches backend + a security-sensitive path, so it fans out
   **backend-developer**, **security-specialist** (always on), and **test-engineer** in
   parallel, merged into one report at `pr-reviews/pr-142-2026-08-04.md`. One 🔴: the limit
   is per-process, not shared across instances.
4. **Fix** — Relay re-verifies that finding against the code (real), fixes it, keeps the
   typecheck green, ticks the box.
5. **Merge** — verdict is now clean, checks pass, no conflicts → merges with
   `--delete-branch`.
6. **Handover** — the PR is merged, so it writes the next handover (what shipped, what's next
   on the `auth` track), updates the board (`auth/rate-limit` → ✅, off Open threads), commits
   to `main`, prints the summary.

`auth/rate-limit` is done. The board shows the next `auth` item as 🔜. Tomorrow's `/next`
will surface it.

## The next morning: tidy up

Over a week you've accumulated finished worktrees and a pile of old handovers.

```
/start-new
```

Relay lists every worktree with its branch, age, and whether it's safe to remove. It
auto-removes only the provably-safe ones (merged + clean + unlocked), **reports** the risky
ones and asks before touching them (a sibling session might be live in one), and archives
handovers the board no longer references and PR reviews past the newest 20. Nothing is
deleted — git keeps it all.

Then it reminds you to `/clear`, because a command can't clear its own context.

---

## The shape of it

```
/next ──► build in worktree ──► /handover ──► /clear
                                    │
                        (cold session, later)
                                    │
                                    ▼
/continue ──► build ──► /wrapup ──► merged + handed off ──► /start-new (weekly)
```

Every arrow that crosses a session boundary crosses through a file on `main`. That's the
whole reason the loop survives parallelism, `/clear`, and the passage of time.
