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
