# Manual cross-provider proof — Codex CLI continues Claude's work

_A by-hand experiment: a fresh **Codex** worker resumes real Relay work from **only** the provider-neutral bootstrap + the existing worktree — no Claude transcript, session id, `/resume`, or hand-reconstructed context. This is a validation harness, **not** a Codex adapter (none is built)._

## Prerequisite (one-time)

Codex CLI must be logged in — in the automated shell it reports **"Not logged in"** (no `~/.codex/auth.json`), and every model call returns `401`. Log in interactively first:

```
! codex login
```

(Everything else below runs headless via `codex exec`.)

## The experiment

Uses one real, low-risk item — `pricing/document-model` — run **read-only** so Codex cannot modify production code; the proof is *information sufficiency*, not code output.

```bash
CE=~/Documents/castles-erp
RH=~/Documents/relay/scripts/relay_harvest.py
SCRATCH=/tmp/xprov ; rm -rf "$SCRATCH"; mkdir -p "$SCRATCH/handover"
cp "$CE/relay/board.md" "$SCRATCH/board.md"          # scratch relay-root: writes nothing into castles-erp
WT=$(git -C "$CE" worktree list | awk '/documents-allowance-enforce/{print $1}')
HEAD=$(git -C "$WT" rev-parse HEAD)

# 1. Claude's worker emits a harvest result (references + disposition + resume delta), runtime applies it
cat <<JSON | python3 "$RH" --relay-root "$SCRATCH" emit
{"harvest_version":1,"lap_id":"xprov-1","work_item":"pricing/document-model",
 "disposition":"stopped:needs-judgment",
 "references":{"branch":"documents-allowance-enforce","head_sha":"$HEAD",
   "brief":"relay/briefs/pricing-model-brief.md","pr":719},
 "resume_delta":{"stage":"build",
   "next_slice":"Overage slice: allow document creation PAST the monthly cap but BILL it at EUR0.15/doc via our own invoicing. FIRST decide: Free stays hard-capped vs paid tiers meter into overage.",
   "in_flight":"clean",
   "scope_edges":["do not touch the counting spine (shipped)","reuse enforceDocumentsAllowance, do not rebuild the meter"],
   "open_questions":["Free hard-capped vs paid-tier overage — which commercial boundary?"]}}
JSON
python3 "$RH" --repo "$CE" --relay-root "$SCRATCH" apply >/dev/null

# 2. Claude session is discarded (do nothing / close it). 3. Relay rediscovers + bootstraps:
python3 "$RH" --repo "$CE" --relay-root "$SCRATCH" bootstrap pricing/document-model > "$SCRATCH/bootstrap.json"

# 4. Codex receives ONLY the bootstrap + read access to the worktree
BOOT=$(cat "$SCRATCH/bootstrap.json")
codex exec -s read-only -C "$WT" --skip-git-repo-check "You are a fresh coding agent taking over in-flight work from a previous agent that is GONE. You have NO access to its transcript, chat, or session — ONLY the handoff below and this repository (cwd = the worktree). Do NOT modify files. 1) In 3-4 sentences say what this work item is and the single most concrete next step. 2) Verify against the repo: name the real files/dirs you'd start in, citing what you found or didn't. 3) List anything you needed but could not obtain from the handoff or the repo.

HANDOFF: $BOOT"
```

## Pass criteria

- Codex names the correct task (the documents-overage billing slice) and a sensible next step **from the bootstrap alone**.
- It locates the real code (`packages/core/src/documents/documents-allowance.ts` — `enforceDocumentsAllowance` is greppable) without the Claude transcript.
- Its "couldn't find" list contains only things the bootstrap legitimately omits (see gaps below), not the core task.

## Gap classification (record each miss as one of)

- **A** genuinely missing durable work state · **B** provider bootstrap/instruction issue · **C** project knowledge/conventions issue · **D** environment/tooling issue · **E** Relay lifecycle assumption.

## Portability gaps — found, then fixed (before the live run)

The bootstrap, worktree, and Codex ingestion were validated headless; only the model call was blocked (auth). Two portability gaps were found and **fixed at the bootstrap layer** (no checkpoint-schema change) so the live run starts clean:

1. **Dangling brief — RESOLVED.** Correction from investigation: briefs **are** durable — tracked on `main` in real projects (the `relay/briefs/` gitignore is *plugin-repo* dogfooding scratch only), and `explore` commits them. The earlier "dangling brief" was a **fabricated filename** in the test harvest result, and some items (`pricing/document-model`) legitimately have **no** brief — their plan lives in the board Detail. Fix: the bootstrap now **resolves** the brief against durable state (worktree → repo → `origin/main`) and either presents a resolvable `brief_path` (with `brief_source`) or marks `brief_status: "absent"` with `brief_fallback: "resume_delta + the board row Detail"` — **never a dangling path**. Real check: `finance/money-evidence` → brief resolved from the worktree; `pricing/document-model` → brief absent + fallback.
2. **Project conventions not pointed at — RESOLVED.** The bootstrap now carries a provider-neutral `project_instructions` list of project-local instruction/guardrail files that **actually resolve** (e.g. `CLAUDE.md`). It never creates `AGENTS.md`, never duplicates or renames anything — it just points at what the project already has. Real check: `project_instructions: ["CLAUDE.md"]`.

**CLAUDE.md determination (as asked):** since `CLAUDE.md` is a normal readable file, *pointing the bootstrap at the existing project-instructions file* is sufficient — no new provider-neutral project-instructions *concept* was warranted, and none was built beyond the `project_instructions` pointer list. Codex reads whatever files that list names.

**Bootstrap invariant (now enforced):** every reference the bootstrap presents either resolves to durable readable state or is explicitly absent-with-fallback; `assert_no_dangling` refuses to emit anything else. So the payload handed to Codex has no silent dangling references.

## Environment note

`codex exec` was exercised end-to-end in this session up to the model call; it accepted the prompt and the read-only sandbox against the real worktree, but returned `401 Unauthorized` because Codex is not logged in here (gap **D**). Run `codex login` first, then the model step completes the proof.
