# Relay context scopes (architecture)

_The foundational boundary of what context Relay owns and operates within. This is the single source of truth for Relay's scope model; other docs link here rather than restating it. **Documentation only** — no Organisation Context / EKR is designed or implemented, and none is part of the current harvest/runtime work._

## The scopes

Relay fundamentally operates with **two required scopes**:

```
   PROJECT
      ⇅
  WORK ITEM
```

A **third scope may optionally exist above Project**:

```
 ORGANISATION        (optional)
      ⇅
   PROJECT           (required)
      ⇅
  WORK ITEM          (required)
```

**Organisation is optional.** Relay must remain fully functional for a standalone project where no organisation-level context exists.

## 1. Organisation / Portfolio — *optional*, externally owned

Knowledge and architecture that transcend an individual project — e.g. business capabilities; systems / applications / services / APIs; organisational architecture; technologies; ownership; shared standards, principles and guardrails; organisational knowledge; lifecycle / strategic / deprecated / sunset state; current and target architecture; initiatives and roadmaps.

**This information is NOT owned by Relay.** In future an organisation may expose an **Enterprise Knowledge Repository (EKR)** or another Organisation Context provider. Relay may then optionally:

- **query / consume** organisation context, and
- **propose / contribute** knowledge or architecture learned through delivery.

The storage / model / protocol is **deliberately unspecified**. Possible future implementations include git-native repositories, MCP, architecture repositories, or adapters to existing systems.

> **Parked — future exploration, not decided architecture.** We discussed **ArchiMate** as a potentially useful semantic foundation and **LikeC4** as a possible visualisation/projection mechanism. These are exploration ideas only — not Relay architecture decisions. **EKR / Organisation Context design and implementation are explicitly parked**, and must not be introduced as part of the current harvest work.

## 2. Project — *required*

Durable truth belonging to the project / product / system: project instructions; architecture; project knowledge; guardrails; decisions / ADRs; briefs; source code; the project board / state; testing conventions.

**Project state must not depend on Organisation Context existing.**

## 3. Work Item — *required*

Durable truth about a particular unit of work: identity; objective; stage; branch / worktree; checkpoint; resume delta; open questions; scope edges; disposition / results.

## Context flow

**When Organisation Context exists**, context flows *down* and knowledge flows *up*:

```
 Organisation ──contextualises──▶ Project ──contextualises──▶ Work Item

 Work Item ──discovery/learning──▶ Project ──distillation/proposed uplift──▶ Organisation
```

The upward, project-to-organisation contribution must be treated conceptually as an **uplift / proposal** — *not* an assumption that project workers directly mutate authoritative organisation knowledge (see the governance principle below).

**When Organisation Context does NOT exist**, the standalone shape

```
 Project ⇅ Work Item
```

is complete and valid. Relay accumulates project-local knowledge normally. If an organisation context is introduced later, common/general knowledge from projects could potentially be distilled/uplifted into it — but nothing in Relay's core depends on that ever happening.

## The Relay boundary

**Relay is the runtime / tool.** Relay does **not** own the organisation's enterprise architecture or organisational truth. A future Organisation Context is an **external context source and contribution target** that Relay can *optionally* integrate with.

Concretely, this is why the provider-neutral **worker bootstrap currently resolves only Project + Work Item context** (see `harvest-design.md` R1.10):

```
 Worker Bootstrap
 ├── Project
 │   ├── project instructions   (e.g. CLAUDE.md — resolved, not owned)
 │   ├── brief                   (optional; <root>/briefs/<slug>.md on main)
 │   └── repository / worktree
 │
 └── Work Item
     ├── objective
     ├── stage
     ├── checkpoint
     └── resume delta
```

A future optional Organisation Context *could* augment this, but **must not** be introduced as part of the current harvest work.

## Validated in practice: continuity is a property of durable state

The claim underneath this whole model — that a worker is a *replaceable executor* and continuity lives in Relay's durable state, not in any provider's session — is not just asserted; it has been demonstrated end to end.

A single real unit of work (`pricing/document-model`) was carried across **three different worker instances of two providers** — **Claude → Codex → a fresh Claude** — where each worker received *only* the provider-neutral bootstrap (resolved Project + Work Item references) plus read/write access to the repository. At every hop there was **no shared transcript, no provider session, no `/resume`, and no manually copied reasoning.**

- The **Codex** worker, from Claude's durable state alone, correctly reconstructed the objective and current code, then produced a genuinely project-aware continuation (a commercial-boundary decision record) — even independently rediscovering the project's own "read the resolved projection, not a tier id" convention.
- The **fresh Claude** worker, from the harvest of Codex's work alone, correctly reconstructed the objective, what existed before Codex, what Codex changed, the current state, the remaining work, and the correct next action — judging, rightly, that the next step was a human policy decision, not code.

So the loop closed both ways: a foreign provider can **consume** Relay's durable state *and* **produce** provider-neutral durable state a different provider resumes from. The one limitation observed was environmental — a locked-down worker sandbox could not run the harvest CLI to emit its own result, so the runtime did the mechanical emit; that is a sandbox-access concern, **not** a contract or per-provider-adapter one. This is the evidence base for the first principle below. The full experiment log (E1, E2) lives in `harvest-design.md` R1.11.

## Architectural principles to record

- **Workers are ephemeral. Work is durable.**
- **Project and Work Item are Relay's required context scopes.**
- **Organisation Context is optional**, and Relay must work without it.
- **Organisation knowledge is externally owned, not Relay-owned.**
- Relay may eventually **consume and contribute to** Organisation Context.
- Organisation contribution should be **governed / proposed, not assumed to be direct mutation**.
- **One fact, one authoritative home.**
- **A durable reference must resolve to durable authoritative state.**
- **Views / projections are not automatically authoritative state** (e.g. the Markdown handover projects the checkpoint; the checkpoint is the truth).
- **Do not couple Relay's core model** to a particular EA repository, notation, storage engine, AI provider, or visualisation technology.
