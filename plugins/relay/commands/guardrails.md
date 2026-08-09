---
description: Establish the project's guardrails — per-dimension, layered (baseline · adapt · extend), opt-in — and write them to the knowledge layer so /refine and the review specialists share one source of "what good means here". Run once at setup; re-runnable to update.
argument-hint: "[optional: one dimension to (re)configure, e.g. 'api' — omit for the full pass]"
---

> **Output** ([[conventions]]): honour `verbosity` (a per-call `terse`/`verbose` word in `$ARGUMENTS`, else `relay.config.local.json` `.verbosity`, else `normal`) — at **terse**, emit only STOP-gate questions and the final landing, no narration or intermediate recaps. Honour `audience` (a per-call `plain`/`informed`/`expert` word in `$ARGUMENTS`, else `relay.config.local.json` `.audience`, else unset) — how much depth surfaces in your **terminal** output; it never thins a **written artifact** (brief, report, ADR, handover), which always keeps full depth. `plain` = executive summary: the decisions and what you need from the user, minimal jargon; `informed` = lead with the decisions and what changed, keep the corrections and open questions that need the user, defer exhaustive evidence/`file:line` tables to the artifact; `expert` = full depth in the terminal too; unset ⇒ today’s default (no shaping). Never drop a STOP-gate question or the decision itself. Render every list (candidates / findings / plan rows) as a **GFM markdown table**, never stacked `Field: value` records or ASCII-rule separators; keep cells terse, overflow to numbered footnotes.

Establish, in one place every reviewer and `/refine` can read, what **"good" means for THIS
project** — its API style, design system, and security/privacy/testing bars — as **layered
guardrails** you can extend and adapt. This is the backbone of the SSDLC knowledge layer: `/refine`
grooms against it, the review specialists check against it, `/persist` feeds back into it.

**The model.** Guardrails are **per-dimension** (`api`, `ui`, `security`, `privacy`, `testing`, …),
each **opt-in** (active only if the project has it), and each resolved in three layers —
**`extends` (project) > selected baseline > Relay default**:
- **baseline** — an opinionated default Relay always provides, so a dimension is never blank.
- **adapt** — swap to a different named baseline, or a ruleset path you supply.
- **extend** — overlay your house rules (local file or URL); they win on conflict.

## Step 0 — Resolve the Relay root
Durable state lives under a per-repo root — default `relay/`, overridable via a `relay.config.json`
at the repo root (`{ "root": "docs" }`). Resolve it once; read every `<root>/…` path below relative
to it. Absent config ⇒ `<root>` = `relay`.
```bash
ROOT="$(jq -r '.root // "relay"' relay.config.json 2>/dev/null || echo relay)"
```

## Step 1 — Sweep the repo for standards evidence (don't ask what you can detect)
Inspect the repo — `CLAUDE.md`, manifests, code layout, **and existing config/standards files** — and
build a **proposed active-set with cited evidence**, rather than interrogating from a blank slate. This
is the brownfield sweep: for each dimension, note the concrete artifact that argues it's in play *and*
that could seed its baseline/`extends`:
- **`api`** — HTTP endpoints, an OpenAPI/GraphQL schema, a `routes/`/`controllers/` layer; a **spectral
  ruleset** or an API-guidelines doc → wire as `extends`.
- **`ui`** — a frontend app, design tokens, a component library / design-system package; a **design
  guide / UX doc** → wire as `extends`.
- **code style** (feeds several dimensions) — `.eslintrc`/`biome`/`.prettierrc`, `tsconfig` strictness,
  an `.editorconfig` — real, enforced house rules already in the repo.
- **`security`**, **`privacy`** — on by default for anything handling user data (say why); a
  `SECURITY.md`, an auth layer, or a privacy/data-handling doc → `extends`.
- **`testing`** — a test runner/suite, coverage config → on, with the expected kind/coverage.
- Others the repo clearly shows (data/DB migrations, i18n locale files, …).
Report the sweep as **evidence, not assumption** — cite the file for each (e.g. "`ui` — found
`docs/design-guide.md` + `packages/ui`"). A dimension the project plainly lacks is **off** — don't
invent it. If `$ARGUMENTS` names one dimension, scope the whole run to just that one.

## Step 2 — For each active dimension, resolve the three layers (discover-then-ask)
Propose a default for every field so the owner **edits, doesn't author**:
1. **baseline** — name Relay's default for the dimension (e.g. `api` → **`vendor-neutral-rest`**,
   `ui` → **`tokens-a11y`**). Offer the **adaptations**: a named baseline Relay bundles
   (`api`: `zalando` · `microsoft` · `google-aip`) **or** a path to a ruleset the project supplies.
2. **extends** — **detect existing house rules** and propose them as overlays: an
   `api-guidelines.md`, a design-system package, a security policy doc. Accept a local path or a URL
   (an external NFR source). These win on conflict with the baseline.
3. Ask the **judgement calls** only — which baseline, threat level, a11y target (WCAG A/AA/AAA),
   privacy regime, copy voice — never what's trivially readable from the repo.

## Step 2.5 — Present the guardrail plan and confirm — **STOP**
Show a compact table and **wait for approval before writing anything**:

> | Dimension | Baseline | Extends (overlay) | Source |
> |---|---|---|---|
> | `api` | `zalando` | `docs/api-house.md` | detected + confirmed |
> | `ui` | `tokens-a11y` | `packages/ui/DESIGN.md` | detected |
> | `security` | `owasp-asvs-L2` | — | asked (threat level: standard) |

Note any dimension you judged **off**, so the user can add one back. **STOP for the go-ahead.**

## Step 3 — Write the machine-readable selection (`relay.config.json`)
Merge a `guardrails` block into `relay.config.json` at the repo root — **preserve existing keys**
(`root`, `paths`); edit surgically, don't clobber:
```json
{
  "root": "relay",
  "guardrails": {
    "api": { "baseline": "zalando", "extends": ["docs/api-house.md"] },
    "ui":  { "baseline": "tokens-a11y", "extends": ["packages/ui/DESIGN.md"] },
    "security": { "baseline": "owasp-asvs-L2" }
  }
}
```
A dimension **absent** from the block is not in play. This is what consumers resolve against.

## Step 4 — Write / refresh the human-authored knowledge docs
Seed the prose guardrails under the knowledge layer (`mkdir -p <root>/knowledge` first; honour a
`paths.knowledge` override if the project relocated it). **Idempotent** — on a re-run, update in
place and **never overwrite hand-authored `extends` content**; only refresh Relay-managed sections.
- `<root>/knowledge/guardrails.md` — the security / privacy / testing bars in plain language,
  seeded from each dimension's baseline + the answers given.
- One doc per **design-system** dimension the project has (`knowledge/api-design.md`,
  `knowledge/ui-design.md`) — castles-style separate UI and API systems live as separate docs, one
  shared `guardrails` config block.
Each doc names its **baseline** and links its **extends**, so a reader sees the resolution at a glance.

## Step 5 — State the resolver contract (for the consumers)
Document, at the top of `guardrails.md`, how anything reading these resolves a dimension:
> `resolve(dimension)` = the project **`extends`** (highest — wins on conflict), then the **selected
> baseline**, then the **Relay default**. A dimension not in the config is inactive — don't apply it.
The review specialists and `/refine` read *this resolution*, not ad-hoc defaults. (Wiring each agent
to read it is a following slice; until then this doc is the shared reference they cite.)

## Step 6 — Report
State the **dimensions established** and, per dimension, the **baseline** chosen and any **extends**
wired; the files written (`relay.config.json` guardrails block + the `knowledge/` docs); and which
dimensions you left **off** and why. Remind the user it's **re-runnable** to adapt a baseline or add
a dimension, and that `/refine` and the review specialists now have one source to check against.
