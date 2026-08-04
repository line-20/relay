# Authoring your own commands and agents

Relay is meant to be extended. It's just Claude Code plugin content — Markdown files with
frontmatter — so adding to it means writing one more file in the right shape. The repeated
instruction you keep typing at Claude is a command waiting to be born.

There's a skill that does this for you interactively. In a session:

```
Use the authoring-skills skill to add a command that <what you keep doing>.
```

It'll ask which of the three kinds you want, copy the nearest existing file as a skeleton,
and shape it to match Relay's conventions. The reference below is the same guidance, for
reading.

## The three kinds

- **Command** (`plugins/relay/commands/<name>.md`) — a user-invoked `/name` procedure. Use
  when you keep giving the same multi-step instruction. The whole payoff is capturing it once.
- **Agent** (`plugins/relay/agents/<name>.md`) — a specialist the main session dispatches for
  a bounded job (usually review). Use when a task needs an independent perspective or a fresh
  context window, not more steps in the main thread.
- **Skill** (`plugins/relay/skills/<name>/SKILL.md`) — knowledge or a procedure pulled in
  *situationally* by the model, not by an explicit `/command`. Use when the trigger is a kind
  of task, not a keystroke.

## What makes a good command

1. **A one-line `description`** in the frontmatter — what it does, not how. It's what shows in
   the picker.
2. **Numbered steps**, each one coherent move, the *why* in a clause not a paragraph. Reads
   before writes.
3. **Explicit STOP gates** — bold **STOP**, and say what to wait for. Where a command pauses
   for you is half its value.
4. **A final "Report" step** — outcome first, terse.
5. **Restrict tools** with `allowed-tools` only when the command should be sandboxed (see
   `/handover`).

## What makes a good review agent

Relay's agents share one contract; a new one should too:

- **Findings only** in a fan-out — no report file, no verdict. `/review-pr` merges them.
- **Severity-graded**: 🔴 blocker · 🟡 should-fix · 🟢 nit, each with a `file:line`.
- **Stack-agnostic** — discover the stack and conventions from the project's `CLAUDE.md` and
  code, never hardcode a framework. This is *why* Relay's agents port between repos unchanged.
- **Honest about its edges** — name what it covers and what it leaves to a sibling agent.

## Keeping the shareable set clean

If you're contributing back to the plugin (rather than keeping a command private to your
repo), strip anything project-specific: no hardcoded package paths, no vendor-specific
commands. Discover them at runtime from `CLAUDE.md` instead. A command that names your repo's
folders is a fine *local* command — put it in your repo's own `.claude/commands/` — but it
doesn't belong in the portable plugin.

> **Local vs shared.** Your repo's own `.claude/commands/` and `.claude/agents/` sit
> alongside Relay's and can freely reference your project's specifics. Keep the project-coupled
> ones there; contribute only the portable ones upstream.
