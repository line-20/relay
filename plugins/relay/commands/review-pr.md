---
description: Review a PR (or the current branch) with domain specialists (frontend, ui-ux, backend, API design, DB) scoped to the touched areas, plus a test-coverage pass, always-on security, and content-gated privacy/architecture/i18n passes, merged into one report
argument-hint: "[pr-number]   # omit to review the current branch"
---

Review PR $ARGUMENTS. If no number was given, review the current branch instead (use that
everywhere `$PR` appears below).

> **Relay ships ten review specialists** as subagents (backend, frontend, ui-ux, api,
> dbms, test, security, privacy, i18n, solution-architect). This command decides which to
> launch from the diff, runs them in parallel, and merges their findings into one report.

## Step 1 — Classify the diff
Get a diffstat before invoking any subagent:
- With a PR number: `gh pr diff $PR | git apply --stat`
- Current branch: `git diff main...HEAD --stat`

**Docs-only short-circuit**: if every changed file is a non-code file (`*.md`, `*.mdx`,
`docs/**`, `LICENSE`, `CHANGELOG*`, and similar), stop here — don't launch any specialist.
Say directly that the diff is docs-only and no specialist review was needed; don't write a
`pr-reviews/` file for it. This is a content fact, not a size guess.

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

## Step 2 — Launch reviewers in parallel
In a single message, launch whichever of these apply — all in "contributor mode" (findings
only, no file write, no verdict; you merge them in Step 3):

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

**security-specialist stays unconditional** — its surface is too broad for a content
pre-filter to safely narrow (a one-line render change can still be an XSS vector).

**Transparency on skips**: whenever a gated specialist (privacy, i18n, solution-architect) is
skipped, still record why in the final report's Notes — e.g. "privacy-specialist skipped: diff
touches no schema/form/log/third-party-call code" — so a skip is always auditable, never silent.

## Step 3 — Merge into one report
When all launched specialists return:
1. `mkdir -p pr-reviews`.
2. Write `pr-reviews/pr-<NUMBER>-<YYYY-MM-DD>.md` (branch name if no PR number):
   ---
   pr: <number or branch>
   date: <YYYY-MM-DD>
   areas: <e.g. apps/admin, packages/schemas>
   verdict: <approve | request-changes>
   blockers: <count>
   ---

   # PR Review: <title>

   ## Summary
   <2–3 sentences you write, drawing on all specialists' findings.>

   ## Findings
   Combined checklist from every specialist that ran, 🔴 first, then 🟡, then 🟢 — keep each
   finding's file path so it's clear which specialist it came from.

   ## Notes
   Merged Notes from every specialist, including any security/privacy Notes about things
   outside code-level review (e.g. a lawful-basis question, or a DPIA that should happen
   separately), and any undocumented-but-inferred rule a specialist flags as worth writing down.
3. Verdict is `request-changes` if ANY specialist reported a 🔴 finding, else `approve`.
   `blockers` is the total 🔴 count across all of them.

## Step 4 — Return
Tell the user the report path and the verdict line — nothing else.
