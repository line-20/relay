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
import argparse, json, os, re, subprocess, sys, time

HARVEST_VERSION = 1
REQUIRED_RESULT_KEYS = ("harvest_version", "lap_id", "work_item", "disposition", "resume_delta")
DISPOSITIONS = {"advanced", "merged", "parked", "watching", "reflect-back"}  # or "stopped:<gate>"
ACTIVE_GLYPHS = ("⚙", "🔍")
_BRANCH_TOKEN = re.compile(r"^[A-Za-z0-9][\w./+-]*$")  # git-ref-ish first token


def _valid_branch(tok):
    """A branch value from free-text frontmatter is trustworthy only if ref-shaped."""
    return bool(tok) and tok.lower() != "none" and bool(_BRANCH_TOKEN.match(tok))


class HarvestError(Exception):
    """Raised on a malformed/incomplete harvest result — nothing is written."""


# ---------- small io helpers ----------

def _run_git(args, cwd):
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True)


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
    if not isinstance(result["lap_id"], str) or not result["lap_id"]:
        raise HarvestError("lap_id must be a non-empty opaque string")
    # provider-neutrality guard: reject obvious provider leakage in durable state
    for banned in ("session_id", "claude_session", "provider"):
        if banned in result:
            raise HarvestError(f"durable harvest result must not carry provider field {banned!r}")


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
    added = 0
    lines = []
    for d in discoveries:
        did = d.get("id")
        if not did or f"disc:{did}" in board:  # already on the board
            continue
        title = d.get("title", "(untitled)")
        one = d.get("one_line", "")
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
    inflight = rd.get("in_flight", "clean")
    if isinstance(inflight, list):
        inflight = "\n".join(f"- `{i.get('path')}` — {i.get('state','?')}" for i in inflight) or "None."
    scope = rd.get("scope_edges") or []
    oq = rd.get("open_questions") or []
    return "\n".join([
        f"# Handover: {rd.get('next_slice', cp['work_item'])}",
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
        "## Next objective", rd.get("next_slice", "(see brief)"),
        "",
        "## In flight", inflight,
        "",
        "## Done when", "\n".join(f"- {s}" for s in scope) or "(see brief slice)",
        "",
        "## Open questions", "\n".join(f"- {q}" for q in oq) or "None.",
        "",
    ])


def apply_one(relay_root, slug, result, board_path=None):
    """Apply one result. Ordered so a crash before the final marker replays cleanly."""
    lap = result["lap_id"]
    cp = _build_checkpoint(result)
    # (1) canonical checkpoint — deterministic, atomic
    _atomic_write(_checkpoint_path(relay_root, slug), json.dumps(cp, indent=2))
    # (2) shared home: discoveries -> board, deduped
    _append_discoveries(board_path, result.get("discoveries"))
    # (3) projection: render the human-readable handover from the checkpoint
    hv_dir = os.path.join(relay_root, "handover")
    _atomic_write(os.path.join(hv_dir, f"next-{_slug_key(lap)}.md"), _render_handover_md(cp))
    # (4) completion marker LAST — its presence == applied
    applied = _read_json(_applied_path(relay_root, slug)) or {"applied": []}
    if lap not in applied["applied"]:
        applied["applied"].append(lap)
    applied["checkpoint_lap"] = lap
    _atomic_write(_applied_path(relay_root, slug), json.dumps(applied, indent=2))


def apply_pending(relay_root, slug=None, board_path=None):
    """Apply all unapplied results (WAL replay). Idempotent + retryable."""
    slugs = [slug] if slug else _all_item_slugs(relay_root)
    summary = {"applied": 0, "skipped": 0, "items": []}
    for s in slugs:
        applied = (_read_json(_applied_path(relay_root, s)) or {}).get("applied", [])
        rdir = _results_dir(relay_root, s)
        if not os.path.isdir(rdir):
            continue
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
            apply_one(relay_root, s, result, board_path=board_path)
            applied.append(lap)
            summary["applied"] += 1
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

def _parse_board_active(board_path):
    """Active (⚙/🔍) rows as (slug, handover_rel_path|None). The row's own
    Latest-handover cell is the authoritative pointer — not 'newest file'."""
    if not board_path or not os.path.exists(board_path):
        return []
    rows = []
    with open(board_path) as fh:
        for line in fh:
            if "|" not in line or not any(g in line for g in ACTIVE_GLYPHS):
                continue
            m = re.search(r"`([\w./-]+)`", line)  # first backticked cell = the item slug
            if not m:
                continue
            hv = re.search(r"(handover/[\w./-]+\.md)", line)  # backticked or not
            rows.append((m.group(1), hv.group(1) if hv else None))
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


def discover_active(repo_root, relay_root, board_path=None, hints_path=None):
    board_path = board_path or os.path.join(relay_root, "board.md")
    hints = _read_json(hints_path) if hints_path else None
    hints = hints or {}
    worktrees = _git_worktrees(repo_root)
    items = []
    for slug, handover_rel in _parse_board_active(board_path):
        cp = _read_json(_checkpoint_path(relay_root, slug))
        branch = _branch_for(relay_root, slug, handover_rel, cp)
        wt = next((w for w in worktrees if branch and w.get("branch") == branch), None)
        items.append({
            "work_item": slug,
            "branch": branch,
            "worktree": wt["path"] if wt else None,
            "has_checkpoint": bool(cp),
            "stage": (cp or {}).get("resume_delta", {}).get("stage"),
            "disposition": (cp or {}).get("disposition"),
            "session_hint": hints.get(slug),           # optional; never required
        })
    return items


# ---------- 6. replace: provider-neutral resume context from durable state ----------

def resume_context(repo_root, relay_root, slug, board_path=None):
    cp = _read_json(_checkpoint_path(relay_root, slug))
    if not cp:
        raise HarvestError(f"no durable checkpoint for {slug!r} — cannot replace from state")
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


# ---------- worker bootstrap: provider-neutral view over resume_context ----------

def worker_bootstrap(repo_root, relay_root, slug, board_path=None):
    """A provider-NEUTRAL bootstrap any coding agent (Claude, Codex, Mistral, …)
    could consume to continue recovered work. Constructed entirely from existing
    authoritative state (resume_context + the brief path) — NOT a new durable
    contract. Carries no slash-command, no session id, no transcript."""
    ctx = resume_context(repo_root, relay_root, slug, board_path=board_path)
    rd = ctx.get("resume_delta") or {}
    return {
        "bootstrap_version": 1,
        "work_item": ctx["work_item"],
        "repo_root": repo_root,
        "worktree_path": ctx["worktree_path"],   # cd here; it is a real git worktree
        "branch": ctx["branch"],                 # already checked out in that worktree
        "checkpoint_ref": ctx["checkpoint_ref"], # last durable commit, if any
        "brief_path": ctx.get("brief"),          # a file in the repo; read it
        "stage": rd.get("stage"),
        "resume_delta": rd,                      # next_slice / in_flight / scope_edges / open_questions
        "objective": rd.get("next_slice"),
        "instructions": [
            f"Change into the worktree at worktree_path ({ctx['worktree_path']}); "
            f"it already has branch {ctx['branch']} checked out.",
            "Read brief_path for the work item's intent, approach and slices.",
            "Inspect the repository directly (git log/status/diff and the code) — "
            "you have everything; do NOT look for a previous worker's transcript.",
            f"Continue from resume_delta (stage '{rd.get('stage')}'): {rd.get('next_slice')}.",
        ],
        "recovered_from": "durable-state",
        "requires_transcript": False,
        "requires_session_id": False,
    }


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
        print(json.dumps(apply_pending(relay_root, slug=args.slug, board_path=board), indent=2)); return 0
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
            print(json.dumps(worker_bootstrap(args.repo, relay_root, args.slug), indent=2))
        except HarvestError as e:
            print(str(e), file=sys.stderr); return 2
        return 0
    if args.cmd == "checkpoint":
        print(autosave(args.worktree, args.lap_id) or ""); return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
