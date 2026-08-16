---
description: Review a PR (or the current branch) with domain specialists (frontend, ui-ux, backend, API design, DB) scoped to the touched areas, plus a test-coverage pass, always-on security, and content-gated privacy/architecture/i18n passes, merged into one report
argument-hint: "[pr-number]   # omit to review the current branch"
---

## Usage
`/relay:review [pr-number] [small|medium|large]` — also `/rlrv` (bare, no prefix) and `/relay:rlrv`

| Argument | Effect |
|---|---|
| `<pr-number>` | Review that PR |
| `small` · `medium` · `large` | Caps how many specialists run |
| `audit` | Widen Step 2.5's refutation from 🔴-only to every 🔴 **and** 🟡 — roughly doubles the review's cost |
| `no-audit` | Skip Step 2.5 entirely — report findings exactly as the specialists raised them |
| *(empty)* | Review the current branch |

**Any command also takes** `small`·`medium`·`large` (session size) · `terse`·`verbose` (how much Relay narrates) · `plain`·`informed`·`expert` (terminal depth) · `ask`·`challenge`·`solo` (who decides) — per-call, winning over `relay.config.local.json` ([[conventions]]). **Reads config:** `review.agents`, `review.verify`.

> **`?` prints this and stops.** If `$ARGUMENTS` is exactly `?`, `help`, `--help` or `-h`, print the
> signature line, the argument table and the words/config line above — verbatim, nothing else, not
> even this note — then **STOP**: no tools, no preamble, no action. `/relay:help <command>` prints
> the same thing.

> **Output** ([[conventions]]): honour `verbosity` (a per-call `terse`/`verbose` word in `$ARGUMENTS`, else `relay.config.local.json` `.verbosity`, else `normal`) — at **terse**, emit only STOP-gate questions and the final landing, no narration or intermediate recaps. Honour `audience` (a per-call `plain`/`informed`/`expert` word in `$ARGUMENTS`, else `relay.config.local.json` `.audience`, else unset) — how much depth surfaces in your **terminal** output; it never thins a **written artifact** (brief, report, ADR, handover), which always keeps full depth. `plain` = executive summary: the decisions and what you need from the user, minimal jargon; `informed` = lead with the decisions and what changed, keep the corrections and open questions that need the user, defer exhaustive evidence/`file:line` tables to the artifact; `expert` = full depth in the terminal too; unset ⇒ today’s default (no shaping). Never drop a STOP-gate question or the decision itself. Render every list (candidates / findings / plan rows) as a **GFM markdown table**, never stacked `Field: value` records or ASCII-rule separators; keep cells terse, overflow to numbered footnotes.

> **Run by the loop.** `/ship` calls this for you (Phase 3). Invoke it standalone only when
> you want a review *without* the rest of the ship loop — e.g. a review pass mid-thread.

Review PR $ARGUMENTS. If no number was given, review the current branch instead (use that
everywhere `$PR` appears below).

> **Relay ships ten review specialists** as subagents (backend, frontend, ui-ux, api,
> dbms, test, security, privacy, i18n, solution-architect). This command decides which to
> launch from the diff, runs them in parallel, and merges their findings into one report.
> A project can **declare its own review agents** in `relay.config.json` (`review.agents`);
> they flow through the same gate → cap → merge machinery as the built-ins (see Step 1/1.5/2
> and [[conventions]] → Custom review agents).

> **Resolve the root first:** durable state lives under the per-repo root (default `relay/`; a
> `relay.config.json` `{ "root": "docs" }` at the repo root overrides). Resolve once —
> `ROOT="$(jq -r '.root // "relay"' relay.config.json 2>/dev/null || echo relay)"` — the merged
> report below is written under `<root>/reviews/`.
>
> **Resolve the session size too** (see [[conventions]]):
> `SESSION="$(jq -r '.session // empty' relay.config.local.json 2>/dev/null)"; : "${SESSION:=$(jq -r '.tier // empty' relay.config.json 2>/dev/null)}"`
> — a per-call word (`small`/`medium`/`large`) in `$ARGUMENTS` overrides. It caps how many specialists
> fan out (Step 1.5). **Empty ⇒ no cap** — every applicable specialist runs. This is the classic
> **fan-out moment**, so if `SESSION` is empty, run at full **and mention once** that setting a session
> size (in `relay.config.local.json`, or per-call) right-sizes it — never block the review on it.
>
> **Resolve the project's declared review agents** (if any):
> `AGENTS="$(jq -c '.review.agents // []' relay.config.json 2>/dev/null || echo '[]')"`
> — each entry is `{ name, gate, tier, scope, priority }` (see [[conventions]] → Custom review
> agents). Empty ⇒ just the built-in ten. These are folded into Steps 1, 1.5 and 2 alongside the
> shipped specialists — same gate, same cap, same merged report.
>
> **Resolve how far to refute** (Step 2.5):
> `VERIFY="$(jq -r '.review.verify // "auto"' relay.config.json 2>/dev/null || echo auto)"`
> — `auto` (the default) · `always` · `never`. Back-compat: a boolean `true` reads as `always`,
> `false` as `never`. A per-call word in `$ARGUMENTS` wins: `audit` ⇒ `always`, `no-audit` ⇒ `never`.
>
> | `$VERIFY` | Step 2.5 refutes |
> |---|---|
> | `auto` *(default)* | every 🔴 — **and only when the review raised at least one**. No blockers ⇒ the step is a no-op and costs nothing. |
> | `always` (`audit`) | every 🔴 **and** every 🟡 |
> | `never` (`no-audit`) | nothing — findings are reported exactly as raised |
>
> **Why blockers are the auto trigger:** diff size doesn't predict a misread (a three-line change in
> unfamiliar code misreads as easily as a big one), but a 🔴 is the only finding class that *costs*
> something — it flips the verdict to `request-changes`, triggers a fix pass and holds the merge.
> Two agents to check a claim that is about to stop the lap is always worth it; a stray 🟡 is a
> paragraph you skim. Most laps raise no blocker, so most laps pay nothing.

## Step 1 — Classify the diff
Get a diffstat before invoking any subagent:
- With a PR number: `gh pr diff $PR | git apply --stat`
- Current branch: `git diff main...HEAD --stat`

**Docs-only short-circuit**: if every changed file is a non-code file (`*.md`, `*.mdx`,
`docs/**`, `LICENSE`, `CHANGELOG*`, and similar), stop here — don't launch any specialist.
Say directly that the diff is docs-only and no specialist review was needed; don't write a
`<root>/reviews/` file for it. This is a content fact, not a size guess.

From the file list, note which side(s) are touched. **Discover the repo's own layout** (from
`CLAUDE.md`, the workspace config, or the directory structure) rather than assuming fixed
paths:
- **frontend** — UI/component/style/client packages and apps.
- **backend** — API/server/database/domain/contract packages and apps.

Also skim the actual diff **content** (not just the file list) for gate signals. These are
content judgments, not size judgments — the question is never "is this diff small," only
"could this diff possibly contain the class of issue this specialist looks for":
- **privacy-relevant** — true if the diff touches a schema/migration/seed file, adds or
  changes a form field, adds/changes a log statement, or adds/changes a call to a
  third-party service. False only if none of those appear anywhere in the diff.
- **architecture-relevant** — true if the diff adds, removes, or changes any import/require
  statement, or touches a dependency manifest (`package.json`, lockfile, etc.). False only
  if the diff changes zero imports and zero dependencies.
- **copy-relevant** — true if the diff touches a locale/i18n file, or adds/changes any
  user-facing string (label, button, heading, placeholder, toast, empty-state, validation
  message). False only if it changes no user-facing text anywhere.

**Custom review agents** (`$AGENTS`, if any): evaluate each declared agent's `gate` the same way.
A `gate` is either the **name of a built-in signal** (`frontend`, `backend`, `privacy-relevant`,
`architecture-relevant`, `copy-relevant`) — fires when that signal is true — **or** a
`{ "paths": [glob, …] }` object, which fires when any changed file matches a glob. A gate that
fires puts its agent in the content-selected set; one that doesn't goes to *Skipped specialists*
with the reason `content gate did not fire`. No `gate` ⇒ treat as always-fires (unconditional).

## Step 1.5 — Apply the session size to the fan-out
Step 1 gives the **content-selected set** — the specialists whose gate fired for this diff. The
session size decides how many of them actually launch. Never trade away safety for budget:

- **Safety core — always runs when its gate fired, never capped:** `security-specialist`
  (unconditional), `test-engineer` (it's the one that runs the typecheck + suite — losing it loses
  verification), and `dbms-specialist` (migration/data-loss safety). These are outside the cap.
- **Cappable set — everything else selected:** `frontend-developer`, `backend-developer`,
  `ui-ux-designer`, `api-architect`, `privacy-specialist`, `i18n-reviewer`, `solution-architect`.
  Fill the budget from this set up to the cap, **prioritised by risk to the primary changed area**
  (the domain developer for the side with the most changed files first, then `privacy-specialist`
  if gated on, then the rest by relevance).
- **Custom agents** join whichever tier they declare: `tier: "safety"` runs uncapped alongside the
  safety core; `tier: "cappable"` (the default) joins the cappable pool, ordered *after* the
  built-ins by descending `priority` (default `0`). A deferred custom agent is logged in *Skipped
  specialists* with the same `deferred — session=<s> budget cap` reason as any built-in.

| `SESSION` | Fan-out |
|---|---|
| `small` | safety core + up to **2** cappable |
| `medium` | safety core + up to **4** cappable |
| `large` / empty | **no cap** — every content-selected specialist runs (today's behaviour) |

Any cappable specialist that its gate selected but the budget deferred is **not silently dropped**
— it goes in Step 3's *Skipped specialists* with the reason `deferred — session=<s> budget cap (re-run
/review standalone for full coverage)`. A budget defer is always auditable, same as a content skip.

## Step 2 — Launch reviewers in parallel
In a single message, launch whichever of these apply **after the Step 1.5 cap** — all in
"contributor mode" (findings only, no file write, no verdict; you merge them in Step 3):

1. **frontend-developer**, target $PR, scoped to the frontend areas — only if frontend files
   are touched. Covers correctness, hooks/component design, data-fetching, rendering.
2. **ui-ux-designer**, target $PR, same scope — only if frontend files are touched. Runs
   alongside frontend-developer: it covers accessibility (WCAG), visual consistency (design
   tokens, component reuse, complete hover/focus/active/disabled states), UX pattern
   consistency, and whether the project's design guide needs updating for any new pattern.
3. **backend-developer**, target $PR, scoped to the backend areas — only if backend files are
   touched. Covers correctness, data-access safety, authN/authZ, multi-tenancy, background-job
   safety, performance.
4. **api-architect**, target $PR, scoped to the API surface — only if the diff touches routes,
   the OpenAPI/contract layer, or shared request/response schemas. Runs alongside
   backend-developer: it covers REST surface design and cross-endpoint consistency.
5. **dbms-specialist**, target $PR, scoped to DB — only if the diff touches a migration file,
   a seed/fixture script, or a hand-maintained DB type. Covers migration safety (backward
   compatibility, locking, RLS on new tables) and seed/fixture safety across environments.
6. **test-engineer**, target $PR, full diff — no path scope. Launch whenever frontend or
   backend files are touched (skip only for a genuinely docs/config-only diff). Reviews test
   coverage/quality across both sides at once. Also ask it to **run the verification step**
   (the project's typecheck + relevant test suites) — it's the one specialist actually running
   the suite, so the others don't duplicate that.
7. **security-specialist**, target $PR, full diff — no path scope. **Always** launch this one,
   regardless of which side(s) are touched or how small the diff is: access-control bugs often
   span the frontend/backend boundary, and skipping security on a "small" PR is exactly the gap
   that leads to an incident.
8. **privacy-specialist**, target $PR, full diff — no path scope. Launch if `privacy-relevant`
   is true. Content gate, not a size gate — only skip when the diff structurally cannot touch
   personal data.
9. **i18n-reviewer**, target $PR, full diff — no path scope. Launch if `copy-relevant` is true.
   Checks that user-facing strings are externalised (not hardcoded), that every touched locale
   stays in sync (a key added to one locale is added to all — locale drift ships as a blank
   label), and that copy follows the project's voice/tone rules. Content gate, not a size gate.
10. **solution-architect**, target $PR, full diff — no path scope. Launch if
   `architecture-relevant` is true. Checks that the change respects the module/layer boundaries
   and any vendor-portability commitments the project's `CLAUDE.md`/architecture docs declare
   (e.g. a vendor SDK required to stay behind an adapter). It has no built-in opinion about what
   the boundaries should be — it discovers them from the project. Content gate, not a size gate.

11. **Custom review agents** (`$AGENTS`) whose gate fired and the cap admitted — launch each via
   its declared subagent type (`agentType: "<name>"`), target $PR, path-scoped per its `scope`
   (`frontend`/`backend`/`full`, default `full`), in the same **contributor mode** (findings only,
   no file write, no verdict). They must return findings in the standard shape (severity-graded,
   each with a `file:line`) — a declared agent that writes its own report or emits a verdict breaks
   the Step 3 merge (see [[conventions]] → Custom review agents for the contract).

**security-specialist stays unconditional** — its surface is too broad for a content
pre-filter to safely narrow (a one-line render change can still be an XSS vector).

**Transparency on skips**: whenever a specialist doesn't run — either a content gate didn't fire
(privacy, i18n, solution-architect) **or** the session-size budget deferred it (Step 1.5) — record why in
the final report's *Skipped specialists* section, e.g. "privacy-specialist skipped: diff touches no
schema/form/log/third-party-call code" or "ui-ux-designer deferred — session=small budget cap". A skip
is always auditable, never silent.

## Step 2.5 — Refute before reporting
Specialists return **claims**, and a claim built from a diff hunk can misread code it only saw a
fragment of. This step tries to kill each one before it reaches the report — and before `/fix`
spends a pass discovering the same thing.

**Scope comes from `$VERIFY`** (resolved above). Take the findings it names:

| `$VERIFY` | Findings to refute | If there are none |
|---|---|---|
| `auto` | every 🔴 | Nothing to do — skip to Step 3, record `verified: none`. No agents launched. |
| `always` | every 🔴 and 🟡 | as above |
| `never` | — | skip to Step 3, record `verified: none` |

**Nits are never refuted**, in any mode — two agents per nit cost more than the nit. Under `auto`,
🟡s aren't either: they don't hold a merge, so they don't earn the spend.

In a single message, launch **two refuters per finding**, each a
`general-purpose` agent given the finding text, the cited `file:line`, and exactly one lens:

| Lens | The question it asks |
|---|---|
| **misread** | Does the cited code actually do what the finding says? Read the whole file, not the diff hunk — the specialist saw a fragment. |
| **mitigated** | Is the concern already handled somewhere the finding didn't look — a guard one layer up, a framework default, a constraint in the schema, a caller that can't reach this path? |

**Never route a finding back to the specialist that raised it.** The value here is an independent
read; the author will confirm its own work.

Each refuter returns exactly `{ refuted: true | false, reason: <one line> }`. Instruct every
refuter to **return `refuted: false` when it is uncertain**. The asymmetry is deliberate: a
dropped real blocker ships a bug, while a surviving noisy finding costs one paragraph in `/fix`.

| Refuter outcome | What happens to the finding |
|---|---|
| **Both refute** | **Dropped** from Findings; listed under *Refuted findings* with both reasons. |
| **One refutes** | **Kept at its original severity**, annotated `(contested: <reason>)`. A split vote never downgrades a blocker and never flips the verdict. |
| **Neither refutes** | Stands, unannotated. |

**A refuted finding is never silently deleted** — same rule as a skipped specialist. The *Refuted
findings* section is how you tell whether this pass is calibrated or is quietly eating real bugs;
read it deliberately for the first few runs on a new project.

### The last blocker is the user's call — STOP
Dropping a 🔴 normally just tidies the report. But if refutation would drop the **last remaining
🔴**, it stops being a reporting decision: the verdict flips `request-changes` → `approve`, and
under `/ship` that is what lets the branch merge. Two refuters would be deciding what lands.

**So when the refuted set would leave zero blockers, STOP before writing the report** and put it to
the user — regardless of `autonomy.decide`, because this is a merge-gate decision, not a routine one:

> *Refutation would clear the last blocker: **<B1 claim>** at `<file:line>` (raised by
> `<specialist>`). misread says: <reason>. mitigated says: <reason>. Drop it and approve, or keep
> it and let the fix pass look?*
>
> - **Drop it** → finding moves to *Refuted findings*, verdict becomes `approve`.
> - **Keep it** → finding stays 🔴, annotated `(contested: refuters disagreed with the specialist)`,
>   verdict stays `request-changes`.

Blockers 2..N are dropped quietly — only the one that would empty the list is escalated. If the
review raised no blocker at all, there is nothing to escalate and no question is asked.

Log the answer to `autonomy.log` like any other decision made mid-loop ([[conventions]]).

## Step 3 — Merge into ONE report, in EXACTLY this structure
The report must look the same every time, no matter which specialists ran or how many findings
they raised — a reader (and `/fix`) should be able to scan any Relay review report
without relearning its shape. `mkdir -p <root>/reviews`, then write
`<root>/reviews/pr-<NUMBER-or-branch>-<YYYY-MM-DD>.md` using this template verbatim — same
frontmatter fields, same sections, same order, every time:

```markdown
---
pr: <number, or branch name if no PR>
date: <YYYY-MM-DD>
areas: <touched areas, comma-separated — e.g. apps/admin, packages/schemas>
specialists: <the ones that RAN, comma-separated>
verified: <none | blockers | all — what Step 2.5 actually refuted>
verdict: <approve | request-changes>
blockers: <total 🔴 count>
counts: { blocker: <n>, should-fix: <n>, nit: <n> }
---

# PR Review: <one-line title>

## Verdict
**<APPROVE | REQUEST-CHANGES>** — <🔴 n blockers · 🟡 n should-fix · 🟢 n nits>. <One sentence
on why: the single most important thing to resolve, or "no blockers" if clean.>

## Findings
<Every finding as ONE checklist line, in this exact per-finding format, ordered 🔴 → 🟡 → 🟢
and within each severity by area. If a section is empty, write "_None._" under its heading —
never omit the heading.>

### 🔴 Blockers
- [ ] **B1** · `<area>` · `<path/to/file.ext:line>` — <one-sentence problem>. **Fix:** <concrete change>. _(<specialist>)_

### 🟡 Should-fix
- [ ] **S1** · `<area>` · `<path/to/file.ext:line>` — <one-sentence problem>. **Fix:** <concrete change>. _(<specialist>)_

### 🟢 Nits
- [ ] **N1** · `<area>` · `<path/to/file.ext:line>` — <one-sentence problem>. **Fix:** <concrete change>. _(<specialist>)_

## Refuted findings
<One line per finding Step 2.5 dropped, in the same shape as a Findings line but with the
original severity emoji and both refuters' reasons instead of a **Fix:** —
`- 🔴 · `<area>` · `<file:line>` — <claim>. **Refuted:** <misread reason> / <mitigated reason>
_(<specialist>)_`. "_None — every refuted finding survived._" if the step ran and dropped nothing.
"_Not run — no blockers to refute._" when `verified: none` because the review was clean, or
"_Not run — `no-audit`._" when it was switched off. Note the scope on the heading line when it
was `blockers` ("🔴 only — `audit` widens this to 🟡 too").>

## Skipped specialists
<One line per specialist that did NOT run, with the reason — a content gate that didn't fire
("privacy-specialist — diff touches no schema/form/log/third-party-call code") or a session-size
budget defer ("ui-ux-designer — deferred, session=small budget cap; re-run /review standalone for full
coverage"). "_None — all applicable specialists ran._" if none were skipped. This makes every gate
and every budget defer auditable.>

## Notes
<Only things that are NOT a code-level finding: a lawful-basis or DPIA question security/privacy
raised, an undocumented-but-inferred rule worth writing down, a follow-up out of this PR's scope.
"_None._" if there are none. Do not restate findings here.>
```

**Rules that keep it uniform:**
- **Every finding is one line** in the `**ID** · area · `file:line` — problem. **Fix:** … _(specialist)_`
  shape — same whether it came from security or i18n. No specialist gets its own private format.
- **IDs are stable within the report** (`B1, B2, S1, N1…`) so a review can be discussed by ID.
- **Never omit a heading.** All five sections (Blockers, Should-fix, Nits, Refuted, Skipped)
  always appear; an empty one says `_None._`. A reader learns the shape once — including
  *Refuted findings*, which says `_Not run — no blockers to refute._` on a clean review.
- **`verdict` is `request-changes` if there is ANY 🔴, else `approve`.** `blockers` = the 🔴
  count. `counts` totals all three severities. These three frontmatter facts must agree with the
  Verdict line and the Findings.
- The findings checklist is what `/fix` consumes — keep the `- [ ]`, the severity
  order, and the `file:line` so it can re-verify and tick each one. Keep any
  `(contested: …)` annotation on the line too: `/fix` reads it as "look at this one yourself
  before changing code".
- **Refuted findings are not checklist items.** They use `- ` not `- [ ]`, so `/fix` never
  picks them up as work.

## Step 4 — Return
Tell the user the report path and the Verdict line — nothing else.
