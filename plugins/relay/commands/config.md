---
description: Set Relay's optional config, layered gentlest-first — lead with session + verbosity, then a compact offer for guardrails/hooks, with root/paths on demand only. Opt-in depth, never a gate.
argument-hint: "[jump to one area: session|verbosity|guardrails|hooks|paths|root|show; omit for the layered pass]"
---

> **Output** ([[conventions]]): honour `verbosity` (a per-call `terse`/`verbose` word in `$ARGUMENTS`, else `relay.config.local.json` `.verbosity`, else `normal`) — at **terse**, emit only STOP-gate questions and the final landing, no narration or intermediate recaps. Render every list as a **GFM markdown table**, never stacked `Field: value` records or ASCII-rule separators; keep cells terse, overflow to numbered footnotes.

The config front door — **opt-in depth, never a gate** ([[conventions]]). It is **layered
gentlest-first** so it never dumps "here's everything, have a pick": it leads with the two cheap driver
prefs, then *compactly* offers the project knobs only if they're relevant, and keeps the structural ones
out of the way unless you ask for them. Decline anything and defaults stand — you can stop after the
first two questions.

## Step 0 — Resolve state (and honour a jump)
```bash
ROOT="$(jq -r '.root // "relay"' relay.config.json 2>/dev/null || echo relay)"
```
Read both surfaces: `relay.config.json` (committed) and `relay.config.local.json` (gitignored).
- If `$ARGUMENTS` names **one area** (`session`/`verbosity`/`guardrails`/`hooks`/`paths`/`root`), skip
  the layering and go straight to that area's step.
- If `$ARGUMENTS` is **`show`**, print the reference table (bottom) and stop — no questions.

## Layer 1 — the two cheap prefs (start here; one brief question each)
These are per-driver, benefit everyone, and cost one question — so always lead with them. **Describe
the options neutrally — say what each does, never who it's for** (see [[conventions]] → *No fabricated
familiarity*). On a fresh session you don't know the user; present the choices plainly and let them pick.
1. **Session size** (`small`/`medium`/`large`) — how big a slice `/refine` cuts and how wide `/review`/
   `/next` fan out. Describe them factually: **small** = narrow slices, tighter fan-out; **medium** =
   balanced; **large** = big slices, wide fan-out (full review panels). You *may* mark one as a
   suggestion **only from a concrete, current signal**, phrased tentatively — never "fits your … style".
   Write the answer to `relay.config.local.json`. Skip ⇒ unset (full fan-out).
2. **Verbosity** (`terse`/`normal`/`verbose`) — how much Relay narrates: **terse** = STOP gates + the
   landing only; **normal** = today's default; **verbose** = also the reasoning. Same rule — neutral
   descriptions; suggest `terse` only if something concrete points that way, and as a light suggestion,
   not a claim about them. Skip ⇒ `normal`.

**Then STOP** — many users are done here. Ask a single line: *"That's the essentials. Want to set up
project standards or wire in your tooling too? (both optional)"* — only continue to Layer 2 on a yes.

## Layer 2 — offer the project knobs (compact, evidence-based, delegated)
Only if the user opted in above. **Offer only what this repo shows evidence for** — never a blank menu:
- **Guardrails — on a brownfield, offer a *sweep*.** If this is an established repo (real code, not
  greenfield), do a quick scan for existing standards material and **name what you actually found**,
  then offer: *"Want me to sweep this repo for guardrails? I found &lt;a design guide, an OpenAPI spec,
  ESLint + Prettier, DB conventions&gt; — I can set up guardrails from what's really here."* Scan for:
  a design-guide/UX doc or design-system package (`ui`); an OpenAPI/GraphQL schema or `routes/`
  (`api`); `.eslintrc`/`.prettierrc`/`biome`/`tsconfig` strictness (code style); a spectral ruleset
  (`api`); a `SECURITY.md`/auth layer (`security`); a privacy/data-handling doc (`privacy`); a test
  runner/suite (`testing`). On **yes, hand off to `/guardrails`** — its discover-then-ask sweep is the
  real thing; don't reimplement it. If it's greenfield or you found nothing concrete, say so and skip —
  **name the repo, never guess the user** (see [[conventions]] → *No fabricated familiarity*).
- **Hooks** — if there are existing `.claude/commands` or skills (a `test-stack`, a `commit`): name them
  and **hand off to `/adopt`**'s `.claude/` reconciliation (keep / remove-redundant / keep-and-hook),
  which writes the `hooks` map.
If the repo shows **no** evidence for either, say so plainly and skip — don't manufacture an offer.

## Advanced — root & paths (on demand only, NOT in the layered pass)
**Do not surface these in the guided flow.** They're structural, for someone who's read the docs, and
reached only via an explicit arg:
- `/relay:config paths` — relocate a logical path (e.g. `knowledge` → `docs/`) so `/persist`/`/guardrails`
  write where your deliverable docs actually live. Confirm the target, merge surgically.
- `/relay:config root` — move where all durable state lives (a real move — safety net, see
  [[conventions]]).
In the layered pass, mention them at most as **one closing line**: *"Advanced: `root`/`paths` on demand
— `/relay:config paths`, or see `docs/conventions.md`."*

## Reference — current vs default (shown on `show`, or if the user asks)
A single table of every area, its current value (or `default: …`), and one line on what it does — the
discoverability an empty default file can't give. Don't lead with this; it's a reference, not the menu.

## Report
State what changed and in which file (nothing if they only looked), that everything else stays at its
sensible default, and that `/relay:config` is safe to re-run anytime to review or adjust.
