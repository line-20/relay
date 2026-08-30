#!/usr/bin/env python3
"""Tests for reflect-commands.py segmentation. Run: python3 scripts/tests/test_reflect_commands.py"""
import importlib.util
import json
import os
import unittest

_HERE = os.path.dirname(os.path.abspath(__file__))
_MOD = os.path.join(_HERE, "..", "reflect-commands.py")
spec = importlib.util.spec_from_file_location("reflect_commands", _MOD)
rc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rc)

CWD = "/repo/.claude/worktrees/wt"


def user_cmd(cmd, ts):
    return {"type": "user", "timestamp": ts, "cwd": CWD, "gitBranch": "feat",
            "message": {"content": f"<command-name>{cmd}</command-name>"}}


def assistant(ts, output, tool_uses=None):
    content = list(tool_uses or [])
    return {"type": "assistant", "timestamp": ts, "cwd": CWD,
            "message": {"model": "claude-opus-4-8",
                        "usage": {"output_tokens": output, "input_tokens": 1,
                                  "output_tokens_details": {"thinking_tokens": output // 10}},
                        "content": content}}


def tool_use(name, **inp):
    return {"type": "tool_use", "name": name, "input": inp}


def tool_error(ts):
    return {"type": "user", "timestamp": ts,
            "message": {"content": [{"type": "tool_result", "is_error": True, "content": "boom"}]}}


def pr_result(ts, n):
    return {"type": "user", "timestamp": ts,
            "message": {"content": [{"type": "tool_result", "content": f"created https://github.com/x/y/pull/{n}"}]}}


class SegmentationTest(unittest.TestCase):
    def setUp(self):
        # A full lap: preamble + /clear (both non-relay, must be dropped) then rlc -> rlt -> rls
        self.lines = [
            assistant("2026-08-01T10:00:00Z", 999),                       # preamble (dropped)
            user_cmd("/clear", "2026-08-01T10:01:00Z"),
            assistant("2026-08-01T10:01:30Z", 500),                       # /clear span (dropped)
            user_cmd("/relay:rlc", "2026-08-01T10:02:00Z"),
            assistant("2026-08-01T10:03:00Z", 100,
                      [tool_use("Edit", file_path=f"{CWD}/src/a.ts")]),
            user_cmd("/relay:rlt", "2026-08-01T10:10:00Z"),
            assistant("2026-08-01T10:11:00Z", 200,
                      [tool_use("Write", file_path=f"{CWD}/src/a.test.ts"),
                       tool_use("Bash", command="npm test")]),
            tool_error("2026-08-01T10:11:30Z"),
            user_cmd("/relay:rls", "2026-08-01T10:20:00Z"),
            assistant("2026-08-01T10:21:00Z", 300,
                      [tool_use("Agent", subagent_type="relay:security-specialist"),
                       tool_use("Agent", subagent_type="relay:test-engineer"),
                       tool_use("Edit", file_path=f"{CWD}/relay/board.md")]),
            pr_result("2026-08-01T10:25:00Z", 42),
        ]
        self.spans = rc.segment(self.lines, "sess-1", "/t.jsonl")

    def test_three_relay_spans_in_order(self):
        self.assertEqual([s["command"] for s in self.spans],
                         ["/relay:rlc", "/relay:rlt", "/relay:rls"])
        self.assertEqual([s["seq"] for s in self.spans], [0, 1, 2])

    def test_transition_chain(self):
        self.assertEqual([s["next"] for s in self.spans],
                         ["/relay:rlt", "/relay:rls", None])

    def test_tokens_attributed_per_span_not_smeared(self):
        # 999 (preamble) and 500 (/clear) must NOT leak into any relay span
        self.assertEqual([s["tokens"]["output"] for s in self.spans], [100, 200, 300])
        self.assertEqual(self.spans[0]["tokens"]["thinking"], 10)

    def test_files_and_artefacts_per_span(self):
        self.assertEqual(self.spans[0]["files"], ["src/a.ts"])
        self.assertEqual(self.spans[1]["files"], ["src/a.test.ts"])
        self.assertEqual(self.spans[2]["files"], ["relay/board.md"])
        # global-state write isolated from worker-local code writes
        self.assertEqual(self.spans[2]["artefacts"], ["relay/board.md"])
        self.assertEqual(self.spans[0]["artefacts"], [])
        self.assertEqual(self.spans[0]["code_write_count"], 1)
        self.assertEqual(self.spans[2]["code_write_count"], 0)

    def test_subagents_only_on_ship_span(self):
        self.assertEqual(self.spans[2]["subagents"],
                         {"relay:security-specialist": 1, "relay:test-engineer": 1})
        self.assertEqual(self.spans[0]["subagents"], {})

    def test_errors_attributed_to_test_span(self):
        self.assertEqual(self.spans[1]["errors"], 1)
        self.assertEqual(self.spans[0]["errors"], 0)

    def test_pr_attributed_to_ship_span(self):
        self.assertEqual(self.spans[2]["prs"], [42])
        self.assertEqual(self.spans[0]["prs"], [])

    def test_duration_and_meta(self):
        self.assertEqual(self.spans[0]["repo"], "repo")
        self.assertEqual(self.spans[0]["branch"], "feat")
        self.assertIsNotNone(self.spans[0]["duration_s"])


class CommandOfTest(unittest.TestCase):
    def test_detects_relay_command(self):
        self.assertEqual(rc.command_of(user_cmd("/relay:rls", "t")), "/relay:rls")

    def test_plain_turn_is_none(self):
        self.assertIsNone(rc.command_of(
            {"type": "user", "message": {"content": "just a message"}}))

    def test_assistant_turn_is_none(self):
        self.assertIsNone(rc.command_of({"type": "assistant", "message": {"content": []}}))


class ScanTranscriptFileTest(unittest.TestCase):
    def test_scan_real_file_skips_garbage_lines(self):
        import tempfile, shutil
        d = tempfile.mkdtemp()
        try:
            tp = os.path.join(d, "sess-1.jsonl")
            rows = [
                {"type": "user", "timestamp": "2026-08-01T10:00:00Z", "cwd": "/repo", "gitBranch": "b",
                 "message": {"content": "<command-name>/relay:rls</command-name>"}},
                "{ this is not valid json",     # line noise — must be tolerated/skipped
                {"type": "assistant", "timestamp": "2026-08-01T10:01:00Z", "cwd": "/repo",
                 "message": {"model": "claude-opus-4-8", "usage": {"output_tokens": 50},
                             "content": [{"type": "tool_use", "name": "Edit", "input": {"file_path": "/repo/a.ts"}}]}},
            ]
            with open(tp, "w") as fh:
                for r in rows:
                    fh.write((r if isinstance(r, str) else json.dumps(r)) + "\n")
            spans = rc.scan_transcript(tp)
            self.assertEqual(len(spans), 1)
            self.assertEqual(spans[0]["command"], "/relay:rls")
            self.assertEqual(spans[0]["tokens"]["output"], 50)   # good lines still parsed
            self.assertEqual(spans[0]["files"], ["a.ts"])
        finally:
            shutil.rmtree(d, ignore_errors=True)

    def test_non_relay_transcript_yields_nothing(self):
        import tempfile, shutil
        d = tempfile.mkdtemp()
        try:
            tp = os.path.join(d, "sess-2.jsonl")
            with open(tp, "w") as fh:
                fh.write(json.dumps({"type": "user", "message": {"content": "<command-name>/clear</command-name>"}}) + "\n")
            self.assertEqual(rc.scan_transcript(tp), [])   # pre-filter: no Relay command
        finally:
            shutil.rmtree(d, ignore_errors=True)


if __name__ == "__main__":
    unittest.main(verbosity=2)
