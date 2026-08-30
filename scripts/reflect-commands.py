#!/usr/bin/env python3
"""reflect-commands.py — per-command (per-stage) segmentation of Relay telemetry.

Session-level telemetry (reflect-sessions.sh) can't tell which Relay command in a
multi-command session did what: a lap that runs /rlc -> /rlt -> /rls is one session,
so files, tokens, artefacts and sub-agents smear across all three. This splits each
Claude Code transcript into COMMAND SPANS delimited by <command-name> markers and
emits one JSON line per RELAY command span to ~/.relay/commands.jsonl
(override RELAY_COMMANDS).

It is the segmented companion to reflect-sessions.sh, not a replacement: same
transcript source (~/.claude/projects), same central dir, linked by session_id. It
does NOT touch sessions.jsonl or movements.jsonl (backward compatible). Observational
only; the batch model means zero impact on live sessions. Each run rewrites the file
in full (idempotent) and backfills the whole on-disk history.

Attribution honesty (see docs/command-telemetry-model.md):
  observed    — tokens/models/tools/files/subagents/prs/errors, from the span's turns
  derived     — duration, artefacts (files under the relay root), code-write count, next
  unavailable — per-sub-agent token cost (not in the transcript), stage outcome/success,
                questions raised, decisions made (a later slice)

Usage:
  ./scripts/reflect-commands.py                 # scan all transcripts -> ~/.relay/commands.jsonl
  ./scripts/reflect-commands.py --transcript F  # print spans for one transcript (no write)
"""
from __future__ import annotations
import json, os, re, sys, glob

RELAY_RE = re.compile(r"^/(?:relay:|rl)")
CMD_RE = re.compile(r"<command-name>\s*(/[^<\s]+)\s*</command-name>")
PR_RE = re.compile(r"pull/(\d+)")
FILE_TOOLS = {"Edit", "Write", "MultiEdit", "NotebookEdit"}
AGENT_TOOLS = {"Agent", "Task"}
TOKEN_KEYS = {  # transcript usage key -> our short name
    "input_tokens": "input",
    "output_tokens": "output",
    "cache_read_input_tokens": "cache_read",
    "cache_creation_input_tokens": "cache_creation",
}


def _content_str(msg) -> str:
    """A JSON-ish string of a message's content, for regex scans (pr numbers)."""
    c = msg.get("content") if isinstance(msg, dict) else None
    if isinstance(c, str):
        return c
    if c is None:
        return ""
    return json.dumps(c)


def command_of(line: dict):
    """The slash command a user turn invokes, e.g. '/relay:rls' — or None."""
    if line.get("type") != "user":
        return None
    content = line.get("message", {}).get("content")
    if not isinstance(content, str):
        return None
    m = CMD_RE.search(content)
    return m.group(1) if m else None


def _new_span(command):
    return {
        "command": command,
        "is_relay": bool(command) and bool(RELAY_RE.match(command)),
        "ts_start": None, "ts_end": None,
        "models": {}, "subagents": {}, "tools": {}, "errors": 0,
        "tokens": {"input": 0, "output": 0, "cache_read": 0,
                   "cache_creation": 0, "thinking": 0},
        "_files": set(), "_prs": set(),
    }


def _accumulate(span: dict, line: dict):
    ts = line.get("timestamp")
    if ts:
        if span["ts_start"] is None or ts < span["ts_start"]:
            span["ts_start"] = ts
        if span["ts_end"] is None or ts > span["ts_end"]:
            span["ts_end"] = ts

    msg = line.get("message", {}) or {}
    typ = line.get("type")

    if typ == "assistant":
        model = msg.get("model")
        usage = msg.get("usage")
        if usage and model != "<synthetic>":
            for k, short in TOKEN_KEYS.items():
                span["tokens"][short] += usage.get(k, 0) or 0
            span["tokens"]["thinking"] += (
                (usage.get("output_tokens_details") or {}).get("thinking_tokens", 0) or 0)
            span["models"][model or "unknown"] = span["models"].get(model or "unknown", 0) + 1
        for block in (msg.get("content") or []):
            if not isinstance(block, dict) or block.get("type") != "tool_use":
                continue
            name = block.get("name", "?")
            span["tools"][name] = span["tools"].get(name, 0) + 1
            inp = block.get("input") or {}
            if name in FILE_TOOLS:
                fp = inp.get("file_path") or inp.get("notebook_path")
                if fp:
                    span["_files"].add(fp)
            elif name in AGENT_TOOLS:
                a = inp.get("subagent_type") or "unknown"
                span["subagents"][a] = span["subagents"].get(a, 0) + 1

    elif typ == "user":
        content = msg.get("content")
        if isinstance(content, list):
            for block in content:
                if isinstance(block, dict) and block.get("type") == "tool_result" \
                        and block.get("is_error"):
                    span["errors"] += 1

    for pr in PR_RE.findall(_content_str(msg)):
        span["_prs"].add(int(pr))


def _session_meta(lines):
    """(cwd, branch) — last non-null wins, mirroring reflect-sessions.sh."""
    cwd = branch = None
    for l in lines:
        if l.get("cwd"):
            cwd = l["cwd"]
        if l.get("gitBranch"):
            branch = l["gitBranch"]
    return cwd, branch


def _repo_of(cwd: str) -> str:
    base = re.sub(r"/\.claude/worktrees/.*$", "", cwd or "")
    return base.rsplit("/", 1)[-1] if base else ""


def segment(lines, session_id: str, transcript_path: str):
    """Return the list of RELAY command spans for a transcript, in order."""
    cwd, branch = _session_meta(lines)
    base = (cwd + "/") if cwd else None

    spans = []
    for line in lines:
        cmd = command_of(line)
        if cmd is not None:
            spans.append(_new_span(cmd))
        elif not spans:
            spans.append(_new_span(None))  # pre-command preamble; dropped below
        _accumulate(spans[-1], line)

    relay = [s for s in spans if s["is_relay"]]
    out = []
    for i, s in enumerate(relay):
        files = sorted(f[len(base):] for f in s["_files"]
                       if base and f.startswith(base)) if base else []
        artefacts = [f for f in files if f.startswith("relay/")]
        dur = None
        if s["ts_start"] and s["ts_end"]:
            dur = _delta_seconds(s["ts_start"], s["ts_end"])
        out.append({
            "v": 1,
            "session_id": session_id,
            "transcript_path": transcript_path,
            "seq": i,
            "command": s["command"],
            "repo": _repo_of(cwd), "branch": branch, "cwd": cwd,
            "ts_start": s["ts_start"], "ts_end": s["ts_end"], "duration_s": dur,
            "models": s["models"], "tokens": s["tokens"],
            "tools": s["tools"], "subagents": s["subagents"], "errors": s["errors"],
            "files": files, "code_write_count": len(files) - len(artefacts),
            "artefacts": artefacts, "prs": sorted(s["_prs"]),
            "next": relay[i + 1]["command"] if i + 1 < len(relay) else None,
        })
    return out


def _delta_seconds(a: str, b: str):
    import datetime
    def p(t):
        return datetime.datetime.fromisoformat(t.replace("Z", "+00:00"))
    try:
        return round((p(b) - p(a)).total_seconds())
    except Exception:
        return None


def _iter_lines(path):
    with open(path, "r", errors="replace") as fh:
        for raw in fh:
            raw = raw.strip()
            if not raw:
                continue
            try:
                yield json.loads(raw)
            except Exception:
                continue


def scan_transcript(path):
    sid = os.path.basename(path)[:-6] if path.endswith(".jsonl") else os.path.basename(path)
    # cheap pre-filter: only files that issued a Relay command
    try:
        with open(path, "r", errors="replace") as fh:
            head = fh.read()
    except OSError:
        return []
    if "<command-name>/relay:" not in head and "<command-name>/rl" not in head:
        return []
    lines = list(_iter_lines(path))
    return segment(lines, sid, path)


def main(argv):
    if "--transcript" in argv:
        path = argv[argv.index("--transcript") + 1]
        for span in scan_transcript(path):
            print(json.dumps(span))
        return 0

    projects = os.environ.get("CLAUDE_PROJECTS", os.path.expanduser("~/.claude/projects"))
    out = os.environ.get("RELAY_COMMANDS", os.path.expanduser("~/.relay/commands.jsonl"))
    os.makedirs(os.path.dirname(out), exist_ok=True)

    rows, scanned = [], 0
    for path in glob.glob(os.path.join(projects, "*", "*.jsonl")):
        scanned += 1
        rows.extend(scan_transcript(path))
    rows.sort(key=lambda r: (r["ts_end"] or "", r["session_id"], r["seq"]))
    tmp = out + ".tmp"
    with open(tmp, "w") as fh:
        for r in rows:
            fh.write(json.dumps(r) + "\n")
    os.replace(tmp, out)
    sys.stderr.write(
        f"Scanned {scanned} transcript(s); wrote {len(rows)} Relay command span(s) "
        f"across {len({r['session_id'] for r in rows})} session(s) -> {out}\n")
    print(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
