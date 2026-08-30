# The harvest result — smallest lossless payload at worker termination

_Derives the **minimum conceptual result** a dying worker must hand over so that terminating it loses nothing. Analysis only: no schema, no implementation, no behaviour change. Builds on `docs/stage-signatures.md` (§"What must survive a worker's death") and the handover decomposition there._

## Current end-of-lap behaviour

Today the "harvest" is not one act — it is a sequence the **worker itself performs** at end of lap, driven by Ship `[obs]/[impl]`:

```
Ship (compound span)
  P5   Merge PR → main            → code becomes durable in git
  P5.6 Release (hooks.release)    → optional
  P5.7 Persist                    → lessons/rules/ADRs/release-note/memory
  P6   Handover                   → handover doc + board row (status/owner)
```

Outside that spine, three more writes happen earlier in the lap: **decisions** are logged to `decisions.md`/`autonomy.log` by Next/Continue/Review as they occur; the **review report** is written by Ship's review phase; **discoveries** are (inconsistently) added to the board by Handover/Next under an offer-don't-auto-write rule.

Two properties of this matter for the derivation:

- **It is distributed and worker-driven.** No single result object is produced; the worker directly writes ~5 shared homes (git, `knowledge/`, `decisions.md`, board, changelog). `[inf]` This is exactly why parallel workers collide on those homes.
- **Outcome is only implicit.** `[obs]` Ship records the lap's fate solely as PR state (`gh pr view --json state`) + the merge commit + the board-row status the Handover writes. There is **no durable, queryable "this lap ended, and how"** fact — and when a lap ends *without* a clean merge (parked / blocked / deliberately abandoned), the reason exists only as handover prose.

## Losslessness criterion

Termination is **lossless** iff, at the moment the worker dies, nothing of value exists *only* inside it — its transcript or its uncommitted worktree. Everything must already be in a durable home, or captured in the result the worker emits to whatever persists it.

The harvest result is therefore the **minimal set of information a worker must emit at death** for that to hold. It has exactly two parts.

## Part A — references to already-durable state (the runtime persists nothing new)

By the time a lap ends, most categories are **already** in durable homes; the harvest only needs to *address* them. The runtime stores a pointer, not a copy.

| Reference | Points at | Durable because | Written by |
|---|---|---|---|
| brief slug | the unit's intent / approach / slices / threat model / done-criteria | `briefs/<slug>.md` on main | Explore, Refine |
| branch + base/head SHA | the code and its diff | git | Next/Continue (build), Test (commit) |
| PR number | diff, checks, review comments, **merge outcome + `mergedAt`** | GitHub | Test (opens), Ship (merges) |
| review report path + verdict | graded findings, refuted findings | `reviews/pr-N-*.md` on main | Review (in Ship) |
| prior handover ref | the thread's history | `handover/` on main | previous Handover |
| board row id | current status / ownership / phase | `board.md` on main | Handover, Next |
| worktree path | the live tree (incl. uncommitted work, *while it survives*) | filesystem (transient) | Next/Continue |

**Precondition that shrinks Part B to almost nothing:** for the *worktree path* row to be a real reference rather than a fragile one, **all code — including work-in-progress — must be committed to git before death** (even as a `wip:` commit). That single discipline converts the one genuinely-fragile category (uncommitted WIP) into an ordinary git reference, and removes any need for the result to carry a diff as data. Losslessness *requires* this; without it, WIP is lost the moment the worktree is pruned.

## Part B — new information the runtime must persist (the delta only the worker knows)

What remains — the genuinely new payload — is small, and much of it is often empty:

| New information | Why it isn't already durable | Target home |
|---|---|---|
| **Lap disposition** | git/PR gives *merged vs open*, not *done · parked · blocked · abandoned*; the reason lives only in the worker | a durable lap-status fact (today: board row + handover prose) |
| **Thread-resume delta** | next-slice pointer, in-flight *intent* (done vs remaining), scope edges, open questions — the interpretation the diff can't show | the handover core |
| **Discoveries** (0..n) | new work found mid-flight, unrelated to this thread — exists only in the worker's context | the board (new rows) |
| **Lessons** (0..n) | non-obvious + will-recur learnings; each tagged to *its* home | `knowledge/` · `decisions.md` · AI memory · changelog |
| **Binding decisions** (0..n) | decisions made this lap that bind future work, not already logged | `decisions.md` / `autonomy.log` |

Note the shape: **one status flag, one small resume delta, three short lists.** On a clean lap the three lists are frequently short or empty, so Part B collapses toward *just the disposition + the resume delta*.

## The smallest harvest result, stated

> **references{ brief, branch+SHAs, PR, review, prior-handover, board-row } + disposition + resume-delta + discoveries[] + lessons[] + decisions[]** — with the invariant that **all code is committed first**, so code is always a reference and never payload.

Everything else a worker holds — its reasoning, its exploration, its intermediate tool output — is **not** in the result: it dies with the transcript, by design, its value already routed into the lines above.

## Which current Relay operations participate

The harvest is not new work — today's operations already produce every piece; they just do it as distributed writes rather than as one result. Mapping each piece to the op that already owns it:

| Harvest piece | Owned today by | Part |
|---|---|---|
| Code → git (merge) | **Ship** (P5) | A (makes the git reference) |
| Commit WIP before death | *no one enforces it* | A (the missing precondition) |
| Review report | **Review** (inside Ship P3) | A (reference) |
| Lessons / rules / ADRs / release note | **Persist** (Ship P5.7 or standalone) | B |
| Decisions during the lap | **Next / Continue / Review** (as they occur) | A/B (already-logged ⇒ reference; unlogged ⇒ new) |
| Thread-resume delta + board status | **Handover** (Ship P6 or standalone) | B + A(board) |
| Discoveries → board | **Handover / Next** (offer-don't-auto-write) | B |
| Lap disposition as a durable fact | *no one* | B (the missing fact) |
| Orchestration of all the above | **Ship** (the driver) | — |

Two participants are **missing**, and they are exactly the losslessness gaps: nothing **commits WIP** to make the worktree reference safe, and nothing **records lap disposition** as a durable queryable fact (only as prose). Everything else in the result already has an owning operation — Ship drives, Persist owns the knowledge delta, Handover owns the resume delta + board, the merge and Review produce references.

## Conclusion (empirical basis for the later contract)

The smallest lossless harvest result is **mostly a reorganisation of what Ship, Persist and Handover already emit** — recast from *distributed writes the worker performs* into *one result the worker hands off* — plus exactly **one new fact** (lap disposition) and **one enforced precondition** (WIP committed). Its durable-new content is genuinely small because, by end of lap, code is in git, intent is in the brief, and findings are in the review — so the worker need only *reference* them and add the short delta only it knows.

This is the empirical shape a future "result contract" would formalise, and it localises the change surface: make the harvest a result the runtime persists (single-writer over the shared homes), rather than writes the dying worker performs itself. *(Stated as the implication of the model — not designed or built here.)*
