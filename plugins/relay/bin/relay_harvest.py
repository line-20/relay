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
import argparse, contextlib, json, os, re, shutil, subprocess, sys, tempfile, time

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


# ---------- state reader: where Relay's notes live (state.branch) ----------
# By default Relay's coordination notes (board, briefs, handovers, reviews, checkpoints) live on the
# repo's durable branch, next to the code. A project that runs a merge queue can move them to their own
# branch with `{ "state": { "branch": "relay-notes" } }` in relay.config.json, so the notes never move
# `main` under a queued batch. This block is the ONE place that knows where the notes are: readers go
# through it and never read a notes file from a working tree when the setting is on, because a worktree
# forked from main holds a frozen copy that would silently resume the wrong lap.
#
# Unset (the default) changes nothing: `state_branch()` is None and every reader behaves as before.
# A setting that is present but unusable is NEVER treated as unset: that would read the durable branch
# while the writers believe the notes live elsewhere, splitting the state in two. It raises instead.

# The volatile notes, as an explicit allow-list under <root>/ (a repo may also keep durable knowledge,
# decisions or reference docs there; those stay on the durable branch and are never read from here).
STATE_PATHS = ("board.md", "briefs", "handover", "reviews", "harvest", "archive", "audits")


def _toplevel(repo_root):
    """The git top-level directory. Every state git call runs from here: `ls-tree -- <path>` is relative
    to the current directory while `git show <ref>:<path>` is relative to the repo root, so running from
    a subdirectory would silently list nothing."""
    r = _run_git(["rev-parse", "--show-toplevel"], repo_root)
    top = r.stdout.strip() if r.returncode == 0 else ""
    return top or repo_root


def _remote_config(repo_root, remote="origin"):
    """relay.config.json as published on the remote's durable branch, so the setting does not depend on
    which branch a worktree forked from (an older slice branch would otherwise keep writing to main).
    The checked-out file is used ONLY when there is no remote durable branch to read at all (no remote,
    never fetched). A remote branch that simply lacks the file means "no config", never "use the local one":
    otherwise turning the setting off on main would not reach a stale checkout, and an untrusted PR branch
    could switch it on."""
    if not repo_root:
        return {}
    top = _toplevel(repo_root)
    ref = f"{remote}/{_durable_branch(top)}"
    if _run_git(["rev-parse", "--verify", "--quiet", ref], top).returncode == 0:
        r = _run_git(["show", f"{ref}:relay.config.json"], top)
        text = r.stdout if r.returncode == 0 else None
    else:
        try:
            with open(os.path.join(top, "relay.config.json")) as fh:
                text = fh.read()
        except OSError:
            text = None
    if not text:
        return {}
    try:
        cfg = json.loads(text)
    except ValueError:
        if '"state"' in text:
            raise HarvestError("relay.config.json is not valid JSON, so it cannot be told whether "
                               "state.branch is set. Fix the file before reading Relay's notes.")
        return {}
    return cfg if isinstance(cfg, dict) else {}


def _valid_state_branch(name, durable):
    """A usable notes-branch name: ref-shaped, no `..` or `//`, not a lock file or a trailing `/`/`.`,
    and never HEAD or the durable branch itself (either would make 'the notes branch' mean the code)."""
    return (isinstance(name, str) and _valid_branch(name) and ".." not in name and "//" not in name
            and not name.endswith(("/", ".", ".lock")) and name != "HEAD" and name != durable)


def state_branch(repo_root, remote="origin"):
    """The configured notes branch, or None when the setting is absent (notes live on the durable branch).
    Raises HarvestError when the setting is present but unusable: never silently 'unset'."""
    cfg = _remote_config(repo_root, remote)
    st = cfg.get("state")
    if st is None:
        return None
    if not isinstance(st, dict):
        raise HarvestError('`state` in relay.config.json must be an object like {"branch": "relay-notes"}.')
    branch = st.get("branch")
    if branch is None:
        return None
    durable = _durable_branch(_toplevel(repo_root))
    if not _valid_state_branch(branch, durable):
        raise HarvestError(f"state.branch {branch!r} is not a usable branch name (it must be a plain "
                           f"branch name, not HEAD or the durable branch {durable!r}).")
    return branch


def _rel_root(repo_root, relay_root):
    """<root> as a repo-relative POSIX path, measured from the git top-level. Raises when the notes
    folder is outside the repository."""
    top = os.path.realpath(_toplevel(repo_root))
    rel = os.path.relpath(os.path.realpath(relay_root), top).replace(os.sep, "/")
    if rel == ".." or rel.startswith("../") or os.path.isabs(rel):
        raise HarvestError(f"the notes folder {relay_root!r} is outside the repository {top!r}.")
    return rel


def _norm_rel(rel):
    """A repo-relative POSIX path, normalised; raises on absolute paths and `..` escapes."""
    import posixpath
    rel = posixpath.normpath(rel.replace(os.sep, "/"))
    if rel.startswith("/") or rel == ".." or rel.startswith("../"):
        raise HarvestError(f"{rel!r} is not a repo-relative path.")
    return rel


def _is_state_path(rel, rel_root):
    """Is this repo-relative path one of the volatile notes (board, briefs, handover, reviews, harvest)?"""
    try:
        rel = _norm_rel(rel)
    except HarvestError:
        return False
    prefix = rel_root.rstrip("/") + "/"
    if not rel.startswith(prefix):
        return False
    return rel[len(prefix):].split("/", 1)[0] in STATE_PATHS


def _state_ref(repo_root, remote="origin", fetch=False):
    """(branch, ref) for the notes branch, or (None, None) when unset. Fails LOUD when the setting is
    on but the branch is missing: falling back to the durable branch would silently split the state."""
    top = _toplevel(repo_root)
    branch = state_branch(top, remote)
    if not branch:
        return (None, None)
    if fetch:
        _run_git(["fetch", remote, branch], top)             # best effort; offline reads the local ref
    ref = f"{remote}/{branch}"
    if _run_git(["rev-parse", "--verify", "--quiet", f"refs/remotes/{ref}"], top).returncode != 0:
        raise HarvestError(
            f"state.branch is set to {branch!r} but {ref} does not exist here. "
            f"Run `git fetch {remote} {branch}`, or create it once with the state init command; "
            f"never fall back to the durable branch, that would split the notes in two.")
    return (branch, ref)


def _git_blob(top, ref, rel):
    try:
        r = subprocess.run(["git", "show", f"{ref}:{rel}"], cwd=top, capture_output=True)
    except OSError:
        return None
    return r.stdout if r.returncode == 0 else None


def _read_blobs(top, shas):
    """{sha: bytes} for blob ids through ONE `git cat-file --batch` process (a snapshot of a repo with a thousand
    handovers must not spawn a thousand `git show` processes)."""
    uniq = sorted(set(shas))
    out = {}
    if not uniq:
        return out
    try:
        r = subprocess.run(["git", "cat-file", "--batch"], cwd=top, input=("\n".join(uniq) + "\n").encode(),
                           capture_output=True)
    except OSError:
        return out
    buf, i = r.stdout, 0
    for _ in uniq:
        nl = buf.find(b"\n", i)
        if nl < 0:
            break
        header = buf[i:nl].decode("utf-8", "replace").split()
        if len(header) == 3 and header[1] == "blob":
            size = int(header[2])
            out[header[0]] = buf[nl + 1:nl + 1 + size]
            i = nl + 1 + size + 1
        else:
            i = nl + 1
    return out


def _ls_tree(top, ref, prefix):
    """Repo-relative file names under `prefix` at `ref`. NUL-separated, so a name with non-ASCII
    characters is never C-quoted (and then silently dropped by a path filter)."""
    try:
        r = subprocess.run(["git", "ls-tree", "-r", "-z", "--name-only", ref, "--", prefix],
                           cwd=top, capture_output=True)
    except OSError:
        return []
    if r.returncode != 0:
        return []
    return [n for n in r.stdout.decode("utf-8", "surrogateescape").split("\0") if n]


def _state_files(top, ref, rel_root):
    return [n for n in _ls_tree(top, ref, rel_root) if _is_state_path(n, rel_root)]


@contextlib.contextmanager
def state_snapshot(repo_root, relay_root, remote="origin", fetch=False):
    """Yield (relay_root_to_read, state_ref). Unset: (relay_root, None), the working tree, as before.
    Set: a throwaway copy of the notes branch's volatile files laid out like the repo, so every existing
    reader works unchanged on it and the worktree's frozen copies are never consulted."""
    _, ref = _state_ref(repo_root, remote, fetch=fetch)
    if not ref:
        yield (relay_root, None)
        return
    top = _toplevel(repo_root)
    rel_root = _rel_root(repo_root, relay_root)
    tmp = tempfile.mkdtemp(prefix="relay-state-")
    tmp_real = os.path.realpath(tmp)
    try:
        entries = [e for e in _tree_entries(top, ref, rel_root) if _is_state_path(e[2], rel_root)]
        blobs = _read_blobs(top, [e[1] for e in entries])
        for _mode, sha, name in entries:
            data = blobs.get(sha)
            if data is None:
                continue
            dest = os.path.realpath(os.path.join(tmp, name))
            if not dest.startswith(tmp_real + os.sep):
                continue                                        # never write outside the snapshot
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            with open(dest, "wb") as fh:
                fh.write(data)
        yield (os.path.join(tmp, rel_root), ref)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def read_note(repo_root, rel, remote="origin", fetch=True, at=None):
    """Read one repo-relative file the way a reader should: a volatile note comes from the notes branch
    when state.branch is set, everything else from the durable branch. Replaces the markdown commands'
    `git fetch origin main; git show FETCH_HEAD:<path>`. Returns text, or None when absent."""
    rel = _norm_rel(rel)
    top = _toplevel(repo_root)
    if at:                                            # a commit the caller already fetched (see state_tip)
        data = _git_blob(top, at, rel)
        return None if data is None else data.decode("utf-8", "replace")
    durable = _durable_branch(top)
    if fetch:
        _run_git(["fetch", remote, durable], top)    # the durable branch carries the setting itself
    root = _relay_root_of(top)
    branch, ref = _state_ref(top, remote, fetch=fetch)
    data = _git_blob(top, ref if ref and _is_state_path(rel, root) else f"{remote}/{durable}", rel)
    return None if data is None else data.decode("utf-8", "replace")


def list_notes(repo_root, prefix, remote="origin", fetch=True):
    """List repo-relative files under a prefix. With the setting on, the notes come from the notes branch
    and everything else from the durable branch, merged: `ls <root>` shows both, never main's frozen notes."""
    prefix = _norm_rel(prefix)
    top = _toplevel(repo_root)
    durable = _durable_branch(top)
    if fetch:
        _run_git(["fetch", remote, durable], top)
    root = _relay_root_of(top)
    branch, ref = _state_ref(top, remote, fetch=fetch)
    names = _ls_tree(top, f"{remote}/{durable}", prefix)
    if ref:
        names = [n for n in names if not _is_state_path(n, root)]
        names += [n for n in _ls_tree(top, ref, prefix) if _is_state_path(n, root)]
    return sorted(set(names))


def _relay_root_of(repo_root):
    """The <root> directory (default `relay`), from the remote's config (`root`), as a repo-relative path."""
    root = _remote_config(repo_root).get("root")
    return root.strip("/") if isinstance(root, str) and root.strip("/") else "relay"


def _state_target(repo_root, remote="origin", fetch=True):
    """(branch, is_state): the branch notes are WRITTEN to. The notes branch when state.branch is set (it
    must already exist: writers never create it, an explicit `state init` does, so two sessions can never
    race to seed competing branches), else the durable branch, as before."""
    top = _toplevel(repo_root)
    durable = _durable_branch(top)
    if fetch:
        _run_git(["fetch", remote, durable], top)         # the durable branch carries the setting itself
    branch, _ = _state_ref(top, remote, fetch=fetch)       # raises loud if set but missing
    return (branch, True) if branch else (durable, False)


_REGULAR = ("100644", "100755")


def _clean_rel(p):
    """A repo-relative path safe to hand to git and to put in an index record: normalised, no `..`, and no
    control characters (a newline in a path would inject extra records into an index list)."""
    rel = _norm_rel(p)
    if any(ord(ch) < 32 or ord(ch) == 127 for ch in rel):
        raise HarvestError(f"{p!r} contains a control character; refusing it.")
    return rel


def _temp_index(top, base=None):
    """A throwaway index (seeded from `base`, or empty) so nothing touches the real index, working tree,
    HEAD or any local branch: the parallel-worktree-safe primitive from docs/conventions.md. Pathspecs are
    literal (`*` is a file name, not a wildcard)."""
    fd, path = tempfile.mkstemp(prefix="relay-state-idx-"); os.close(fd)
    os.remove(path)                                        # git creates it; an empty file is not a valid index
    env = {"GIT_INDEX_FILE": path, "GIT_LITERAL_PATHSPECS": "1"}
    if base:
        rt = _run_git(["read-tree", base], top, env=env)
        if rt.returncode != 0:
            return (path, env, (rt.stderr.strip().splitlines() or ["read-tree failed"])[-1])
    return (path, env, None)


def _drop(path):
    try:
        os.remove(path)
    except OSError:
        pass


def _push(top, remote, sha, branch):
    push = _run_git(["push", remote, f"{sha}:refs/heads/{branch}"], top)
    if push.returncode == 0:
        return (True, None)
    lines = [ln.strip() for ln in push.stderr.splitlines() if ln.strip()]
    said = [ln for ln in lines if ln.startswith("remote:") or "rejected" in ln]    # what the remote itself said
    return (False, " | ".join(said[:3]) or (lines[-1] if lines else "push failed (offline or remote rejected)"))


def _tree_entries(top, ref, prefix):
    """[(mode, sha, path)] for the REGULAR files under `prefix` at `ref` (NUL-separated, so no C-quoting).
    Symlinks, submodules and paths with control characters are never carried."""
    try:
        r = subprocess.run(["git", "ls-tree", "-r", "-z", ref, "--", prefix], cwd=top, capture_output=True)
    except OSError:
        return []
    out = []
    if r.returncode != 0:
        return out
    for rec in r.stdout.decode("utf-8", "surrogateescape").split("\0"):
        if not rec or "\t" not in rec:
            continue
        meta, path = rec.split("\t", 1)
        parts = meta.split()
        if (len(parts) == 3 and parts[1] == "blob" and parts[0] in _REGULAR
                and not any(ord(ch) < 32 or ord(ch) == 127 for ch in path)):
            out.append((parts[0], parts[2], path))
    return out


def _index_info(top, env, entries):
    """Stage (mode, sha, path) records into the temp index. NUL-terminated (`-z`), so a path can never smuggle
    in a second record."""
    data = b"".join(f"{mode} {sha}\t{path}".encode("utf-8", "surrogateescape") + b"\0" for mode, sha, path in entries)
    return subprocess.run(["git", "update-index", "--add", "-z", "--index-info"], cwd=top, input=data,
                          capture_output=True, env={**os.environ, **env})


def _tip(top, remote, branch):
    return _run_git(["rev-parse", "--verify", "--quiet", f"refs/remotes/{remote}/{branch}"], top).stdout.strip()


def _fetch_branch(top, remote, branch):
    """Fetch one branch into its remote-tracking ref (not FETCH_HEAD, which a concurrent fetch in the same
    checkout would overwrite)."""
    return _run_git(["fetch", remote, f"+refs/heads/{branch}:refs/remotes/{remote}/{branch}"], top)


def _result(status, branch, reason=None, **extra):
    """status: pushed | nothing | rejected (the branch moved or the remote refused: re-read and re-apply) |
    offline | error (could not build the commit)."""
    out = {"status": status, "branch": branch, "reason": reason,
           "committed": status in ("pushed", "rejected"), "pushed": status in ("pushed", "nothing")}
    out.update(extra)
    return out


def state_tip(repo_root, remote="origin"):
    """Fetch and report the tip of the branch the notes live on. A caller that is about to EDIT a shared note
    (the board) records this tip, reads the note `--at` it, and hands the same tip back to `state_commit` as
    `base`: the commit is built on exactly what was read, so a sibling's change in between makes the push
    non-fast-forward instead of being silently overwritten."""
    top = _toplevel(repo_root)
    branch, is_state = _state_target(top, remote, fetch=True)
    if _fetch_branch(top, remote, branch).returncode != 0:
        raise HarvestError(f"cannot fetch {remote}/{branch} (offline?).")
    tip = _tip(top, remote, branch)
    if not tip:
        raise HarvestError(f"no {remote}/{branch} to read from.")
    return {"branch": branch, "tip": tip, "state_branch": bool(is_state)}


SNAPSHOT_MARKER = ".relay-snapshot"


def state_snapshot_dir(repo_root, out_dir, remote="origin"):
    """Materialise the notes (allow-listed files only) at the current tip into a NEW directory laid out like the
    repo, so a command can read and edit them freely without touching a working tree. A marker file records the
    tip and the notes folder: `state_commit(sync_dir=...)` takes its base from the marker, so a directory taken at
    an older tip can never be committed as if it were current."""
    info = state_tip(repo_root, remote)
    top = _toplevel(repo_root)
    root = _relay_root_of(top)
    out = os.path.abspath(out_dir)
    if os.path.islink(out):
        raise HarvestError(f"{out} is a symlink; refusing to write the snapshot through it.")
    if os.path.exists(out):
        if not os.path.isdir(out) or os.listdir(out):
            raise HarvestError(f"{out} is not an empty directory.")
    else:
        try:
            os.makedirs(out, mode=0o700)
        except OSError as e:
            raise HarvestError(f"cannot create {out}: {e.strerror}")
    out_real = os.path.realpath(out)
    n = 0
    entries = [e for e in _tree_entries(top, info["tip"], root) if _is_state_path(e[2], root)]
    blobs = _read_blobs(top, [e[1] for e in entries])
    for mode, sha, path in entries:
        data = blobs.get(sha)
        dest = os.path.realpath(os.path.join(out, path))
        if data is None or not dest.startswith(out_real + os.sep):
            continue
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        with open(dest, "wb") as fh:
            fh.write(data)
        n += 1
    os.makedirs(os.path.join(out, root), exist_ok=True)
    with open(os.path.join(out, SNAPSHOT_MARKER), "w") as fh:
        json.dump({"root": root, "base": info["tip"], "branch": info["branch"]}, fh)
    return {"dir": out, "root": root, "branch": info["branch"], "base": info["tip"], "files": n}


def _regular_path(path, label=None):
    """`path` (made absolute) if it is a regular file: never a symlink, a directory or a device."""
    import stat
    path = os.path.abspath(path)
    try:
        st = os.lstat(path)
    except OSError:
        raise HarvestError(f"cannot commit {label or path!r}: no such file")
    if not stat.S_ISREG(st.st_mode):
        raise HarvestError(f"cannot commit {label or path!r}: not a regular file (symlinks and directories are refused).")
    return path


def _read_regular(path, top, label=None):
    """Bytes of a regular file the caller may legitimately hand over: under the system temp directory or the
    repository, never a symlink (opened with O_NOFOLLOW, checked on the open descriptor, so a swap between
    check and use cannot redirect it). Keeps `--put ~/.ssh/id_rsa` from ever being committed."""
    import stat
    path = os.path.abspath(path)
    real = os.path.realpath(path)
    allowed = {os.path.realpath(tempfile.gettempdir()), os.path.realpath("/tmp"), os.path.realpath(top)}
    if not any(real == a or real.startswith(a + os.sep) for a in allowed):
        raise HarvestError(f"cannot commit {label or path!r}: only files under the temp directory or the repository can be handed over.")
    try:
        fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    except OSError as e:
        raise HarvestError(f"cannot commit {label or path!r}: {e.strerror or 'cannot open'}")
    try:
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            raise HarvestError(f"cannot commit {label or path!r}: not a regular file.")
        with os.fdopen(fd, "rb", closefd=False) as fh:
            return fh.read()
    finally:
        os.close(fd)


def _hash_bytes(top, data):
    r = subprocess.run(["git", "hash-object", "-w", "--stdin"], cwd=top, input=data, capture_output=True)
    return r.stdout.decode().strip() if r.returncode == 0 else ""


def _is_dotfile(rel):
    name = rel.rsplit("/", 1)[-1]
    return name.startswith(".") or name.endswith("~") or name.endswith(".swp")


def _regular_file(top, rel):
    """The absolute path of a regular file in the working tree."""
    return _regular_path(os.path.join(top, rel), rel)


def state_commit(repo_root, message, add=(), put=(), remove=(), moves=(), sync_dir=None, base=None,
                 allow_mass_delete=False, remote="origin"):
    """Commit Relay notes (board, briefs, handover, reviews, harvest, archive, audits) onto the branch they
    live on, with the temp-index primitive: stage ONLY the named changes into a throwaway index seeded from the
    tip, write a tree, `commit-tree`, push. One attempt: a rejected push is reported, never blindly retried.

    Changes: `add` = files from the working tree; `put` = [(rel, file)] content from any regular file (so a
    shared note such as the board can be edited in a scratch copy and the working tree never touched);
    `remove`; `moves` = [(old, new)] taking the content from the tip; `sync_dir` = a directory laid out like the
    repo (see state_snapshot_dir): the notes in it become the notes on the branch, as a delta against `base`.

    `base` is the tip the caller READ its inputs from (state_tip). The commit is built on it, so if the branch
    has moved since, the call is rejected up front instead of overwriting a sibling's edit: the old hand-written
    snippet had this property by reading and committing from the same fetch, and it must not be lost. A change
    to board.md without `base` is refused. Only notes are accepted, in both modes: durable docs are not
    committed here. Returns a status dict (see _result); raises HarvestError for a refusal."""
    top = _toplevel(repo_root)
    branch, is_state = _state_target(top, remote, fetch=True)
    root = _relay_root_of(top)
    board = f"{root}/board.md"

    adds = [_clean_rel(p) for p in add]
    puts = [(_clean_rel(r), f) for r, f in put]
    rems = [_clean_rel(p) for p in remove]
    mvs = [(_clean_rel(a), _clean_rel(b)) for a, b in moves]
    touched = adds + [r for r, _ in puts] + rems + [x for pair in mvs for x in pair]
    for rel in touched:
        if not _is_state_path(rel, root):
            raise HarvestError(f"{rel!r} is not a Relay note ({', '.join(STATE_PATHS)} under {root}/); "
                               f"only notes are committed here, durable docs go through the project's normal flow.")
    marker = None
    if sync_dir:
        sd_real = os.path.realpath(sync_dir)
        try:
            with open(os.path.join(sd_real, SNAPSHOT_MARKER)) as fh:
                marker = json.load(fh)
        except (OSError, ValueError):
            raise HarvestError(f"{sync_dir!r} is not a snapshot (no {SNAPSHOT_MARKER}): take one with `state snapshot --out DIR`.")
        if marker.get("root") != root or not os.path.isdir(os.path.join(sd_real, root)):
            raise HarvestError(f"{sync_dir!r} has no {root}/ folder: pass the snapshot directory itself, not a folder inside it.")
        if base and base != marker.get("base"):
            raise HarvestError("--base does not match the tip this snapshot was taken from; the snapshot's own tip is used.")
        base = marker.get("base")
    if base and not re.fullmatch(r"[0-9a-f]{40}", base):
        raise HarvestError("--base must be the full 40-character commit id that `state tip` / `state snapshot` printed.")
    if board in touched and not base:
        raise HarvestError("board.md is shared and may have changed since you read it: pass --base <the tip you "
                           "read it from> (state tip / state snapshot print it).")

    if _fetch_branch(top, remote, branch).returncode != 0:
        return _result("offline", branch, "offline: cannot fetch " + f"{remote}/{branch}")
    tip = _tip(top, remote, branch)
    if not tip:
        return _result("error", branch, f"no remote {remote}/{branch} to build on")
    if base:
        if _run_git(["cat-file", "-e", f"{base}^{{commit}}"], top).returncode != 0:
            raise HarvestError(f"--base {base!r} is not a commit here.")
        if base != tip:
            return _result("rejected", branch,
                           f"the notes branch moved since you read it (you read {base[:9]}, it is now {tip[:9]}): "
                           f"re-read the current copy, re-apply your edit, and commit again.")
    parent = tip

    # --- compute the delta from a sync directory (deltas only: never a wholesale overwrite)
    ignored = []
    if sync_dir:
        sd = os.path.realpath(sync_dir)
        have = {e[2]: e for e in _tree_entries(top, parent, root) if _is_state_path(e[2], root)}
        seen = set()
        def _walk_error(e):
            raise HarvestError(f"cannot read the sync directory: {e}")
        for dirpath, _dirs, files in os.walk(os.path.join(sd, root), onerror=_walk_error):
            for fn in files:
                full = os.path.join(dirpath, fn)
                rel = _clean_rel(os.path.relpath(full, sd))
                if _is_dotfile(rel):
                    continue
                if not _is_state_path(rel, root):
                    ignored.append(rel)
                    continue
                if os.path.islink(full):
                    raise HarvestError(f"{rel!r} is a symlink in the sync directory; refusing it.")
                seen.add(rel)
                h = _hash_bytes(top, _read_regular(full, top, rel))
                if rel not in have or have[rel][1] != h:
                    puts.append((rel, full))
        gone = [r for r in have if r not in seen]
        if len(gone) > 5 and len(gone) > len(have) // 2 and not allow_mass_delete:
            raise HarvestError(f"this sync would delete {len(gone)} of {len(have)} notes: the directory looks wrong or "
                               f"incomplete. Nothing was committed. (Pass --allow-mass-delete if that is really intended.)")
        rems += gone

    idx, env, err = _temp_index(top, parent)
    try:
        if err:
            return _result("error", branch, "read-tree failed: " + err)
        entries = []
        for rel in adds:
            path = _regular_file(top, rel)
            r = _run_git(["add", "--", rel], top, env=env)
            if r.returncode != 0:
                return _result("error", branch, "add failed: " + (r.stderr.strip().splitlines() or ["?"])[-1])
        for rel, f in puts:
            sha = _hash_bytes(top, _read_regular(f, top, rel))
            if not sha:
                return _result("error", branch, f"could not read {f!r}")
            entries.append(("100644", sha, rel))
        for rel in rems:
            hit = _tree_entries(top, parent, rel)
            if len(hit) != 1 or hit[0][2] != rel:
                return _result("error", branch, f"cannot remove {rel!r}: not a file on {remote}/{branch}")
            r = _run_git(["rm", "--cached", "-f", "-q", "--", rel], top, env=env)
            if r.returncode != 0:
                return _result("error", branch, "remove failed: " + (r.stderr.strip().splitlines() or ["?"])[-1])
        for old_path, new_path in mvs:
            hit = _tree_entries(top, parent, old_path)
            if len(hit) != 1 or hit[0][2] != old_path:
                return _result("error", branch, f"cannot move {old_path!r}: not a regular file on {remote}/{branch}")
            dest = _tree_entries(top, parent, new_path)
            if dest and dest[0][2] == new_path and dest[0][1] != hit[0][1]:
                return _result("error", branch, f"cannot move {old_path!r}: {new_path!r} already exists with different content")
            entries.append((hit[0][0], hit[0][1], new_path))
            r = _run_git(["rm", "--cached", "-f", "-q", "--", old_path], top, env=env)
            if r.returncode != 0:
                return _result("error", branch, "move failed: " + (r.stderr.strip().splitlines() or ["?"])[-1])
        if entries:
            r = _index_info(top, env, entries)
            if r.returncode != 0:
                return _result("error", branch, "could not stage: " + r.stderr.decode("utf-8", "replace").strip())
        tree = _run_git(["write-tree"], top, env=env).stdout.strip()
    finally:
        _drop(idx)
    if not tree:
        return _result("error", branch, "write-tree failed")
    if tree == _run_git(["rev-parse", f"{parent}^{{tree}}"], top).stdout.strip():
        return _result("nothing", branch, "nothing to commit", sha=parent)
    commit = _run_git(["commit-tree", tree, "-p", parent, "-m", message], top)
    if commit.returncode != 0 or not commit.stdout.strip():
        return _result("error", branch, "commit-tree failed: " + (commit.stderr.strip().splitlines() or ["unknown"])[-1])
    sha = commit.stdout.strip()
    ok, reason = _push(top, remote, sha, branch)
    return _result("pushed" if ok else "rejected", branch, reason, sha=sha, ignored=ignored)


def state_init(repo_root, branch="relay-notes", remote="origin"):
    """Create the notes branch ONCE, as an orphan seeded with the durable branch's current volatile notes.
    The only thing that ever creates it. Idempotent: an existing branch is reported, never touched.

    Safe order: land `state.branch` on the durable branch FIRST, then run this straight away. Until it runs,
    every Relay command fails loud (nothing is written anywhere), so no note can land on `main` after the seed
    is taken and go missing. If you run it before the setting lands, a note written to `main` in between is
    not on the branch."""
    top = _toplevel(repo_root)
    durable = _durable_branch(top)
    if not _valid_state_branch(branch, durable):
        raise HarvestError(f"{branch!r} is not a usable notes-branch name (not HEAD or {durable!r}, no `..`).")
    fetch = _run_git(["fetch", remote, durable], top)
    if fetch.returncode != 0:
        raise HarvestError("cannot reach the remote to seed the notes branch: "
                           + (fetch.stderr.strip().splitlines() or ["fetch failed"])[-1])
    if _run_git(["ls-remote", "--exit-code", "--heads", remote, branch], top).returncode == 0:
        return {"created": False, "branch": branch,
                "reason": "already exists on the remote; left untouched. If it is old, its notes may be out of date: "
                          "compare with the durable branch, or `state export --delete-branch` and init again."}
    root = _relay_root_of(top)
    src = f"{remote}/{durable}"
    entries = [e for e in _tree_entries(top, src, root) if _is_state_path(e[2], root)]
    idx, env, _ = _temp_index(top)
    try:
        r = _index_info(top, env, entries)
        if r.returncode != 0:
            raise HarvestError("could not stage the seed: " + r.stderr.decode("utf-8", "replace").strip())
        tree = _run_git(["write-tree"], top, env=env).stdout.strip()
    finally:
        _drop(idx)
    head = _run_git(["rev-parse", "--short", src], top).stdout.strip()
    commit = _run_git(["commit-tree", tree, "-m", f"relay: seed notes branch from {durable} @ {head}"], top)
    if commit.returncode != 0 or not commit.stdout.strip():
        raise HarvestError("could not create the seed commit: " + (commit.stderr.strip() or "unknown"))
    sha = commit.stdout.strip()
    ok, reason = _push(top, remote, sha, branch)            # no force: a racing init loses cleanly
    if not ok:
        if _run_git(["ls-remote", "--exit-code", "--heads", remote, branch], top).returncode == 0:
            return {"created": False, "branch": branch, "reason": "already exists (a concurrent init created it first); left untouched."}
        raise HarvestError(f"could not push the notes branch {branch!r}: {reason}")
    return {"created": True, "branch": branch, "sha": sha, "files": len(entries), "seeded_from": src}


def state_export(repo_root, branch=None, prune=False, delete_branch=False, remote="origin"):
    """Copy the notes branch's volatile notes BACK onto the durable branch as one commit, so switching the
    setting off does not lose the work that landed on the notes branch. It OVERLAYS: notes that exist only on
    the durable branch are kept (a handover written to `main` in the gap between turning the setting off and
    running this is not deleted) and reported; `prune=True` deletes them instead. `delete_branch=True` removes
    the remote notes branch afterwards, so turning the setting on again later seeds from fresh notes, not from
    a stale branch. Pass the branch explicitly when the setting is already off."""
    top = _toplevel(repo_root)
    durable = _durable_branch(top)
    _run_git(["fetch", remote, durable], top)
    branch = branch or state_branch(top, remote)
    if not branch:
        raise HarvestError("no notes branch to export from: pass --branch, or set state.branch.")
    if not _valid_state_branch(branch, durable):
        raise HarvestError(f"{branch!r} is not a usable notes-branch name.")
    if _fetch_branch(top, remote, branch).returncode != 0:
        raise HarvestError(f"cannot fetch {remote}/{branch}.")
    root = _relay_root_of(top)
    notes_ref, durable_ref = f"{remote}/{branch}", f"{remote}/{durable}"
    notes = [e for e in _tree_entries(top, notes_ref, root) if _is_state_path(e[2], root)]
    have = {e[2] for e in notes}
    only_main = [e[2] for e in _tree_entries(top, durable_ref, root)
                 if _is_state_path(e[2], root) and e[2] not in have]
    idx, env, err = _temp_index(top, durable_ref)
    try:
        if err:
            raise HarvestError("read-tree failed: " + err)
        if prune and only_main:
            _run_git(["rm", "--cached", "-f", "-q", "--ignore-unmatch", "--", *only_main], top, env=env)
        r = _index_info(top, env, notes)
        if r.returncode != 0:
            raise HarvestError("could not stage the export: " + r.stderr.decode("utf-8", "replace").strip())
        tree = _run_git(["write-tree"], top, env=env).stdout.strip()
    finally:
        _drop(idx)
    skipped = [n for n in _ls_tree(top, notes_ref, root) if _is_state_path(n, root) and n not in have]
    out = {"branch": durable, "files": len(notes), "left_on_main": [] if prune else only_main,
           "removed": len(only_main) if prune else 0, "skipped": skipped}
    if tree == _run_git(["rev-parse", f"{durable_ref}^{{tree}}"], top).stdout.strip():
        out.update(exported=False, reason="the durable branch already matches the notes branch")
        ok = True
    else:
        head = _run_git(["rev-parse", "--short", notes_ref], top).stdout.strip()
        commit = _run_git(["commit-tree", tree, "-p", durable_ref, "-m",
                           f"relay: export notes from {branch} @ {head} back to {durable}"], top)
        if commit.returncode != 0 or not commit.stdout.strip():
            raise HarvestError("could not create the export commit: " + (commit.stderr.strip() or "unknown"))
        sha = commit.stdout.strip()
        ok, reason = _push(top, remote, sha, durable)
        out.update(exported=ok, sha=sha, reason=reason)
    if ok and delete_branch:
        d = _run_git(["push", remote, "--delete", branch], top)
        out["branch_deleted"] = d.returncode == 0
        if d.returncode != 0:
            out["reason"] = (d.stderr.strip().splitlines() or ["delete failed"])[-1]
    return out


def state_status(repo_root, remote="origin"):
    """Where the notes live right now, for a human or an agent to read."""
    top = _toplevel(repo_root)
    durable = _durable_branch(top)
    try:
        branch = state_branch(top, remote)
        err = None
    except HarvestError as e:
        branch, err = None, str(e)
    out = {"durable_branch": durable, "state_branch": branch, "problem": err}
    if branch:
        ref = f"{remote}/{branch}"
        exists = _run_git(["rev-parse", "--verify", "--quiet", f"refs/remotes/{ref}"], top).returncode == 0
        out["exists_locally"] = exists
        if exists:
            out["head"] = _run_git(["rev-parse", "--short", ref], top).stdout.strip()
            out["files"] = len(_state_files(top, ref, _relay_root_of(top)))
    return out


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


def discover_active(repo_root, relay_root, board_path=None, hints_path=None, state_ref=None):
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
            # read FROM the notes branch (state_ref): it is on the remote by construction
            "replicated": ((True if state_ref else _checkpoint_on_remote(repo_root, relay_root, slug))
                           if cp_present else None),
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


def _resolve_ref(repo_root, worktree_path, rel, state=None):
    """Where a repo-relative reference is DURABLY readable, or None. Checks the
    worker's worktree first (what it will actually read), then the repo root,
    then origin/main (durable even if this branch predates the file).
    `state=(ref, rel_root)` (notes branch set): a volatile note resolves ONLY against that ref — the
    worktree's copy is a frozen leftover and must never be preferred."""
    if not rel:
        return (None, None)
    if os.path.isabs(rel) and state:
        # a checkpoint may carry an absolute path to a note; with the setting on it is still a note
        for base in (worktree_path, repo_root):
            if base and rel.startswith(base.rstrip(os.sep) + os.sep):
                rel = os.path.relpath(rel, base).replace(os.sep, "/")
                break
    if os.path.isabs(rel):
        return (rel, "abs") if os.path.exists(rel) else (None, None)
    if state and _is_state_path(rel, state[1]):
        ref = state[0]
        if repo_root and _run_git(["cat-file", "-e", f"{ref}:{rel}"], repo_root).returncode == 0:
            return (f"{ref}:{rel}", ref)
        return (None, None)
    for base, src in ((worktree_path, "worktree"), (repo_root, "repo")):
        if base and os.path.exists(os.path.join(base, rel)):
            return (os.path.join(base, rel), src)
    if repo_root and _run_git(["cat-file", "-e", f"origin/main:{rel}"], repo_root).returncode == 0:
        return (f"origin/main:{rel}", "origin/main")   # read via `git show`
    return (None, None)


def _project_instructions(repo_root, worktree_path, relay_root, state=None):
    """Resolved project-local instruction/guardrail files a fresh worker must read
    before continuing. Returns only files that actually resolve — never a name that
    doesn't exist, never a provider-specific file we invented."""
    found = []
    for name in _INSTRUCTION_CANDIDATES:
        path, _ = _resolve_ref(repo_root, worktree_path, name, state)
        if path:
            found.append(name)
    rel_root = state[1] if state else (os.path.relpath(relay_root, repo_root) if repo_root else "relay")
    guardrails = f"{rel_root}/knowledge/guardrails.md"
    if _resolve_ref(repo_root, worktree_path, guardrails, state)[0]:
        found.append(guardrails)
    return found


# ---------- worker bootstrap: provider-neutral view over resume_context ----------

def worker_bootstrap(repo_root, relay_root, slug, board_path=None, state=None):
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

    brief_abs, brief_src = _resolve_ref(repo_root, wt, ctx.get("brief"), state)
    brief_ok = brief_abs is not None
    wt_ok = bool(wt) and os.path.isdir(wt)
    instr = _project_instructions(repo_root, wt, relay_root, state)

    # Resolved durable reference to the project board (the coordination home).
    # Never duplicates the board Detail — it points a worker at where the item's
    # authoritative row lives, keyed by the work_item slug. Derived in the view.
    # with a notes branch, relay_root is a throwaway snapshot dir: the real <root> name travels in `state`
    rel_root = state[1] if state else (os.path.relpath(relay_root, repo_root) if repo_root else "relay")
    board_rel = f"{rel_root}/board.md"
    board_abs, board_src = _resolve_ref(repo_root, wt, board_rel, state)
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
                     + (f" — via `git show {brief_abs}`" if brief_src not in ("worktree", "repo", "abs") else ""))
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
        "brief_source": brief_src,                              # worktree | repo | origin/<branch> | None
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


def validate_bootstrap(repo_root, bs, state=None):
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
        if not _resolve_ref(repo_root, wt, bs.get("brief_path"), state)[0]:
            v.append("brief_path presented but does not resolve")
    elif bs.get("brief_status") == "absent":
        if bs.get("brief_path") is not None:
            v.append("brief marked absent but a path is still present (dangling risk)")
        if not bs.get("brief_fallback"):
            v.append("brief absent without a fallback")
    for name in bs.get("project_instructions", []):
        if not _resolve_ref(repo_root, wt, name, state)[0]:
            v.append(f"project instruction {name!r} does not resolve")
    if bs.get("board_ref") and not _resolve_ref(repo_root, wt, bs["board_ref"], state)[0]:
        v.append("board_ref presented but does not resolve")
    if not bs.get("branch"):
        v.append("no branch reference")
    return v


def assert_no_dangling(repo_root, bs, state=None):
    issues = validate_bootstrap(repo_root, bs, state)
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
    # origin/HEAD is unset after `git init` + `remote add` + `fetch`: prefer whichever of main/master exists
    for cand in ("main", "master"):
        if _run_git(["rev-parse", "--verify", "--quiet", f"refs/remotes/origin/{cand}"], repo_root).returncode == 0:
            return cand
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
    try:
        durable, _ = _state_target(repo_root, remote, fetch=True)   # the notes branch when state.branch is set (_ = is it)
    except HarvestError as e:
        return {"lap": lap, "committed": False, "replicated": False, "reason": str(e)}
    paths = [_checkpoint_path(relay_root, slug), _applied_path(relay_root, slug),
             os.path.join(relay_root, "handover", f"next-{_slug_key(lap)}.md")]
    if board_path:
        paths.append(board_path)
    paths = [p for p in paths if os.path.exists(p)]
    if _ and paths:                                   # notes branch: it only ever holds notes, and never this
        root = _rel_root(repo_root, relay_root)       # worktree's board (a frozen copy would replace the live one)
        paths = [p for p in paths if _is_state_path(os.path.relpath(p, repo_root).replace(os.sep, "/"), root)
                 and os.path.abspath(p) != os.path.abspath(board_path or "")]
    if not paths:
        return {"lap": lap, "committed": False, "replicated": False, "reason": "no checkpoint files"}
    rels = [os.path.relpath(p, repo_root) for p in paths]

    fetch = _fetch_branch(repo_root, remote, durable)
    if fetch.returncode != 0:
        return {"lap": lap, "committed": False, "replicated": False,
                "reason": "offline: " + (fetch.stderr.strip().splitlines() or ["fetch failed"])[-1]}
    base = _tip(repo_root, remote, durable)
    if not base:
        return {"lap": lap, "committed": False, "replicated": False,
                "reason": f"no remote {remote}/{durable} to build on"}

    # A throwaway index seeded from the remote tip: read-tree/add/write-tree touch ONLY this file, so
    # repo_root's real index, working tree, HEAD and branch are never disturbed. `git add -- <rels>`
    # stages exactly our files (nothing a sibling session has staged in a shared checkout).
    fd, tmpidx = tempfile.mkstemp(prefix="relay-cp-idx-"); os.close(fd)
    try:
        idx = {"GIT_INDEX_FILE": tmpidx, "GIT_LITERAL_PATHSPECS": "1"}
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
    if not branch:
        try:
            branch = state_branch(repo_root, remote) or _durable_branch(repo_root)
        except HarvestError:
            return None  # an unusable setting: can't tell where the checkpoint should be
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
    dc = sub.add_parser("discover", help="list active work from durable sources")
    rs = sub.add_parser("resume", help="print provider-neutral resume context for a work item")
    rs.add_argument("slug")
    bs = sub.add_parser("bootstrap", help="print a provider-neutral worker bootstrap for a work item")
    bs.add_argument("slug")
    for sp in (dc, rs, bs):
        sp.add_argument("--no-fetch", action="store_true",
                        help="with state.branch set, read the local remote-tracking ref without fetching it")
    sub.add_parser("state-branch", help="print the configured notes branch (empty when notes live on the durable branch)")
    sc = sub.add_parser("state-commit", help="commit Relay notes onto the branch they live on (one attempt)")
    sc.add_argument("--message-file", required=True, help="file holding the commit message (never on the command line)")
    sc.add_argument("--base", help="the tip you read your inputs from (state tip / state snapshot); required to change board.md")
    sc.add_argument("--add", action="append", default=[], help="repo-relative file to stage from the working tree (repeatable)")
    sc.add_argument("--put", action="append", nargs=2, metavar=("REL", "FILE"), default=[],
                    help="stage FILE's content (a scratch copy) as REL (repeatable)")
    sc.add_argument("--remove", action="append", default=[], help="repo-relative file to delete; must exist on the branch (repeatable)")
    sc.add_argument("--move", action="append", nargs=2, metavar=("OLD", "NEW"), default=[],
                    help="move a file on the branch, taking its content from the branch tip (repeatable)")
    sc.add_argument("--sync-dir", help="a directory from `state snapshot`, edited freely: its notes become the branch's (its own tip is the base)")
    sc.add_argument("--allow-mass-delete", action="store_true", help="allow a sync that deletes most of the notes")
    st = sub.add_parser("state", help="manage the notes branch: init | export | status | tip | snapshot")
    st.add_argument("action", choices=["init", "export", "status", "tip", "snapshot"])
    st.add_argument("--branch", help="notes branch name (init defaults to relay-notes; export defaults to state.branch)")
    st.add_argument("--out", help="snapshot: the new directory to write the notes into")
    st.add_argument("--prune", action="store_true", help="export: also delete notes that exist only on the durable branch")
    st.add_argument("--delete-branch", action="store_true", help="export: remove the remote notes branch afterwards")
    sh = sub.add_parser("show", help="print one repo-relative file from where its notes live (notes branch or durable branch)")
    sh.add_argument("path")
    sh.add_argument("--no-fetch", action="store_true", help="read the local remote-tracking ref without fetching")
    sh.add_argument("--at", help="read from this commit (the tip `state tip` printed) instead of the current tip")
    ls = sub.add_parser("ls", help="list repo-relative files under a prefix, from where its notes live")
    ls.add_argument("prefix")
    ls.add_argument("--no-fetch", action="store_true")
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
    if args.cmd == "state-commit":
        # exit: 0 pushed (or nothing to commit) · 1 rejected/offline: re-read and retry later ·
        #       2 refused (a guard, a missing branch, bad input) · 3 could not build the commit
        try:
            with open(args.message_file) as fh:
                message = fh.read().strip()
            res = state_commit(args.repo, message, add=args.add, put=[tuple(x) for x in args.put],
                               remove=args.remove, moves=[tuple(m) for m in args.move],
                               sync_dir=args.sync_dir, base=args.base, allow_mass_delete=args.allow_mass_delete)
        except (HarvestError, OSError) as e:
            print(str(e), file=sys.stderr); return 2
        print(json.dumps(res, indent=2))
        return {"pushed": 0, "nothing": 0, "rejected": 1, "offline": 1}.get(res["status"], 3)
    if args.cmd == "state":
        try:
            if args.action == "init":
                res = state_init(args.repo, branch=args.branch or state_branch(args.repo) or "relay-notes")
            elif args.action == "export":
                res = state_export(args.repo, branch=args.branch, prune=args.prune, delete_branch=args.delete_branch)
            elif args.action == "tip":
                res = state_tip(args.repo)
            elif args.action == "snapshot":
                if not args.out:
                    print("state snapshot needs --out DIR", file=sys.stderr); return 2
                res = state_snapshot_dir(args.repo, args.out)
            else:
                res = state_status(args.repo)
        except (HarvestError, OSError) as e:
            print(str(e), file=sys.stderr); return 2
        print(json.dumps(res, indent=2))
        if args.action == "init" and not res.get("created"):
            return 1                        # already exists: it may be stale, the caller must look before carrying on
        if args.action == "export" and res.get("exported") is False and res.get("reason") and "already matches" not in res["reason"]:
            return 1
        return 0
    if args.cmd == "state-branch":
        print(state_branch(args.repo) or ""); return 0
    if args.cmd == "show":
        try:
            text = read_note(args.repo, args.path, fetch=not args.no_fetch, at=args.at)
        except HarvestError as e:
            print(str(e), file=sys.stderr); return 2
        if text is None:
            print(f"{args.path}: not found", file=sys.stderr); return 1
        sys.stdout.write(text); return 0
    if args.cmd == "ls":
        try:
            names = list_notes(args.repo, args.prefix, fetch=not args.no_fetch)
        except HarvestError as e:
            print(str(e), file=sys.stderr); return 2
        print("\n".join(names)); return 0
    if args.cmd in ("discover", "resume", "bootstrap"):
        # Read through the notes branch when state.branch is set; otherwise the working tree, as before.
        try:
            if state_branch(args.repo) and not args.relay_root:
                relay_root = os.path.join(_toplevel(args.repo), _relay_root_of(args.repo))
            with state_snapshot(args.repo, relay_root, fetch=not args.no_fetch) as (read_root, sref):
                rel_root = _rel_root(args.repo, relay_root)
                state = (sref, rel_root) if sref else None
                read_board = os.path.join(read_root, "board.md")
                if args.cmd == "discover":
                    print(json.dumps(discover_active(args.repo, read_root, board_path=read_board,
                                                     state_ref=sref), indent=2))
                elif args.cmd == "resume":
                    print(json.dumps(resume_context(args.repo, read_root, args.slug,
                                                    board_path=read_board if sref else None), indent=2))
                else:
                    bs = assert_no_dangling(args.repo, worker_bootstrap(
                        args.repo, read_root, args.slug, board_path=read_board if sref else None,
                        state=state), state)
                    print(json.dumps(bs, indent=2))
        except HarvestError as e:
            print(str(e), file=sys.stderr); return 2
        return 0
    if args.cmd == "checkpoint":
        print(autosave(args.worktree, args.lap_id) or ""); return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
