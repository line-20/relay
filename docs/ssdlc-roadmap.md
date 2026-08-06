# Roadmap — Relay → a Secure SDLC workbench (the 1.0 arc)

**Status:** 🚧 in progress. North-star doc for the next major release (the 1.0 arc). Decisions at
the end are settled; the increment arc is locked. **Shipped so far: increment #1 (`/guardrails` +
guardrail-aware review specialists) in 0.8.0; #2 (budget/tier in config, `/review-pr` + `/whats-next`
budget-aware) in 0.9.0; #3 (`/refine` — context + guardrails + threat model + budget slicing) in
0.10.0; #4 (`/persist` — knowledge harvest into the extends overlay + design system + memory) in
0.11.0; #5 (`/deploy` — orchestrate/verify + security-gate a PR preview) in 0.12.0** — the rest is
sequenced below. **The 1.0 breaking cut is now in progress on branch `1.0`** (0.14.0 stays on main
untouched until the cut lands): command renames (#7) and explore-split (#8)
done; epics (#9), reflect loop (#10), and per-path config + migration + docs rewrite (#11) still to
do. The tables below still use the pre-1.0 names/paths — they get rewritten as part of #11.

## Vision
Turn Relay from a continuity-first *loop* into a continuity-first **Secure SDLC workbench** — one
that carries an idea from a napkin sketch to shipped, reviewed, tested, deployed code, and then
**harvests what it learnt back into the project's living knowledge** so the next lap starts smarter.
The point isn't more process; it's a workbench where **quality and security compound** instead of
leaking away each session — good enough to iterate castlesERP on daily, and clean enough to share
with the world.

## The one principle that keeps it from becoming waterfall
SSDLC done badly is a gantt chart with an AI. Relay's version has to stay a **spiral, not a
pipeline**:
- **Every phase is emergent and optional** — invoked when the work needs it, skipped when it
  doesn't. You can go `explore → build → ship` on a one-liner, or run the full lap on an epic.
- **It's a ring you re-enter, not a line you finish** — phase (i) loops back to (c) or (b).
- **Each lap raises the floor** — phase (j) feeds guardrails/design-system/memory that phase (c)
  reads next lap. That compounding is the whole value; without (j) it's just an SDLC.
- **Stack-, budget-, and vendor-agnostic** — the same way every review agent already discovers the
  stack from `CLAUDE.md` rather than assuming one.

## The cycle

```text
     ┌───────────────────────────── the SSDLC spiral ──────────────────────────────┐
     │        each lap ends by raising the knowledge floor — (j) feeds (c) next lap  │
     ▼                                                                              │
  a. INIT ─▶ b. EXPLORE ─▶ c. REFINE ─▶ d. BUILD ─▶ e. REVIEW ⇄ f. FIX             │
 (root+       (context-      (context+     (parallel    (coordinator   (remediate,   │
  guardrails   free ideas,    guardrails+   worktrees,   picks 10+      then re-      │
  baseline,    from scratch   memory+       epics or     agents →       review) ─┐   │
  budget/tier) or assets)     budget-aware  independent  one report)             │   │
                              slicing +     threads)          ▲                  │   │
                              threat model)                   └──────────────────┘   │
                                                                                      │
  j. PERSIST ◀──── i. REFLECT ◀──── g. TEST ⇄ h. DEPLOY-PREVIEW                       │
 (harvest into    (result seen;    (scenarios to user/AI;   (PR-triggered            │
  guardrails,      new idea or      local or against a        preview/test           │
  design system,   change of        preview build)            build)                 │
  arch diagrams,   heart?) ──┬─▶ back to (c)  refine this idea further ───────────────┘
  ops/user docs,             └─▶ back to (b)  a genuinely new idea
  AI memory) ───────────────────── the harvested knowledge is (c)'s input next lap ───┘
```

## Phase → command map (what exists, what's new)

| # | Phase | Command | State |
|---|---|---|---|
| a | Initialize | `/relay-init` (+ configurable root ✓, budget tier ✓) | **exists** — still to seed guardrails |
| b | Explore | `/explore` | **refine** — make it *purely* context-free; accept "from assets" / "from a prior iteration" as inputs |
| c | Refine | `/refine` ✅ | **shipped 0.10.0** — context + guardrails + memory; budget-aware slicing; threat model |
| d | Build | `/whats-next`, `/continue` (topic-worktrees ✓) | **exists** — add *epic* grouping |
| e | Review | `/review-pr` (the coordinator + fan-out ✓, budget-aware ✓) | **exists** — still to formalize the "review coordinator" role |
| f | Fix | `/fix-pr-review` (↔ e loop ✓) | **exists** |
| g | Test | `/test-drive` (scenarios, AI-driven, preview-aware ✓) | **exists** (just shipped) |
| h | Deploy preview | `/deploy` ✅ | **shipped 0.12.0** — orchestrate/verify + security-gate a PR preview, don't own deployment |
| i | Reflect | *(no command — a loop edge)* | **NEW behaviour** — re-enter `/explore` or `/refine` with the result as input |
| j | Persist | `/persist` ✅ | **shipped 0.11.0** — harvest into guardrails overlay + design system + memory + human-readable release notes (arch/ADR/ops/manual deferred) |

Backbone that isn't a phase but everything leans on: **`/groundwork`** (the guardrails/tech-context
doc — already shaped in [[tech-context]]). It's (c)'s input and (j)'s output — the two ends of one
knowledge layer.

## The three things that actually need designing
Most of a–j already exists; the new design effort concentrates here.

1. **(c) Refine — context + budget-aware slicing.** The most distinctive idea in the set. Takes a
   context-free idea from (b) and grooms it *against the project*: guardrails, memory, existing code,
   and — crucially — the **driver's AI budget**, slicing the work into parts that fit a free Claude
   Code setup vs a €180/mo max plan. This is also where the **threat model** is done, so security is
   designed in, not bolted on. Depends on `/groundwork` (guardrails) and a budget signal in config.

2. **(j) Persist — knowledge harvest.** What makes the spiral compound. After a lap, selectively
   feed what was learnt into the living docs: UI/UX design system, architectural guardrails,
   architecture diagrams, operational + maintenance docs, user manuals — and AI memory. Generalizes
   the pattern `ui-ux-designer` already uses (steward one design guide) to every knowledge surface.
   **Guard against doc-sprawl**: apply memory's "was it non-obvious?" test — persist the decision and
   the why, not a transcript.

3. **The "S" — shift security left.** Today security lives almost entirely in (e) review. To earn
   the extra S it must thread the whole spiral: threat model in (c), secure-by-default guardrails in
   `/groundwork`, always-on security review in (e) ✓, security-focused scenarios in (g), a security
   gate in (h), and security lessons persisted in (j). Cross-cutting concern, not a phase.

## The guardrails model — opinionated, extensible, adaptable
The knowledge layer can't be one-size-fits-all: a simple site has no design system; castles has
both a UI *and* an API design system. So guardrails are **layered, per-dimension modules** — the
`extends` + local-`rules` pattern devs know from ESLint / Spectral / Tailwind.

**Dimensions are opt-in.** Each concern — `api`, `ui`, `security`, `privacy`, `testing`, … — is a
separate module, active only when the project declares or Relay detects it. Absent dimension ⇒ it
simply doesn't apply (no baseline, no false findings). This is the simple-site-vs-castles variance.

**Each active dimension resolves in three layers, highest wins** — and this is exactly a/b/c:

| Ask | Layer | Mechanism |
|---|---|---|
| **a) opinionated** | Relay **baseline** (always present) | every active dimension ships a real default — never "no rules" |
| **c) adapt** | project **swaps** the baseline | `api.baseline: microsoft` — a wholesale ruleset swap |
| **b) extend** | project **overlays** rules | `extends: [local-or-URL]` — wins on conflict |

Precedence: **`extends` > selected baseline > Relay default.**

```json
{ "guardrails": {
    "api": { "baseline": "zalando",     "extends": ["docs/api-house.md"] },
    "ui":  { "baseline": "tokens-a11y", "extends": ["packages/ui/DESIGN.md"] },
    "security": { "baseline": "owasp-asvs-L2", "extends": ["https://intranet/nfr.md"] }
} }
```

Baselines ship as a small **named library** (`vendor-neutral-rest` [default], `zalando`,
`microsoft`, `google-aip`; UI `tokens-a11y`); a baseline may also be a path to a ruleset the project
supplies. Consumers share the *resolved* ruleset: the review agents read it (`api-architect` already
half-does this), `/refine` grooms + threat-models against it, and **`/persist` only ever writes the
`extends` layer** — never mutating a shipped baseline. The shipped default stays **vendor-neutral**;
Zalando/Microsoft/AIP are adaptations (decided).

> **Review has a ceiling — mind which quality attribute a dimension actually is.** Guardrails-as-a-
> review-lens can only enforce **design-time / inspectable** attributes (structure, security patterns,
> a11y, API consistency, testability, i18n) — things a reviewer can judge from a diff. **Runtime /
> measurable** attributes (scalability, performance, availability, reliability, resilience,
> recoverability) *cannot be proven from code* — no `scalability-specialist` reading a diff settles
> whether it holds at a million tx/day. Those dimensions must be enforced at **`/test` (load/chaos) →
> `/deploy` → observability/`/persist`**, not at review. (A third class — process/provenance:
> auditability, traceability, reproducibility — Relay already delivers *for the work itself* via the
> board, handovers, review reports, and git.) So every dimension carries a **class tag** that routes
> it to the phase that can actually enforce it — see R1.

## Cross-cutting concerns
- **Budget / economy.** A **`tier`** (`free` / `pro` / `max`) in `relay.config.json`, asked once at
  `/init`, drives: slice size in (c), how many review agents fan out in (e), `/test` depth in (g),
  whether a workflow fan-out is affordable at all. Ties to Relay's existing token-economics doc.
- **Security.** As above — a thread, not a phase.
- **Interactivity.** Every phase stays interactive: it asks for direction/approval at the points of
  real choice, and only there (Relay's existing STOP-gate discipline).

## The increment arc — 🔒 LOCKED (ship additively, tag the break once)
Build it as independently-shippable increments on castles, **not** a big-bang. Order follows
dependency: guardrails is the backbone `/refine` and `/persist` both stand on, so it's first;
budget unblocks the budget-aware slicing in `/refine`; the breaking bits wait until last so every
lap of design is proven additively before anything breaks. Only the schema/flow breaks are
quarantined into the final major cut.

**Additive (0.x — no break, prove each on castles):**
1. **`/guardrails` + the knowledge layer** ✅ *(increment #1 — shipped 0.8.0)* — the layered
   guardrails model (baseline/adapt/extend, opt-in dimensions) and the `<root>/knowledge/` home, incl.
   the per-path config that lets a deliverable live outside `relay/`. Backbone for (c) and (j).
   *(brief: [[guardrails]])*
2. **Budget/tier in config** ✅ *(increment #2 — shipped 0.9.0)* — a `tier` (`free`/`pro`/`max`) in
   `relay.config.json`, asked once at `/relay-init`; `/review-pr` caps its specialist fan-out (safety
   core never capped, defers logged) and `/whats-next` scales its verify/audit research width. Absent
   tier ⇒ no cap (fully back-compatible). Unblocks budget-aware everything.
3. **`/refine` (phase c)** ✅ *(increment #3 — shipped 0.10.0)* — the big pillar. Context + budget
   slicing + threat model, against the resolved guardrails from #1 and the tier from #2. Grooms an
   `/explore` brief in place; never writes code or guardrails.
4. **`/persist` (phase j)** ✅ *(increment #4 — shipped 0.11.0)* — the other big pillar. Knowledge
   harvest into the #1 layer (writes the `extends` overlay only, never a baseline), sprawl-guarded via
   memory's non-obvious test. Ships guardrails + design-system + memory + human-readable release-notes
   targets; arch/ADR/ops/manual deferred to later slices. Release notes are the *outward* deliverable
   (gated on user-visibility, not non-obviousness). `/wrapup` now offers it after merge (1.0 makes it
   a phase of `ship`).
5. **`/deploy` (phase h)** ✅ *(increment #5 — shipped 0.12.0)* — orchestrate/verify + security-gate
   a PR preview via the project's own pipeline (stay out of owning deploys); hands a verified URL to
   `/test-drive`. No preview mechanism ⇒ it stops, never invents one.
6. **Security shift-left** — threat model in (c), security scenarios in (g), gate in (h); mostly
   falls out of 1/3/4 once they exist.

**Breaking (assemble into the major cut — 1.0):**
7. **Command renames** ✅ *(done on branch `1.0`)* — `relay-init`→`init`, `whats-next`→`next`,
   `review-pr`→`review`, `fix-pr-review`→`fix`, `test-drive`→`test`, `wrapup`→`ship`,
   `garbage-collect`→`gc` (files renamed, every cross-reference + docs swept). Dir renames
   (`pr-reviews/`→`reviews/`, `board-audit/`→`audits/`) are part of #11's per-path work, not here.
8. **Explore split (phase b)** ✅ *(done on branch `1.0`)* — `/explore` is now purely context-free
   (never inspects the project); the pre-build fit check and all code-grounding moved to `/refine`.
9. **Epic modeling (phase d)** — epics grouping slices on the board (board schema change).
10. **Reflect loop (phase i)** — formalize result → `/refine`/`/explore` re-entry.
11. **1.0 cut** — general migration path (the configurable-root work is the template) + the one-time
    **castlesERP conversion** + docs/quickstart/board-model rewritten around the spiral.

## Clean break — naming & structure (1.0)
A major release is the one chance to drop historical baggage. **Rule: rename only where it earns
clarity** — align a command to its lifecycle verb, or shed a name that describes old plumbing.
Names that are already good (`explore`, `continue`, `handover`, `cross-check`, `watch`) don't
change — churn for its own sake costs muscle memory and teaches nothing.

**Guiding principle: command name = phase verb.** The lifecycle becomes learnable by learning the
commands. The one-time castles conversion + a general migration map (configurable-root is the
template) absorb the break.

### Commands

| Phase | Today | 1.0 | Why |
|---|---|---|---|
| a | `relay-init` | `init` | the `relay:` namespace already says "relay"; `-init` is redundant |
| b | `explore` | `explore` | good name — keep |
| c | *(new)* | `refine` | the verb for context-aware grooming |
| d | `whats-next` | `next` | `whats-next` is casual; `next` is the verb |
| d | `continue` | `continue` | keep |
| e | `review-pr` | `review` | it reviews a branch too — the `-pr` is historical |
| f | `fix-pr-review` | `fix` | shed the plumbing name; `fix` is the verb |
| g | `test-drive` | `test` ✅ | verb — fits the gang |
| h | *(new)* | `deploy` | preview/test deploy |
| i | *(loop)* | — | a loop edge, not a command |
| j | *(new)* | `persist` | harvest knowledge (name still open) |
| — | `wrapup` | `ship` ✅ | the composite tail: review→fix→merge→persist→handover (stays a command) |
| — | `garbage-collect` | `gc` | shorten the jargon |
| — | `groundwork` | `guardrails` ✅ | name it to the artifact it writes |

✅ = decided. Default root stays **`relay/`** — it's the brand and the sensible default.

### Durable-state layout — two kinds of state, both resolved through config
A key distinction the single-root model blurred: some of what Relay touches is **its own working
memory**, and some is **real project deliverables that have their own home**. Documentation, a
design system, architecture diagrams — those belong *with the code*, not siloed in Relay's scratch
folder. So the config generalizes from one `root` to **per-path overrides**: default under
`<root>/`, but any path can point wherever the project actually keeps it.

**1. Process state — Relay's working memory.** One root (default `relay/`), rarely relocated:

```text
<root>/
  board.md      front door
  briefs/       explore/refine output
  reviews/      was pr-reviews/  (the "pr-" was historical)
  audits/       was board-audit/ (drop "board-"; it's already under the root)
  reference/    cross-check frames
  handover/     (+ archive/)
  archive/
```

**2. Deliverable knowledge — real project artifacts, each individually configurable.** Default
under `<root>/knowledge/`, but pointable at the project's own home for each:

```text
<root>/knowledge/           (the persist (j) targets — the compounding layer)
  guardrails.md       secure-by-default + NFRs (what /guardrails writes; /refine reads)
  design-system.md    UI/UX system (ui-ux-designer's steward target)
  architecture/       diagrams + ADRs + boundary rules
  operations.md       runbook / maintenance
  manual/             user-facing docs
```

**Config shape** (generalizes configurable-root — one resolver, list only what you move):

```json
{
  "root": "relay",
  "paths": {
    "knowledge": "docs",
    "design-system": "packages/ui/DESIGN.md"
  }
}
```

Resolution: `resolve(name)` → `paths[name]` if set, else `<root>/<default-sub>`. Uniform mechanism
for *every* logical path; you only add an entry for a folder you actually relocate. Back-compatible:
no `paths` ⇒ everything under `<root>/` exactly as today.

This supersedes the shipped configurable-root (`root` becomes the default base; per-path overrides
layer on) — so it's a natural 1.0 evolution, not a rewrite.

## Reach — fitting more project types (post-1.0)
A what-if across 11 project archetypes (static site, marketing site, web shop, native mobile,
Arduino→cloud, POS+hardware, PWA, desktop client-server, high-volume ecommerce, ETL/BI workbench,
ERP) showed fit varies **by layer, not by project** — and *not by much*, given the guardrails
architecture. Relay isn't a Swiss-army knife; it extends by declaring dimensions.

**Fit by layer:**
- **Continuity core** (board · handover · worktrees · explore · refine · persist) — fits **all 11**.
  It manages parallel AI-driven work, not a stack.
- **Guardrail dimensions** — fit by *adding a dimension*; opt-in, so simple projects stay simple.
  Cheap, and the model already supports it. Most gaps close here.
- **Review roster** — web/API/UI/DB-centric today; native/embedded/data-eng need other lenses.
- **Test/deploy medium** — `/test` assumes a browser, which native/hardware/data don't have.

**Fit grouping:**
- **Sweet spot** (web/API/data-backed + PR/preview): marketing site, web shop, PWA, high-volume
  ecommerce (backend-heavy), ETL (data-heavy), ERP. Gaps = a dimension or two.
- **Partial** (native/hardware, non-browser test): iOS/Android, POS+hardware, native desktop,
  Arduino *firmware* — while that project's **cloud+web** half sits in the sweet spot. Continuity
  fits; roster + test-medium strain.
- **Overkill-but-fine**: static site — emergent/optional phases already keep it light.

**Reach increments (post-1.0, in reach-per-effort order):**
- **R1 — Dimension library expansion (cheap, highest leverage).** Ship `seo`, `perf`, `payments-pci`,
  `offline`/`pwa`, `mobile`, `embedded`, `data-quality` as guardrail dimensions — each a baseline +
  an optional reviewer lens, opt-in. This *is* the low-effort path to fitting more project types, and
  it validates the layered-guardrails direction we already committed to.
  - **Seed the catalog from a standard taxonomy.** The canonical *list of system quality attributes*
    (the ~80 "-ilities") is the NFR menu; use it so the dimension library is principled and
    complete-ish, not ad-hoc. **Tag every dimension with a class** that routes it to the phase that
    can enforce it:
    - **design-time / inspectable** → guardrails + `/review` (maintainability, security, a11y, API
      consistency, testability, i18n, portability, modularity). Relay strong.
    - **runtime / measurable** → `/test` (load/chaos) + `/deploy` + observability (scalability, perf,
      availability, reliability, resilience, recoverability). *Not diff-reviewable* — the honest gap
      R3 + an `observability`/`ops` dimension close.
    - **process / provenance** → already delivered by Relay's machinery (auditability, traceability,
      reproducibility, accountability) — no dimension needed; note it as a standing property.
- **R2 — Dimension-driven review roster (medium).** `/review` selects specialists by **active
  guardrail dimensions**, not only file-type — and supports **project/community-contributed**
  specialist agents (embedded, mobile, perf-at-scale, data-engineering). Unlocks half the partials.
- **R3 — Pluggable test medium (the real design item).** Separate the `/test` **plan** (scenarios +
  non-happy-path discipline — universal) from the **driver** (browser / simulator / device /
  data-validation / load-test). `/test-drive` becomes the browser driver; others plug in. Unblocks
  mobile, desktop, hardware, and data projects.
- Note: `/deploy` is already positioned right (orchestrate/verify the project's *own* pipeline, never
  own deployment) — that's what lets it span App Store, firmware flash, and warehouse deploy without
  special-casing.

**Honest limit:** native/hardware **test execution** and the web-centric **roster** are the only
non-cheap gaps; both are addressed by R2/R3. Everything else is a dimension away.

## Decisions — 🔒 closed
- **Command names.** `init`, `explore`, `refine`, `next`, `continue`, `review`, `fix`, `test`,
  `deploy`, `persist`, `ship`, `guardrails`, `gc` — plus unchanged `handover`, `cross-check`,
  `watch`. `persist` (over harvest/capture/learn) and **`ship` stays** as the composite
  review→fix→merge→persist→handover tail (not dissolved). Default root stays `relay/`.
- **Budget signal.** A **`tier`** — `free` / `pro` / `max` — in `relay.config.json`, **asked once at
  `/init`**. Drives slice size in `/refine`, agent fan-out in `/review`, depth in `/test`. (A
  power-user per-lap token target can layer on later; not 1.0-critical.)
- **Guardrails default stance.** Shipped default is **`vendor-neutral-rest`**; Zalando / Microsoft /
  Google-AIP are **selectable adaptations**, not the default — Relay stays portable, castles opts in.
  Bundled library stays **thin at first** (neutral + `tokens-a11y`) + "bring your own ruleset path";
  named baselines fill in as a later slice.
- **Per-path config.** **Uniform** — every logical path is overridable via `paths`, list only what
  you move. `briefs/` and `reference/` stay **siblings** of `knowledge/` (in-flight vs settled).
- **Committed vs gitignored.** Deliverable knowledge is **always committed** (it's project truth).
  Process state **defaults to committed** (the board must be shared for `/continue` to work across
  sessions), but may be gitignored for solo/scratch use — documented, user's choice.
- **Reflect (i)** is a **loop edge, not a command** — re-enter `/explore` (new idea) or `/refine`
  (same idea, changed) with the result as input.
- **Epics** start as a **slug convention** (`epic/slice`) + a grouping view, not a board-schema
  change — avoid weight until it's earned.
- **Deploy (h)** **orchestrates and verifies** a preview the project's own CI produces — it never
  becomes a deployment tool (stays stack-agnostic).
- **Persist (j) targets:** ship **guardrails + design-system + memory + human-readable release
  notes** first (release notes gated on user-visibility, not the non-obvious lesson test); add
  architecture / ops / manual / ADRs in later slices.
- **Threat model** is a **section inside guardrails**, not a separate doc — one fewer sprawl surface.
- **Work-inputs vs deliverable knowledge (brownfield adoption).** Two categories of existing doc, and
  they live in different places. **Work-inputs** (ideas, specs, plans, TODOs, notes — *volatile*,
  value spent once shipped) belong **in Relay** (`<root>/briefs/`, tracked on the board, archived when
  done); `/relay-init` **imports** them on a brownfield repo. **Deliverable knowledge** (design system,
  architecture, conventions, runbooks, manuals — *durable*, still true after shipping) stays **with the
  code** and feeds the knowledge layer. The "live with the code" principle governs only the latter. A
  doc that is both is imported as a brief; `/persist` lifts its durable decision into the knowledge
  layer at completion. Adoption **triages, STOPs for approval, preserves git history** (`git mv`), and
  **does not assume git** (plain `mv` fallback; never force-`git init`).
- **Version line.** The breaking cut is **1.0** (first stable major from 0.x). castles runs ahead on
  a **pre-release channel**; the world gets the additive 0.x increments until 1.0 assembles the break.

_Roadmap complete. Increments #1–#5 shipped (0.8.0 → 0.12.0); the additive arc has only **#6 security
shift-left** left (and it mostly falls out of #1/#3/#4/#5) before the breaking 1.0 cut (#7–#11). Next
action: prove #1–#5 on castlesERP, then close out #6._
