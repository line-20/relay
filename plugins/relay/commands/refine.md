---
description: Groom a shaped idea against THIS project — its code, guardrails, memory, and your session size — into project-grounded, session-sized slices with a threat model, ready to build. The bridge from /explore to /next.
argument-hint: "[track/slug of a brief to refine; omit to pick from the board]"
---

Take a brief that `/explore` shaped **in the abstract** and groom it **against this project** —
its existing code, its guardrails, its accumulated memory, and the driver's **session size** — so
what reaches the builder is grounded, security is designed in, and every slice is sized to the
budget it'll actually run under. This is phase (c): `/explore` shapes the idea, `/refine` fits it to
the project, `/next` builds it. Like `/explore`, it **does not write code** — it grooms the plan.

> **Where `/refine` sits.** `/explore` is deliberately context-free (it shapes *what* to build
> without letting the codebase bias it). `/refine` is the opposite: its whole job is context —
> grounding that shaped idea in what already exists. Don't re-interrogate the idea here; if it was
> never shaped, send it back to `/explore` first (Step 1).

## Step 0 — Resolve the root, session, and guardrails
Durable state lives under a per-repo root — default `relay/`, overridable via `relay.config.json`
(`{ "root": "docs" }`). Resolve the root, the session size, and whether guardrails exist:
```bash
ROOT="$(jq -r '.root // "relay"' relay.config.json 2>/dev/null || echo relay)"
# session sizing: local prefs → (committed tier, back-compat) → a per-call word in $ARGUMENTS wins
SESSION="$(jq -r '.session // empty' relay.config.local.json 2>/dev/null)"; : "${SESSION:=$(jq -r '.tier // empty' relay.config.json 2>/dev/null)}"
GUARDRAILS="$(jq -r '.guardrails // empty | keys | join(",")' relay.config.json 2>/dev/null)"
```
`SESSION` (`small`/`medium`/`large`) drives slice size and fan-out (Steps 2, 5) — see
[[conventions]]: it's **context appetite**, sizing a slice to finish within the healthy part of the
window. A **per-call word** in `$ARGUMENTS` (`small`/`medium`/`large`) overrides for this run. **Empty
⇒ no shaping** — slice by natural seams. Since this is a **fan-out moment**, if `SESSION` is empty,
proceed at full and **offer once** to set it (in `relay.config.local.json`, or per-call) — never block.
`GUARDRAILS` is the active dimensions (from `/guardrails`); **empty ⇒ no guardrails configured**, and
every guardrail step below falls back gracefully (Steps 3, 4) — a repo that never ran `/guardrails`
still refines, just without that layer.

## Step 1 — Locate the brief and confirm the target
`$ARGUMENTS` is a `track/slug`. If empty, fetch the board (`git show FETCH_HEAD:<root>/board.md`
after `git fetch origin main`) and offer the **🔜 queued items that have a brief but haven't been
refined** — then **STOP** for a pick.

Read the brief from main: `git show FETCH_HEAD:<root>/briefs/<slug>.md`.
- **No brief exists** for this idea ⇒ it was never shaped. **Say so and stop** — point at
  `/explore <the idea>` to shape it first. `/refine` grooms an existing brief; it doesn't replace
  `/explore`'s interrogation.
- **A brief exists** ⇒ play back its Problem + Approach in one or two plain sentences — "here's the
  shaped idea I'm about to ground in the project" — and confirm you've got the right target before
  spending the run. If the brief already has a `## Project grounding` / `## Threat model` section,
  this is a **re-refine** — update in place rather than duplicating.

## Step 1.5 — Pull a referenced legacy input in (adopt-on-touch)
If the item's board **`Detail` points outside `<root>/`** (e.g. `ideas/foo.md`) — or the "brief" you
were handed is a legacy doc still living in its original spot — this refine **adopts it into Relay**
as it grooms it. This is how a brownfield repo gets pristine gradually: each idea moves in the moment
someone actually works it. On approval (say what you're about to do):
- **Move it** into `<root>/briefs/<slug>.md` — history-preserving where there's git, plain move
  otherwise (not every project is a git repo):
  ```bash
  if git rev-parse --is-inside-work-tree >/dev/null 2>&1 && git ls-files --error-unmatch "<src>" >/dev/null 2>&1
  then git mv "<src>" "<root>/briefs/<slug>.md"; else mkdir -p "<root>/briefs" && mv "<src>" "<root>/briefs/<slug>.md"; fi
  ```
  **Safety net** (see [[conventions]]): in git, ensure the source is committed first (git is the
  backup); no git ⇒ copy it to `<root>/archive/pre-adopt/` before moving. **State the move
  explicitly** — "moved `<src>` → `briefs/<slug>.md`; original gone."
- **Rewrite path references** to it (`CLAUDE.md`, cross-links); name-based `[[wikilinks]]` survive.
- **Repoint the board row** `Detail` to `<root>/briefs/<slug>.md`, and **stamp provenance** at the top
  of the brief: `_Adopted from `<src>` (moved) · <date>_`. The legacy spot is now empty — the board no
  longer shows this item as "outside `relay/`".
- **Actualise as you groom** (Steps 2 & 7): don't preserve a fossil. Because you're grounding against
  current code anyway, reconcile the doc with reality — cut what's already shipped, correct drifted
  assumptions, tighten. Import the *actualised* version.

If the brief already lives under `<root>/briefs/`, skip this — it's already adopted; just refine it.
(To pull in a whole area at once instead of one-at-a-time, that's `/adopt [area]`.)

## Step 2 — Ground it in the actual project (context — the part `/explore` skipped)
Find out what the codebase already says about this work, so the plan builds *with* the grain instead
of against it. Read, don't assume:
- The **code area** this touches — the modules, endpoints, components, or schema it will extend or
  sit next to. What already exists to **reuse**? What must it **not break**?
- The project's **durable knowledge** — `CLAUDE.md`, `<root>/knowledge/` docs, architecture notes,
  and any **AI memory** the harness exposes — for prior decisions that bear on this (a chosen
  pattern, a past mistake, a documented constraint). Don't re-decide what's already decided.
- The **pre-build fit check** — if the project's `CLAUDE.md` defines a checklist for a new
  feature/module (packaging, separability, tiering, portability — whatever it requires), run it
  against the approach now and fold the answers into the brief. (This moved here from `/explore` in
  1.0: it needs the project, so it belongs in grounding, not in context-free shaping.) If the project
  defines none, skip it.

**Scale the grounding to the session size** — this is the first sizing lever:
- `small` ⇒ one inline pass; read the obvious files directly.
- `medium` ⇒ fan out ~3 code-scout agents over the distinct affected areas, in parallel.
- `large` / empty ⇒ fan out one scout per affected area; go wide.

Each scout reports: **what exists here already**, **the safe extension point**, **what would break**,
and **2–3 evidence pointers** (`file:line`, a prior commit, a knowledge-doc section). Collect these into
a short **Project grounding** you'll fold into the brief — concrete, cited, not asserted.

## Step 3 — Resolve the guardrails that apply
For each active dimension in `GUARDRAILS` that this change *touches*, pull the concrete bar from the
resolved guardrails (`extends` > baseline > default — read `<root>/knowledge/guardrails.md` and any
design-system doc) and turn it into an **explicit requirement** the slices must meet:
- `api` ⇒ the endpoint/contract conventions the new surface must follow.
- `ui` ⇒ the design tokens / a11y target (WCAG A/AA/AAA) the new UI must hit.
- `security` / `privacy` ⇒ the bars that feed the threat model (Step 4).
- `testing` ⇒ the coverage/kind expected for this change.
**No guardrails configured (or dimension off)** ⇒ skip that requirement and note it — don't invent a
bar. These requirements become acceptance criteria attached to the relevant slices, not vague hopes.

**No guardrails at all?** Proceed with sensible defaults, but **offer once**: this project has no
guardrails, and `/guardrails` establishes them so `/refine` and the review specialists check against
*your* standards instead of generic defaults — especially worth it if there's an existing design guide
or API doc `/adopt`/`/guardrails` could register. Non-blocking; refine still finishes without it.

## Step 4 — Threat model (security, designed in — content-gated)
Do this whenever the change has a **security or privacy surface** — it touches auth/authZ, handles
user or personal data, adds an endpoint or external integration, changes storage/schema, or accepts
untrusted input (uploads, imports, webhooks). If it structurally cannot (a pure copy/docs/styling
change), write **"no threat surface — threat model not needed"** and skip; this is a content judgment,
not a size one.

When it applies, run a **lightweight threat model** against the `security`/`privacy` guardrail bar:
1. **Assets & entry points** — what of value this touches, and every new trust boundary it crosses
   (a new route, a new input, a new integration, a new place data is stored).
2. **Threats** — walk the change for the relevant classes (spoofing/auth, tampering, disclosure,
   escalation, injection, SSRF, data-retention/consent for personal data). Name the plausible ones,
   not a textbook dump.
3. **Mitigations** — for each real threat, the concrete defence — and **fold it into a slice as a
   requirement**, so security ships *inside* the work, not as a later bolt-on. A threat you choose
   not to mitigate is an explicit **Out-of-scope** line with the reason, never a silent gap.

## Step 5 — Re-slice to the session size (the distinctive move)
Re-cut the brief's slices so each is **end-to-end, demoable, and sized to finish within the healthy
part of a `SESSION` context window** — carrying its Step 3 requirements and Step 4 mitigations. The
session size sets the grain:
- `small` ⇒ **small, sequential** slices that each fit one modest session with no fan-out; sequence
  dependent work rather than parallelising it; one slice in flight at a time.
- `medium` ⇒ moderate slices; parallelise the genuinely independent ones.
- `large` ⇒ may decompose into an **epic of parallel independent threads** (note the `epic/slice`
  seams); larger slices acceptable, since a big window stays healthy longer; lean on fan-out.
- empty ⇒ slice by natural shippable seams, no shaping (the default).

Every slice states its **acceptance criteria** (incl. the guardrail requirements + threat
mitigations that apply to it). Keep YAGNI: cut anything not needed for the real problem.

## Step 6 — Present the refined plan and confirm — **STOP**
Show a compact summary and **wait for approval before writing anything**:
- **Grounding** — the key "what already exists / safe extension point / don't break" facts (cited).
- **Guardrail requirements** — the bars this must meet (or "none configured").
- **Threat model** — assets, the real threats, the mitigations now baked into slices (or "no threat
  surface").
- **Slice plan** — the session-sized slices with their acceptance criteria, and the session size they are sized for.
Note anything the grounding **changed** versus `/explore`'s approach (a reuse that shrinks it, a
constraint that reshapes it). **STOP for the go-ahead**, a redirect, or a re-slice.

## Step 7 — Write the refined brief back (main-owned)
On approval, extend the existing `<root>/briefs/<slug>.md` **in place** — keep `/explore`'s sections,
add/replace these (idempotent on a re-refine: update, don't duplicate):
- `## Project grounding` — the cited facts from Step 2.
- `## Guardrail requirements` — from Step 3 (or "None configured").
- `## Threat model` — from Step 4 (or "No threat surface").
- Replace `## Slices` with the Step 5 budget-sized slices, each with **acceptance criteria** and a
  `(sized for session: <s>)` note.
- Leave a one-line `**Refined:** <date> · session <s>` marker under the status so a reader knows it's
  been groomed.

The board is **shared and main-owned** — edit from main's copy and commit the brief (+ any board-row
status touch) back onto `main` surgically: if on `main`, a normal `git add && git commit && git push`;
if on a feature branch, use the temp-index push `/handover` uses so you don't switch branches. If the
push is rejected, say so — the brief is correct locally and the user can commit it.

**Boundary:** if the grounding reveals a guardrail *gap* (a rule the project should adopt but hasn't),
**note it — don't write it here.** Writing guardrails is `/guardrails`' job; harvesting lessons back
into them is `/persist`'s. `/refine` only reads the knowledge layer.

## Step 8 — Report
State, outcome-first: the item (`track/slug`), how the grounding **changed** the plan (the single
most important reshape), the **threat-model verdict** (surface + mitigations, or none), the **slice
count** and the session size they are sized for, and that **`/next`** (or `/continue`) now builds it.
Do not start building.
