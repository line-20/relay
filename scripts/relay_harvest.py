#!/usr/bin/env python3
"""relay_harvest.py — first runtime slice: durable worker-harvest & recovery.

Proves the loop from docs/harvest-design.md (Revision R1):

    durable work  ->  worker disappears  ->  Relay rediscovers work  ->  fresh
    worker resumes

without Claude /resume and without transcript archaeology.

Design anchors it implements (see docs/harvest-design.md):
  - The worker EMITS a structured Harvest Result to a write-ahead location
    (unique per lap_id -> conflict-free). §1, §3.
  - The runtime APPLIES results idempotently to a canonical durable checkpoint
    + shared homes, marking completion last (WAL + idempotent replay). §3.
  - Rediscovery reads only durable sources: the board's active rows, git
    worktrees/branches, and the persisted checkpoint. R1.3, R1.7.
  - Replace produces a provider-neutral resume context from durable state —
    no session id, no transcript. R1.4 tier (b).
  - The Markdown handover is a PROJECTION of the checkpoint, never canonical. §4.
  - Local checkpoint = a local git commit; no network required. R1.6.

Provider neutrality: durable files (results, checkpoints) carry NO Claude- or
session-specific fields. `lap_id` is an opaque, provider-agnostic string. The
only place a provider/session id may appear is an OPTIONAL local hints file,
which is never required to recover work.
"""
from __future__ import annotations
import argparse, json, os, re, subprocess, sys, tempfile, time

HARVEST_VERSION = 1
REQUIRED_RESULT_KEYS = ("harvest_version", "lap_id", "work_item", "disposition", "resume_delta")
DISPOSITIONS = {"advanced", "merged", "parked", "watching", "reflect-back"}  # or "stopped:<gate>"
RESUME_STATES = {"done", "remaining"}  # per-path in_flight state (the whole tree uses the IN_FLIGHT_CLEAN sentinel)
IN_FLIGHT_CLEAN = "clean"              # string form of in_flight for a clean tree (list form: omit or [])
ACTIVE_GLYPHS = ("⚙", "🔍")
_BRANCH_TOKEN = re.compile(r"^[A-Za-z0-9][\w./+-]*$")  # git-ref-ish first token
_BANNED_PROVIDER_KEYS = ("session_id", "claude_session", "provider")  # durable state is provider-neutral


def _valid_branch(tok):
    """A branch value from free-text frontmatter is trustworthy only if ref-shaped."""
    return bool(tok) and tok.lower() != "none" and bool(_BRANCH_TOKEN.match(tok))


class HarvestError(Exception):
    """Raised on a malformed/incomplete harvest result — nothing is written."""


def _scan_provider_leak(obj, where):
    """Recurse dicts/lists and reject any banned provider/session key at ANY depth. The checkpoint is
    pushed to origin permanently and copies `references`/`resume_delta` wholesale, so a top-level-only
    denylist would let a nested `{"meta": {"session_id": …}}` or an `in_flight[i].session_id` land in
    shared git history. Cheap: durable payloads are small."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k in _BANNED_PROVIDER_KEYS:
                raise HarvestError(f"durable {where} must not carry provider field {k!r}")
            _scan_provider_leak(v, where)
    elif isinstance(obj, list):
        for item in obj:
            _scan_provider_leak(item, where)


# ---------- small io helpers ----------

def _run_git(args, cwd, env=None):
    try:
        run_env = None
        if env:
            run_env = {**os.environ, **env}
        return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, env=run_env)
    except OSError as e:
        # git not on PATH, fd exhaustion, a transient OS error — surface as a FAILED run, never let
        # it raise. Callers already branch on returncode; a replication path that must "never fail an
        # apply" (R1.12) depends on this not escaping.
        return subprocess.CompletedProcess(["git", *args], returncode=127, stdout="", stderr=str(e))


def _slug_key(slug: str) -> str:
    """Filesystem-safe key for a track/slug work item."""
    return re.sub(r"[^\w.-]", "__", slug)


def _atomic_write(path: str, text: str):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = f"{path}.tmp.{os.getpid()}"
    with open(tmp, "w") as fh:
        fh.write(text)
    os.replace(tmp, path)


def _read_json(path):
    try:
        with open(path) as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return None


# ---------- durable paths (all under <relay_root>/harvest/<slug_key>/) ----------

def _item_dir(relay_root, slug):
    return os.path.join(relay_root, "harvest", _slug_key(slug))

def _results_dir(relay_root, slug):
    return os.path.join(_item_dir(relay_root, slug), "results")

def _checkpoint_path(relay_root, slug):
    return os.path.join(_item_dir(relay_root, slug), "checkpoint.json")

def _applied_path(relay_root, slug):
    return os.path.join(_item_dir(relay_root, slug), "applied.json")


# ---------- 1. emit (worker side): write the harvest result to the WAL ----------

def _validate_resume_delta(rd: dict):
    """Field-level shape of resume_delta — the resume-state contract (docs/harvest-design.md).
    Each field is checked WHEN PRESENT; none is required, because a merged/parked lap
    legitimately has nothing to resume (an empty resume_delta is valid). The point is to reject
    a *malformed* delta at emit time, so a cold resumer never inherits a broken one at read time.
    Matches what the worker emits and _render_handover_md consumes."""
    # Gate on key PRESENCE, not on a non-None value: rd.get(k) can't tell an absent key from a
    # present `null`, but the renderer can (rd.get(k, default) only falls back when k is absent), so
    # a present null would pass here and then crash _render_handover_md. Absent keys stay valid (an
    # empty resume_delta is fine for a merged/parked lap); a present key must be well-formed.
    if "next_slice" in rd:
        ns = rd["next_slice"]
        if not isinstance(ns, str) or not ns.strip():
            raise HarvestError("resume_delta.next_slice must be a non-empty string when present")
    if "in_flight" in rd:
        inflight = rd["in_flight"]
        if isinstance(inflight, str):
            if inflight != IN_FLIGHT_CLEAN:
                raise HarvestError(
                    f"resume_delta.in_flight string must be {IN_FLIGHT_CLEAN!r}, got {inflight!r}")
        elif isinstance(inflight, list):
            for i, entry in enumerate(inflight):
                if not isinstance(entry, dict):
                    raise HarvestError(f"resume_delta.in_flight[{i}] must be an object")
                if not isinstance(entry.get("path"), str) or not entry["path"].strip():
                    raise HarvestError(f"resume_delta.in_flight[{i}].path must be a non-empty string")
                if entry.get("state") not in RESUME_STATES:
                    raise HarvestError(
                        f"resume_delta.in_flight[{i}].state must be one of {sorted(RESUME_STATES)}, "
                        f"got {entry.get('state')!r}")
        else:  # None (present null), or any non-str/non-list
            raise HarvestError(
                f"resume_delta.in_flight must be the string {IN_FLIGHT_CLEAN!r} or a list of "
                "{path, state} objects")
    for key in ("scope_edges", "open_questions"):
        if key in rd and not isinstance(rd[key], list):
            raise HarvestError(f"resume_delta.{key} must be a list when present")
    if "stage" in rd:
        stage = rd["stage"]
        if not isinstance(stage, str) or not stage.strip():
            raise HarvestError("resume_delta.stage must be a non-empty string when present")
    # Provider-neutrality applies inside resume_delta too — durable state carries no provider identity
    # (recurse: a banned key on an in_flight entry or a nested object must be caught, not just a top key).
    _scan_provider_leak(rd, "resume_delta")


def validate_result(result: dict):
    if not isinstance(result, dict):
        raise HarvestError("harvest result must be a JSON object")
    missing = [k for k in REQUIRED_RESULT_KEYS if k not in result]
    if missing:
        raise HarvestError(f"harvest result missing required keys: {missing}")
    if result["harvest_version"] != HARVEST_VERSION:
        raise HarvestError(f"unsupported harvest_version {result['harvest_version']!r}")
    disp = result["disposition"]
    if not (disp in DISPOSITIONS or (isinstance(disp, str) and disp.startswith("stopped:"))):
        raise HarvestError(f"unknown disposition {disp!r}")
    if not isinstance(result["resume_delta"], dict):
        raise HarvestError("resume_delta must be an object")
    _validate_resume_delta(result["resume_delta"])
    if not isinstance(result["lap_id"], str) or not result["lap_id"]:
        raise HarvestError("lap_id must be a non-empty opaque string")
    if _slug_key(result["work_item"]) in (".", ".."):     # would resolve harvest/<slug> to a parent dir
        raise HarvestError(f"invalid work_item {result['work_item']!r}")
    # provider-neutrality guard: reject provider/session leakage ANYWHERE in the durable payload — the
    # whole result is scanned recursively (top level, `references`, `resume_delta`, nested objects and
    # list entries), because _build_checkpoint copies references/resume_delta wholesale into the
    # checkpoint that is committed and pushed to origin permanently.
    _scan_provider_leak(result, "harvest result")


def emit_result(relay_root: str, result: dict) -> str:
    """Validate and durably stage one harvest result. Malformed -> raise, write nothing."""
    validate_result(result)  # fail-safe: raises before any write
    slug, lap = result["work_item"], result["lap_id"]
    path = os.path.join(_results_dir(relay_root, slug), f"{_slug_key(lap)}.json")
    _atomic_write(path, json.dumps(result, indent=2))
    return path


# ---------- 3. apply (runtime side): WAL -> checkpoint + shared homes, idempotent ----------

def _build_checkpoint(result: dict) -> dict:
    refs = result.get("references", {}) or {}
    return {
        "harvest_version": HARVEST_VERSION,
        "work_item": result["work_item"],
        "applied_from_lap": result["lap_id"],
        "applied_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "disposition": result["disposition"],
        "references": refs,
        "resume_delta": result["resume_delta"],
        "checkpoint_ref": refs.get("head_sha"),
    }


def _append_discoveries(board_path, discoveries):
    """Append discovered follow-ups to the board, deduped by stable id. Idempotent."""
    if not discoveries or not board_path or not os.path.exists(board_path):
        return 0
    with open(board_path) as fh:
        board = fh.read()
    def _cell(s):  # keep a discovery to a single, well-formed table cell
        return re.sub(r"[\r\n|]+", " ", str(s)).strip()

    added = 0
    lines = []
    for d in discoveries:
        did = _cell(d.get("id"))
        if not did or f"disc:{did}" in board:  # already on the board
            continue
        title = _cell(d.get("title", "(untitled)"))
        one = _cell(d.get("one_line", ""))
        lines.append(f"| 💡 {title} | {one} | discovered | <!-- disc:{did} -->")
        added += 1
    if added:
        if not board.endswith("\n"):
            board += "\n"
        board += "\n".join(lines) + "\n"
        _atomic_write(board_path, board)
    return added


def _render_handover_md(cp: dict) -> str:
    """§4 — the Markdown handover as a PROJECTION of the checkpoint (never canonical)."""
    rd = cp.get("resume_delta", {})
    refs = cp.get("references", {})
    inflight = rd.get("in_flight")
    if inflight is None:  # absent, or a legacy checkpoint with an explicit null (pre-validation)
        inflight = "clean"
    if isinstance(inflight, list):
        inflight = "\n".join(f"- `{i.get('path')}` — {i.get('state','?')}" for i in inflight) or "None."
    scope = rd.get("scope_edges") or []
    oq = rd.get("open_questions") or []
    return "\n".join([
        f"# Handover: {rd.get('next_slice') or cp['work_item']}",
        "",
        "_Projection of the durable checkpoint — not canonical. Regenerated from "
        f"harvest/{_slug_key(cp['work_item'])}/checkpoint.json._",
        "",
        f"- item: `{cp['work_item']}`",
        f"- branch: `{refs.get('branch','?')}`",
        f"- stage: `{rd.get('stage','?')}`  ·  disposition: `{cp.get('disposition','?')}`",
        f"- checkpoint_ref: `{cp.get('checkpoint_ref') or '(none)'}`",
        f"- brief: `{refs.get('brief','?')}`" + (f"  ·  PR #{refs['pr']}" if refs.get("pr") else ""),
        "",
        "## Next objective", rd.get("next_slice") or "(see brief)",
        "",
        "## In flight", inflight,
        "",
        "## Done when", "\n".join(f"- {s}" for s in scope) or "(see brief slice)",
        "",
        "## Open questions", "\n".join(f"- {q}" for q in oq) or "None.",
        "",
    ])


def apply_one(relay_root, slug, result, board_path=None, write_projection=True):
    """Apply one result. Ordered so a crash before the final marker replays cleanly.

    write_projection=False skips step (3): a caller that authors its own richer handover
    (e.g. /handover) suppresses the thin projection so main never ends up advertising it.
    The checkpoint (step 1) is still the canonical durable state either way."""
    lap = result["lap_id"]
    cp = _build_checkpoint(result)
    # (1) canonical checkpoint — deterministic, atomic
    _atomic_write(_checkpoint_path(relay_root, slug), json.dumps(cp, indent=2))
    # (2) shared home: discoveries -> board, deduped
    _append_discoveries(board_path, result.get("discoveries"))
    # (3) projection: render the human-readable handover from the checkpoint
    if write_projection:
        hv_dir = os.path.join(relay_root, "handover")
        _atomic_write(os.path.join(hv_dir, f"next-{_slug_key(lap)}.md"), _render_handover_md(cp))
    # (4) completion marker LAST — its presence == applied
    applied = _read_json(_applied_path(relay_root, slug)) or {"applied": []}
    if lap not in applied["applied"]:
        applied["applied"].append(lap)
    applied["checkpoint_lap"] = lap
    _atomic_write(_applied_path(relay_root, slug), json.dumps(applied, indent=2))


def apply_pending(relay_root, slug=None, board_path=None, repo_root=None, replicate=True,
                  remote="origin", write_projection=True):
    """Apply all unapplied results (WAL replay). Idempotent + retryable.

    When repo_root is given and replicate is on, each item's checkpoint is committed to the durable
    branch and pushed (git-durability, slice 3) — so a pruned/foreign-machine worktree (or another
    device) still resumes. Replication is best-effort and reported under summary["replication"]; it
    never fails the apply. Omit repo_root (or pass replicate=False) to apply state only.

    write_projection=False suppresses the Markdown projection handover (step 3 of apply_one) — a
    caller that authors its own richer handover (/handover) passes it so main never advertises the
    thin projection; the checkpoint is still the canonical durable state."""
    slugs = [slug] if slug else _all_item_slugs(relay_root)
    summary = {"applied": 0, "skipped": 0, "items": []}
    for s in slugs:
        applied = (_read_json(_applied_path(relay_root, s)) or {}).get("applied", [])
        rdir = _results_dir(relay_root, s)
        if os.path.isdir(rdir):
            for fn in sorted(os.listdir(rdir)):
                if not fn.endswith(".json"):
                    continue
                result = _read_json(os.path.join(rdir, fn))
                if not result:
                    continue
                lap = result.get("lap_id")
                if lap in applied:
                    summary["skipped"] += 1
                    continue
                try:
                    validate_result(result)
                except HarvestError:
                    summary["skipped"] += 1  # malformed staged result: skip, don't corrupt state
                    continue
                apply_one(relay_root, s, result, board_path=board_path,
                          write_projection=write_projection)
                applied.append(lap)
                summary["applied"] += 1
        # Replicate ONCE per item, reconcile-style: drive it against the checkpoint's CURRENT state
        # whether or not a lap was newly applied this pass. This makes replication self-healing —
        # apply_one writes its completion marker BEFORE this runs, so a crash between the two, or a
        # push a sibling's advance rejected non-fast-forward, would otherwise leave a checkpoint
        # applied-but-never-durable with no retry path (the lap is already in applied.json, so a
        # per-lap push would never fire again). Keying on checkpoint-vs-remote instead re-drives it
        # next apply. The checkpoint is an upsert (latest lap wins), so committing the final state
        # once per invocation is the per-checkpoint durability the ref decision calls for.
        if repo_root and replicate:
            cp = _read_json(_checkpoint_path(relay_root, s))
            if cp:
                summary.setdefault("replication", []).append(
                    _replicate_checkpoint(repo_root, relay_root, s,
                                          cp.get("applied_from_lap") or "reconcile",
                                          remote=remote, board_path=board_path))
        summary["items"].append(s)
    return summary


def _all_item_slugs(relay_root):
    hroot = os.path.join(relay_root, "harvest")
    if not os.path.isdir(hroot):
        return []
    out = []
    for name in os.listdir(hroot):
        cp = _read_json(os.path.join(hroot, name, "checkpoint.json"))
        if cp:
            out.append(cp["work_item"])
        elif os.path.isdir(os.path.join(hroot, name, "results")):
            # recover slug from any staged result
            for fn in os.listdir(os.path.join(hroot, name, "results")):
                r = _read_json(os.path.join(hroot, name, "results", fn))
                if r:
                    out.append(r["work_item"]); break
    return sorted(set(out))


# ---------- 1/6. discover active work from durable sources only ----------

def _board_cells(line):
    """Split a board table row into cells. The board schema is
    `| Item | Status | Owner | Latest handover | Detail… |`, so columns 1-4 are
    structured and column 5+ (Detail, which contains free prose incl. pipes,
    glyphs and handover-like paths) is merged back together — never parsed for
    structured values. Returns None for a non-row line."""
    s = line.rstrip("\n")
    if not s.lstrip().startswith("|"):
        return None
    parts = [c.strip() for c in s.strip().strip("|").split("|")]
    if len(parts) < 4:
        return None  # partial/malformed row — fail safe (caller skips)
    item, status, owner, handover = parts[0], parts[1], parts[2], parts[3]
    return {"item": item, "status": status, "owner": owner, "handover": handover}


def _slug_from_item_cell(cell):
    m = re.search(r"`([^`]+)`", cell)          # prefer the backticked identity
    tok = (m.group(1) if m else cell).strip()
    tok = tok.split()[0] if tok else ""
    return tok if re.match(r"^[\w][\w./-]*$", tok) and tok.lower() != "item" else None


def _parse_board_active(board_path):
    """Active (⚙/🔍) rows as (slug, handover_rel|None) — decided ONLY from the
    authoritative cells (Item / Status / Latest-handover), never from Detail prose."""
    if not board_path or not os.path.exists(board_path):
        return []
    rows = []
    with open(board_path) as fh:
        for line in fh:
            cells = _board_cells(line)
            if not cells:
                continue
            slug = _slug_from_item_cell(cells["item"])
            if not slug:                                    # header/separator/no identity
                continue
            if not any(g in cells["status"] for g in ACTIVE_GLYPHS):  # STATUS cell only
                continue
            hv = re.search(r"(handover/[\w./-]+\.md)", cells["handover"])  # 4th cell only
            rows.append((slug, hv.group(1) if hv else None))
    return rows


def _branch_from_handover_file(relay_root, handover_rel):
    """First ref-shaped token of the `branch:` frontmatter of a SPECIFIC handover."""
    if not handover_rel:
        return None
    path = os.path.join(relay_root, handover_rel)
    try:
        with open(path) as fh:
            text = fh.read()
    except OSError:
        return None
    m = re.search(r"^branch:\s*(.+)$", text, re.M)
    if not m:
        return None
    tok = m.group(1).strip().split()[0] if m.group(1).strip() else ""
    return tok if _valid_branch(tok) else None


def _git_worktrees(repo_root):
    out = _run_git(["worktree", "list", "--porcelain"], repo_root).stdout
    trees, cur = [], {}
    for line in out.splitlines():
        if line.startswith("worktree "):
            if cur:
                trees.append(cur)
            cur = {"path": line[len("worktree "):]}
        elif line.startswith("branch "):
            cur["branch"] = line[len("branch "):].replace("refs/heads/", "")
    if cur:
        trees.append(cur)
    return trees


def _branch_for(relay_root, slug, handover_rel, cp):
    """Resolve an item's branch, most-authoritative first:
    (1) the checkpoint's own reference (a clean git ref emitted by the worker),
    (2) the board row's designated handover's frontmatter (validated),
    (3) last-ditch: newest handover mentioning the slug (validated).
    Returns None rather than a malformed value — a garbage branch is worse than none."""
    ref = (cp or {}).get("references", {}).get("branch")
    if _valid_branch(ref):
        return ref
    b = _branch_from_handover_file(relay_root, handover_rel)
    if b:
        return b
    hv_dir = os.path.join(relay_root, "handover")
    if os.path.isdir(hv_dir):
        for fn in sorted(os.listdir(hv_dir), reverse=True):
            try:
                with open(os.path.join(hv_dir, fn)) as fh:
                    txt = fh.read()
            except OSError:
                continue
            if slug in txt:
                m = re.search(r"^branch:\s*(.+)$", txt, re.M)
                tok = (m.group(1).strip().split()[0] if m and m.group(1).strip() else "")
                if _valid_branch(tok):
                    return tok
                break  # this is the item's newest handover; don't keep scanning older ones
    return None


def _checkpoint_resume_delta(cp: dict, slug: str) -> dict:
    """The checkpoint's resume_delta, validated. Raises HarvestError (never TypeError) on a
    malformed or legacy checkpoint — a present-`null`/missing/non-object resume_delta, or a
    bad-shaped one — so the read side fails closed with an actionable message instead of
    silently seeding a broken resumer. Mirrors validate_result's isinstance guard (a
    pre-validation checkpoint may hold shapes emit would reject today)."""
    rd = cp.get("resume_delta")
    if not isinstance(rd, dict):
        raise HarvestError(
            f"checkpoint for {slug!r} has a malformed resume_delta ({type(rd).__name__}) — "
            "regenerate the handover (`/relay:handover`) to rewrite it")
    _validate_resume_delta(rd)
    return rd


def discover_active(repo_root, relay_root, board_path=None, hints_path=None):
    board_path = board_path or os.path.join(relay_root, "board.md")
    hints = _read_json(hints_path) if hints_path else None
    hints = hints or {}
    worktrees = _git_worktrees(repo_root)
    items = []
    for slug, handover_rel in _parse_board_active(board_path):
        cpp = _checkpoint_path(relay_root, slug)
        cp = _read_json(cpp)
        cp_present = os.path.exists(cpp)
        # Enumerate path (R1.7 step 1): resilient listing — one bad checkpoint must NOT blind the
        # whole active-work view, so validate per-item and degrade to a status, never raise.
        cp_status, rd = None, {}
        if cp is not None:
            try:
                rd = _checkpoint_resume_delta(cp, slug)
                cp_status = "valid"
            except HarvestError:          # a contract violation degrades; a real bug still surfaces
                cp_status = "invalid"
        elif cp_present:
            cp_status = "invalid"         # file on disk but unparseable JSON — corrupt; regenerate it
        branch = _branch_for(relay_root, slug, handover_rel, cp)
        wt = next((w for w in worktrees if branch and w.get("branch") == branch), None)
        items.append({
            "work_item": slug,
            "branch": branch,
            "worktree": wt["path"] if wt else None,
            "has_checkpoint": cp_present,              # a file exists (parseable or not)
            "checkpoint_status": cp_status,            # None (no file) | valid | invalid
            # replicated: is this checkpoint on the durable remote branch, i.e. resumable from
            # another device/clone (git-durability, slice 3)? True/False, or None when undeterminable
            # (no checkpoint, or the remote branch isn't fetched here). Reads the local remote ref only.
            "replicated": (_checkpoint_on_remote(repo_root, relay_root, slug) if cp_present else None),
            "stage": rd.get("stage"),                  # None on invalid — never a present-null crash
            "disposition": (cp or {}).get("disposition"),
            "session_hint": hints.get(slug),           # optional; never required
        })
    return items


# ---------- 6. replace: provider-neutral resume context from durable state ----------

def resume_context(repo_root, relay_root, slug, board_path=None):
    cp = _read_json(_checkpoint_path(relay_root, slug))
    if not cp:
        raise HarvestError(f"no durable checkpoint for {slug!r} — cannot replace from state")
    # Replace path (R1.7 step 3): this seeds a worker, so fail CLOSED on a malformed/legacy
    # checkpoint rather than resume from broken state (the brief's slice-2 acceptance).
    _checkpoint_resume_delta(cp, slug)
    refs = cp.get("references", {})
    row = next((r for r in _parse_board_active(board_path or os.path.join(relay_root, "board.md"))
                if r[0] == slug), (slug, None))
    branch = _branch_for(relay_root, slug, row[1], cp)
    wt = next((w for w in _git_worktrees(repo_root) if branch and w.get("branch") == branch), None)
    return {
        "work_item": slug,
        "branch": branch,
        "worktree_path": wt["path"] if wt else None,
        "brief": refs.get("brief"),
        "checkpoint_ref": cp.get("checkpoint_ref"),
        "resume_delta": cp.get("resume_delta"),
        "continue_command": f"/relay:continue {slug}",
        "source": "durable-state",
        "requires_transcript": False,      # tier (b): recover from worktree/git only
        "requires_session_id": False,
    }


# ---------- reference resolution (durably-resolvable guarantee) ----------

# Provider-neutral project-instruction filenames. We only ever LIST ones that
# already exist — we never create any (so no AGENTS.md-for-Codex, no duplication).
_INSTRUCTION_CANDIDATES = ("CLAUDE.md", "AGENTS.md", "GEMINI.md", ".cursorrules")


def _resolve_ref(repo_root, worktree_path, rel):
    """Where a repo-relative reference is DURABLY readable, or None. Checks the
    worker's worktree first (what it will actually read), then the repo root,
    then origin/main (durable even if this branch predates the file)."""
    if not rel:
        return (None, None)
    if os.path.isabs(rel):
        return (rel, "abs") if os.path.exists(rel) else (None, None)
    for base, src in ((worktree_path, "worktree"), (repo_root, "repo")):
        if base and os.path.exists(os.path.join(base, rel)):
            return (os.path.join(base, rel), src)
    if repo_root and _run_git(["cat-file", "-e", f"origin/main:{rel}"], repo_root).returncode == 0:
        return (f"origin/main:{rel}", "origin/main")   # read via `git show`
    return (None, None)


def _project_instructions(repo_root, worktree_path, relay_root):
    """Resolved project-local instruction/guardrail files a fresh worker must read
    before continuing. Returns only files that actually resolve — never a name that
    doesn't exist, never a provider-specific file we invented."""
    found = []
    for name in _INSTRUCTION_CANDIDATES:
        path, _ = _resolve_ref(repo_root, worktree_path, name)
        if path:
            found.append(name)
    rel_root = os.path.relpath(relay_root, repo_root) if repo_root else "relay"
    guardrails = f"{rel_root}/knowledge/guardrails.md"
    if _resolve_ref(repo_root, worktree_path, guardrails)[0]:
        found.append(guardrails)
    return found


# ---------- worker bootstrap: provider-neutral view over resume_context ----------

def worker_bootstrap(repo_root, relay_root, slug, board_path=None):
    """A provider-NEUTRAL bootstrap any coding agent (Claude, Codex, Mistral, …)
    could consume to continue recovered work. Constructed from existing
    authoritative state (resume_context + resolved references) — NOT a new durable
    contract, no checkpoint-schema change. No slash-command, no session id, no
    transcript. INVARIANT: every reference it presents either resolves to durable
    readable state, or is explicitly absent with a defined fallback — never a
    silent dangling path (enforce with validate_bootstrap / assert_no_dangling)."""
    ctx = resume_context(repo_root, relay_root, slug, board_path=board_path)
    rd = ctx.get("resume_delta") or {}
    wt = ctx["worktree_path"]

    brief_abs, brief_src = _resolve_ref(repo_root, wt, ctx.get("brief"))
    brief_ok = brief_abs is not None
    wt_ok = bool(wt) and os.path.isdir(wt)
    instr = _project_instructions(repo_root, wt, relay_root)

    # Resolved durable reference to the project board (the coordination home).
    # Never duplicates the board Detail — it points a worker at where the item's
    # authoritative row lives, keyed by the work_item slug. Derived in the view.
    rel_root = os.path.relpath(relay_root, repo_root) if repo_root else "relay"
    board_rel = f"{rel_root}/board.md"
    board_abs, board_src = _resolve_ref(repo_root, wt, board_rel)
    board_ref = board_rel if board_abs else None
    slug = ctx["work_item"]

    # A brief-less item's fallback must deterministically locate its board Detail.
    if brief_ok:
        brief_fallback = None
    elif board_ref:
        brief_fallback = (f"resume_delta + the `{slug}` row Detail in {board_ref} "
                          f"(the row whose Item cell is `{slug}`)")
    else:
        brief_fallback = "resume_delta"

    steps = []
    if wt_ok:
        steps.append(f"Change into the worktree at worktree_path ({wt}); "
                     f"branch {ctx['branch']} is already checked out.")
    else:
        steps.append(f"No live worktree; create one from the branch: "
                     f"git worktree add <path> {ctx['branch']}, then work there.")
    if instr:
        steps.append(f"Read the project instructions first: {', '.join(instr)}.")
    if brief_ok:
        steps.append(f"Read the brief ({brief_src}): {ctx.get('brief')}"
                     + (f" — via `git show {brief_abs}`" if brief_src == "origin/main" else ""))
    elif board_ref:
        steps.append(f"No brief file for this item — its plan is the resume_delta below plus its "
                     f"board Detail: open {board_ref} and read the row whose Item cell is `{slug}`.")
    else:
        steps.append("No brief file and no resolvable board — its plan is the resume_delta below.")
    steps.append("Inspect the repository directly (git log/status/diff and the code) — "
                 "you have everything; do NOT look for a previous worker's transcript.")
    steps.append(f"Continue from resume_delta (stage '{rd.get('stage')}'): {rd.get('next_slice')}.")

    return {
        "bootstrap_version": 1,
        "work_item": slug,
        "repo_root": repo_root,
        "worktree_path": wt if wt_ok else None,
        "worktree_status": "resolved" if wt_ok else "absent",
        "worktree_fallback": None if wt_ok else f"git worktree add <path> {ctx['branch']}",
        "branch": ctx["branch"],
        "checkpoint_ref": ctx["checkpoint_ref"],
        "brief_path": ctx.get("brief") if brief_ok else None,   # never a dangling path
        "brief_status": "resolved" if brief_ok else "absent",
        "brief_source": brief_src,                              # worktree | repo | origin/main | None
        "brief_fallback": brief_fallback,
        "board_ref": board_ref,                                 # resolved <root>/board.md, or None
        "board_source": board_src,
        "project_instructions": instr,                          # resolved files to read first
        "stage": rd.get("stage"),
        "resume_delta": rd,
        "objective": rd.get("next_slice"),
        "instructions": steps,
        "recovered_from": "durable-state",
        "requires_transcript": False,
        "requires_session_id": False,
    }


def validate_bootstrap(repo_root, bs):
    """Enforce the bootstrap invariant: every presented reference either resolves
    to durable readable state, or is explicitly marked absent with a fallback.
    Returns a list of violations (empty == valid)."""
    v = []
    wt = bs.get("worktree_path")
    if bs.get("worktree_status") == "resolved" and not (wt and os.path.isdir(wt)):
        v.append("worktree_path presented but does not resolve")
    if bs.get("worktree_status") == "absent" and not bs.get("worktree_fallback"):
        v.append("worktree absent without a fallback")
    if bs.get("brief_status") == "resolved":
        if not _resolve_ref(repo_root, wt, bs.get("brief_path"))[0]:
            v.append("brief_path presented but does not resolve")
    elif bs.get("brief_status") == "absent":
        if bs.get("brief_path") is not None:
            v.append("brief marked absent but a path is still present (dangling risk)")
        if not bs.get("brief_fallback"):
            v.append("brief absent without a fallback")
    for name in bs.get("project_instructions", []):
        if not _resolve_ref(repo_root, wt, name)[0]:
            v.append(f"project instruction {name!r} does not resolve")
    if bs.get("board_ref") and not _resolve_ref(repo_root, wt, bs["board_ref"])[0]:
        v.append("board_ref presented but does not resolve")
    if not bs.get("branch"):
        v.append("no branch reference")
    return v


def assert_no_dangling(repo_root, bs):
    issues = validate_bootstrap(repo_root, bs)
    if issues:
        raise HarvestError("bootstrap invariant violated: " + "; ".join(issues))
    return bs


# ---------- 7. local checkpoint: a local git commit; NO network ----------

def autosave(worktree, lap_id):
    """Make uncommitted work locally durable via a marked commit. No push (R1.6)."""
    _run_git(["add", "-A"], worktree)
    staged = _run_git(["diff", "--cached", "--quiet"], worktree)
    if staged.returncode == 0:  # nothing staged
        head = _run_git(["rev-parse", "HEAD"], worktree)
        return head.stdout.strip() or None
    _run_git(["commit", "--no-verify", "-m",
              f"wip: Relay autosave checkpoint\n\nRelay-Autosave: {lap_id}"], worktree)
    return _run_git(["rev-parse", "HEAD"], worktree).stdout.strip()


# ---------- 8. checkpoint git-durability: commit to the durable branch + push (R1.6) ----------
# Slice 3. The autosave above makes work locally durable on a *topic* branch; that is invisible
# to a fresh clone (which checks out the durable branch) and dies when the branch is merged+deleted.
# The rediscover/resume readers walk the checked-out working tree (discover_active / _all_item_slugs
# read <root>/harvest/*/checkpoint.json off the filesystem), so for a pruned or foreign-machine
# worktree — or a phone — to resume, every checkpoint must live in the DURABLE branch's working
# tree, which is where board.md and handovers already commit (R1.10). Hence: commit the checkpoint
# to the durable branch and push it. Local commit is the offline-safe floor; the push is
# opportunistic and NEVER fatal (R1.6 splits local durability from remote). See relay/decisions.md
# (2026-09-17, slice 3) for the ruled ref choice.

def _durable_branch(repo_root):
    """The branch Relay's durable state lives on — where board/handover/brief already commit.
    origin/HEAD's target when resolvable (no network — reads the local remote ref), else 'main'."""
    r = _run_git(["symbolic-ref", "--short", "refs/remotes/origin/HEAD"], repo_root)
    if r.returncode == 0 and r.stdout.strip():
        return r.stdout.strip().split("/", 1)[-1]
    return "main"


def _replicate_checkpoint(repo_root, relay_root, slug, lap, remote="origin", board_path=None):
    """Commit the just-applied checkpoint (+ completion marker, projection, board) to the durable
    branch and push it — WITHOUT touching repo_root's working tree, index, HEAD or local branch.
    Returns a status dict; NEVER raises — replication failing must not fail an apply.

    Uses the parallel-worktree-safe temp-index primitive that `/handover` Step 4b and `/tidy` use to
    write `main` while ~10 sessions run concurrent worktrees against one checkout (docs/conventions.md
    "Parallel-worktree-safe commits"): read the freshly-fetched durable tip into a throwaway index,
    stage only our files into it, write a tree and `commit-tree` it onto that tip, then push
    `<commit>:<durable>`. Because the parent is the fetched remote tip — never repo_root's (possibly
    stale) local branch — the push is a fast-forward whenever the remote hasn't moved since the fetch,
    and it lands on the durable branch by construction. So there is no branch guard and this runs
    correctly from ANY checkout, the slice worktree included; repo_root only needs the checkpoint
    files on disk. Nothing local advances, so an offline/non-ff push strands nothing: the next apply
    rebuilds from a fresh fetch and re-pushes (self-heal). The `Relay-Checkpoint` trailer marks it."""
    durable = _durable_branch(repo_root)
    paths = [_checkpoint_path(relay_root, slug), _applied_path(relay_root, slug),
             os.path.join(relay_root, "handover", f"next-{_slug_key(lap)}.md")]
    if board_path:
        paths.append(board_path)
    paths = [p for p in paths if os.path.exists(p)]
    if not paths:
        return {"lap": lap, "committed": False, "replicated": False, "reason": "no checkpoint files"}
    rels = [os.path.relpath(p, repo_root) for p in paths]

    fetch = _run_git(["fetch", remote, durable], repo_root)
    if fetch.returncode != 0:
        return {"lap": lap, "committed": False, "replicated": False,
                "reason": "offline: " + (fetch.stderr.strip().splitlines() or ["fetch failed"])[-1]}
    base = _run_git(["rev-parse", "--verify", "--quiet", "FETCH_HEAD"], repo_root).stdout.strip()
    if not base:
        return {"lap": lap, "committed": False, "replicated": False,
                "reason": f"no remote {remote}/{durable} to build on"}

    # A throwaway index seeded from the remote tip: read-tree/add/write-tree touch ONLY this file, so
    # repo_root's real index, working tree, HEAD and branch are never disturbed. `git add -- <rels>`
    # stages exactly our files (nothing a sibling session has staged in a shared checkout).
    fd, tmpidx = tempfile.mkstemp(prefix="relay-cp-idx-"); os.close(fd)
    try:
        idx = {"GIT_INDEX_FILE": tmpidx}
        rt = _run_git(["read-tree", base], repo_root, env=idx)
        if rt.returncode != 0:
            return {"lap": lap, "committed": False, "replicated": False,
                    "reason": "read-tree failed: " + (rt.stderr.strip().splitlines() or ["?"])[-1]}
        add = _run_git(["add", "--", *rels], repo_root, env=idx)
        if add.returncode != 0:
            return {"lap": lap, "committed": False, "replicated": False,
                    "reason": "add failed: " + (add.stderr.strip().splitlines() or ["?"])[-1]}
        tree = _run_git(["write-tree"], repo_root, env=idx).stdout.strip()
    finally:
        try:
            os.remove(tmpidx)
        except OSError:
            pass
    if not tree:
        return {"lap": lap, "committed": False, "replicated": False, "reason": "write-tree failed"}
    base_tree = _run_git(["rev-parse", f"{base}^{{tree}}"], repo_root).stdout.strip()
    if tree == base_tree:
        # our files are byte-identical to the remote tip already — idempotent re-apply, nothing to push.
        return {"lap": lap, "committed": False, "replicated": True, "sha": base}

    commit = _run_git(["commit-tree", tree, "-p", base, "-m",
                       f"relay: checkpoint {slug} @ {lap}\n\nRelay-Checkpoint: {lap}"], repo_root)
    if commit.returncode != 0 or not commit.stdout.strip():
        # unconfigured user.name/email, a hook refusal — nothing built, so don't push.
        return {"lap": lap, "committed": False, "replicated": False,
                "reason": "commit-tree failed: " + (commit.stderr.strip().splitlines() or ["unknown"])[-1]}
    sha = commit.stdout.strip()
    push = _run_git(["push", remote, f"{sha}:refs/heads/{durable}"], repo_root)  # non-ff/offline non-fatal
    ok = push.returncode == 0
    reason = None if ok else (
        (push.stderr.strip().splitlines() or ["push failed"])[-1] if push.stderr.strip()
        else "push failed (offline or remote rejected)")
    return {"lap": lap, "committed": True, "sha": sha, "replicated": ok, "reason": reason}


def _checkpoint_on_remote(repo_root, relay_root, slug, remote="origin", branch=None):
    """True/False when determinable, None when it can't be (no such remote ref) — is this item's
    checkpoint file byte-identical to the durable remote branch's copy? Reads the local
    remote-tracking ref only (no network). Used to report `replicated` without re-pushing.

    Compares blob hashes, not `git diff`: diff silently ignores an UNTRACKED file, so a
    never-committed checkpoint would falsely read as replicated. A missing remote blob, or a
    working file that has drifted since the push, both correctly read False."""
    branch = branch or _durable_branch(repo_root)
    ref = f"{remote}/{branch}"
    if _run_git(["rev-parse", "--verify", "--quiet", ref], repo_root).returncode != 0:
        return None  # remote branch not fetched here — can't tell
    rel = os.path.relpath(_checkpoint_path(relay_root, slug), repo_root)
    remote_blob = _run_git(["rev-parse", "--verify", "--quiet", f"{ref}:{rel}"], repo_root)
    if remote_blob.returncode != 0:
        return False  # the checkpoint path isn't on the remote branch at all
    local_blob = _run_git(["hash-object", _checkpoint_path(relay_root, slug)], repo_root)
    if local_blob.returncode != 0:
        return False
    return remote_blob.stdout.strip() == local_blob.stdout.strip()


# ---------- CLI ----------

def _relay_root(args):
    return args.relay_root or os.path.join(args.repo or os.getcwd(), "relay")


def main(argv=None):
    p = argparse.ArgumentParser(description="Relay harvest runtime (first slice)")
    p.add_argument("--repo", default=os.getcwd())
    p.add_argument("--relay-root")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("emit", help="stage a harvest result read as JSON from stdin")
    ap = sub.add_parser("apply", help="apply pending results (idempotent)")
    ap.add_argument("--slug")
    ap.add_argument("--no-replicate", action="store_true",
                    help="apply durable state only; skip the checkpoint commit+push (git-durability)")
    ap.add_argument("--no-projection", action="store_true",
                    help="skip the Markdown projection handover (the caller authors its own richer one)")
    ap.add_argument("--no-board", action="store_true",
                    help="leave board.md untouched (the caller owns the board commit)")
    sub.add_parser("discover", help="list active work from durable sources")
    rs = sub.add_parser("resume", help="print provider-neutral resume context for a work item")
    rs.add_argument("slug")
    bs = sub.add_parser("bootstrap", help="print a provider-neutral worker bootstrap for a work item")
    bs.add_argument("slug")
    cp = sub.add_parser("checkpoint", help="local autosave commit in a worktree")
    cp.add_argument("worktree"); cp.add_argument("lap_id")
    args = p.parse_args(argv)
    relay_root = _relay_root(args)
    board = os.path.join(relay_root, "board.md")

    if args.cmd == "emit":
        try:
            path = emit_result(relay_root, json.load(sys.stdin))
        except HarvestError as e:
            print(f"harvest result rejected: {e}", file=sys.stderr); return 2
        print(path); return 0
    if args.cmd == "apply":
        print(json.dumps(apply_pending(relay_root, slug=args.slug,
                                       board_path=None if args.no_board else board,
                                       repo_root=args.repo, replicate=not args.no_replicate,
                                       write_projection=not args.no_projection),
                         indent=2)); return 0
    if args.cmd == "discover":
        print(json.dumps(discover_active(args.repo, relay_root, board_path=board), indent=2)); return 0
    if args.cmd == "resume":
        try:
            print(json.dumps(resume_context(args.repo, relay_root, args.slug), indent=2))
        except HarvestError as e:
            print(str(e), file=sys.stderr); return 2
        return 0
    if args.cmd == "bootstrap":
        try:
            bs = assert_no_dangling(args.repo, worker_bootstrap(args.repo, relay_root, args.slug))
            print(json.dumps(bs, indent=2))
        except HarvestError as e:
            print(str(e), file=sys.stderr); return 2
        return 0
    if args.cmd == "checkpoint":
        print(autosave(args.worktree, args.lap_id) or ""); return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
