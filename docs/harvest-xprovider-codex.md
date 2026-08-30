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

## Static findings before the model call (from this session)

The bootstrap, worktree, and Codex ingestion were all validated headless; only the model call was blocked (auth). Two gaps are already visible without the live run:

1. **`brief_path` is a dangling reference — gap C (with an A flavour).** `relay/briefs/pricing-model-brief.md` is **gitignored local scratch**; it is not tracked and not in the worktree, so no fresh worker (Codex *or* Claude) can read it from the tree. The bootstrap references a "durable" artefact that isn't durable. Mitigation already in place: the `resume_delta` is self-contained (names the overage slice, the `enforceDocumentsAllowance` symbol, the scope edges), and that symbol *is* greppable — so orientation is feasible without the brief; the brief's richer context (alternatives, threat model) is simply unavailable.
2. **Project conventions live in `CLAUDE.md` — gap C.** It is present and readable in the worktree (281 lines, tracked), but Codex won't auto-load it (Codex's convention is `AGENTS.md`, which is absent) and the bootstrap doesn't point at it. So Codex would miss the project's conventions unless told where they are.

**CLAUDE.md determination (as asked — not solved here):** because `CLAUDE.md` is a normal readable file, simply *pointing the bootstrap at the existing project-instructions file* (whatever its name) is very likely sufficient for Codex — a whole new provider-neutral project-instructions *concept* is **not** yet warranted. The near-term gap is only that the bootstrap currently points at nothing for conventions. (Left unsolved by design.)

## Environment note

`codex exec` was exercised end-to-end in this session up to the model call; it accepted the prompt and the read-only sandbox against the real worktree, but returned `401 Unauthorized` because Codex is not logged in here (gap **D**). Run `codex login` first, then the model step completes the proof.
