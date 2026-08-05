---
description: Read the latest PR review, re-verify each finding against the current code, fix, and tick off
allowed-tools: Bash(ls:*), Bash(cat:*), Bash(gh pr diff:*), Bash(git:*), Bash(pnpm:*), Bash(npm:*), Read, Edit, Write, Glob, Grep
---

> **Run by the loop.** `/wrapup` calls this for you (Phase 4). Invoke it standalone only when
> you're working an existing review report outside a full wrapup.

Work through the PR review report and fix what's real. Target: $ARGUMENTS (a report filename, or empty = use the most recent file in <root>/pr-reviews/).

> **Resolve the root first:** durable state lives under the per-repo root (default `relay/`; a
> `relay.config.json` `{ "root": "docs" }` at the repo root overrides). Resolve once —
> `ROOT="$(jq -r '.root // "relay"' relay.config.json 2>/dev/null || echo relay)"` — and read every
> `<root>/…` path below relative to it.

## Step 1 — Load
1. If no file given, run `ls -t <root>/pr-reviews/*.md | head -1` and use that.
2. Read the report. Parse the frontmatter (pr, areas, blockers) and the unchecked `- [ ]` findings.
3. Get current state: `gh pr diff` (or the diff for the PR number in frontmatter) plus the actual files referenced.

## Step 2 — Re-verify BEFORE fixing
Treat every finding as a *claim to verify*, not an instruction to obey. For each unchecked box, in 🔴 → 🟡 → 🟢 order:
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

## Step 5 — Update the report & report back
1. In the report file, tick each handled box: `[x]` fixed, `[~]` stale, `[x] ~~...~~` rejected — each with a one-line note and the commit SHA where relevant.
2. Append a `## Fix pass <date>` section summarizing: fixed N, stale N, rejected N, needs-judgment N.
3. Commit the updated report. Do NOT auto-push; print a summary and the suggested `git push` so the user reviews first.
4. List anything left for the user: needs-judgment items and any reverted fixes.
