---
description: "Maintainer-only: pool the Relay trail across your dogfooding repos and analyse it into a ranked friction report — evidence-grounded ideas for improving Relay itself."
argument-hint: "[out-report-path]  ·  gather-only  ·  --print-hook"
---

## Usage
`/reflect [out-report-path | gather-only | --print-hook]`

This is a **maintainer tool**, not a shipped Relay command. It lives in this repo's `.claude/`, so
it's available to Relay contributors working *in the Relay repo* — it never ships to plugin users.
Its job is to improve **Relay itself** from real usage, instead of from whoever last remembered a
friction.

| Argument | Effect |
|---|---|
| *(empty)* | Gather the pooled trail, analyse it, write the report |
| `<path>` | Same, writing the report to `<path>` (default `reflect/reports/<date>.md`) |
| `gather-only` | Run the gather step and stop — just produce the pooled file |
| `--print-hook` | Print the phase-2 movement-logging hook snippet and stop |

## What it reads
Your dogfooding repos, listed in `./reflect.repos` (one path per line — `cp reflect.repos.example
reflect.repos` first). For each, it pools the durable Relay trail — board, `decisions.md`, handovers,
`reviews/`, `audits/`, the `movements.jsonl` log if phase-2 logging is installed, CHANGELOG — plus
`git log`. All of this is **local maintainer data**: the pooled file and the report are gitignored and
must never be committed.

## Step 1 — Gather the pooled trail
Run the gather script (it reads `reflect.repos`, or takes repo paths as args):
```bash
POOLED="$(./scripts/reflect-gather.sh)"
```
If it complains there's no `reflect.repos`, stop and tell the user to `cp reflect.repos.example
reflect.repos` and list their real projects — don't invent repo paths. If `$ARGUMENTS` is
`gather-only`, report `$POOLED` and stop here. If it's `--print-hook`, run
`./scripts/reflect-install-hook.sh --print` and stop.

## Step 2 — Analyse the pooled file into a friction report
Read `$POOLED` and look for **patterns across laps and repos**, not one-off events. A single repo, or
a single lap, is noise; a pattern that repeats is signal. Work these lenses (skip any the data can't
support — say which you skipped and why):

- **Command mix & sequence** — which commands run, in what order, which never run at all. A command
  nobody reaches is either undiscoverable or unneeded.
- **Overridden `/next` picks** — where the trail shows the ⭐ recommendation and the item actually
  started (the worktree/branch that appeared, the next handover's slug) *disagree*. Persistent
  override ⇒ the ranking is miscalibrated (e.g. the maturity lens too weak/strong).
- **Gate friction** — STOP gates hit repeatedly, decisions that went `challenge`/`solo` vs `ask`
  (from `decisions.md`), autonomy budget exhaustion, re-runs of the same command (a flow that didn't
  land first time).
- **Abandoned flows** — a lap that reached `/next` or `/test` but never a merge/handover; a brief that
  never became a board item; a review whose findings were never fixed.
- **Review & refutation calibration** — blocker rates, how often refuters drop findings (the *Refuted*
  section), whether the same specialist gets refuted the same way repeatedly.
- **Lap shape** — rough time-in-flight between a topic's first and last movement (needs phase-2
  timestamps); recurring re-slicing (slices that were too big).

For **each pattern**, write: the **observation**, the **evidence** (cite repo + file/commit — never
assert without a source), a **hypothesis** for the cause, and a **concrete suggested Relay change**
(the command/file it would touch, in one line). Rank by how much friction the pattern causes ×
how often it recurs.

## Step 3 — Write the report
Write to `$ARGUMENTS`-as-path, else `reflect/reports/<date>.md` (`mkdir -p reflect/reports`; get the
date from `date +%Y-%m-%d-%H%M`). Structure:
- a one-paragraph summary (repos and laps covered, headline finding),
- a **ranked findings table** — `# · pattern · repos seen · friction · suggested change`,
- a section per finding with observation / evidence / hypothesis / suggestion,
- a **Thin-data caveat**: name every lens you couldn't run for lack of data (usually the phase-2
  ones until logging is installed), so the report never reads as more complete than it is.

## Step 4 — Present and stop
Show the ranked findings table in the terminal and point at the written report. Then **offer** to turn
the strongest one or two findings into `/relay:explore` briefs **against the Relay repo** — offer, do
not auto-write. A usage pattern is a *hypothesis*, not a verified fix; it earns a brief only once you've
eyeballed the evidence. Never edit any Relay command as a side effect of reflecting.

## Phase 2 — installing movement logging (optional, do this once)
The lenses that need the movement stream (overrides, abandonment, timing) stay thin until the logger
is installed in the repos you work in. It's a Claude Code `UserPromptSubmit` hook that appends one
JSON line per Relay command to `<repo>/<root>/movements.jsonl`:
```bash
./scripts/reflect-install-hook.sh ~/Documents/castlesERP ~/Documents/other-project
./scripts/reflect-install-hook.sh -          # or user-global: log Relay commands in EVERY repo
./scripts/reflect-install-hook.sh --print    # just show the snippet
```
Add `<root>/movements.jsonl` to each target repo's `.gitignore`. The logger never fails a prompt —
a logging hiccup exits cleanly and never blocks your work. Outcomes aren't captured at log time; Step 2
reconstructs them by correlating the movement stream against the durable trail.
