# Worker harvest — minimal first design

_A design document only. **No code, no lifecycle changes, no contract framework, no runtime** are proposed for building here — this specifies the smallest coherent design and the single slice that would prove it. Evidence base: `docs/stage-signatures.md` and `docs/harvest-result.md`._

> **Revision R1 (below) supersedes parts of §4, §6 and §8** for nomadic/mobile operation, where forced worker loss (lid, network, VS Code crash) is normal. Read §1–§3, §5, §7 as written; take §4, §6 and §8 together with R1.

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

**Determination:** the crash case requires *one* additional durability mechanism beyond the invariant — periodic autosave-commit-push — plus treating the already-durable transcript as a recovery log. No further durability is required. **(Revised by R1.4–R1.6:** in nomadic use the crash case is *normal*, autosave splits into local-commit vs opportunistic-push, and the transcript is demoted to a best-effort tier-(c) source behind a durable-state recovery path that never touches session residue.)**

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

---

# Revision R1 — nomadic operation (forced loss is normal)

_This revision supersedes parts of §4, §6 and §8. The base design above optimised **intentional** end-of-lap harvest; in real use Relay runs nomadically — lids close, trains drop connectivity, VS Code force-quits with ~10 workers live, terminals get closed by accident, and provider `/resume` does not reliably recover the right session. Forced worker death is **normal operation**, not an edge case. That changes the design in one structural way: worker-continuity must stand entirely on durable state, never on provider session residue._

## R1.1 — Three concerns the base design conflated into "harvest"

| Concern | What it restores | Trigger | Reliability |
|---|---|---|---|
| **Reconnect** | the *same* provider session (context intact) | terminal closed, session still alive | **best-effort only** — `/resume` is unreliable; never depended on |
| **Recover / replace** | a *fresh* worker seeded from durable state (no transcript) | session gone (crash/force-quit) | **the designed normal path** |
| **Semantic harvest** | knowledge externalised (references + delta + lessons) | clean stage boundary | independent of the above |

Worker-continuity (reconnect / replace) is **not** knowledge-continuity (harvest). The base design only had the third. Nomadic operation requires the first two — and makes *replace* the reliable primary, with *reconnect* a bonus.

## R1.2 — Provider session id is not the identity of work

Durable identity is the **work item** (slug), bound to its branch and topic-keyed worktree. The provider session id is a **volatile reconnect hint** — possibly stale, possibly absent — and must never be the key anything durable is stored under. Grounding: worktrees are deterministically topic-keyed (`.claude/worktrees/<topic>`, branch `<topic>`, discoverable via `git worktree list` with no session id), and the board's **Open threads** table is already the durable index of in-flight work `[impl]`. So work is fully addressable without any session id.

## R1.3 — The Active Work representation

The smallest durable record per active item, split by volatility:

| Field | Layer | Notes |
|---|---|---|
| `work_item` (slug) | **durable** — board row | the identity |
| `branch` | **durable** — git + handover frontmatter | where code lives |
| `stage` | **durable** — board status / last checkpoint | where in the lifecycle |
| `checkpoint_ref` (last autosave SHA + last harvest/resume-delta) | **durable** — git | **where to resume from, transcript-free** |
| `worktree_path` | **local** | machine-specific but *derivable* from topic |
| `provider_session_id` | **local, hint** | reconnect only; may be null/stale |
| `liveness` (heartbeat, connectivity) | **local, volatile** | is a worker attached and alive now |

The durable half is **mostly already present** — the board's ⚙ rows carry `work_item` + Owner + Latest-handover (→ branch), git carries the branch and commits. Genuinely new: a per-item **`checkpoint_ref`** so replace-from-state needs no transcript, and a thin **local overlay** (session hint + liveness) that is *rebuilt on restart, never trusted across it*. So the **Active Work Registry is largely a view over board + git + checkpoints**, plus a small local file — not a new database.

## R1.4 — Recovery tiers (revises §6's transcript-as-recovery-log)

The normal recovery path must **not** require locating or interpreting provider-internal session residue. What recovery is possible with:

- **(a) provider session still available** → **reconnect** via the session hint. Cheapest, full context — but unreliable, so treated as an *optimisation*, never a requirement.
- **(b) only worktree/git available** → **replace**: start a fresh worker from `worktree + branch + checkpoint_ref` (last autosave commit + last resume-delta). Fully durable, **transcript-free and network-free**. This is the **designed normal path**, and the design guarantees it always suffices by always keeping a recent checkpoint (R1.5).
- **(c) provider session lost *and* no recent checkpoint** → **re-derive**: the replacement worker rebuilds context from durable state (brief + code + board) — slower but correct. Automatic transcript mining (runtime resolves the transcript from the local hint and mines it) is permitted here as *best-effort*, but is never required and never manual.

The transcript is thereby **demoted**: a convenience source the runtime *may* use automatically in tier (c), never something Erik locates, never the authority, never on the normal path. Tier (b) is the reliable floor.

## R1.5 — Continuous checkpoints, not only end-of-lap harvest

For tier (b) to always suffice, a recent durable checkpoint must *always* exist. So harvest is no longer only the end-of-lap act: there is a **lightweight checkpoint stream** written at **stage transitions** (and optionally periodically) — each recording `{stage, autosave commit SHA, minimal resume-delta}`. The end-of-lap harvest is simply the richest checkpoint. Forced death then loses at most the work since the last checkpoint, never a whole lap.

## R1.6 — Autosave: local vs remote durability (revises §4)

Split the guarantee, because requiring the network on every checkpoint would make train/offline operation brittle:

- **Local durability** (against process / session / VS Code loss — the **frequent** cases): a **local git commit**. No network. Always available. A replacement worker on the same machine resumes purely from local git. **This is the primary nomadic guarantee.**
- **Remote durability** (against machine loss/theft — **rare**): a **push**. Network-dependent, done **opportunistically** when connectivity returns, **never blocking a checkpoint**.

So: **commit locally on every checkpoint (offline-safe); push when online.** `checkpoint_ref` is the local SHA; a separate `replicated` flag tracks remote state. Offline on a train you still have full protection against the common failures; only machine-loss protection waits for connectivity. §4's "commit + push" becomes "commit always, push opportunistically."

## R1.7 — Acceptance scenario

> 10 work items active · VS Code force-quit · Relay/VS Code restarted.

Relay must, with **no** `/resume`, no session-id hunting, no transcript inspection:

1. **Enumerate active work from durable state** — the board's ⚙ Open-threads rows + their branches + `checkpoint_ref`s → all 10 items. No VS Code, no session needed.
2. **Per item, locate the topic worktree** deterministically (`git worktree list` → `/<topic>`) and read its last checkpoint.
3. **Reconnect if a live session hint resolves** (best-effort) — **else start a replacement Continue worker seeded from the checkpoint** (worktree + branch + resume-delta).
4. Erik does nothing.

The reliable path is step 3-*replace*; reconnect is a bonus that never gates recovery.

## R1.8 — Revised first slice (revises §8)

Handover→Continue **stays**, but is **not sufficient alone**: it proves knowledge-continuity, not rediscovery. The acceptance scenario needs a **minimal Active Work Registry + a rediscover-and-replace operation**. So slice 1 is two pieces, minimal *together*:

1. **Harvest + resume on Handover→Continue** (as in §8): structured result → runtime persist → fresh Continue resumes from durable state.
2. **Minimal Active Work Registry + `rediscover`:** maintain the small per-item record (mostly a **view** over board + git, plus `checkpoint_ref` from piece 1 and a thin local session-hint/liveness file); a `rediscover` operation that lists active work from durable state and, per item, **starts a replacement Continue worker**. **Reconnect is deferred** — the reliable path is replace-from-state, for which piece 1 already produces the durable checkpoint.

These are minimal together because piece 2 reuses the **board as the active-work list**, the **topic-keyed worktree** as the deterministic locator, and the **harvest checkpoint** as the resume point — the only genuinely new artefacts are the thin local overlay and the `rediscover` read. This makes the slice satisfy the acceptance scenario (rediscover 10 items and replace their workers) rather than only proving the resume of a single known thread.

**Added to "NOT in the first slice":**
- **Reconnect** to a live provider session (optimisation; replace-from-state is the reliable path).
- **Automatic transcript mining** for tier-(c) recovery (best-effort, later).
- **Remote-push / replication guarantees** beyond opportunistic best-effort push.
- **Sub-stage / periodic checkpointing** finer than a checkpoint at stage transitions (start at transition boundaries; add granularity only if forced-loss evidence demands it).
- A generic liveness/heartbeat service — slice 1's liveness may be as crude as "is a process holding the worktree lock?"; a real heartbeat comes with the supervisor, later.

## R1.9 — Implementation notes (slice 1 as built)

Built in `scripts/relay_harvest.py` (+ `scripts/tests/test_relay_harvest.py`). What implementation confirmed or adjusted vs. the design above:

- **Durable layout (concretises the abstract `checkpoint_ref`):** per work item, `<root>/harvest/<slug>/` holds `results/<lap_id>.json` (the write-ahead log the worker emits, unique per lap → conflict-free), `checkpoint.json` (the single canonical resume state the runtime writes — an upsert, so idempotent by nature), and `applied.json` (the completion marker: the set of applied `lap_id`s). This is the one genuinely-new durable artefact; everything else stays a reference.
- **Worktree resolution is by branch, not by path-parsing** — `git worktree list --porcelain` → match the checkpoint's `references.branch`. More robust and fully session-independent; the deterministic `.claude/worktrees/<topic>` path is not relied upon.
- **The Active Work Registry is a *view*, not a file** — `discover_active()` computes it live from the board's active (⚙/🔍) rows + git worktrees + checkpoints. Confirms R1.3's "mostly a view over board + git." The only optional new local artefact is a session-hints file, and it is *never read on the recovery path* (proven by a test with no hints).
- **Disposition vocabulary** is validated at emit: `advanced|merged|parked|watching|reflect-back|stopped:<gate>` (R1.1 / §2). Work-item status and merge outcome remain references, not copied.
- **Provider-neutrality is enforced, not just intended:** `validate_result()` rejects any durable result carrying `session_id`/`provider`/`claude_session`. `lap_id` is an opaque string.
- **Deviation (scope):** the only shared-home *write* moved to the runtime in this slice is **discoveries → board** (deduped by a `<!-- disc:ID -->` marker). Board status/owner updates were deliberately **not** moved — rediscovery only needs the board to *list* active work, which it already does. Ship/Persist are untouched. So "the worker no longer performs the shared write" is demonstrated on one surface (discoveries), not yet all of Handover's writes.
- **Continue wiring** is a single additive step in `continue.md`: prefer the durable checkpoint via `relay_harvest.py resume <slug>`; the Markdown handover remains as projection/fallback. No procedure was restructured.

## R1.10 — Durably-resolvable bootstrap references (Project / Work-Item scope)

Relay has two required durable scopes — **Project → Work Item** (an Organisation context above Project is optional and externally owned; see `docs/context-scopes.md` for the full boundary). A durable worker reference must be resolvable within those scopes. Cross-provider validation forced two clarifications, both fixed at the **bootstrap layer** (no checkpoint-schema change):

- **Brief authoritative home = `<root>/briefs/<slug>.md`, committed to `main`** (durable; `explore` commits it). The `relay/briefs/` gitignore exists **only in the Relay plugin repo** (maintainer dogfooding scratch) and must not be copied into a managed project. A brief is **optional per item** — some items carry their plan in the board Detail. The bootstrap therefore *resolves* the brief (worktree → repo → `origin/main`) and, when absent, states a fallback (`resume_delta` + board Detail) rather than emitting a path that doesn't resolve.
- **Project instructions** are exposed provider-neutrally as `project_instructions`: the project-local instruction/guardrail files that actually resolve (today `CLAUDE.md`, plus the relay guardrails doc when present). This is a *pointer list to existing files*, not a new concept, not a provider-specific file, not a duplication — a fresh worker of any provider reads whatever it names.

**Bootstrap invariant (enforced):** every reference presented to a replacement worker either (A) resolves to durable readable state, or (B) is explicitly absent with a defined fallback — no silent dangling references. `validate_bootstrap` / `assert_no_dangling` guard it, over brief, project instructions, board reference, worktree, and branch. Organisation-context/EKR handling is explicitly not designed here.

## R1.11 — Empirical validation log

Not a procedure (that's `docs/harvest-xprovider-codex.md` and `docs/harvest-manual-test.md`) — the recorded evidence.

### E1 · Claude → durable state → fresh Codex (2026-08-30) — validated

- **Experiment:** `Claude → durable Relay state → fresh Codex`.
- **Constraints:** Codex received the provider-neutral bootstrap + read-only worktree access only — **no transcript, no provider session, no `/resume`, no manually supplied Claude context.**
- **Observed:** on real item `pricing/document-model`, Codex correctly reconstructed the objective (document-overage billing), the implementation state (found `documents-allowance.ts` / the meter / migration 0148 from the resume-delta symbol, read `CLAUDE.md` via `project_instructions`), the current repo state (clean at checkpoint `481887b3`), and the genuine open questions (the Free-vs-paid commercial decision; the absent billing engine) — rather than inventing them.
- **Observed gap:** for the brief-less item the bootstrap named "the board row Detail" as fallback but gave no path to the board, so Codex missed `relay/board.md`. **Classification B** (durable state existed; bootstrap omitted how to find it). Fixed by R1's `board_ref` (above).
- **Conclusion the evidence supports:** *a fresh worker from another provider can reconstruct and continue meaningful work from Relay's durable Project + Work Item state.* Worker continuity can be a property of Relay's durable state rather than of the AI provider's session.
- **What it does NOT prove:** that a foreign worker can *produce* Relay-compatible durable state for a different provider to consume (the reverse direction — see E2). Nor anything about Organisation-scope context.

### E2 · Claude → Codex → fresh Claude (2026-08-30) — validated

- **Experiment:** a real unit of work (`pricing/document-model`, in a disposable worktree off the real branch) crossed **Claude → durable state → Codex → durable harvest → fresh Claude**, each worker receiving only the provider-neutral bootstrap + worktree access. No transcript, session, `/resume`, or manually copied reasoning at any hop.
- **Codex produced (semantic, class A):** a genuinely meaningful, project-aware continuation — a decision record recommending "Free hard-capped, paid capped tiers meter into overage at €0.15/doc, uncapped unchanged," and it independently surfaced the project's real convention that enforcement must read *the resolved projection, not a tier id*. So the semantic contract works in the reverse direction: a foreign worker can produce continuation worth harvesting.
- **Mechanical gap — class D, not B.** Codex could not `git commit` or run `relay_harvest.py emit` itself: its `workspace-write` sandbox excludes the worktree's `.git/worktrees/…` metadata, so git failed (it correctly refused to fabricate a SHA). This is an environment/tooling limit, **not** a missing adapter — the existing provider-neutral CLI *is* the interface; the runtime completed the commit+emit. No adapter was built.
- **Fresh Claude reconstructed (from durable state alone):** the original objective (pricing by the document, the full PR arc from the board), what existed before Codex (the shipped hard cap), what Codex changed (the docs-only decision at the checkpoint commit), the current worktree state, the remaining work + both open questions, and the correct next action — which it correctly judged to be *a human policy confirmation before any code*, naming the exact files (`documents-allowance.ts` lines 86-120, via a resolved projection field) it would edit next.
- **Conclusion the evidence supports:** *a real unit of work crossed Claude → Codex → fresh Claude without transcript or provider-session continuity, each replacement worker correctly orienting and continuing meaningful work.* This is evidence for the stronger claim: **workers are replaceable executors; work continuity belongs to Relay's durable state.** The `board_ref` fix (R1) held — no repeat of E1's class-B gap.
- **What it does NOT prove:** that a foreign worker can emit the result itself under a locked-down sandbox (the D limit above — an environment fix, not a contract one); anything about a real multi-provider *runtime/supervisor* (orchestration was still a manual harness); code-level continuation across providers (Codex's bounded step was a decision doc, deliberately not core code); git-durability of the checkpoint (it lived on-disk in the worktree, resolvable but uncommitted — a hardening, not proven); and nothing about Organisation scope.
