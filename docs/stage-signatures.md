# Relay stage signatures (empirical)

_An empirical model of the **current** Relay lifecycle, built to inform the next step: designing versioned stage contracts. It describes what stages **do today** — it invents no future architecture, defines no schema, and changes no behaviour._

> **Re-derived 2026-09-17** against the refreshed corpus (859 spans / 307 sessions, 17 Aug → 17 Sep 2026 — up from 741 / 282 at the 29 Aug cut). The dominant paths and the contract analysis held; what changed most is that standalone **Review / Persist / Handover / Fix** spans have all but vanished (they now run inside Ship almost every lap), so their `[obs]` evidence has collapsed and their confidence is downgraded accordingly. The compound-span caveat below is now the single most load-bearing fact in the model.

## Method & how to read this

Two evidence sources, kept separate:

- **`[obs]` observed** — from the command-level telemetry corpus (`~/.relay/commands.jsonl`, 859 spans / 307 sessions, 17 Aug – 17 Sep 2026; ~88% CastlesERP, with `declarant-assist-poc` now a secondary source and a handful from `relay` itself). Says what stages *actually did*.
- **`[impl]` implementation** — from the command specs in `plugins/relay/commands/*.md`. Says what stages are *designed to* consume, read, and hand on — including things telemetry can't see (a stage *reading* a file leaves no trace; only *writes* do).
- **`[inf]` inference** — a reading of the two above, flagged so it isn't mistaken for evidence.

**Confidence** = High (both sources agree, many spans) · Med (implementation clear, telemetry sparse or one-sided) · Low (sparse or single-source).

Alias note: short and long names are merged to one stage (`/rlt`+`/test` → Test, etc.).

### The caveat that frames everything: compound spans

The segmentation boundary is the **invoked command**, not the **logical stage**. `/ship` runs Test → Review → Fix → Merge → Persist → Handover *inline* — it spawns the review specialists and edits the review report directly, rather than typing `/relay:review`. So those sub-stages create **no span of their own**; their telemetry is absorbed into the Ship span. This is why standalone Review (**0** spans now), Persist (**2**), Handover (**1**) and Fix (**1**) are essentially unobserved while Ship — 232 spans — shows their surfaces (board 53, briefs 53, reviews 52, handover 50, knowledge 49 writes). The gap has widened sharply since the August cut: standalone Handover was 35 spans then and is 1 now, Persist 22 → 2. **Consequence for contracts:** the observable, artefact-bearing seams are *between* commands run in sequence (Explore→Refine→Next→Test→Ship); the seams *inside* Ship are real logical boundaries but are not observable as transitions and have no artefact handed across a session.

## The five result classes (A–E)

Every stage output falls into one of these; keeping them apart is what a future contract must do:

- **A · Worker-local artefacts** — code in the isolated worktree. `[obs]` `code_write_count` / `files`. Ephemeral to the lap; the PR is how they leave the worktree.
- **B · Lifecycle results** — the thing the *next* stage consumes: a brief, a PR + test-plan, a review report, a handover. Some are worker-local (PR), some shared (brief, review, handover).
- **C · Persistent / global-state mutations** — writes under the relay root to *shared* surfaces: `board.md`, `knowledge/`, `decisions.md`, `briefs/`, guardrails, design-system. `[obs]` `artefacts`. The concurrency-sensitive class.
- **D · Discoveries & follow-up work** — new board items, noted gaps, reflect-signals sending work back a stage. Mostly routed to the board or surfaced to the human, rarely a file of their own.
- **E · Human decisions** — approvals at STOP gates, autonomy choices, last-blocker escalations. Logged to `decisions.md`/`autonomy.log` when durable; otherwise ephemeral in the transcript. Largely **unavailable** to telemetry.

## Stage signatures

Each table uses the requested columns. "Writes" = all files (class A+B+C); "Global mutations" isolates class C. Evidence cites span counts and the dominant transition.

### Explore — shape a rough idea into a brief

| | |
|---|---|
| **Consumes** | `[impl]` a rough idea string (args); no prior artefact — front of the loop. Deliberately context-free. |
| **Reads** | `[impl]` `relay.config.json` only; **never** code/CLAUDE.md/conventions. Optional `reference/<topic>.md`. |
| **Produces** | `[obs]` a brief (11/12 spans wrote `briefs/`); `[impl]` + one board row. Class **B/C**. |
| **Writes** | `[obs]` `briefs/` + `board.md`; ~2 non-relay files (reference notes). |
| **Global mutations** | `[obs]` 92% of spans write shared state — `briefs/` (11), `board` (8). `[impl]` board is main-owned (fetch → surgical row → temp-index push). |
| **Typical next** | `[obs]` **Refine** (10/12 = 83%), else session ends (2/12). |
| **Alt transitions** | `[impl]` idea not worth building → write nothing, stop (class D: a kill is a valid result); decompose → several briefs; → `/next` directly if small. |
| **Evidence / confidence** | Med — n still small (12) and shrank, but telemetry and spec agree tightly; the Refine share rose (50%→83%). |
| **Unknowns** | Whether a brief was *accepted* or discarded (both leave/leave-no file, but "killed idea" is invisible). |

Decisions/discoveries `[impl]`: chosen approach + alternatives-beaten → brief `## Approach`; open questions → `## Open questions`.

### Refine — ground a brief against this project

| | |
|---|---|
| **Consumes** | `[impl]` `track/slug` + optional session-size; **precondition: an existing brief** (else → Explore). |
| **Reads** | `[impl]` board+brief (from main), **project code**, `CLAUDE.md`, `knowledge/`, resolved guardrails + design-system, **AI memory**. The first stage that reads the codebase. |
| **Produces** | `[obs]` extends the brief in place (24/39 wrote `briefs/`); adds `## Project grounding / Guardrail requirements / Threat model / Slices`. Class **B**. |
| **Writes** | `[obs]` `briefs/` (24), `board` (16), ~4 files; `[obs]` spawns agents in **56%** of spans (challenger / cross-check). |
| **Global mutations** | `[obs]` 67% write shared state (`briefs/`+`board`). `[impl]` **reads** the knowledge layer but only **notes** a guardrail gap — never writes it (that's `/guardrails`). |
| **Typical next** | `[obs]` **Next** (18/39 = 46%), else session ends (10/39) or straight to Test (7/39). |
| **Alt transitions** | `[impl]` no brief → Explore; re-refine → update in place; no guardrails → defaults + offer `/guardrails`; no threat surface → write "none" + skip. |
| **Evidence / confidence** | High — spec explicit, telemetry consistent (agent-spawn + brief-write signature is distinctive). |
| **Unknowns** | Which guardrail/memory items were *read* (class-C inputs) — reads are invisible. |

Decisions/discoveries `[impl]`: threat mitigations → per-slice requirements; guardrail bars → per-slice acceptance criteria; gaps noted, not written.

### Next — recommend and start the next board item

| | |
|---|---|
| **Consumes** | `[impl]` optional track/slug bias + level (`verify`/`audit`) + autonomy + session word; **precondition: a board with startable items** (excludes in-flight ⚙/🔍). |
| **Reads** | `[impl]` board (from main), shortlist briefs via **Detail** column, `git log`/`grep`; at L2/L3 fans out agents over `reviews/`, `handover/`, code, `gh` PR/issue history. |
| **Produces** | `[obs]` worker-local **code** (mean 6 files, median 4); `[impl]` L3 → a dated `audits/<ts>.md`. Class **A** (+B: the started branch). |
| **Writes** | `[obs]` code in a topic worktree; global only 8%. |
| **Global mutations** | `[obs]` low (8%). `[impl]` board drift-fixes + L3 compaction are **offer-don't-auto-write**; autonomy → `decisions.md`. |
| **Typical next** | `[obs]` **Test** (52/80 = 65%) — "point at verify, not ship". |
| **Alt transitions** | `[impl]` dep on sibling's unlanded work + hold → `/watch`; missing board → `/init`; dirty worktree → STOP. |
| **Evidence / confidence** | High (80 spans). |
| **Unknowns** | Which board item was picked vs offered (the shortlist→pick decision, class E, is ephemeral). |

### Continue — resume an in-flight thread from a handover

| | |
|---|---|
| **Consumes** | `[impl]` optional slug/handover-path + autonomy; **precondition: an existing handover** (or brief-only thread) + board row. Resumes, doesn't select. |
| **Reads** | `[impl]` **the thread's latest handover** (from main), board, brief-if-no-handover, project `CLAUDE.md`/README, sibling worktrees for deps. The handover is its primary input. |
| **Produces** | `[obs]` worker-local **code** (mean 7 files, median 5). Class **A**. |
| **Writes** | `[obs]` code on the topic branch; global 18% (mostly folded in later by Handover, not by Continue itself `[impl]`). |
| **Global mutations** | `[impl]` does **not** edit board — defers to `/handover` at session end. Autonomy → `decisions.md`. |
| **Typical next** | `[obs]` **Test** (135/218 = 61%). |
| **Alt transitions** | `[impl]` shipped-shape handover (branch merged) → re-baseline off main, cut next slice (the `/next` path); dep + hold → `/watch`. |
| **Evidence / confidence** | High (218 spans — now the second-largest stage; the 61% Test share is unchanged from the August cut). |
| **Unknowns** | Which handover fields were actually *used* vs ignored — the core question for a Coding-input contract. |

### Test — verify between build and ship

| | |
|---|---|
| **Consumes** | `[impl]` focus/area **or** PR number + mode (`plan-only`/`drive`) + env (`preview`/`local`); config `test.target`, `hooks`. Precondition: a built slice; not on default branch. |
| **Reads** | `[impl]` **the diff** (`git diff origin/main...HEAD` or `gh pr diff`), project `CLAUDE.md` for invariants, config. |
| **Produces** | `[impl]` commits the slice, opens/reuses a **draft PR**, writes the `## 🧪 Test drive` plan into the PR body; optional GIF + PR comment. Class **B** (the PR+plan), **A** (commit). |
| **Writes** | `[obs]` browser-driven (`mcp__claude-in-chrome__computer` 3584 uses corpus-wide — distinctive; 52% of Test spans drive a browser), code fixes, PR body; **no relay-root writes**. |
| **Global mutations** | `[obs]` ~none (6% noise). `[impl]` only offer-once `hooks.env` config wiring; may bring a **local env up** (recorded so Ship tears down only what this session started). |
| **Typical next** | `[obs]` **Ship** (190/235 = 80%). |
| **Alt transitions** | `[obs]/[impl]` drive turned red → **Fix**; reflect-signal (broken assumption) → back to **Refine/Explore**; `plan-only` → print, no PR. |
| **Evidence / confidence** | High (235 spans — the largest stage). |
| **Unknowns** | Pass/fail outcome — `errors>0` appears in 160/235 spans (routine failed tool calls), so it is **not** a success signal. |

### Review — multi-specialist PR review (usually inside Ship)

| | |
|---|---|
| **Consumes** | `[impl]` optional PR number (else current branch) + session + `audit` flag; config `review.agents/verify`. |
| **Reads** | `[impl]` diffstat + diff content for gate signals, repo layout from `CLAUDE.md`; specialists read the PR/code themselves. |
| **Produces** | `[impl]` **one merged report** `reviews/pr-<n>-<date>.md` with graded findings (🔴/🟡/🟢) + verdict. Class **B**. |
| **Writes** | `[obs]` `reviews/`; spawns specialists (security + test-engineer always-on; others content-gated — a `packaging-reviewer` now appears in the gated set, 50 spawns across Ship spans). |
| **Global mutations** | writes only under `reviews/` (per-PR artefact). Escalation answer → `autonomy.log`. |
| **Typical next** | **Fix** (findings feed `/fix`) `[impl]`; **0 standalone spans** now — impossible to observe directly. |
| **Alt transitions** | `[impl]` docs-only diff → short-circuit, no report; last-🔴 refuted → **STOP, escalate to human** regardless of autonomy. |
| **Evidence / confidence** | Low (was Med) — spec explicit, but standalone spans have dropped from 2 to **0**; Review is now seen only as a surface of Ship (which spawns review specialists in 93% of spans, mean 5.8 subagents each). |
| **Unknowns** | Standalone behaviour now entirely unobserved; refute-drop rates. |

Discoveries/decisions `[impl]`: refute-before-report (both refuters kill a finding → *Refuted findings*); last-blocker drop is a **merge-gate human decision** (class E).

### Ship — end-of-session orchestrator (the compound stage)

| | |
|---|---|
| **Consumes** | `[impl]` optional `no-verify`/`audit`; config `persist.cadence`, `tidy.level`, many `hooks`. Precondition: a built slice on a feature branch. |
| **Reads** | `[impl]` PR state + body/comments (for test-drive evidence), the review report, `gh pr checks`, merged diff. |
| **Produces** | `[obs]` code (fix, mean 9 files) + **merges to main**; via delegation the review report, handover, and persist outputs. Class **A+B+C**, all of them. |
| **Writes** | `[obs]` the widest of any stage — `board` (53), `briefs` (53), `reviews` (52), `handover` (50), `knowledge` (49), `decisions` (8). **93% spawn subagents** (mean 5.8 each). |
| **Global mutations** | `[obs]` 31% + **the only stage that merges to main**. Note: much of its `knowledge/handover/reviews` writes are the *delegated* Persist/Handover/Review running inside the span (compound-span caveat) — and since those stages barely run standalone any more, Ship is now effectively where all end-of-lap global state is written. |
| **Typical next** | `[obs]` **session end** (196/232 = 84% — Ship is terminal, up from 69%); Persist/Handover almost never follow separately now (2 and 1 standalone spans total). |
| **Alt transitions** | `[impl]` docs-only → skip verify+review; last-blocker / needs-judgment → STOP; **merges only on clean-green path**, else STOP; stale merge-base (via `hooks.affects`) → re-verify. |
| **Evidence / confidence** | High for *what it touches* (232 spans); Low for *internal phase boundaries* (not separately observable — and now the only place those phases appear at all). |
| **Unknowns** | The internal Test→Review→Fix→Merge→Persist→Handover seams — invisible as transitions. |

### Fix — re-verify review findings, fix, tick off (usually inside Ship)

| | |
|---|---|
| **Consumes** | `[impl]` optional report filename (else most recent `reviews/`); **precondition: a review report with unchecked findings**. |
| **Reads** | `[impl]` the report + frontmatter (`pr`, `blockers`, `verified`), `gh pr diff` + cited files, nearest `CLAUDE.md`. |
| **Produces** | `[obs]` **code** edits + ticks the report boxes, appends `## Fix pass <date>`. Class **A+B**. |
| **Writes** | `[obs]` code + `reviews/` report; **no push, no merge** standalone. |
| **Global mutations** | `[obs]` the 1 standalone span wrote `reviews/`. No board/memory writes. |
| **Typical next** | `[obs]` **Ship** (1/1) — re-verify. |
| **Alt transitions** | `[impl]` blocker-class fix-delta → re-review loop (max 2 rounds, then STOP); wrong finding → reject, don't change code; can't resolve → revert + flag (never false-green). |
| **Evidence / confidence** | Low (was Med) — standalone spans dropped 7 → **1**; Fix now runs inside Ship almost every time. |
| **Unknowns** | Per-finding confirmed/stale/wrong/needs-judgment split (class D/E, in-report only). |

### Persist — harvest a lap's knowledge (the knowledge writer)

| | |
|---|---|
| **Consumes** | `[impl]` PR/slug (else most recent merge); config `persist.level/cadence/kinds`, `paths.adr/design-system`. Precondition: a merged lap. |
| **Reads** | `[impl]` the lap's diff, **the review report incl. refuted findings**, **the brief** (threat model, alternatives, decisions), handovers, **AI memory index** for dedupe/supersede. |
| **Produces** | `[obs]/[impl]` guardrail `extends` overlay, design-system doc, **AI memory**, release notes; at `full` → ADRs. Class **C** (durable knowledge). |
| **Writes** | `[impl]` `knowledge/`, `briefs/` (the `Distilled:` stamp); most durable writes land **outside** the relay root via `paths.*`. (Standalone `[obs]` now too thin to quantify — see confidence.) |
| **Global mutations** | `[impl]` **the knowledge-layer writer** and the **only stage that removes an AI memory** (retires what this lap superseded — "one fact, one home"). Auto-writes additions; whispers once before a lossy trim. |
| **Typical next** | `[obs]` only 2 standalone spans (→ Next, → Ship); the real Persist runs inside Ship, which writes `knowledge/` in 49 spans. |
| **Alt transitions** | `[impl]` `level:none` → stop; nothing durable + nothing user-visible → "nothing to persist"; ADR-worthy below `full` → **deferred + listed**, not written. |
| **Evidence / confidence** | Low for standalone (was Med-High) — spans dropped 22 → **2**; the stage is now almost exclusively a Ship phase. `[impl]` unchanged. |
| **Unknowns** | Which memories were retired vs added (removal not captured); ADR deferrals. |

### Handover — write the cold-start handover (the cross-session carrier)

| | |
|---|---|
| **Consumes** | `[impl]` optional focus (else infers next item from board); config `tidy.level`. Standalone or as Ship Phase 6. |
| **Reads** | `[impl]` **board (Open threads = source of truth)**, `roadmap.md`, the item's linked handover, git log/status/diff, **this session's own memory**. |
| **Produces** | `[obs]/[impl]` `handover/next-<ts>.md` (9 structured sections, see below) + updates the board row. Class **B+C**. |
| **Writes** | `[impl]` `handover/` + `board`, ~1 file; commits **both to main**. Observed as a Ship surface: `handover` written in 50 Ship spans. |
| **Global mutations** | `[impl]` board main-owned; Step 4.5 tidy archives superseded handovers/reviews + trims done rows (gated by `tidy.level`). |
| **Typical next** | `[obs]` the 1 standalone span ended the session `[impl]`; prints a ready-to-paste `/rlc <path>` line → next session's **Continue**. |
| **Alt transitions** | `[impl]` PR still open/closed unexpectedly → warn + STOP; stray unrelated worktree work → STOP, don't auto-delete. |
| **Evidence / confidence** | Low for standalone (was High) — spans dropped 35 → **1**; Handover now runs inside Ship. This is the awkward one: the model's strongest contract candidate is now its least-observed stage. `[impl]` is unchanged and the between-command Handover→Continue seam is still real (via `/rlc`, 213 Continue spans downstream). |
| **Unknowns** | Whether the next Continue actually used each field. |

### Deploy — gate the project's PR preview (rarely run)

| | |
|---|---|
| **Consumes** | `[impl]` optional PR number; config `hooks.deploy`. Precondition: an open PR (no PR → STOP). |
| **Reads** | `[impl]` `hooks.deploy`, `gh pr checks`, CI workflow config, the deploy check's URL, project security checks. |
| **Produces** | `[impl]` **nothing durable** — deliberately thin; never deploys, only drives the project's own pipeline + gates it. |
| **Writes** | optional offer-once `hooks.deploy` config wiring; no relay-root writes. |
| **Global mutations** | none. |
| **Typical next** | `[impl]` **Test** (`/test <pr> drive` against the verified URL). |
| **Alt transitions** | `[impl]` no mechanism + declined → fall back to Test local; any gate fail → report which gate, go back not forward. |
| **Evidence / confidence** | Low (near-absent from telemetry — deploy is rarely used in these repos). |
| **Unknowns** | Almost everything, empirically — too few runs. |

## Observed transition analysis

The dominant path, from the transition matrix (share of each stage's outgoing edges):

```
Explore ─83%→ Refine ─46%→ Next ─65%→ Test ─80%→ Ship ─(84% end)
                              Continue ─61%→ Test
```

Persist and Handover no longer appear as their own outgoing edges — at 2 and 1 standalone spans they run *inside* Ship, so the lap now terminates at Ship (84% → session end) and resumes next session via Continue. The old Ship→Persist→Handover tail is now entirely internal to the Ship span.

Conditions on the alternatives `[impl]`, where the data shows a fork:

- **Test → Fix** (not Ship): a drive turned the happy path red.
- **Test → Refine/Explore**: a drive exposed a broken assumption or scope error (an explicit "reflect signal" backward edge).
- **Continue → Next-path** (re-baseline): the handover was shipped-shape (branch merged/gone).
- **→ Watch**: a dependency on a sibling's unlanded work + user says hold.
- **Ship → STOP** (no forward edge): tests red, last-blocker, needs-judgment, or not-clean-green.
- **∅ end** dominates Ship (84%): Ship is now the near-universal lap terminal — the session stops, and the thread resumes later via Continue. (Handover no longer shows as its own terminal; it fires inside Ship.)

Backward/loop edges exist but are rare (Test→Ship 190 dominant; Test→Test 11, Ship→Test 12, Ship→Ship 7, Fix→Ship 1), consistent with re-verify loops rather than churn.

## The handover contract, from its actual consumer (a fresh AI session)

**The consumer is not a human.** The handover is read almost exclusively by the next AI session, via Continue, starting from a clean context. So the design question is not "is this readable?" but:

> **What is the minimum durable information a completely fresh AI session needs to continue the work correctly** — given everything else it can reconstruct for itself?

### The enabling fact: the consumer is not context-starved about artefacts

Handover keeps the topic worktree alive (`ExitWorktree keep`, never `remove`; uncommitted work is deliberately left in place) and Continue always resumes in **that same worktree**, with the board and handovers committed to main so a fresh checkout still finds them `[impl]`. So before it reads a single word of prose, the resuming session already has: the **repository**, the **branch**, the **uncommitted diff** (`git status`/`git diff` in the live worktree), the **brief**, the **board row**, **git history**, and the **PR** (diff, checks, comments). The handover's job is therefore not to *carry* any of that — it is to **point** at it, **select** within it (which slice is next), and **interpret** the parts that aren't self-evident. This is consistent with what the stage is designed to do `[impl]` (the standalone `[obs]` signal has thinned to a single span this window, ~25k output, ~2 files, as Handover moved inside Ship) — it is already a light pointer stage, not a payload.

### Field-by-field: what's durable state vs what's reconstructable

| Handover field | Holds | A fresh session reconstructs it from | Verdict |
|---|---|---|---|
| `item` (track/slug) | the thread's identity | — (it *is* the key) | **Structured state** — the anchor every reference resolves through |
| `branch` | which branch to continue | board row, weakly | **Structured state** — cheap to carry, costly to guess |
| `phase` | milestone, for prioritisation | `roadmap.md` + the board track | **Reference** — derive, don't store |
| `Where we are` | project/milestone/goal orientation | roadmap + board + brief | **Redundant** — pure orientation; ~nothing irreducible |
| `What just landed` | commits + non-obvious decisions | `git log`/PR diff (the *what*); `decisions.md`/memory (the *why*, if persisted) | **Reference** (commit range / PR#) + thin residue: rationale not yet persisted |
| `In flight` | uncommitted work by path + status | the **live worktree** (`git status`/`git diff`) | **Reconstructable** from the persisted worktree + residue: *intent* (done vs remaining) |
| `Next objective` | the next slice/line | brief `## Slices` + roadmap | **Reference + pointer** — which slice is next |
| `Context you need` | files/roles/decisions/conventions/gotchas | repo (grep), `decisions.md`, `CLAUDE.md`, `knowledge/` | **Mostly reconstructable**; residue: unpersisted gotchas |
| `Start here` | first 2–4 concrete actions | derivable from objective + brief + code state | **Derivable** — an accelerant, not durable state |
| `Done when` | done-criteria + scope edges | brief slice acceptance criteria (from Refine) | **Reference** + residue: scope edges absent from the brief |
| `Open questions` | unresolved decisions | — (or the board / `decisions.md`) | **Irreducible** — but belongs routed to the board, not re-typed |

### Yes — it decomposes into state + references + thin human-context

The three-way split the clarification asks about is real. The minimum durable core is:

- **Structured state (the irreducible spine)** — `item`/slug, `branch`, a base ref (merge-base commit or PR#), a **next-slice pointer**, **in-flight paths + per-path status**, **scope edges**, and **open-question ids**. Small; mostly identifiers and pointers.
- **References (replace the enumerated prose)** — brief (slug → objective, approach, slices, threat model, done-criteria), roadmap line (phase), PR (diff/checks/comments), board row, review report, commit range, worktree path. Dereferenced on demand, never copied.
- **Human-context (only where genuinely irreducible)** — the *why* behind non-obvious in-flight choices, gotchas not yet in durable knowledge, and the interpretation of half-done work. Thin — and shrinking (see below).

**Redundancy verdict:** of the 9 body fields, ~3 are reconstructable orientation/plan (`Where we are`, `Start here`, most of `Context you need`), 3 are references-with-a-pointer (`What just landed`, `Next objective`, `Done when`), 1 is reconstructable-from-worktree with a thin intent residue (`In flight`), and 2 carry genuinely durable small facts (`item`/`branch`; `Open questions`). **The handover's true durable payload is a fraction of its current prose.**

### The redundancy is also a Persist/Handover boundary problem

Much of the "irreducible" residue — persisted-worthy rationale, gotchas, lessons — is in the handover *only because Persist didn't capture it*. "One fact, one home" says durable knowledge belongs in `knowledge/`, `decisions.md`, and AI memory (Persist's surfaces), and the handover should **reference** those, not duplicate them. So minimising handover duplication and strengthening Persist are the same move: **the handover carries thread-resume *state*; it must not carry project *knowledge*.**

### Durability caveat (a design input, not a change)

Uncommitted in-flight work is reconstructable only while the worktree survives — normally it does, but a pruned or foreign-machine worktree loses it, and there the handover prose is the only backstop. Two later options (do **not** implement now): capture in-flight as structured `paths + status` in the handover (durable), or have Handover emit a `wip:` commit so **git** becomes the carrier and `In flight` collapses to pure interpretation.

### Conclusion for the contract step

Markdown should be a **projection**, not the canonical form. The canonical handover is a small **structured-state + references** object with a **thin human-context slot**; the 9-section document is rendered from it (for the rare human read, and as the AI's convenient readable form). This is the strongest contract candidate precisely *because* its durable core turns out to be small and mostly already-referenceable — the contract mostly formalises pointers, not payload.

## Clearest contract candidates vs ambiguous boundaries

**Clearest (real span seam + a well-defined durable artefact + observed high-frequency transition):**

1. **Handover → Continue** — the single strongest candidate. Carrier is **not** the 9-field prose doc but a small **structured-state + references** core (item/branch/base-ref, next-slice pointer, in-flight paths+status, scope edges) that mostly *points* into artefacts the resuming session already has (brief, board, PR, git, the live worktree). Markdown becomes a projection of it. See the consumer-centric analysis above — its durable payload is a fraction of the current document, and part of the residue actually belongs to Persist.
2. **Explore → Refine** — carrier: the brief (`## Approach`, `## Open questions`). Explore writes it, Refine reads+extends it. 83% transition.
3. **Refine → Next** — carrier: the refined brief (`## Slices`, `## Threat model`, `## Guardrail requirements`). Next reads it. 46% transition (the rest split to session-end or straight to Test).
4. **Next/Continue → Test** — carrier: the PR diff + commits. Test reads the diff. 65%/61%, high volume (Continue alone is 218 spans).
5. **Test → Ship** — carrier: the PR + `## 🧪 Test drive` plan + drive evidence in the PR body. Ship reads the body for evidence. 80%, highest-volume edge (190 spans).

**Ambiguous / not yet contract-ready:**

- **Everything inside Ship** (Test→Review→Fix→Merge→Persist→Handover) — real logical boundaries, but executed inline as one compound span with no artefact handed across a session, so unobservable as transitions. Contract-ising these means contract-ising Ship's *internal phases*, a different exercise than the between-command seams.
- **Review → Fix** — the artefact (the graded review report with checkboxes) is clean and well-defined, but the transition is now **unobserved as a transition**: both run inside Ship, and standalone spans have fallen to 0 (Review) and 1 (Fix). Good artefact, essentially no direct evidence.
- **Ship → Persist → Handover** — the artefacts are well-defined (merged diff, review report, brief → durable knowledge; then handover), but they usually run inside Ship, so the seam rarely appears as a transition.
- **Deploy** anywhere — too few runs to model empirically.

**Cross-cutting gaps a contract layer will have to solve regardless:** stage *outcome/success* is unavailable (no reliable signal; `errors` is not it); class-C *reads* are invisible (we see what a stage writes, never what it consumed); and class-E *human decisions* are only captured when they happen to be logged to `decisions.md`/`autonomy.log`.

## What must survive a worker's death — and where each kind lives

A worker's death is the **normal, designed event**: sessions are meant to be ephemeral, and context reset is the point, not a failure. The discipline that makes that safe is simple to state and is what every stage above is really doing: **before a worker dies, each kind of information it produced must already have been externalised to its correct durable home.** The one failure mode is information whose *only* home is the dying worker — an uncommitted worktree, an unlogged decision, a discovery mentioned once in a transcript.

So the question decomposes into (a) which categories must outlive the worker, and (b) the single home each belongs in. The homes that outlive any worker are: **git** (code + history), **the brief** (a unit's intent), **the board** (backlog/status/ownership/discoveries), **the roadmap** (phase/strategic intent), **persistent knowledge** (`knowledge/`, `decisions.md`, AI memory, changelog), **the handover** (thread-resume state), and **telemetry** (`~/.relay/*.jsonl`, outside every repo). Two things are explicitly *not* durable homes: the **worktree** (transient scratch) and the **transcript** (the worker's mind).

| Information category | Class | Survive? | Correct home | Lives there today? |
|---|---|---|---|---|
| Committed code + its history | A | Yes | **git** (branch / PR / commits) | ✅ durable |
| Uncommitted work-in-progress | A | Yes — it's real work | **git** (should be a `wip:` commit) | ⚠️ only in the worktree + handover prose — dies if the worktree is pruned |
| Thread-resume state (next slice, in-flight intent, scope edges, open Qs) | B | Yes | **the handover** (small structured core + references) | ⚠️ present but bloated — should shrink to the core |
| Unit intent/plan (objective, approach, slices, threat model, done-criteria) | B | Yes | **the brief** | ✅ — handover should *reference*, not copy it |
| Project knowledge (lessons, guardrail overlays, ADRs, rationale) | C | Yes | **knowledge/ · decisions.md · AI memory · changelog** (Persist writes these) | ⚠️ stranded in handover/transcript when Persist doesn't run |
| Discoveries & follow-up work found mid-flight | D | Yes — else re-discovered | **the board** (new rows) | ⚠️ often stranded in handover prose or the transcript |
| Cross-thread coordination (status, ownership, phase) | C | Yes | **board.md · roadmap.md** | ✅ durable — but the concurrency-contended surface |
| Binding human decisions | E | Yes | **decisions.md · autonomy.log** | ⚠️ captured only when explicitly logged; most die in the transcript |
| Observability (cost/model/files/transitions) | — | Optional (analysis, not correctness) | **telemetry `~/.relay/*.jsonl`** | ✅ (this instrumentation work) |
| The worker's reasoning / transcript | — | **No** — distil, then let it die | transcript persists on disk but is **not** authority | ✅ correct *if* value was extracted first |

`[obs]/[impl]` grounding: the ✅ rows are directly evidenced (git, board/roadmap on main, brief in `briefs/`, telemetry files, Persist's surfaces). The ⚠️ rows are `[inf]` from where the analysis above shows information actually sitting — chiefly the handover-decomposition and the compound-span finding. Confidence: High on the homes, Med on the size of each gap.

**Three principles fall out:**

1. **One fact, one home — across homes, not just within one.** Each category has exactly one correct owner; anything appearing in a second place is duplication that will drift. The bloated handover and the "part of the residue belongs to Persist" finding are both this principle being violated.
2. **A simple routing rule for any piece of information at death:** does it bind work beyond this thread (other threads, the whole project, a future lap)? → a *shared* durable home (board / knowledge / decisions / roadmap). Is it only this thread's resume state? → the *handover*. Is it code? → *git*. Is it the worker's own reasoning? → *let it die*, once its value has been routed to one of the above.
3. **The transcript is the thing that must die.** Treating "reload the previous context" as the continuation mechanism defeats the point of ephemeral workers. The system's job is to have *extracted* each category into its home *before* death — which is exactly what Persist (knowledge), Handover (resume state), the board (discoveries/coordination), and git (code) each do. The gaps above are the places where extraction is currently incomplete, so something valuable rides on the transcript surviving — which it shouldn't have to.

**Where this meets the concurrency problem.** The categories that must survive into *shared* homes — board, knowledge, decisions, roadmap — are exactly the surfaces that collide when ~10 workers write them at end-of-lap (see §"Global-state writes per stage"). So "what must survive, and where" and "why do parallel workers conflict" have the same answer: **worker death is the harvest moment, and the harvest targets a handful of shared homes.** That is precisely the seam a "workers produce results, the runtime owns global state" design would mediate — the runtime becomes the single writer of those shared homes at the moment each worker dies, while git, the brief, and the per-thread handover stay worker-owned. (Stated as the implication of the empirical model — not a change to build here.)

The smallest result a worker must emit for that death to be lossless is derived separately in **`docs/harvest-result.md`**.
