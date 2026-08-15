---
name: authoring-skills
description: >-
  Use when adding a new command, agent, or skill to a Relay-style workflow — or
  when a repeated instruction the user keeps giving should be captured as a
  reusable command instead of re-typed each session. Produces a well-shaped
  command/agent file that matches Relay's conventions (clear frontmatter,
  step-numbered procedure, explicit STOP gates, findings-only review agents).
---

# Authoring a Relay command, agent, or skill

Relay is just Claude Code plugin content — Markdown files with frontmatter. Adding to it
means writing one more file in the right shape. This skill keeps new additions consistent
with the ones already there.

## First: which of the three is it?

- **Command** (`commands/<name>.md`) — a user-invoked `/name` procedure. Reach for this when
  the user keeps giving the same multi-step instruction ("run the tests, open a PR, review
  it…"). Capture it once as a command.
- **Agent** (`agents/<name>.md`) — a specialist the main session dispatches for a bounded
  job (usually review). Reach for this when a task needs an independent perspective or a
  fresh context window, not more steps in the main thread.
- **Skill** (`skills/<name>/SKILL.md`) — reference knowledge or a procedure the model should
  pull in *situationally* (not by an explicit `/command`). Reach for this when the trigger is
  a kind of task ("whenever you touch a chart…"), not a keystroke.

## The shape of a good command

1. **Frontmatter**: a one-line `description` (shown in the picker — say what it does, not how),
   and an `argument-hint` if it takes arguments. Add `allowed-tools` only to *restrict* a
   command to a safe set (as `/handover` does). **Never add a `name:`** — a plugin command is
   named by its filename and `name:` *replaces* that name, dropping the command out of the `/`
   menu under the name people type. Short names come from generated twin files instead
   (`scripts/gen-short-names.sh` in the Relay repo).
2. **A `## Usage` block** directly after the frontmatter: the signature, a GFM table of one row
   per argument, the shared per-call words, the config keys it reads, and the `?` gate that
   prints the block verbatim and STOPs. Copy the shape from any existing command — it's what
   `/relay:<cmd> ?` and `/relay:help <cmd>` both surface, so it has to stay in step with the
   `argument-hint` above it.
3. **One-sentence statement of intent** — what question this command answers.
4. **Numbered steps.** Each step is one coherent move. Put the *why* in a clause, not a
   paragraph. Front-load reads (fetch state) before writes.
5. **Explicit STOP gates.** Mark every point where the model must pause for the user with a
   bold **STOP** and say exactly what to wait for. The value of these commands is as much in
   where they *pause* as in what they do.
6. **A final "Report" step** that says what to tell the user — outcome first, terse.

## The shape of a good review agent

Relay's review agents all follow one contract, and a new one should too:
- **Findings only.** In a fan-out (`/review`), an agent returns findings — no report file,
  no verdict. The command merges them. Say this in the agent's own description. This is also the
  contract for a **project-declared review agent**: ship it as a `.claude/agents/*.md`, then register
  it in `relay.config.json` under `review.agents` (`{ name, gate, tier, scope, priority }`) and
  `/review` folds it into the fan-out alongside the built-ins (see [[conventions]] → Custom review
  agents). A declared agent that writes its own report or emits a verdict breaks the merge.
- **Severity-graded**: 🔴 blocker · 🟡 should-fix · 🟢 nit. Each finding carries a `file:line`.
- **Stack-agnostic**: discover the actual stack/conventions from the project's `CLAUDE.md` and
  code rather than hardcoding a framework. This is why Relay's agents port cleanly between repos.
- **Scoped, and honest about its edges**: name what it covers AND what it explicitly leaves to
  a sibling agent ("does NOT cover X — that's Y's job; pair as needed").

## Process

1. **Confirm it's worth capturing.** A one-off doesn't need a file. Capture what recurs.
2. **Copy the nearest existing file** as a skeleton — don't start blank. Match its voice,
   its step density, its STOP-gate style.
3. **Strip anything project-specific** if this is going into the shareable plugin: no
   hardcoded package paths, no vendor-specific commands. Discover them at runtime instead.
4. **Write the frontmatter description last**, once the body tells you what the thing really does.
5. **Dry-run it in your head**: walk the steps against a real recent task. Where would it stall,
   over-ask, or skip a gate? Fix those before shipping.
6. **Register nothing** — plugin commands/agents/skills are discovered by their location. Just
   put the file in `commands/`, `agents/`, or `skills/<name>/`.
