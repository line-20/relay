---
description: Read the latest PR review, re-verify each finding against the current code, fix, and tick off
argument-hint: "[a review report filename — omit for the most recent in <root>/reviews/]"
allowed-tools: Bash(ls:*), Bash(cat:*), Bash(gh pr diff:*), Bash(git:*), Bash(pnpm:*), Bash(npm:*), Read, Edit, Write, Glob, Grep, Task
---

## Usage
`/relay:fix [report-filename]` — also `/rlf` (bare, no prefix) and `/relay:rlf`

| Argument | Effect |
|---|---|
| `<report filename>` | The review report to work from |
| *(empty)* | The most recent file in `<root>/reviews/` |

**Any command also takes** `small`·`medium`·`large` (session size) · `terse`·`verbose` (how much Relay narrates) · `plain`·`informed`·`expert` (terminal depth) · `ask`·`challenge`·`solo` (who decides) — per-call, winning over `relay.config.local.json` ([[conventions]]).

> **`?` prints this and stops.** If `$ARGUMENTS` is exactly `?`, `help`, `--help` or `-h`, print the
> signature line, the argument table and the words/config line above — verbatim, nothing else, not
> even this note — then **STOP**: no tools, no preamble, no action. `/relay:help <command>` prints
> the same thing.

> **Output** ([[conventions]]): honour `verbosity` (a per-call `terse`/`verbose` word in `$ARGUMENTS`, else `relay.config.local.json` `.verbosity`, else `normal`) — at **terse**, emit only STOP-gate questions and the final landing, no narration or intermediate recaps. Honour `audience` (a per-call `plain`/`informed`/`expert` word in `$ARGUMENTS`, else `relay.config.local.json` `.audience`, else unset) — how much depth surfaces in your **terminal** output; it never thins a **written artifact** (brief, report, ADR, handover), which always keeps full depth. `plain` = executive summary: the decisions and what you need from the user, minimal jargon; `informed` = lead with the decisions and what changed, keep the corrections and open questions that need the user, defer exhaustive evidence/`file:line` tables to the artifact; `expert` = full depth in the terminal too; unset ⇒ today’s default (no shaping). Never drop a STOP-gate question or the decision itself. Render every list (candidates / findings / plan rows) as a **GFM markdown table**, never stacked `Field: value` records or ASCII-rule separators; keep cells terse, overflow to numbered footnotes.

> **Run by the loop.** `/ship` calls this for you (Phase 4). Invoke it standalone only when
> you're working an existing review report outside a full ship.

Work through the PR review report and fix what's real. Target: $ARGUMENTS (a report filename, or empty = use the most recent file in <root>/reviews/).

> **Resolve the root first:** durable state lives under the per-repo root (default `relay/`; a
> `relay.config.json` `{ "root": "docs" }` at the repo root overrides). Resolve once —
> `ROOT="$(jq -r '.root // "relay"' relay.config.json 2>/dev/null || echo relay)"` — and read every
> `<root>/…` path below relative to it.

## Step 1 — Load
1. If no file given, run `ls -t <root>/reviews/*.md | head -1` and use that.
2. Read the report. Parse the frontmatter (pr, areas, blockers) and the unchecked `- [ ]` findings.
3. Get current state: `gh pr diff` (or the diff for the PR number in frontmatter) plus the actual files referenced.

## Step 2 — Re-verify BEFORE fixing
Treat every finding as a *claim to verify*, not an instruction to obey. For each unchecked box, in 🔴 → 🟡 → 🟢 order:

**How hard to look** depends on what the report already did. Its `verified:` frontmatter names the
scope refutation covered — `blockers` (🔴 only, the automatic default), `all` (🔴+🟡, from `audit`)
or `none`. Whatever it covered, two independent refuters already tried and failed to kill those
findings, so a **fast confirm** is enough there: open the cited line, check the issue is still
present, move on.

Look at full strength for everything outside that scope — every 🟢 always (refutation never touches
nits), 🟡 on a `verified: blockers` report, everything on `verified: none` — and for anything
annotated `(contested: …)`, which is the finding most likely to be wrong: two refuters split on it.
Never skip the *stale* check on any finding: the code may have moved since the review, which is a
different question from whether the claim was true when it was made.
1. Open the cited `file:line` and confirm the issue still exists and is real.
2. Classify it:
   - **confirmed** — real, reproduce it mentally, proceed to fix.
   - **stale** — code moved or already fixed; mark the box `[~]` and add `(stale: <reason>)`.
   - **wrong** — the finding misread the code; mark `[x]` struck through with `(rejected: <reason>)`. Do NOT change code to satisfy a wrong finding.
   - **needs-judgment** — a design call, not a clear bug; leave unchecked, note it, surface to the user at the end.

## Step 3 — Fix confirmed findings
1. Make the smallest change that resolves the issue; don't refactor beyond scope.
2. Respect the conventions in the nearest `CLAUDE.md`.
3. Group related fixes into coherent commits with messages like `fix(review): <finding> [pr-N]`.
4. For anything touching a security boundary (auth / access-control / SQL / tenant isolation), be conservative: if the correct fix is ambiguous, downgrade to needs-judgment rather than guess.

## Step 4 — Verify the gate
1. Run the project's typecheck (discover it from `CLAUDE.md`/`package.json` — e.g. `pnpm -w tsc --noEmit`). It must be green — that's the gate.
2. Run the relevant tests for the touched area.
3. If a fix broke either, resolve it before moving on. If it can't be resolved cleanly, revert that fix and flag it.

## Step 4.5 — Re-review the fix delta (the fix is the most defect-dense diff)
The gate above proves the suite is green — but that is not enough. **A fix pass is the most
defect-dense diff in the loop:** the change made to satisfy one finding routinely breaks a
*neighbouring* invariant, and a green suite hides it because the new tests are sequential and
happy-path. So before reporting, re-review **the fix delta itself** — only what this pass changed,
never the original PR diff (the review already covered that).

Scope it to this pass: `git diff origin/main...HEAD` narrowed to the fix commits from Step 3 (the
delta you just added, not the whole branch).

Launch **one independent `general-purpose` agent** over that delta — *independent* because the
author confirms its own work, the same rule `/review`'s Step 2.5 follows (never let the writer grade
the write). Give it the delta, the findings Step 3 just closed, and this brief:
> Re-review this fix delta. Two questions: **(1) Did each closed finding actually get fixed**, or
> only papered over — does the cited issue still reproduce? **(2) Did the fix break a neighbouring
> invariant** — a concurrency guard, a co-located contract, a rule the touched code already stated,
> an adjacent path the diff never exercised? Read the whole file around each change, not just the
> hunk. **Grade each concern `blocker`** (the closed finding is not actually closed, or the fix
> introduced a real regression — a broken invariant, a security/data/concurrency hole) **`should-fix`
> or `nit`**. Return each as `{ file:line, problem, severity }`, or `clean` if none.

**Escalate to the real specialists when the fix delta is high-risk.** A generalist re-read is enough
for most deltas, but the fix pass's worst escapes — an auth bypass, a lost-update, a broken
migration — live in a few dimensions where a domain specialist sees what a generalist misses.
Classify the *fix delta* exactly as `/review` Step 1 does (its content gates, read against the delta,
not the whole PR), and when it trips a **safety-core** dimension, also launch that dimension's
specialist over the delta — in the same contributor mode `/review` uses (findings only, no report, no
verdict):

| Delta touches (per `/review` Step 1 gates) | Also launch |
|---|---|
| auth / access-control / SQL / secrets / untrusted input | `security-specialist` |
| a migration, seed, or hand-maintained DB type | `dbms-specialist` |
| backend / server / data-access code | `backend-developer` |

Nothing high-risk in the delta ⇒ the generalist floor is the whole check; don't spend a specialist on
a copy or docs fix. The specialists review the **fix delta only**, never the original PR diff — so
this never re-does the Phase-3 review that `/ship` already ran; it reviews only what the fix *added*.
Merge their findings with the generalist's into one severity-graded set (dedupe an issue both raise),
then act on that set below.

Act on the result **by severity** — the same discipline `/review`'s Step 2.5 uses (only a
merge-deciding blocker escalates; a nit never loops):
- **Clean, or only `should-fix`/`nit` concerns ⇒ proceed to Step 5.** Record those lower-severity
  concerns in the fix-pass summary so the user sees them, but **do NOT loop on them** — a re-review
  that bounces `/fix` back on nits becomes a nag and gets skipped, which is the whole failure this
  step must avoid.
- **A `blocker`-class concern ⇒ feed it back into Step 2** as a new claim to verify-then-fix (the
  finding isn't closed, or the fix broke something real), then re-run this step on the new delta.
- **Bound the loop — at most 2 re-review rounds** of blocker-class concerns. If a third would be
  needed, **STOP** and hand the outstanding concerns to the user rather than spinning: the fix is
  fighting itself and wants a human eye.

**Fail safe.** If this step cannot run (the generalist or an escalated specialist errors, the delta
can't be computed), do **not** report green — say the fix delta is **unverified** and why, and carry
it as a needs-judgment item into Step 5. A false all-clear here is worse than an honest "couldn't
check": it is the exact silent-green this step exists to remove. An escalation specialist that its
gate selected but that could not launch is named in the summary, never silently dropped — same rule
`/review` holds for a skipped specialist.

## Step 5 — Update the report & report back
1. In the report file, tick each handled box: `[x]` fixed, `[~]` stale, `[x] ~~...~~` rejected — each with a one-line note and the commit SHA where relevant.
2. Append a `## Fix pass <date>` section summarizing: fixed N, stale N, rejected N, needs-judgment N, and the **fix-delta re-review** result (clean / N blocker-concerns fixed over M rounds / unverified) — noting which specialists escalated (Step 4.5) or that only the generalist ran — plus any `should-fix`/`nit` the re-review reported but did not loop on.
3. Commit the updated report. Do NOT auto-push; print a summary and the suggested `git push` so the user reviews first.
4. List anything left for the user: needs-judgment items, any reverted fixes, and an **unverified fix delta** (Step 4.5 could not run) if there is one.
