---
description: Harvest what a lap produced back into the project's living knowledge — guardrails and the design system (as the extends overlay only), AI memory, and human-readable release notes. Sprawl-guarded on the lessons; every user-facing change earns a release note. Phase (j) — the step that makes the spiral compound.
argument-hint: "[pr-number or slug — the lap to harvest from; omit for the most recent merge]"
---

Close the lap by feeding what it produced back into the project's living knowledge, so the next lap
starts smarter — and so a human can see what shipped. This is phase (j), the compounding step. It
**never writes code**, and it produces **two kinds of output**, each with its own discipline:

- **Lessons — the *inward*, compounding knowledge.** Guardrails overlay, design system, AI memory.
  Harvested **selectively**, filtered by the "was it non-obvious, and will it recur?" test — a
  lesson worth keeping, never a transcript. `/refine` and the review specialists read these next lap,
  so a lesson persisted once is enforced for free forever after.
- **Release notes — the *outward* deliverable.** A human-readable summary of what this lap shipped,
  in user-benefit language. **This is NOT filtered by the non-obvious test** — every change a user
  would *notice* earns a note, even one that taught nothing. Gated instead on "would a user notice?"

> **What it writes, and what it never writes.** Target surfaces are **guardrails**, the **design
> system**, **AI memory**, and **release notes**. For guardrails it only ever writes the **`extends`
> overlay** (the project's house rules) — **never a shipped baseline**. Architecture diagrams / ADRs
> / ops / manual are **later persist slices**: capture them as deferred, don't write them yet.
> Establishing guardrails from scratch is `/guardrails`' job; `/persist` only grows the overlay.

## Step 0 — Resolve the root and the knowledge targets
```bash
ROOT="$(jq -r '.root // "relay"' relay.config.json 2>/dev/null || echo relay)"
GUARDRAILS="$(jq -r '.guardrails // empty | keys | join(",")' relay.config.json 2>/dev/null)"
RELEASE_NOTES="$(jq -r '.paths["release-notes"] // empty' relay.config.json 2>/dev/null)"
: "${RELEASE_NOTES:=$ROOT/knowledge/release-notes.md}"
```
`GUARDRAILS` is the active dimensions whose overlays `/persist` may grow. **Empty ⇒ no guardrails
configured**: `/persist` can still write AI memory and release notes and can *offer* to seed a first
overlay, but it points at `/guardrails` for establishing a dimension — it won't invent one.
`RELEASE_NOTES` is where the human-readable notes live — default `<root>/knowledge/release-notes.md`,
relocatable via a `paths["release-notes"]` override (e.g. a product docs site outside `relay/`).

## Step 1 — Identify the lap and gather the evidence
`$ARGUMENTS` names the lap — a PR number or a `track/slug`. If empty, take the **most recent merge**
(`git log --merges -1` / `gh pr list --state merged --limit 1`). Gather everything the lap produced,
because the lessons live in the gap between what was planned and what actually shipped:
- The **diff** — what really changed (`gh pr diff <n>` or `git diff` for the merged range).
- The **review report** — `<root>/pr-reviews/pr-<n>-*.md`: its findings are the richest lesson source
  (a 🔴 that recurred, a fix pattern applied more than once).
- The **brief** — `<root>/briefs/<slug>.md`: its **Threat model**, the **alternatives it beat**, and
  any decision recorded mid-flight.
- The **handover(s)** for the thread, and `git log` for the work.

## Step 2 — Extract only the durable, non-obvious lessons
Apply **memory's test: was it non-obvious, and will it recur?** If the code, the git history, or an
existing doc already records it, it is **not** a lesson — skip it. Sprawl is the enemy of a knowledge
layer; a doc nobody trusts because it's bloated is worse than no doc. Look for:
- **A rule the review kept finding** — a 🔴/🟡 that appeared here and could reappear anywhere. It
  should become a guardrail rule so next lap's `/refine` and review catch it *up front*, not after.
- **A design pattern / component / token** the change introduced that belongs in the design system —
  generalising what `ui-ux-designer` already does for one design guide.
- **A security lesson** from the threat model or a security finding → the `security`/`privacy` overlay.
- **An architectural decision** worth recording (ADR-worthy) — **defer** (later slice), but capture it.
- **A non-obvious gotcha** for **AI memory** — the decision and its *why*, one fact each.

Each candidate carries its **evidence** (finding ID, `file:line`, PR#) — persist cited facts, not
assertions.

## Step 2.5 — Draft the release note (the outward deliverable — a different gate)
Separately from the lessons, ask: **did this lap change something a user would notice?** — a new or
changed feature, a fixed bug they hit, a behaviour or UI difference. If yes, it earns a release note;
this gate is **user-visibility, not non-obviousness**, so don't suppress it just because the change
taught you nothing. If the lap is **purely internal** (a refactor, a dep bump, infra) with no
user-visible effect, write **no** release note and say so — an internal-only lap has nothing to
announce.

When it applies, draft **1–3 lines in the user's language**, not the committer's:
- **Benefit-first, plain language.** "You can now export a workspace to CSV," not "added
  `exportWorkspace()` to the reports module." Say what the user can now do, or what no longer breaks.
- **Follow the project's copy voice.** Read the copy/voice rules (the `i18n`/UX guardrails or
  `CLAUDE.md`) and match them — **British English** for English copy, the project's tone and
  pronoun conventions. Release notes are user-facing copy; hold them to the copy bar.
- **Not the CHANGELOG.** A dev-facing CHANGELOG (semver, technical, per-commit) is a different
  artefact; if the project keeps one, the release note is the *human* companion to it, not a copy of
  it. Categorise lightly if the project already does (**New** / **Improved** / **Fixed**).

## Step 3 — Route each output to a surface (defer what isn't a first-slice target)
| Output | Target now | Mechanism |
|---|---|---|
| Recurring review rule / security bar | guardrails `extends` overlay for its dimension | Step 5 |
| Design pattern / token / component | the design-system doc | Step 5 |
| Non-obvious decision + why | AI memory | Step 5 |
| **User-visible change (from Step 2.5)** | **the release notes (`$RELEASE_NOTES`)** | **Step 5** |
| ADR / architecture diagram / ops / manual | **deferred** | list it, don't write it |

List the deferred ones explicitly so nothing is lost — they're the backlog for a later persist slice,
not a silent drop.

## Step 4 — Dedupe against what's already written
Before proposing any write, read the target doc and confirm it doesn't already say this. If it does,
drop the candidate (or, if the existing line is weaker, propose a **sharpening** of it, not a
duplicate). Persist the decision and the why — never the play-by-play of how you got there.

## Step 5 — Present the harvest plan and confirm — **STOP**
The knowledge layer is **project truth** — committed, shared, main-owned. **Offer, don't auto-write.**
Show a compact table and **wait for approval**:

> | Output | → Target | Line to add | Evidence |
> |---|---|---|---|
> | Tenant filter must be in the query, not the app layer | `security` overlay (`docs/security-house.md`) | "Every tenant-scoped query filters by tenant_id in SQL; app-layer filtering is a 🔴." | B2 in pr-471 review |
> | New `<StatusPill>` states | design system (`knowledge/ui-design.md`) | pill token + the four interactive states | pr-471 `StatusPill.tsx:1` |
> | **Release note** | **release notes (`knowledge/release-notes.md`)** | **New — "Export a workspace to CSV from its ⋯ menu."** | **pr-471** |

Show the **drafted release note verbatim** (it's user-facing copy — the user should approve the exact
words), list the **deferred** lessons under the table, and note if there's **no release note** (an
internal-only lap). **STOP for the go-ahead** — the user may cut a lesson, reword the note, or
redirect a target.

## Step 6 — Write the approved harvest
On approval, write **surgically and idempotently** — update in place, never clobber hand-authored content:
- **Guardrails (`extends` overlay ONLY):** append the rule to the dimension's house-rules file (the
  path in its `extends`). If the dimension has **no** `extends` file yet, create one
  (`<root>/knowledge/<dim>-house.md`), add the rule, and register it by **surgically merging** the
  path into that dimension's `extends` array in `relay.config.json` (preserve every other key — see
  the merge pattern `/relay-init` uses). **Never touch a baseline.**
- **Design system:** append the pattern/token to the design-system doc (`<root>/knowledge/ui-design.md`,
  honouring a `paths.design-system` override) in its Relay-managed section.
- **AI memory:** write each non-obvious decision as one fact (decision + why + how-to-apply) via the
  harness's memory mechanism, if available.
- **Release notes:** add the drafted note to `$RELEASE_NOTES` (create the file with a top-level
  heading if it's the first note). Group under the **current release heading** — the project's version
  (from its version manifest or the latest tag) or an **`## Unreleased`** section that accretes until a
  release cuts. Newest release on top; within a release, group by **New / Improved / Fixed** if the
  project does. **Idempotent** — re-running `/persist` on the same lap must **update, not double**: if
  this change already has a note, refine it in place rather than adding a second.

Commit the knowledge docs — guardrails overlay, design system, **release notes** (`$RELEASE_NOTES`)
— plus any `extends` config pointer, back onto `main`; main-owned, so edit from main's copy and push
surgically (the temp-index pattern `/handover` uses if you're on a feature branch). AI memory is
written through the harness, not necessarily via this commit.

## Step 7 — Report
State, outcome-first: **what was harvested and where** (each lesson → its surface), the **release
note** written (or that the lap was internal-only, so none), **what was deferred** to a later persist
slice, and that next lap's `/refine` and the review specialists now read the grown overlay — the
lesson is enforced from here on. If a lap taught no durable lesson **and** shipped nothing
user-visible, say so plainly: **"nothing to persist — no durable lesson, no user-visible change"** is
a valid, sprawl-respecting outcome, not a failure. (A common case: a user-visible lap that taught
nothing still gets a release note but no lesson — that's correct, not a half-result.)
