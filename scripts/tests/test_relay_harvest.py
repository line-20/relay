#!/usr/bin/env python3
"""Tests for relay_harvest.py — the first durable worker-harvest/recovery slice.

Builds a REAL git repo with multiple topic worktrees, simulates worker/VS Code
loss (a fresh process reading only durable state), and proves rediscover ->
replace -> resume without any session id or transcript.

Run: python3 scripts/tests/test_relay_harvest.py
"""
import importlib.util, json, os, shutil, subprocess, tempfile, unittest

_HERE = os.path.dirname(os.path.abspath(__file__))
_spec = importlib.util.spec_from_file_location("relay_harvest", os.path.join(_HERE, "..", "relay_harvest.py"))
rh = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(rh)


def git(args, cwd):
    r = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True)
    assert r.returncode == 0, f"git {args} failed: {r.stderr}"
    return r.stdout.strip()


BOARD = """# Board

## Open threads

| Item | Status | Owner | Latest handover |
|------|--------|-------|-----------------|
| `masterdata/import` | ⚙ in-progress | someworker | handover/next-a.md |
| `platform/operator` | 🔍 in-review | — | handover/next-b.md |
| `misc/done-thing`   | ✅ done | — | handover/next-c.md |
"""

ITEMS = [  # (slug, branch)
    ("masterdata/import", "wt-masterdata"),
    ("platform/operator", "wt-operator"),
]


def make_result(slug, branch, lap, head_sha, discoveries=None):
    return {
        "harvest_version": 1,
        "lap_id": lap,
        "work_item": slug,
        "emitted_at": "2026-08-29T10:00:00Z",
        "disposition": "advanced",
        "references": {
            "branch": branch, "head_sha": head_sha,
            "brief": f"relay/briefs/{slug.replace('/', '__')}.md", "pr": 900,
        },
        "resume_delta": {
            "stage": "build",
            "next_slice": f"finish {slug} slice 2",
            "in_flight": [{"path": "src/x.ts", "state": "remaining"}],
            "scope_edges": ["do not touch billing"],
            "open_questions": [],
        },
        "discoveries": discoveries or [],
    }


class HarvestSliceTest(unittest.TestCase):
    def setUp(self):
        self.parent = tempfile.mkdtemp()
        self.repo = os.path.join(self.parent, "repo")
        os.makedirs(self.repo)
        git(["init", "-q", "-b", "main"], self.repo)
        git(["config", "user.email", "t@t"], self.repo)
        git(["config", "user.name", "t"], self.repo)
        self.relay = os.path.join(self.repo, "relay")
        os.makedirs(os.path.join(self.relay, "briefs"))
        with open(os.path.join(self.relay, "board.md"), "w") as fh:
            fh.write(BOARD)
        for slug, _ in ITEMS:
            with open(os.path.join(self.relay, "briefs", slug.replace("/", "__") + ".md"), "w") as fh:
                fh.write(f"# {slug}\n\nbrief body\n")
        git(["add", "-A"], self.repo)
        git(["commit", "-q", "-m", "init"], self.repo)
        # deterministic topic worktrees on their branches
        self.wt = {}
        for slug, branch in ITEMS:
            path = os.path.join(self.parent, "wt", branch)
            git(["worktree", "add", "-q", path, "-b", branch], self.repo)
            self.wt[slug] = (branch, path)

    def tearDown(self):
        shutil.rmtree(self.parent, ignore_errors=True)

    def _emit_and_apply_all(self):
        for slug, (branch, path) in self.wt.items():
            head = git(["rev-parse", "HEAD"], path)
            rh.emit_result(self.relay, make_result(slug, branch, f"lap-{branch}", head))
        return rh.apply_pending(self.relay, board_path=os.path.join(self.relay, "board.md"))

    # ---- PRIMARY ACCEPTANCE ----
    def test_acceptance_rediscover_and_replace(self):
        self._emit_and_apply_all()
        # "VS Code force-quit; fresh Relay, no session ids" == a plain discover call
        active = rh.discover_active(self.repo, self.relay)
        found = {a["work_item"] for a in active}
        self.assertEqual(found, {"masterdata/import", "platform/operator"})  # done item excluded
        for a in active:
            self.assertTrue(a["has_checkpoint"])
            self.assertIsNotNone(a["worktree"], f"worktree unresolved for {a['work_item']}")

        # pick one, replace-from-state
        ctx = rh.resume_context(self.repo, self.relay, "masterdata/import")
        self.assertEqual(ctx["branch"], "wt-masterdata")
        self.assertTrue(os.path.isdir(ctx["worktree_path"]))
        # the fresh worker really lands in the right worktree/branch
        self.assertEqual(git(["rev-parse", "--abbrev-ref", "HEAD"], ctx["worktree_path"]), "wt-masterdata")
        self.assertEqual(ctx["resume_delta"]["next_slice"], "finish masterdata/import slice 2")
        self.assertTrue(ctx["brief"].endswith("masterdata__import.md"))
        # transcript-free, session-free
        self.assertFalse(ctx["requires_transcript"])
        self.assertFalse(ctx["requires_session_id"])
        # no provider-specific value leaked into the recovery context
        self.assertNotIn("claude", json.dumps(ctx).lower())

    # ---- retry does not duplicate board/state ----
    def test_apply_idempotent_no_duplicate(self):
        slug, (branch, path) = "masterdata/import", self.wt["masterdata/import"]
        head = git(["rev-parse", "HEAD"], path)
        disc = [{"id": "abc123", "title": "race in Y", "one_line": "module Y unguarded"}]
        rh.emit_result(self.relay, make_result(slug, branch, "lap-1", head, discoveries=disc))
        board = os.path.join(self.relay, "board.md")
        rh.apply_pending(self.relay, slug=slug, board_path=board)
        s2 = rh.apply_pending(self.relay, slug=slug, board_path=board)  # retry
        self.assertEqual(s2["applied"], 0)  # nothing re-applied
        with open(board) as fh:
            self.assertEqual(fh.read().count("disc:abc123"), 1)  # discovery not duplicated
        applied = json.load(open(rh._applied_path(self.relay, slug)))
        self.assertEqual(applied["applied"].count("lap-1"), 1)

    def test_missing_provider_metadata_ok(self):
        self._emit_and_apply_all()
        active = rh.discover_active(self.repo, self.relay, hints_path=None)
        self.assertTrue(all(a["session_hint"] is None for a in active))
        ctx = rh.resume_context(self.repo, self.relay, "platform/operator")
        self.assertIsNotNone(ctx["worktree_path"])  # recovered without any provider metadata

    def test_offline_no_remote_needed(self):
        self._emit_and_apply_all()
        # fixture repo has NO remote; discovery + resume must still work
        self.assertEqual(subprocess.run(["git", "remote"], cwd=self.repo,
                                        capture_output=True, text=True).stdout.strip(), "")
        self.assertIsNotNone(rh.resume_context(self.repo, self.relay, "masterdata/import")["worktree_path"])

    def test_worktree_discovery_independent_of_terminal(self):
        self._emit_and_apply_all()
        # discovery reads git worktree list, not any session/terminal state
        active = {a["work_item"]: a for a in rh.discover_active(self.repo, self.relay)}
        self.assertTrue(active["masterdata/import"]["worktree"].endswith("wt-masterdata"))
        self.assertTrue(active["platform/operator"]["worktree"].endswith("wt-operator"))

    def test_malformed_result_fails_safe(self):
        with self.assertRaises(rh.HarvestError):
            rh.emit_result(self.relay, {"work_item": "x/y"})  # missing required keys
        # nothing written for x/y
        self.assertFalse(os.path.exists(rh._results_dir(self.relay, "x/y")))
        # a malformed staged result is skipped by apply, not corrupting state
        slug = "masterdata/import"
        os.makedirs(rh._results_dir(self.relay, slug), exist_ok=True)
        with open(os.path.join(rh._results_dir(self.relay, slug), "bad.json"), "w") as fh:
            fh.write("{not json")
        s = rh.apply_pending(self.relay, slug=slug, board_path=os.path.join(self.relay, "board.md"))
        self.assertEqual(s["applied"], 0)
        self.assertFalse(os.path.exists(rh._checkpoint_path(self.relay, slug)))  # no checkpoint from garbage

    def test_provider_leak_rejected(self):
        slug, (branch, path) = "masterdata/import", self.wt["masterdata/import"]
        head = git(["rev-parse", "HEAD"], path)
        bad = make_result(slug, branch, "lap-x", head)
        bad["session_id"] = "claude-abc"  # provider leakage into durable state
        with self.assertRaises(rh.HarvestError):
            rh.emit_result(self.relay, bad)

    def test_handover_projection(self):
        self._emit_and_apply_all()
        hv = os.path.join(self.relay, "handover", "next-lap-wt-masterdata.md")
        self.assertTrue(os.path.exists(hv))
        text = open(hv).read()
        self.assertIn("Projection of the durable checkpoint", text)   # not canonical
        self.assertIn("masterdata/import", text)
        self.assertIn("finish masterdata/import slice 2", text)
        # re-render from the checkpoint reproduces the projection deterministically
        cp = json.load(open(rh._checkpoint_path(self.relay, "masterdata/import")))
        self.assertEqual(rh._render_handover_md(cp), text)

    def test_wal_replay_after_lost_marker(self):
        slug, (branch, path) = "masterdata/import", self.wt["masterdata/import"]
        head = git(["rev-parse", "HEAD"], path)
        disc = [{"id": "d1", "title": "t", "one_line": "o"}]
        rh.emit_result(self.relay, make_result(slug, branch, "lap-1", head, discoveries=disc))
        board = os.path.join(self.relay, "board.md")
        rh.apply_pending(self.relay, slug=slug, board_path=board)
        # simulate a crash that lost the completion marker (result still staged, durable)
        os.remove(rh._applied_path(self.relay, slug))
        rh.apply_pending(self.relay, slug=slug, board_path=board)  # replay
        self.assertTrue(os.path.exists(rh._checkpoint_path(self.relay, slug)))
        with open(board) as fh:
            self.assertEqual(fh.read().count("disc:d1"), 1)  # replay didn't duplicate

    def test_branch_frontmatter_is_free_text_safe(self):
        # real handovers carry free-text branch frontmatter — must not yield garbage
        self.assertFalse(rh._valid_branch("(none"))
        self.assertFalse(rh._valid_branch("none"))
        self.assertTrue(rh._valid_branch("worktree-money-evidence-3b-bank-csv"))
        hv = os.path.join(self.relay, "handover")
        os.makedirs(hv, exist_ok=True)
        cases = {
            "next-none.md": "---\nbranch: (none — docs-only board close)\nitem: a/b\n---\n",
            "next-real.md": "---\nbranch: real-branch (merged; remote deleted)\nitem: a/b\n---\n",
            "next-plain.md": "---\nbranch: main\n---\n",
        }
        for fn, txt in cases.items():
            with open(os.path.join(hv, fn), "w") as fh:
                fh.write(txt)
        self.assertIsNone(rh._branch_from_handover_file(self.relay, "handover/next-none.md"))
        self.assertEqual(rh._branch_from_handover_file(self.relay, "handover/next-real.md"), "real-branch")
        self.assertEqual(rh._branch_from_handover_file(self.relay, "handover/next-plain.md"), "main")

    def test_worker_bootstrap_provider_neutral(self):
        self._emit_and_apply_all()
        bs = rh.worker_bootstrap(self.repo, self.relay, "masterdata/import")
        self.assertEqual(bs["work_item"], "masterdata/import")
        self.assertTrue(os.path.isdir(bs["worktree_path"]))
        self.assertEqual(bs["branch"], "wt-masterdata")
        self.assertTrue(bs["brief_path"].endswith("masterdata__import.md"))
        self.assertEqual(bs["objective"], "finish masterdata/import slice 2")
        self.assertTrue(bs["instructions"])
        blob = json.dumps(bs).lower()
        for claudeism in ("claude", "/relay:", "session", "transcript"):
            if claudeism in ("session", "transcript"):  # only the require_* flags may mention these
                self.assertNotIn(claudeism + "_id_value", blob)  # no actual id
            else:
                self.assertNotIn(claudeism, blob)
        self.assertFalse(bs["requires_transcript"])
        self.assertFalse(bs["requires_session_id"])

    def test_bootstrap_brief_absent_no_dangling(self):
        slug, (branch, path) = "masterdata/import", self.wt["masterdata/import"]
        head = git(["rev-parse", "HEAD"], path)
        r = make_result(slug, branch, "lap-nb", head)
        r["references"]["brief"] = "relay/briefs/does-not-exist.md"   # dangling in the result
        rh.emit_result(self.relay, r); rh.apply_pending(self.relay, slug=slug)
        bs = rh.worker_bootstrap(self.repo, self.relay, slug)
        self.assertEqual(bs["brief_status"], "absent")
        self.assertIsNone(bs["brief_path"])            # never a dangling path
        self.assertTrue(bs["brief_fallback"])
        self.assertEqual(rh.validate_bootstrap(self.repo, bs), [])
        rh.assert_no_dangling(self.repo, bs)

    def test_bootstrap_project_instructions_resolved(self):
        slug, (branch, path) = "masterdata/import", self.wt["masterdata/import"]
        with open(os.path.join(path, "CLAUDE.md"), "w") as fh:
            fh.write("# project rules\n")
        head = git(["rev-parse", "HEAD"], path)
        rh.emit_result(self.relay, make_result(slug, branch, "lap-pi", head))
        rh.apply_pending(self.relay, slug=slug)
        bs = rh.worker_bootstrap(self.repo, self.relay, slug)
        self.assertIn("CLAUDE.md", bs["project_instructions"])
        for name in bs["project_instructions"]:                 # every one resolves
            self.assertIsNotNone(rh._resolve_ref(self.repo, bs["worktree_path"], name)[0])
        rh.assert_no_dangling(self.repo, bs)

    def test_bootstrap_invariant_catches_dangling(self):
        slug, (branch, path) = "masterdata/import", self.wt["masterdata/import"]
        head = git(["rev-parse", "HEAD"], path)
        rh.emit_result(self.relay, make_result(slug, branch, "lap-inv", head))
        rh.apply_pending(self.relay, slug=slug)
        bs = rh.worker_bootstrap(self.repo, self.relay, slug)
        rh.assert_no_dangling(self.repo, bs)                    # valid passes
        bad = dict(bs); bad["brief_status"] = "resolved"; bad["brief_path"] = "relay/briefs/nope.md"
        with self.assertRaises(rh.HarvestError):
            rh.assert_no_dangling(self.repo, bad)

    def test_bootstrap_worktree_absent_has_fallback(self):
        rh.emit_result(self.relay, make_result("ghost/item", "ghost-branch", "lap-g", "0" * 40))
        rh.apply_pending(self.relay, slug="ghost/item")
        bs = rh.worker_bootstrap(self.repo, self.relay, "ghost/item")
        self.assertEqual(bs["worktree_status"], "absent")
        self.assertIsNone(bs["worktree_path"])
        self.assertIn("ghost-branch", bs["worktree_fallback"])
        self.assertEqual(rh.validate_bootstrap(self.repo, bs), [])

    def test_board_parser_is_cell_aware(self):
        board = os.path.join(self.parent, "b.md")
        with open(board, "w") as fh:
            fh.write(
                "# Board\n\n## Open threads\n\n"
                "| Item | Status | Owner | Latest handover | Detail |\n"
                "|------|--------|-------|-----------------|--------|\n"
                # (a) glyph ⚙ ONLY in Detail prose -> must NOT be active
                "| `a/done` | ✅ done | — | handover/next-a.md | still ⚙ churning per the notes |\n"
                # (b) handover-like path in Detail prose; col-4 is the real one
                "| `b/active` | ⚙ in-progress | w | handover/next-real.md | see old `handover/next-OLD.md` |\n"
                # (c) completed item with misleading in-progress-sounding text
                "| `c/done` | ✅ | — | — | in-progress-sounding work that is actually finished |\n"
                # (d) active with a valid handover reference (backticked)
                "| `d/active` | 🔍 in-review | — | `handover/next-d.md` | review pending |\n"
                # (e) malformed/partial row (too few cells) -> skipped safely
                "| junk | ⚙ |\n"
                "not a table row with a ⚙ glyph and handover/next-x.md in it\n"
            )
        rows = dict(rh._parse_board_active(board))
        self.assertNotIn("a/done", rows)                 # (a) glyph in Detail ignored
        self.assertNotIn("c/done", rows)                 # (c) misleading prose ignored
        self.assertEqual(set(rows), {"b/active", "d/active"})
        self.assertEqual(rows["b/active"], "handover/next-real.md")  # (b) col-4, not prose
        self.assertEqual(rows["d/active"], "handover/next-d.md")     # (d) valid ref

    def test_local_checkpoint_commit_no_network(self):
        slug, (branch, path) = "masterdata/import", self.wt["masterdata/import"]
        with open(os.path.join(path, "wip.txt"), "w") as fh:
            fh.write("half done")
        sha = rh.autosave(path, "lap-1")
        self.assertTrue(sha)
        self.assertIn("Relay-Autosave: lap-1", git(["log", "-1", "--format=%B"], path))
        # clean tree -> no new commit, returns HEAD
        self.assertEqual(rh.autosave(path, "lap-2"), git(["rev-parse", "HEAD"], path))


if __name__ == "__main__":
    unittest.main(verbosity=2)
