# Worker harvest — minimal first design

_A design document only. **No code, no lifecycle changes, no contract framework, no runtime** are proposed for building here — this specifies the smallest coherent design and the single slice that would prove it. Evidence base: `docs/stage-signatures.md` and `docs/harvest-result.md`._

## Hypothesis being designed against

> An ephemeral worker may **intentionally** terminate only after every durable result it produced either **(A)** already has an authoritative durable reference, or **(B)** has been successfully persisted into its authoritative home.

The worker's transcript/context is **not** durable state. It may serve as a crash-recovery log (§6), but it is never the authority for anything.

---

## 1. The Harvest Result

The smallest structured representation a terminating worker emits. Conceptual fields only (no schema). It is dominated by **references**; the genuinely-new content is a status, a small delta, and three usually-short lists.

**Identity** (for idempotency and addressing — §7):
- `lap_id` — the worker/session id (stable, already the key in `commands.jsonl`).
- `work_item` — the board slug this worker served.

**A · References to already-durable state** (persist a pointer, never a copy):
- `brief` → `briefs/<slug>.md`
- `branch` + `base_sha` + `head_sha`
- `pr` → number (carries diff, checks, and **merge outcome**)
- `review` → `reviews/pr-N-*.md` (if a review ran)
- `prior_handover` → the handover this thread resumed from
- `board_row` → the item's row (carries **work-item status**)

**B · New information the runtime must persist** (the delta only the worker holds):
- `disposition` — the worker's **termination reason** (§2). The *only* new disposition fact; work-item status and merge outcome are references above, not copied here.
- `resume_delta` — `next_slice` pointer · `in_flight` (per-path: done vs remaining, or `clean`) · `scope_edges` · `open_questions`.
- `discoveries[]` — follow-up found mid-flight, each `{title, one_line, link?}` → the board.
- `lessons[]` — each `{claim, home: guardrail|decision|memory|release_note}` → knowledge surfaces.
- `decisions[]` — binding decisions not already logged → `decisions.md`.

**Rule applied throughout:** *one fact → one authoritative home.* Anything reachable through a reference is never duplicated in the body. `discoveries/lessons/decisions` are frequently empty; on a clean forward lap the result reduces to *references + disposition + `next_slice`*.

---

## 2. Disposition

Investigating the existing system shows disposition is **not one vocabulary but three orthogonal axes** — and two of them already have authoritative homes:

| Axis | Authoritative home today | Vocabulary (existing) | In the result |
|---|---|---|---|
| **Work-item completion** | the board row | `init.md`: 💡 idea · 🔜 next · ⚙ in-progress · 🔍 in-review · ⏸ parked · ✅ done | **reference** (`board_row`) |
| **PR/merge outcome** | the PR (GitHub) | OPEN · MERGED · CLOSED (+ draft, checks) | **reference** (`pr`) |
| **Lap execution outcome** | *nowhere durable today* | derived below | **new** (`disposition`) |

So the harvest must **not** adopt a fresh `done/parked/blocked/abandoned` enum — `done`/`parked` already exist as board glyphs, and `merged` already exists as PR state. The only genuinely-new fact is **why this worker's session stopped**, whose values are grounded in Relay's actual STOP gates and terminal transitions `[impl]/[obs]`:

- `advanced` — the worker completed its stage; the next stage is known (built→test, tested→ship). Continues normally.
- `merged` — Ship reached a clean merge; the lap's forward work is done (PR state is the authority; this just records that this session is the one that landed it).
- `stopped:<gate>` — halted at an existing STOP gate, `<gate>` ∈ {`tests-red`, `needs-judgment`, `last-blocker`, `not-clean-green`, `branch-protected`, `no-drive-evidence`}. Awaits a human/decision.
- `parked` — deliberately set aside (writes board ⏸; the board glyph is the authority).
- `watching` — blocked on a sibling's unlanded work → `/watch` (an existing transition).
- `reflect-back` — a drive exposed a broken assumption; work returns to Refine/Explore (an existing backward edge).

`disposition` also classifies the termination itself: `advanced`/`merged`/`parked`/`watching`/`reflect-back`/`stopped:*` are all **intentional** (the invariant applies); their *absence* is a **forced** termination (crash — §6), which the invariant cannot cover.

---

## 3. Durability invariant

**A worker is safe to intentionally terminate iff its harvest is _complete_:** every field of the Harvest Result is either backed by an authoritative reference (A) or has been persisted to its home (B), and a **completion marker** for `lap_id` exists.

- **What must already be durable (A):** committed code (git), the brief, the review report, the PR. Precondition: uncommitted work has been made durable (§4) — otherwise the `branch`/`head_sha` reference is a lie.
- **What the runtime must persist (B):** `disposition` (+ the small residue), `resume_delta` → handover home, `discoveries` → board, `lessons` → knowledge, `decisions` → `decisions.md`.

**Harvest is one logical operation over non-transactional homes.** Make it behave atomically with a **write-ahead + idempotent-replay + completion-marker** pattern (not a distributed transaction):

1. **Stage the whole Harvest Result durably first**, as one atomic write to a unique per-`lap_id` location (§7 makes this conflict-free). After this point nothing is lost even if every subsequent step fails.
2. **Fan out to homes idempotently** — each home write keyed by `lap_id` (+ per-item id), so re-applying is a no-op.
3. **Write the completion marker last** — its presence *is* the definition of "harvested".

- **Partial failure (some homes written, marker absent):** harvest is incomplete → worker is **not** safe to terminate → the runtime retries only the unfinished homes (idempotent), then writes the marker.
- **Safe to retry:** yes, by construction — step 1 is durable and steps 2–3 are idempotent, so the entire harvest can be replayed from the staged result any number of times.
- **Duplicate prevention:** every home write is an upsert keyed by a stable id (`lap_id` for the resume-delta/disposition; `lap_id`+content-hash for each discovery/lesson/decision), so replay never double-writes.
- **How the runtime knows harvest completed:** the completion marker for `lap_id` exists. Nothing else is consulted; the marker is the single source of truth for "done".

---

## 4. WIP durability

The reference `branch`+`head_sha` is only honest if the worker's uncommitted work is durable off-machine before death. Comparing the smallest git-native options against Relay's existing worktree/branch/PR model:

| Option | Durable off-machine? | Resumable? | Fits Relay? | Verdict |
|---|---|---|---|---|
| Leave it in the worktree | ✗ (dies with a pruned/foreign worktree) | only same machine | it's today's fragile default | **reject as the mechanism** |
| `git stash` | ✗ (local, not pushed) | local only | no | **reject** |
| Plain `wip:` commit (local) | ✗ until pushed | yes | partial | insufficient alone |
| **Autosave commit + push to the branch's (draft) PR** | ✓ | yes (checkout + resume-delta) | **yes — Relay already opens a draft PR at Test and pushes to it** | **recommended** |
| Dedicated `refs/relay/wip/<lap>` ref | ✓ | yes | novel machinery | over-engineered for slice 1 |

**Recommendation:** the requirement is *durability + resumability*, and Relay already has the durable off-machine home for in-progress code — **the branch on the remote, surfaced as a draft PR** (opened at Test, pushed by Ship). So WIP durability = *commit the dirty tree as a marked autosave commit and ensure the branch is pushed*. The mark (a commit-message trailer, e.g. `Relay-Autosave: <lap_id>`) lets a resuming worker recognise it and continue-or-amend cleanly, and lets Ship squash it at merge. This reuses the existing branch/PR seam rather than introducing stash or custom refs. A dedicated `refs/relay/wip/*` ref is strictly more isolated but is not warranted until evidence shows the autosave commit causes real friction.

---

## 5. Ownership: what moves, what stays

Today Ship/Persist/Handover each **write shared homes directly, from inside the dying worker** — the root of the merge-conflict problem (`stage-signatures.md` §global-state). The shift separates *producing* the result from *persisting* it:

```
TODAY:   Worker → Ship → Persist → Handover → (each writes board/knowledge/decisions/handover directly)
DESIGN:  Worker → Harvest Result → Runtime → (single writer of the shared homes)
```

**Moves to the runtime (the writes):** persisting `resume_delta` → handover home, `discoveries` → board, `lessons` → knowledge, `decisions` → `decisions.md`, disposition/status. The runtime becomes the **single writer of the contended shared homes**.

**Stays worker-owned (the production):**
- **Code** — the worker commits to *its own branch* (worker-local; git is already conflict-free per-branch). The merge to main is the one shared write; it can stay Ship-driven initially.
- **The Harvest Result content** — only the worker knows its delta, discoveries, lessons, decisions, and disposition. Producing it is reasoning, not a shared write.
- **The review** — the worker spawns specialists and produces the report (compute → a reference).
- **Deciding what is a lesson / what the resume-delta is** — Persist's and Handover's *judgment* stays worker-side; only their *writes* move.

So **Ship/Persist/Handover don't disappear — they split.** Their compute (orchestrate, judge, draft) becomes "build the Harvest Result"; their writes to shared homes become "hand the result to the runtime." Ship remains the worker-side orchestrator that assembles the result; the runtime consumes it.

---

## 6. Failure scenarios

| Scenario | Disposition | Durable via | Safe to terminate? |
|---|---|---|---|
| Clean merged lap | `merged` | code=git(merged), refs; resume-delta may point at next slice | ✓ after marker |
| Coding done, tests failed | `stopped:tests-red` | WIP committed+pushed; resume-delta = "red at X, fix Y" | ✓ (a clean stop; work durable) |
| Blocked worker | `stopped:needs-judgment` / `watching` | refs + `open_questions` | ✓ |
| Context exhaustion mid-slice | `stopped:context-exhausted` | **must** autosave-commit + emit resume-delta first | ✓ iff harvest completes |
| Intentionally parked | `parked` (board ⏸) | refs + resume-delta | ✓ |
| **Worker crashes before harvest** | *(none — forced)* | see below | **N/A — invariant does not apply** |
| Harvest partially succeeds | any | staged result (step 1) is durable | not until replay → marker |
| Runtime crashes during harvest | any | staged result is durable | resume: replay staged result idempotently → marker |
| Two workers find the same follow-up | — | board dedup by discovery id | ✓ (runtime dedups) |
| Two workers harvest shared state at once | — | runtime serialises per home | ✓ (no worker-side merge) |

**The crash-before-harvest case (called out as important).** "No successful harvest → no intentional termination" protects *intentional* exits only; a process kill produces no Harvest Result, so Part-B state (uncommitted WIP, resume-delta, discoveries, lessons, decisions) that lived only in the transcript/worktree is **lost**. Two mitigations bound the loss — and neither is a transaction system:

1. **A continuous durability floor, not just an end-of-lap harvest:** periodic **autosave-commit-push** (§4) during the lap bounds *code* loss to the last checkpoint regardless of how the worker dies. This is the single most valuable addition the crash case requires.
2. **The transcript as a crash-recovery log (not as state):** Claude Code persists every transcript on disk — and Relay already mines it (`reflect-sessions.py`/`reflect-commands.py`). So after a crash the runtime can run a **best-effort recovery harvest** from the dead worker's transcript + git, recovering the references, committed code, and (by mining) discoveries/decisions. This reframes the transcript precisely: it is *not* authoritative state, but it *is* a durable write-ahead log for the harvest — which is exactly why it must never be the authority, only a recovery source. The irreducible residue that recovery cannot get back is un-committed code beyond the last autosave and un-verbalised intent — which mitigation 1 minimises.

**Determination:** the crash case requires *one* additional durability mechanism beyond the invariant — periodic autosave-commit-push — plus treating the already-durable transcript as a recovery log. No further durability is required.

---

## 7. Idempotency & concurrency

The eventual runtime supervises many workers; the design must be concurrency-ready without a generic DTC.

- **Stable identity:** `lap_id` (session id) + per-item content-hash ids. Every persisted thing is addressable and re-addressable.
- **Retry-safe:** all home writes are upserts keyed by those ids; replaying a harvest is a no-op after the first success. The completion marker prevents re-running a finished harvest.
- **No worker-side merges of shared state:** workers **never** write board/knowledge — they emit results; the runtime is the single writer, so `board.md`/`knowledge/` merge conflicts are eliminated *by construction*, not resolved.
- **Conflict-free result emission:** the staged Harvest Result is a **unique per-`lap_id` file** (like `movements.jsonl` lines are per-event) — two workers never write the same path, so even staging to a shared location (git on main) is conflict-free. Contention exists only when *applying* to a shared home, and the single-writer runtime serialises that (a simple per-home queue/lock per repo).
- **Concurrent harvests:** serialised by the runtime per shared home; because each staged result is durable and idempotent, order doesn't affect correctness, only board/knowledge write ordering.

**No generic distributed-transaction system is warranted.** Write-ahead (durable staged result) + idempotent replay + single-writer-per-home + a completion marker is sufficient for everything above, and the evidence shows nothing that needs more.

---

## 8. First implementation slice

**Prove the architecture on the single highest-confidence seam — Handover → Continue — without touching the rest of the lifecycle.** It is already Relay's resume mechanism, already structured (9 fields), and already the strongest contract candidate.

**The slice:**
1. At **intentional handover of a clean (committed) thread**, the worker emits a **structured Harvest Result** — references + `disposition` + `resume_delta` (+ any `discoveries`) — as one unique per-`lap_id` file in a durable staged location (git on main, conflict-free by name).
2. A **thin runtime persist step** (a script, in the spirit of the existing `reflect-*` tooling — *not* a supervisor) reads staged results and applies them **idempotently**: writes the board row + renders the human-readable handover doc **as a projection of the result**, then writes the completion marker.
3. A fresh **Continue** worker resumes **from the persisted resume-state**, not from the transcript.

This demonstrates the whole loop — *ephemeral worker → structured harvest result → runtime-owned persistence → fresh worker resumes* — on one seam, reusing the handover file (now a projection) and the board write (now runtime-owned). It can even bootstrap the references from existing `commands.jsonl` telemetry.

**Explicitly NOT in the first slice:**
- Lessons/knowledge harvest (leave `/persist` exactly as-is) and `decisions` routing.
- WIP autosave-commit-push (design §4 stands; slice 1 handles only the already-committed case).
- Crash-recovery harvest from transcripts (§6) — designed, not built.
- The generic runtime/supervisor, model routing, or multi-worker scheduling.
- Any versioned-contract framework or schema formalisation.
- Migrating the other seams (Explore→Refine, Refine→Next, Test→Ship).
- Making the Harvest Result canonical over Markdown everywhere — in slice 1 it is canonical for **resume-state only**; the rest of the handover doc may remain prose.
- Removing writes from Ship/Persist — only Handover's board+handover write moves to the runtime step in this slice.

**Why this seam first:** it is the one place where a durable artefact is *already* handed across worker death, its consumer (Continue) is well-understood, and its payload (§1's resume-delta) is the smallest. Adapting it proves single-writer runtime persistence and structured hand-off with the least risk and no lifecycle refactor — a real proof, not a framework.
