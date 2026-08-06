---
description: Build or consult a reference frame — how other systems, products, standards and people handle this problem — and cross-check your approach against it for alignment, divergence, and blind spots.
argument-hint: "[a topic, a brief slug, or a design decision to check]"
---

> **Output** ([[conventions]]): honour `verbosity` (a per-call `terse`/`verbose` word in `$ARGUMENTS`, else `relay.config.local.json` `.verbosity`, else `normal`) — at **terse**, emit only STOP-gate questions and the final landing, no narration or intermediate recaps. Render every list (candidates / findings / plan rows) as a **GFM markdown table**, never stacked `Field: value` records or ASCII-rule separators; keep cells terse, overflow to numbered footnotes.

Sanity-check your thinking against the world before you commit to it. This command builds a
durable **reference frame** — a curated picture of how *others* handle a problem (competitor
products, established prior art, standards and patterns, known expert approaches, and the
lessons from what failed) — and cross-checks your current approach against it. The frame is
reusable: every run reads and extends it, so the knowledge accrues instead of being
re-gathered each time.

Use it **standalone** at the start of a domain ("what's the landscape for X?") or to pressure-
test a design, and it's offered at the end of `/explore` before a design is committed.

> **Relay convention.** Reference frames live at `<root>/reference/<topic-slug>.md`, committed to
> `main` like the board — durable, shared, and cross-referenced by later work.

> **Resolve the root first:** durable state lives under the per-repo root (default `relay/`; a
> `relay.config.json` `{ "root": "docs" }` at the repo root overrides). Resolve once —
> `ROOT="$(jq -r '.root // "relay"' relay.config.json 2>/dev/null || echo relay)"` — and read every
> `<root>/…` path below relative to it.

## Step 1 — Scope it
Work out the **topic** and whether there's an **approach to check**:
- If `$ARGUMENTS` names a brief (`<root>/briefs/<slug>.md`), read it — the "Approach" section is
  what you'll cross-check; derive the topic from the problem it addresses.
- If `$ARGUMENTS` is a bare topic or a design statement, use it directly (topic = the problem
  space; approach = the statement, if one is given).
- If empty, ask what to cross-check and wait.

Pick a stable **topic slug** for the reference frame (the problem space, not the feature — e.g.
`rate-limiting`, `full-text-search`, `competitive-landscape`), so future work on the same space
extends the same frame.

## Step 2 — Load or start the frame
Read `<root>/reference/<topic-slug>.md` if it exists (`git show origin/main:...` to get the
shared copy). If it doesn't, you'll create it in Step 4. An existing frame is a head start, not
gospel — treat its entries as claims to confirm and extend.

## Step 3 — Gather prior art (name names, be concrete)
Research how this problem is actually solved elsewhere. **If your environment has web
search/fetch tools, use them** for current, specific detail; otherwise work from your own
knowledge and **say so in the frame** (mark it "from model knowledge, unverified — confirm
before relying on it"). Cover, as far as each applies:
- **Products / systems** — the notable tools, competitors, or systems in this space, and *how*
  each handles it (not just that they do).
- **Prior art & patterns** — established design patterns, algorithms, or architectures for this
  problem.
- **Standards & specs** — any relevant standard, RFC, protocol, or regulation that constrains
  or guides the right answer.
- **People & sources** — recognised authorities, papers, or writing worth citing.
- **Lessons & anti-patterns** — known failure modes, deprecated approaches, "everyone regrets
  doing it this way" traps.

Prefer specifics over generalities: "Stripe idempotency-keys writes on a client-supplied key"
beats "some APIs handle retries".

## Step 4 — Write / update the reference frame
Write `<root>/reference/<topic-slug>.md` (`mkdir -p <root>/reference` first — it may not exist in a
fresh clone) using this structure (merge into an existing frame rather than overwriting — keep
prior entries, add and correct):

```markdown
# Reference frame: <topic>

_Last updated <YYYY-MM-DD>. <"Web-researched" | "From model knowledge — unverified, confirm before relying on it.">_

## How others handle it

| Reference | How they do it | Takeaway for us |
|---|---|---|
| <product/standard/person> | <their approach, concretely> | <what we should borrow, avoid, or note> |

## Patterns & standards
- <established pattern / relevant standard, and when it applies>

## Anti-patterns & lessons
- <known trap, and why>

## Open questions for our design
- <what this frame surfaced that we still need to decide>
```

## Step 5 — Cross-check the approach (only if one was given)
Hold your approach up against the frame and report, in plain language, under four headings —
omit any that's empty:
- **Aligns** — where your approach matches strong prior art (reassurance, not filler).
- **Diverges** — where you differ from how others do it. For each: is the divergence
  **deliberate and justified**, or an **oversight**? Say which; a justified divergence is fine,
  an accidental one is a finding.
- **Blind spots** — something most references do that your approach doesn't address at all.
- **Reinvention** — a standard, library, or well-trodden pattern you'd be rebuilding by hand.

Recommend concrete adjustments. If this is running inside `/explore`, **STOP for direction**
— the user may fold the findings into the approach before the brief is written.

## Step 6 — Commit the frame and report
Commit `<root>/reference/<topic-slug>.md` to `main` (durable, shared — use the temp-index push
`/handover` uses if you're on a feature branch, or a normal commit on main). Then report: the
frame path, a one-line landscape summary, and — if you cross-checked an approach — the sharpest
one or two findings and your recommendation. Don't paste the whole frame into the terminal.
