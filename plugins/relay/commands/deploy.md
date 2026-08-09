---
description: Orchestrate and verify the PR preview the project's OWN CI produces — ensure it built, wait for it, smoke-check it's healthy, and gate it (including security) — then hand a trustworthy preview URL to /test. Never owns deployment. Phase (h).
argument-hint: "[pr-number — omit to use the current branch's PR]"
---

> **Output** ([[conventions]]): honour `verbosity` (a per-call `terse`/`verbose` word in `$ARGUMENTS`, else `relay.config.local.json` `.verbosity`, else `normal`) — at **terse**, emit only STOP-gate questions and the final landing, no narration or intermediate recaps. Honour `audience` (a per-call `plain`/`informed`/`expert` word in `$ARGUMENTS`, else `relay.config.local.json` `.audience`, else unset) — how much depth surfaces in your **terminal** output; it never thins a **written artifact** (brief, report, ADR, handover), which always keeps full depth. `plain` = executive summary: the decisions and what you need from the user, minimal jargon; `informed` = lead with the decisions and what changed, keep the corrections and open questions that need the user, defer exhaustive evidence/`file:line` tables to the artifact; `expert` = full depth in the terminal too; unset ⇒ today’s default (no shaping). Never drop a STOP-gate question or the decision itself. Render every list (candidates / findings / plan rows) as a **GFM markdown table**, never stacked `Field: value` records or ASCII-rule separators; keep cells terse, overflow to numbered footnotes.

Make a PR's **preview** ready and trustworthy to test against. This is phase (h): it sits between
build/review and `/test`, and its whole value is turning "there might be a preview building
somewhere" into "here is a verified, security-gated URL, click through it." It is deliberately
**thin — it never deploys anything itself.** It only ever drives the **project's own pipeline**
(its PR-triggered preview, its CI checks), which is exactly what lets one command span a Vercel
preview, a container on a review env, or any other setup without special-casing a vendor.

> **The boundary that keeps it portable.** `/deploy` **orchestrates and verifies**; it does not own
> deployment. If the project has no preview mechanism, `/deploy` says so and stops — it does not
> invent one, spin up infrastructure, or push to an environment. Discover the pipeline; use the
> pipeline; never replace it.

## Step 0 — Identify the PR (a preview needs one)
`$ARGUMENTS` is a PR number; if empty, use the current branch's PR (`gh pr view --json
number,url,state,headRefName`). A preview is a **PR artefact**, so:
- **No PR for this branch ⇒ STOP** — point at `/test` (which opens one) or `gh pr create`.
  `/deploy` verifies a preview; it doesn't open PRs.
- A merged/closed PR ⇒ note it; a preview may no longer exist. Ask before proceeding.

## Step 1 — Discover the preview mechanism (the project overlay — don't assume a vendor)
Find out **how this project previews a PR**, from the project itself:
- `CLAUDE.md`/README for a documented **preview-URL pattern + how to authenticate to it**.
- `gh pr checks <n>` for a **deploy/preview check** that builds and publishes a URL.
- the CI config (`.github/workflows`, or whatever the repo uses) for a preview/deploy job and how
  it's triggered (automatic on PR, a label, a `workflow_dispatch`, a comment command).

**No preview mechanism found ⇒ STOP** and say so plainly: this project has no PR preview, so there's
nothing for `/deploy` to verify — testing falls back to a **local run** (`/test` handles that
path). Don't fabricate a deploy. This is the honest edge, not a failure.

## Step 2 — Ensure the preview build is running (through the project's own trigger only)
- **Auto-triggered on PR (the common case):** confirm the preview job actually started for this
  PR's head SHA (`gh pr checks <n>` shows it queued/in-progress/done). If it's there, go to Step 3.
- **Not started, but the project exposes a manual trigger** you discovered in Step 1 (a
  `workflow_dispatch`, a label, a re-run): fire it **through that mechanism** — `gh workflow run
  <file> …`, `gh pr edit <n> --add-label <preview-label>`, or `gh run rerun <id>`. Only ever the
  project's own trigger.
- **No build and no way to trigger one ⇒ STOP** — report how a human kicks the project's preview,
  and stop. Never hand-build or hand-deploy.

## Step 3 — Wait for it to finish (bounded, non-thrashing)
Poll the preview/deploy check until it reaches a terminal state — `gh pr checks <n> --watch`, or a
bounded poll loop on `gh pr checks <n>` / `gh run view`. Report progress only if it changes what the
user would do (still building after a long wait; a genuine blocker) — otherwise stay quiet and wait.
- **Build FAILED ⇒ STOP.** Surface the failing check name and its logs (`gh run view <id> --log-failed`
  or the check's details URL). **Do not bless a broken preview** — a green testable preview is the
  whole point; a failed one goes back to fix, not forward to test.

## Step 4 — Verify the preview is actually healthy (not just "check went green")
A green deploy check is necessary, not sufficient — verify the thing responds:
1. **Resolve the real preview URL** — from the deploy check's output/deployment, or the project's
   documented URL pattern. Never hardcode one; read it from the project.
2. **Smoke-check it** — the app root returns a success status (or the project's documented healthcheck
   passes). If it 4xx/5xx's or won't load, **STOP** and report — a check can pass while the app is
   broken behind an auth wall or a bad env var.

## Step 5 — Security gate (phase h's gate — content-gated on what the project actually has)
Don't bless a preview that failed the project's own security bar:
- **Required security checks green.** If the project's CI runs security checks (SAST, dependency/secret
  scan, a security workflow — discover them, don't assume), require them **passing** for this SHA
  before declaring the preview usable. A **failing** security check ⇒ **STOP** and surface it — this
  is a gate, not a warning.
- **The preview is a preview.** Confirm the target is an **ephemeral/preview** environment, not
  production or a shared staging with real data — `/deploy` must never bless pushing an unreviewed
  PR at prod. If you can't tell it's non-prod, **STOP and ask** rather than assume.
- **No security checks configured ⇒ note the gap** in the Report (a candidate lesson for `/persist`
  to turn into a guardrail), but don't fabricate a gate you can't run.

## Step 6 — Report and hand off
State, outcome-first:
- the **verified preview URL** and how to authenticate to it (from Step 1),
- **what gated it** — the checks that passed, the security checks that passed (or the noted gap), and
  that it's confirmed a preview env,
- the handoff: **`/test <pr> drive`** now exercises the happy path (and the safe non-happy-path
  probes) against this URL.

If anything stopped the flow (no mechanism, build failed, unhealthy, security gate failed), report
**that** instead — which gate stopped it and the one concrete next step to clear it. A preview that
fails a gate is a caught problem, not a dead end.
