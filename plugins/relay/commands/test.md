---
description: After a chunk of work, open (or reuse) a PR and write a consistent, structured test plan — preconditions, happy path, and the edge/error/tenant-isolation cases an LLM skips by default. Can then DRIVE the happy path in the browser against the preview and report. 'plan-only' prints the checklist without a PR.
argument-hint: "[focus/area · a PR number · 'plan-only' (checklist alone) · 'drive'/'run' (also run it in the browser)]"
---

Answer one question for whoever tests this next: **if we deploy this change, what exactly
should we click through — including the ways it could break — to trust it?** Produce a plan
that's the *same shape every time*, so testing a Relay PR is muscle memory — then, if asked,
take it for a drive in the browser.

This collapses the two asks you'd otherwise type by hand — *"open a PR"* and *"tell me what to
test"* — into one keystroke, and it's robust to the PR already existing or not: it reuses an
open PR or opens one, never a second.

**Modes** (from `$ARGUMENTS`):
- **Default (PR mode)** — ensure a PR (reuse or open) and write the plan into it. Then, unless
  the caller already said otherwise, **ask once** whether to drive it (Step 6).
- **`plan-only`** — just produce the plan and print it; **do not open, touch, or require a PR**.
  Use when the work isn't PR-ready, or you only asked for "what to test". No drive, no ask.
- **`drive`/`run`** — do PR mode, then **drive the plan in the browser** (Step 6) without asking.

This is NOT `/ship`. `/ship` ships (merges). `/test` **stops at a tested-but-unmerged
PR** (or a printed checklist) — a human (or Claude, in drive mode) exercises it against the
preview before anyone merges. Merge later with `/ship` or by hand once it passes.

## Step 1 — Ensure a PR (committed work only; never merge here)
**`plan-only` mode → skip this whole step.** Don't open, push, or require anything — go straight
to Step 2 and emit the plan to the terminal in Step 5. (Still read the diff; the plan is only as
good as Step 2, PR or no PR.)

1. If `$ARGUMENTS` is a **PR number**, use that PR and skip to Step 2.
2. `git branch --show-current`. If it's `main`/`master`/the default branch, **STOP** — there's
   nothing to open a PR for.
3. `gh pr view --json number,url,state,isDraft` — if a PR already exists for this branch, use it.
4. No PR yet:
   a. `git status`. **If the tree is dirty, STOP** — committing is the user's call. Ask them to
      commit (or stash), then re-run. Don't commit for them.
   b. Clean tree: push if needed (`git push -u origin <branch>`), then `gh pr create --fill
      --draft`. Keep it a **draft** — this command's whole point is a *pre-merge* test pass.

## Step 2 — Read the change (ground every step in the real diff, not guesses)
A plan invented from the PR title is worthless. Read what actually changed — from the **right**
source for the mode:
1. Read the diff and its meaningful hunks:
   - default / drive: `git diff origin/main...HEAD --stat` (the branch's committed change);
   - **PR-number** argument: `gh pr diff <n>` (you may not be on that PR's branch — the branch
     diff would be wrong or empty);
   - **plan-only**: also `git diff HEAD` and `git status --porcelain` for **uncommitted + untracked**
     work — plan-only exists for not-yet-PR-ready trees, whose changes aren't in the committed diff.
2. Inventory what the diff **touches**, because each maps to test cases:
   - user-facing surfaces — routes/screens, endpoints, CLI, emails, background jobs;
   - data-model changes — new/changed fields, migrations, constraints;
   - auth / permission touchpoints — role checks, ownership, visibility;
   - multi-tenant boundaries — anything keyed by tenant/org/workspace;
   - external integrations — third-party calls, webhooks, payments.
3. Read the project's `CLAUDE.md` for the **domain invariants** (tenant model, roles, the rules
   that must never break). This is what makes the non-happy-path cases *real* for this project
   rather than generic filler.

## Step 3 — Detect the preview-deploy hook (the project overlay)
Most repos have no preview deploy; some (e.g. a PR-triggered preview) do. Discover, don't assume:
- Check `CLAUDE.md`/README for a documented **preview-URL pattern + how to authenticate to it**,
  and `gh pr checks <n>` for a deploy/preview check that publishes a URL.
- **Preview exists** → the plan's "how to reach it" steps use the **preview URL** and its login,
  and it's the target the drive step (Step 6) exercises. Grab the actual URL from the PR's deploy
  check once it's green (or leave a clear `<preview-url>` placeholder + how to find it if the
  deploy is still running).
- **No preview** → fall back to **local run** steps (the project's run command from `CLAUDE.md`).
- Say which mode you used in the Report. Never hardcode a URL or login — read it from the project.

## Step 4 — Build the plan (the fixed structure IS the value)
Always the same headings, in this order, so every PR reads the same. Include a category **only if
the diff actually implicates it** — don't pad, but don't quietly drop a category the change does
touch. Every step is a concrete action + its expected result, as a `- [ ]` checkbox to tick.

1. **What changed** — 1–3 plain-English bullets, framed as a user sees it.
2. **Preconditions** — the state/data/roles/tenants needed first; the preview URL (or local run)
   and how to log in.
3. **Happy path** — numbered, click-level steps that reach the actual screen/endpoint changed,
   each with the expected result.
4. **Non-happy paths** — the discipline; this is what an LLM skips by default, so be deliberate.
   Enumerate the ones the diff touches:
   - **Invalid / boundary input** — empty, too long, wrong type, malformed, zero/negative.
   - **Error & failure states** — network/backend failure, 4xx/5xx, timeout, partial save, retry.
   - **Auth / permission** — unauthenticated, wrong role, expired session, forbidden action.
   - **Tenant / data isolation** — as tenant B, can you read/edit tenant A's data? (Always test
     this on a multi-tenant project — it's the highest-cost, easiest-missed failure.)
   - **Concurrency / staleness** — two tabs, double-submit, edit-then-someone-else-edited, refresh
     mid-operation.
   - **Idempotency** — re-submit / replay where money, state, or external calls are involved.
   Each with a concrete step and the **safe** result you expect (rejected, scoped out, no leak).
5. **Regression watch** — nearby surfaces this change could dent; quick sanity checks.
6. **Not covered** — be honest about what this plan does NOT test (perf, browsers, etc.).

## Step 5 — Deliver the plan
**`plan-only` mode → print the plan straight to the terminal** as a `## 🧪 Test drive` block, then
**skip Step 6 and go to Step 7**. Don't create a scratch file, don't touch git or `gh`.

**PR mode → write it into the PR body (idempotent):**
- Wrap it as a `## 🧪 Test drive` section. If the body already has one, replace that section and
  leave everything above/below it intact; else append it. Use `gh pr edit <n> --body-file <tmp>`
  with the merged body (write the new body to a scratch file first).
- **Don't change the PR's draft/ready state** — only a PR *you* opened in Step 1 is a draft; leave
  a reused PR as you found it. Never `gh pr ready`, never merge — it gets exercised first.

## Step 6 — Drive it in the browser (explicit, or ask once)
**Decide whether to drive:**
- `drive`/`run` in `$ARGUMENTS` → drive, no question.
- `plan-only`, or the caller already said not to → **skip** this step.
- **Otherwise ask once and STOP for the answer:** *"Want me to drive the happy path against the
  preview in Chrome and report back? (y/N)"* Skip on no; a plan alone is a complete result.

**If driving:**
1. **Need a reachable target.** Use the preview URL (Step 3) once its deploy check is green, or a
   local run if that's the mode. If the preview is still building or you want it gated (incl.
   security) before trusting it, run **`/deploy <n>`** first — it waits for, health-checks, and
   security-gates the preview, then hands back a verified URL. If nothing's reachable yet and you
   don't want to wait, say so and **skip the drive** rather than blocking — the plan still stands.
2. **Use the Claude-in-Chrome browser tools** (load them via ToolSearch if they're deferred; open
   a fresh tab, don't hijack the user's). Record with `gif_creator` — grab a few frames before
   and after each action so the clip is watchable.
3. **Run the happy path**, then the **safe** non-happy-path checks — the ones that *should fail
   closed*: invalid input rejected, permission-denied for the wrong role, a tenant-B **read**
   probe that must return nothing. These prove the guard works without changing data.
4. **Guardrails — do NOT let the drive cause harm:**
   - **No irreversible/destructive actions** (deletes, payments, real emails/SMS, publishing)
     unless the caller explicitly authorised them. List them as *"not driven — verify by hand."*
   - **Isolation probes stay read-only** — attempt to *view* another tenant's data, never mutate.
   - **Avoid native `alert`/`confirm`/`prompt` dialogs** — they freeze the browser session. If a
     step would trigger one, note it and skip rather than click into it.
   - If browser tools error 2–3 times or a page won't load, **stop and report** what you got —
     don't thrash.
5. **Record the outcome per step:** pass / fail / blocked, with what you observed. Tick the
   `- [ ]` boxes that passed. In PR mode, post a **results comment** on the PR (`gh pr comment`)
   with the pass/fail summary and update the ticked boxes in the body. Note: `gh` can't attach a
   binary — give the **GIF's local path** in the comment and the terminal report (the user drags it
   into the PR if they want it embedded); don't paste a local path as if it renders. In
   `plan-only`/terminal, just print the summary.

## Step 7 — Report
One compact block: **where the plan is** (the PR url, or "printed above"), the **mode** (preview
vs local), and a count — *N happy-path steps, M non-happy-path cases across <categories>*. If you
drove it, add a one-line **pass/fail tally** and the **GIF path**. If a preview URL is live, print
it so the user can click straight through; if the deploy is still running, say where it'll appear.
Don't recap the plan itself — it's on the PR (or just above).
