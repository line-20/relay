---
description: End-of-session orchestrator — test → open PR → verify gate → review → fix → merge to main → handover. Runs the whole loop; merges only on a clean green path, and won't spend the review fan-out on work nobody has exercised.
argument-hint: "['no-verify' — skip the Phase 2.5 verify gate and go straight to review]"
---

## Usage
`/relay:ship [no-verify]` — also `/rls` (bare, no prefix) and `/relay:rls`

| Argument | Effect |
|---|---|
| `no-verify` | Skip the Phase 2.5 verify gate and go straight to review |
| `audit` | Widen Phase 3's refutation from 🔴-only to every 🔴 **and** 🟡 (~2× review cost) |
| `no-audit` | Skip refutation entirely — report findings exactly as the specialists raised them |
| *(empty)* | The full lap — test → gate → review → fix → merge → handover |

**Any command also takes** `small`·`medium`·`large` (session size) · `terse`·`verbose` (how much Relay narrates) · `plain`·`informed`·`expert` (terminal depth) · `ask`·`challenge`·`solo` (who decides) — per-call, winning over `relay.config.local.json` ([[conventions]]). **Reads config:** `persist.cadence`, `tidy.level`, `hooks.test`, `hooks.release`, `hooks.env.down`.

> **`?` prints this and stops.** If `$ARGUMENTS` is exactly `?`, `help`, `--help` or `-h`, print the
> signature line, the argument table and the words/config line above — verbatim, nothing else, not
> even this note — then **STOP**: no tools, no preamble, no action. `/relay:help <command>` prints
> the same thing.

> **Output** ([[conventions]]): honour `verbosity` (a per-call `terse`/`verbose` word in `$ARGUMENTS`, else `relay.config.local.json` `.verbosity`, else `normal`) — at **terse**, emit only STOP-gate questions and the final landing, no narration or intermediate recaps. Honour `audience` (a per-call `plain`/`informed`/`expert` word in `$ARGUMENTS`, else `relay.config.local.json` `.audience`, else unset) — how much depth surfaces in your **terminal** output; it never thins a **written artifact** (brief, report, ADR, handover), which always keeps full depth. `plain` = executive summary: the decisions and what you need from the user, minimal jargon; `informed` = lead with the decisions and what changed, keep the corrections and open questions that need the user, defer exhaustive evidence/`file:line` tables to the artifact; `expert` = full depth in the terminal too; unset ⇒ today’s default (no shaping). Never drop a STOP-gate question or the decision itself. Render every list (candidates / findings / plan rows) as a **GFM markdown table**, never stacked `Field: value` records or ASCII-rule separators; keep cells terse, overflow to numbered footnotes.

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

## Phase 1 — Test (the automated suite)
Run the project's test suite. **If `relay.config.json` has a `hooks.test`** (a project command/skill,
e.g. `test-stack`), **dispatch that** — it's the project's own way to bring the fixture stack up and
run tests (see [[conventions]] → Hooks). Otherwise discover the command from
`CLAUDE.md`/`package.json`/README (e.g. `pnpm test`, `npm test`, `cargo test`) and, if there are
DB-backed integration tests behind a fixture stack, bring it up and run them too.
- **If anything fails, STOP.** Report the failing suites and don't touch the PR.
- If green, continue. (Tear down any throwaway fixture at the very end, after handover.)

## Phase 2 — Ensure a PR (commit the slice if needed)
1. `git branch --show-current`. If it's `main`/`master`/the default branch, **STOP**.
2. **Dirty tree? Commit it — don't ask.** Getting the slice onto a PR is the point; in Relay's
   worktree-per-session model the tree *is* this session's slice. `git status`; if anything is
   uncommitted or untracked, author a **Conventional-Commits** message from the real diff
   (`type(scope): summary` + short body, in the repo's commit voice), then `git add -A && git commit`.
   This never asks: committing is additive and reversible, not the destructive tree operation a safety
   gate guards ([[conventions]] → autonomy).
3. `gh pr view --json number,url,state` — if an OPEN PR exists for this branch, push any commits it's
   missing (`git push`), use it, and go to Phase 2.5.
4. No PR: push (`git push -u origin <branch>`), then `gh pr create --fill --draft`.

## Phase 2.5 — Verify gate (has anyone actually exercised this?)
A green suite is not the same as *someone clicked through it*. The review fan-out in Phase 3 is the
most expensive thing this loop does, and spending it on a change nobody has exercised is the waste
this gate exists to prevent. So before the fan-out, look for **evidence of a hands-on pass** — cheap,
from the PR:
- a `## 🧪 Test drive` section in the PR body with **ticked** `- [x]` boxes, or
- a `/test` **results comment** on the PR (`gh pr view <n> --json body,comments`) with a pass tally.

**Evidence found ⇒ say so in one line and continue to Phase 3.**

**No evidence ⇒ ask once and STOP for the answer:**
> *PR #<n> hasn't been exercised yet — no test-drive results on it. Review is the expensive phase;
> spending it on unverified work is usually the waste. **Run `/test` first**, or review anyway?*

- **Run `/test`** → run `/relay:test <n>` end to end (it picks the verify target — preview via
  `/deploy`, or local via `hooks.env.up` — writes the plan and, on a `drive`, exercises it). Then
  re-enter this phase. If driving turns something red, **STOP** — that's a fix, not a ship.
- **Review anyway** → note the choice and continue; the answer holds for the rest of this run, so
  the gate asks at most once.
- **Skip the gate entirely, no question asked**, when it would only be noise: a **docs-only** diff
  (Phase 3 short-circuits those anyway), or the caller already said `no-verify` / already answered.

## Phase 3 — Review (multi-specialist fan-out)
Review the PR with the **`/review` fan-out**, not a single reviewer — follow the
playbook in that command exactly:
1. **Classify the diff** (its Step 1): note which side(s) are touched (frontend / backend)
   and the privacy / architecture / copy content gates. If the diff is **docs-only**,
   short-circuit — no specialist review, say so, and go straight to Phase 5.
2. **Launch the applicable specialists IN PARALLEL, in a single message**, in contributor
   mode (findings only, no per-agent report, no per-agent verdict). Which ones apply is
   decided by `/review` Step 2. security-specialist is **always** launched.
3. **Refute the blockers before reporting** (its Step 2.5). This is **automatic and needs no
   argument**: if the fan-out raised at least one 🔴, each one gets two independent refuters —
   one checking whether the specialist misread the code, one checking whether the concern is
   already handled elsewhere. A finding is dropped only if **both** refute, and every drop lands
   in the report's *Refuted findings* section. **A clean review costs nothing** — no blockers
   means no refuters launched. `audit` widens it to 🟡 as well; `no-audit` skips it.
   - **STOP if refutation would clear the LAST blocker.** That flips the verdict to `approve`
     and would let Phase 5 merge on two agents' say-so. Put the claim and both refuters' reasons
     to the user and let them choose drop-and-approve or keep-and-fix — see `/review` Step 2.5.
     Blockers 2..N are dropped quietly; only the merge-deciding one is escalated.
4. **Merge** every specialist's findings into ONE report at
   `<root>/reviews/pr-<N>-<YYYY-MM-DD>.md` (🔴/🟡/🟢, blocker-first, each finding keeping its
   file path). Verdict is `request-changes` if ANY specialist raised a 🔴, else `approve`;
   `blockers` = the total 🔴 count.

- If verdict is **approve with zero blockers**, skip Phase 4 and go to Phase 5.

## Phase 4 — Fix (only if there are findings)
Work the report the way `/fix` does:
- Re-verify each finding against the current code BEFORE changing anything (confirmed / stale / wrong / needs-judgment). The report's `verified:` frontmatter says what refutation already covered — `blockers` (🔴 only), `all` (🔴+🟡) or `none`. A **fast confirm** is enough for anything it covered; keep full strength for everything it didn't, for anything annotated `(contested: …)`, and always for the stale check.
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
- **The green is against the CURRENT base.** `git fetch origin && git rev-list --count HEAD..origin/<base>` — if it's not `0`, the base moved after those checks ran (typically a sibling session merged first) and the green proves nothing about the merged result. Update the branch, push, and wait for checks again before merging. This is the one condition that makes parallel sessions safe to merge without coordinating: whoever gets there second re-verifies.

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

## Phase 5.6 — Cut a release for what just landed (hook-driven, non-fatal)
A lap that merged and then stopped leaves the project's version describing a past that no longer
exists. **One release per lap** keeps a version number meaning "a session's work" rather than
"sometime in the last month" — and it has to happen here, because a release nobody remembers to cut
is a release that doesn't happen. (Seen in the wild: a release proposal open for three weeks while
1,637 commits landed behind it.)

```bash
RELEASE="$(jq -r '.hooks.release // empty' relay.config.json 2>/dev/null)"
```
- **Hook set** ⇒ dispatch it. The project owns the mechanics entirely — merging a release-bot's
  proposal, running a bump script, tagging. Relay only decides *when*.
- **No hook** ⇒ skip silently. Do **not** invent a release: guessing a version scheme, writing tags,
  or editing version files in a repo that never asked is exactly the ownership Relay doesn't take.
  If the repo shows an obvious release mechanism (an open release-bot PR, a release workflow, a
  `release` script) you may **mention it once** and offer to wire `hooks.release` via
  `authoring-skills` — then carry on either way.
- **Non-fatal.** A failed or skipped release never blocks the handover; report it and continue.

Docs-only laps and laps that shipped nothing user-visible don't need a release — say so and skip.

## Phase 5.7 — Persist what the lap taught (policy-driven, non-fatal)
The merge is in; before handing over, this is the moment to compound. **First decide whether the lap
taught something durable** — a review finding that should become a guardrail rule, a design pattern
worth stewarding, a non-obvious decision, **or a user-visible change worth a release note**. If it
taught *nothing* durable and shipped nothing user-visible, say so and skip — regardless of policy.

If the gate fired, `persist.cadence` decides what happens next — read it (committed, project-wide;
a flat `persist: "…"` from an earlier version is still honoured):
```bash
PERSIST="$(jq -r 'if (.persist|type)=="object" then .persist.cadence else .persist end // "ask"' relay.config.json 2>/dev/null || echo ask)"
```
- **`ask`** (default) — **offer `/persist`**; run it only on a yes.
- **`always`** — run `/persist` without asking. (The gate still applies: `always` means "don't ask,"
  not "run on an empty lap.")
- **`never`** — skip the offer entirely.

`/persist` harvests into the knowledge layer (guardrails `extends` overlay + design system + AI memory,
+ ADRs/procedures/how-tos at `persist.level: full`) and drafts a human-readable **release note** — all
to durable docs **outside `<root>/`**. Non-fatal — never block the handover on it, whatever the policy.
(At 1.0 this becomes a first-class phase of `ship`; today it's this policy-driven step.)

## Phase 6 — Handover (and end-of-session tidy)
The PR is now merged, so proceed directly into the handover. Run `/handover` end to end:
its Step 0 guard passes (PR is MERGED), it generates the cold-start handover, commits it to
main, prints the compact summary, **and does the end-of-session housekeeping** — its Step 4.5
archives superseded handovers + old PR reviews **and trims done rows off the board** (both gated by
`tidy.level`; the first trim in a repo asks once), and its Step 6 exits this thread's topic worktree
(keeping it on disk for the topic's next slice) and prunes dead worktree entries. There is no
separate cleanup command; this is it.

Then tear down what **this session** brought up, and only that:
- any throwaway test fixture Phase 1 started;
- the local test environment, **if this session started it** — dispatch `hooks.env.down`, the
  project's own stack command. **If Relay didn't bring it up here, leave it alone.** A local stack
  is routinely shared with a sibling session, and killing one out from under a live thread is
  exactly the damage this rule prevents. No `hooks.env.down` declared ⇒ nothing to do.

That closes the session.

**Reflect (loop edge).** Shipping is a lap's end, not the loop's. If this lap surfaced a new idea or
changed your mind about the work, say so and re-enter: `/relay:explore` (a genuinely new idea) or
`/relay:refine` (this idea, changed) — with the result as input. That re-entry is the spiral.
