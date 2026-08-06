---
description: End-of-session orchestrator — test → open PR + review → fix → merge to main → handover. Runs the whole loop; merges only on a clean green path.
argument-hint: "(no arguments)"
---

Run the full end-of-session loop in sequence. Move straight through; STOP only at the
gates called out below. This DOES merge and DOES hand over — but the merge proceeds only
on the unambiguous green path defined in Phase 5; on anything ambiguous it stops.

**Resolve the Relay root first.** Durable state lives under a per-repo root — default `relay/`,
overridable via a `relay.config.json` at the repo root (`{ "root": "docs" }`). Resolve it once; read
every `<root>/…` path below relative to it. Absent config ⇒ `<root>` = `relay`. (The commands this
loop composes — `/review`, `/handover` — resolve it themselves too.)
```bash
ROOT="$(jq -r '.root // "relay"' relay.config.json 2>/dev/null || echo relay)"
```

## Phase 1 — Test
Run the project's test suite (discover the command from `CLAUDE.md`/`package.json`/README —
e.g. `pnpm test`, `npm test`, `cargo test`). If the project has DB-backed integration tests
behind a fixture stack, bring it up and run them too.
- **If anything fails, STOP.** Report the failing suites and don't touch the PR.
- If green, continue. (Tear down any throwaway fixture at the very end, after handover.)

## Phase 2 — Ensure a PR (committed work only)
1. `git branch --show-current`. If it's `main`/`master`/the default branch, **STOP**.
2. `gh pr view --json number,url,state` — if an OPEN PR exists for this branch, use it and go to Phase 3.
3. No PR:
   a. `git status`. **If the tree is dirty, STOP** — committing is the user's call. Ask them to commit (or stash), then re-run.
   b. Clean tree: push committed work if needed (`git push -u origin <branch>`), then `gh pr create --fill --draft`.

## Phase 3 — Review (multi-specialist fan-out)
Review the PR with the **`/review` fan-out**, not a single reviewer — follow the
playbook in that command exactly:
1. **Classify the diff** (its Step 1): note which side(s) are touched (frontend / backend)
   and the privacy / architecture / copy content gates. If the diff is **docs-only**,
   short-circuit — no specialist review, say so, and go straight to Phase 5.
2. **Launch the applicable specialists IN PARALLEL, in a single message**, in contributor
   mode (findings only, no per-agent report, no per-agent verdict). Which ones apply is
   decided by `/review` Step 2. security-specialist is **always** launched.
3. **Merge** every specialist's findings into ONE report at
   `<root>/pr-reviews/pr-<N>-<YYYY-MM-DD>.md` (🔴/🟡/🟢, blocker-first, each finding keeping its
   file path). Verdict is `request-changes` if ANY specialist raised a 🔴, else `approve`;
   `blockers` = the total 🔴 count.

- If verdict is **approve with zero blockers**, skip Phase 4 and go to Phase 5.

## Phase 4 — Fix (only if there are findings)
Work the report the way `/fix` does:
- Re-verify each finding against the current code BEFORE changing anything (confirmed / stale / wrong / needs-judgment).
- Fix confirmed findings with the smallest change; for security/auth/SQL boundaries, downgrade to needs-judgment rather than guess.
- Keep the typecheck green; run the relevant tests; tick the boxes in the report.
- Commit the fixes (they'll be pushed in Phase 5 — the merge needs them on the remote).
- **If any needs-judgment items or reverted fixes remain, STOP** and surface them; those are the user's call before the loop can close.

## Phase 5 — Merge (clean green path only)
Merge only if ALL of these hold. If any fails, **STOP** and report which one:
- Review verdict is approve, OR every 🔴 blocker is resolved (no unchecked 🔴 left in the report).
- No needs-judgment items or reverted fixes outstanding from Phase 4.
- The PR is mergeable: `gh pr view --json mergeable,mergeStateStatus` → mergeable, no conflicts.
- Required checks are already green: `gh pr checks <n>` → all pass. **If checks are still running or failing, STOP** (don't merge into the unknown).

If all hold:
1. Push the fix commits: `git push`.
2. Mark the PR ready if it's still a draft: `gh pr ready <n>`.
3. Merge, cleaning up the branch: `gh pr merge <n> --merge --delete-branch`
   (Use `--squash` or `--rebase` if the repo prefers; `--merge` keeps every commit.)
4. `git fetch origin` so local refs reflect the merge. Report that `origin/main` now has everything.

Note: if `main` has branch protection requiring an approving review, the merge will be
rejected — that's fine, it just means a human approval is the enforced gate. Report the
rejection and STOP if so.

## Phase 5.5 — Run any post-merge project setup (only if the merge shipped schema/dep changes)
A test fixture may self-migrate, but a **persistent local dev environment** usually does
not — so a merged schema/dependency change can leave the next session hitting errors.
1. Check whether the merged diff touched migrations/dependencies (e.g.
   `git diff --name-only origin/main~1 origin/main`). If it didn't, **skip this phase**.
2. If it did, run whatever setup the project's `CLAUDE.md`/README names for a local dev
   environment (install, migrate, regrant, regenerate).
3. **Best-effort and NON-fatal.** If the local environment isn't running, note it and
   continue to handover rather than stopping.

## Phase 5.7 — Persist what the lap taught (offer, non-fatal)
The merge is in; before handing over, this is the moment to compound. **If the lap taught something
durable** — a review finding that should become a guardrail rule, a design pattern worth stewarding,
a non-obvious decision, **or a user-visible change worth a release note** — **offer `/persist`** to
harvest it into the knowledge layer (guardrails `extends` overlay + design system + AI memory) and
draft a human-readable **release note**. Offer, don't force: for a routine change that taught nothing
and shipped nothing user-visible, say so and skip. Non-fatal — never block the handover on it. (At 1.0
this becomes a first-class phase of `ship`; today it's an offered step.)

## Phase 6 — Handover (and end-of-session tidy)
The PR is now merged, so proceed directly into the handover. Run `/handover` end to end:
its Step 0 guard passes (PR is MERGED), it generates the cold-start handover, commits it to
main, prints the compact summary, **and does the end-of-session housekeeping** — its Step 4.5
archives superseded handovers + old PR reviews, and its Step 6 exits this thread's topic worktree
(keeping it on disk for the topic's next slice) and prunes dead worktree entries. There is no
separate cleanup command; this is it. Then tear down any throwaway test fixture. That closes the
session.
