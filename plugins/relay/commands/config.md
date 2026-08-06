---
description: See and set Relay's optional config with guidance — it proposes what's worth setting for THIS repo and walks it as Q&A. The config front door; nothing here ever gates getting to work.
argument-hint: "[a single area to configure, e.g. 'session' | 'guardrails' | 'hooks'; omit for the full guided pass]"
---

> **Output** ([[conventions]]): honour `verbosity` (a per-call `terse`/`verbose` word in `$ARGUMENTS`, else `relay.config.local.json` `.verbosity`, else `normal`) — at **terse**, emit only STOP-gate questions and the final landing, no narration or intermediate recaps. Render every list as a **GFM markdown table**, never stacked `Field: value` records or ASCII-rule separators; keep cells terse, overflow to numbered footnotes.

The **config front door**. Relay's guiding rule is **opt-in depth, never a gate** ([[conventions]]):
nothing here is required to start work — absent keys are sensible defaults. This command exists for
the *"now I want more"* moment: it **shows what's set and what's available**, **proposes what's worth
setting for this specific repo**, and **walks the ones you agree to as questions**. It never
interrogates you into a corner — decline anything and the defaults stand.

## Step 0 — Resolve current state
```bash
ROOT="$(jq -r '.root // "relay"' relay.config.json 2>/dev/null || echo relay)"
```
Read both surfaces: `relay.config.json` (committed — `root`, `paths`, `guardrails`, `hooks`) and
`relay.config.local.json` (gitignored — `session`, `verbosity`). If `$ARGUMENTS` names one area, scope
the whole run to just that.

## Step 1 — Show current config vs what's available
Render one table: each config area, its **current value** (or "default: …" if unset), and a one-line
"what it does". This alone answers "what *is* set / what *can* I set?" — the discoverability the empty
default file can't give:

> | Area | Current | What it does |
> |---|---|---|
> | `root` | `relay` (default) | where durable state lives |
> | `session` | _unset_ → full fan-out | slice size + fan-out width (`small`/`medium`/`large`) |
> | `verbosity` | `normal` | how much Relay narrates |
> | `guardrails` | _none_ | per-dimension "what good means" the reviewers check |
> | `hooks` | _none_ | dispatch your own `.claude/` commands/skills at Relay phases |
> | `paths` | _none_ | relocate a logical path (e.g. `knowledge` → `docs/`) |

## Step 2 — Propose what's worth setting for THIS repo (don't offer a blank menu)
Inspect the repo and **recommend only the relevant** areas, with the reason — this is the difference
between a helpful proposal and a questionnaire:
- An API surface / a design-system package present ⇒ suggest **guardrails** (or defer to `/guardrails`).
- Existing `.claude/commands` or skills (e.g. a `test-stack`) ⇒ suggest **hooks** (via `/adopt`'s
  reconciliation).
- Deliverable docs living outside `<root>/` ⇒ suggest a **`paths`** override.
- Always offer the cheap driver prefs: a default **`session`** size and **`verbosity`**.
Present the proposal and **STOP** — the user picks which (if any) to set now; declining is a first-class
answer that changes nothing.

## Step 3 — Walk the agreed areas as Q&A, then write
For each area the user picked, ask the **judgement calls only** (never what's readable from the repo),
then write it to the right surface:
- **`session` / `verbosity`** → `relay.config.local.json` (create it; it's gitignored). One question each.
- **`guardrails`** → **hand off to `/guardrails`** (its discover-then-ask interview is the deep version;
  don't reimplement it here — launch it).
- **`hooks`** → **hand off to `/adopt`**'s `.claude/` reconciliation (keep / remove-redundant /
  keep-and-hook), which writes the `hooks` map.
- **`root` / `paths`** → confirm the target, then **merge surgically** into `relay.config.json`
  (preserve every existing key). Moving the root relocates durable state — treat as a real move
  (safety net, see [[conventions]]); usually `paths` overrides are enough.

Write **only what was agreed**; leave everything else at its default (absent). Never scaffold empty
placeholder keys — absent *is* the default, and a blank key is just clutter.

## Step 4 — Report
State what changed, in which file, and the effective config after (current-vs-default table again if
useful). Remind the user the rest stays at sensible defaults until they want it, and that any of this is
re-runnable — `/relay:config` is safe to run anytime to review or adjust.
