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
        # structural provider-neutrality: no provider value, no identity key —
        # only the two boolean flag keys may legitimately mention session/transcript
        self.assertNotIn("claude", json.dumps(bs).lower())
        self.assertNotIn("/relay:", json.dumps(bs))
        self.assertEqual(set(bs) & {"session_id", "transcript_path", "claude_session_id"}, set())
        self.assertEqual([k for k in bs if "session" in k.lower()], ["requires_session_id"])
        self.assertEqual([k for k in bs if "transcript" in k.lower()], ["requires_transcript"])
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

    def test_board_ref_resolves_and_no_dangling(self):
        self._emit_and_apply_all()
        bs = rh.worker_bootstrap(self.repo, self.relay, "masterdata/import")
        self.assertEqual(bs["board_ref"], "relay/board.md")
        self.assertIsNotNone(rh._resolve_ref(self.repo, bs["worktree_path"], bs["board_ref"])[0])
        rh.assert_no_dangling(self.repo, bs)

    def test_board_ref_is_brief_fallback_when_brief_absent(self):
        slug, (branch, path) = "masterdata/import", self.wt["masterdata/import"]
        head = git(["rev-parse", "HEAD"], path)
        r = make_result(slug, branch, "lap-bf", head); r["references"]["brief"] = "relay/briefs/nope.md"
        rh.emit_result(self.relay, r); rh.apply_pending(self.relay, slug=slug)
        bs = rh.worker_bootstrap(self.repo, self.relay, slug)
        self.assertEqual(bs["brief_status"], "absent")
        self.assertEqual(bs["board_ref"], "relay/board.md")       # brief-less item gets a board pointer
        self.assertIn("relay/board.md", bs["brief_fallback"])     # fallback names WHERE to look
        self.assertIn(slug, bs["brief_fallback"])                 # and WHICH row
        rh.assert_no_dangling(self.repo, bs)

    def test_validate_bootstrap_flags_bad_board_ref(self):
        self._emit_and_apply_all()
        bs = rh.worker_bootstrap(self.repo, self.relay, "masterdata/import")
        bad = dict(bs); bad["board_ref"] = "relay/does-not-exist-board.md"
        self.assertIn("board_ref presented but does not resolve", rh.validate_bootstrap(self.repo, bad))

    def test_board_ref_absent_when_no_board(self):
        repo = os.path.join(self.parent, "nb"); os.makedirs(repo)
        git(["init", "-q", "-b", "main"], repo); git(["config", "user.email", "t@t"], repo); git(["config", "user.name", "t"], repo)
        relay = os.path.join(repo, "relay"); os.makedirs(relay)
        open(os.path.join(repo, "f.txt"), "w").write("x"); git(["add", "-A"], repo); git(["commit", "-qm", "init"], repo)
        wtp = os.path.join(self.parent, "nbwt"); git(["worktree", "add", "-q", wtp, "-b", "nb-branch"], repo)
        head = git(["rev-parse", "HEAD"], wtp)
        rh.emit_result(relay, make_result("x/y", "nb-branch", "lap-nb2", head))
        rh.apply_pending(relay, slug="x/y")
        bs = rh.worker_bootstrap(repo, relay, "x/y")
        self.assertIsNone(bs["board_ref"])                        # no board -> absent, not dangling
        self.assertEqual(bs["brief_fallback"], "resume_delta")
        rh.assert_no_dangling(repo, bs)

    def test_branch_for_fallback_tiers(self):
        hv = os.path.join(self.relay, "handover"); os.makedirs(hv, exist_ok=True)
        with open(os.path.join(hv, "next-t2.md"), "w") as fh:
            fh.write("---\nbranch: tier2-branch (merged; deleted)\nitem: a/b\n---\n")
        # tier 2: checkpoint branch invalid -> the board row's designated handover frontmatter
        self.assertEqual(
            rh._branch_for(self.relay, "a/b", "handover/next-t2.md", {"references": {"branch": "(none"}}),
            "tier2-branch")
        # tier 3: no checkpoint, no handover_rel -> newest handover mentioning the slug
        with open(os.path.join(hv, "next-t3.md"), "w") as fh:
            fh.write("---\nbranch: tier3-branch\n---\ncontinuing ghost/tier3 here\n")
        self.assertEqual(rh._branch_for(self.relay, "ghost/tier3", None, None), "tier3-branch")

    def test_resolve_ref_origin_main(self):
        r = os.path.join(self.parent, "orig"); os.makedirs(r)
        git(["init", "-q", "-b", "main"], r); git(["config", "user.email", "t@t"], r); git(["config", "user.name", "t"], r)
        open(os.path.join(r, "base.txt"), "w").write("base"); git(["add", "-A"], r); git(["commit", "-qm", "base"], r)
        open(os.path.join(r, "only-main.md"), "w").write("durable"); git(["add", "-A"], r); git(["commit", "-qm", "add"], r)
        git(["update-ref", "refs/remotes/origin/main", "HEAD"], r)   # keep the commit as origin/main
        git(["reset", "--hard", "HEAD~1"], r)                        # but drop it from the working tree
        self.assertFalse(os.path.exists(os.path.join(r, "only-main.md")))
        self.assertEqual(rh._resolve_ref(r, None, "only-main.md"), ("origin/main:only-main.md", "origin/main"))
        self.assertEqual(rh._resolve_ref(r, None, "nope.md"), (None, None))

    def test_apply_pending_mixed_batch_does_not_abort(self):
        slug, (branch, path) = "masterdata/import", self.wt["masterdata/import"]
        head = git(["rev-parse", "HEAD"], path)
        rh.emit_result(self.relay, make_result(slug, branch, "lap-1", head))
        # a valid-JSON but INVALID result, sorting between the two good ones
        with open(os.path.join(rh._results_dir(self.relay, slug), "lap-2.json"), "w") as fh:
            json.dump({"harvest_version": 1, "lap_id": "lap-2"}, fh)   # missing required keys
        rh.emit_result(self.relay, make_result(slug, branch, "lap-3", head))
        rh.apply_pending(self.relay, slug=slug, board_path=os.path.join(self.relay, "board.md"))
        applied = json.load(open(rh._applied_path(self.relay, slug)))["applied"]
        self.assertIn("lap-1", applied)     # before the bad one
        self.assertIn("lap-3", applied)     # after the bad one — batch did not abort
        self.assertNotIn("lap-2", applied)  # bad one skipped, not applied

    def test_validate_result_rejection_branches(self):
        base = lambda: {"harvest_version": 1, "lap_id": "x", "work_item": "a/b",
                        "disposition": "advanced", "resume_delta": {}}
        for mutate in (lambda r: r.update(harvest_version=99),
                       lambda r: r.update(disposition="weird"),
                       lambda r: r.update(resume_delta="notdict"),
                       lambda r: r.update(lap_id="")):
            r = base(); mutate(r)
            with self.assertRaises(rh.HarvestError):
                rh.validate_result(r)
        rh.validate_result(base())                                   # clean passes
        r = base(); r["disposition"] = "stopped:tests-red"; rh.validate_result(r)   # gate form accepted

    def test_resume_delta_shape_contract(self):
        # The resume-state contract: each resume_delta field is validated WHEN PRESENT,
        # none required (empty is valid for merged/parked). Malformed -> HarvestError at emit.
        base = lambda: {"harvest_version": 1, "lap_id": "x", "work_item": "a/b",
                        "disposition": "advanced", "resume_delta": {}}
        def with_rd(rd):
            r = base(); r["resume_delta"] = rd; return r

        # accepted shapes
        for ok in ({},                                                   # empty (nothing to resume)
                   {"in_flight": "clean"},                               # string sentinel
                   {"in_flight": []},                                    # empty list
                   {"in_flight": [{"path": "src/x.ts", "state": "done"},
                                  {"path": "src/y.ts", "state": "remaining"}],
                    "next_slice": "finish slice 2", "scope_edges": ["no billing"],
                    "open_questions": ["q-1"], "stage": "build"}):
            rh.validate_result(with_rd(ok))                              # must not raise

        # rejected shapes — a malformed delta fails before any write
        for bad in ({"in_flight": "dirty"},                             # non-sentinel string
                    {"in_flight": 5},                                    # wrong type
                    {"in_flight": None},                                 # present null (would crash render)
                    {"in_flight": ["not-a-dict"]},                       # list entry not an object
                    {"in_flight": [{"path": "x"}]},                      # missing state
                    {"in_flight": [{"state": "done"}]},                  # missing path
                    {"in_flight": [{"path": "x", "state": "wip"}]},      # unknown state
                    {"in_flight": [{"path": "", "state": "done"}]},      # empty path
                    {"scope_edges": "nope"},                             # not a list
                    {"open_questions": "nope"},                          # not a list
                    {"next_slice": ""},                                  # empty string
                    {"next_slice": 5},                                   # wrong type
                    {"next_slice": None},                                # present null (would crash render)
                    {"stage": ""},                                       # empty string
                    {"stage": 5},                                        # wrong type
                    {"session_id": "s-1"},                               # provider leak inside resume_delta
                    {"provider": "claude"}):                             # provider leak inside resume_delta
            with self.assertRaises(rh.HarvestError):
                rh.validate_result(with_rd(bad))

    def test_malformed_resume_delta_fails_safe_via_emit(self):
        # The fail-safe proven through the REAL write path (mirrors test_malformed_result_fails_safe):
        # a malformed resume_delta raises in emit_result and writes NOTHING to the WAL.
        slug, branch = "masterdata/import", "wt-masterdata"
        bad = make_result(slug, branch, "lap-bad", "0" * 40)
        bad["resume_delta"] = {"in_flight": None}   # present null — accepted before this fix
        with self.assertRaises(rh.HarvestError):
            rh.emit_result(self.relay, bad)
        self.assertFalse(os.path.exists(rh._results_dir(self.relay, slug)))  # nothing written

    def test_present_null_in_flight_would_not_crash_render(self):
        # Defence in depth: even a legacy checkpoint with in_flight: null (written before validation
        # existed) must render, not raise — the renderer treats a present null as "clean".
        cp = {"work_item": "a/b", "disposition": "advanced", "checkpoint_ref": None,
              "references": {"branch": "b"}, "resume_delta": {"in_flight": None, "next_slice": None}}
        md = rh._render_handover_md(cp)   # must not raise
        self.assertIn("## In flight", md)

    def _corrupt_checkpoint(self, slug, resume_delta):
        # Overwrite a checkpoint's resume_delta to simulate a legacy/pre-validation or hand-edited file.
        cpp = rh._checkpoint_path(self.relay, slug)
        cp = json.load(open(cpp)); cp["resume_delta"] = resume_delta
        with open(cpp, "w") as fh:
            json.dump(cp, fh)

    def test_resume_context_rejects_malformed_checkpoint(self):
        # Replace path fails CLOSED: a malformed/legacy checkpoint must raise HarvestError
        # (not TypeError), never seed a resumer from broken state.
        self._emit_and_apply_all()
        # present-null (the legacy target) raises with an ACTIONABLE message
        self._corrupt_checkpoint("masterdata/import", None)
        with self.assertRaisesRegex(rh.HarvestError, "regenerate the handover"):
            rh.resume_context(self.repo, self.relay, "masterdata/import")
        for bad_rd in ("clean", {"in_flight": [{"path": "x"}]}, {"next_slice": ""}):
            self._corrupt_checkpoint("masterdata/import", bad_rd)
            with self.assertRaises(rh.HarvestError):
                rh.resume_context(self.repo, self.relay, "masterdata/import")
        # an empty delta (nothing to resume — merged/parked) still resumes, does NOT raise
        self._corrupt_checkpoint("masterdata/import", {})
        self.assertEqual(
            rh.resume_context(self.repo, self.relay, "masterdata/import")["resume_delta"], {})
        # the untouched item still resumes fine
        ctx = rh.resume_context(self.repo, self.relay, "platform/operator")
        self.assertEqual(ctx["resume_delta"]["next_slice"], "finish platform/operator slice 2")

    def test_discover_tolerates_malformed_checkpoint(self):
        # Enumerate path DEGRADES: one corrupt checkpoint must not blind the whole listing,
        # crash on a present-null delta, or drop the item.
        self._emit_and_apply_all()
        self._corrupt_checkpoint("masterdata/import", None)   # present-null: the legacy target
        active = {a["work_item"]: a for a in rh.discover_active(self.repo, self.relay)}
        self.assertEqual(set(active), {"masterdata/import", "platform/operator"})  # neither dropped
        self.assertEqual(active["masterdata/import"]["checkpoint_status"], "invalid")
        self.assertIsNone(active["masterdata/import"]["stage"])                    # no crash, no magic stage
        self.assertEqual(active["platform/operator"]["checkpoint_status"], "valid")
        self.assertEqual(active["platform/operator"]["stage"], "build")

    def test_discover_flags_unparseable_checkpoint(self):
        # A checkpoint file that exists but isn't valid JSON is 'invalid' (regenerate me),
        # not silently 'absent'.
        self._emit_and_apply_all()
        with open(rh._checkpoint_path(self.relay, "masterdata/import"), "w") as fh:
            fh.write("{not json")
        a = {x["work_item"]: x for x in rh.discover_active(self.repo, self.relay)}["masterdata/import"]
        self.assertTrue(a["has_checkpoint"])                 # a file is present
        self.assertEqual(a["checkpoint_status"], "invalid")  # ...just unreadable
        self.assertIsNone(a["stage"])

    def test_validate_bootstrap_more_violations(self):
        self._emit_and_apply_all()
        bs = rh.worker_bootstrap(self.repo, self.relay, "masterdata/import")
        b1 = dict(bs); b1["worktree_path"] = "/no/such/dir"
        self.assertTrue(rh.validate_bootstrap(self.repo, b1))        # resolved but missing
        b2 = dict(bs); b2["project_instructions"] = ["definitely-not-a-file.md"]
        self.assertTrue(rh.validate_bootstrap(self.repo, b2))        # unresolved instruction
        b3 = dict(bs); b3.update(worktree_status="absent", worktree_fallback=None, worktree_path=None)
        self.assertTrue(rh.validate_bootstrap(self.repo, b3))        # absent without fallback

    def test_dotdot_work_item_rejected(self):
        for bad in ("..", "."):
            with self.assertRaises(rh.HarvestError):
                rh.emit_result(self.relay, make_result(bad, "b", "lap-d", "0" * 40))

    def test_discovery_newline_cannot_forge_board_row(self):
        slug, (branch, path) = "masterdata/import", self.wt["masterdata/import"]
        head = git(["rev-parse", "HEAD"], path)
        # a discovery whose title smuggles a whole active board row via a newline
        evil = [{"id": "e1", "title": "x |\n| `evil/injected` | ⚙ in-progress | — | h.md",
                 "one_line": "pwn"}]
        rh.emit_result(self.relay, make_result(slug, branch, "lap-e", head, discoveries=evil))
        board = os.path.join(self.relay, "board.md")
        rh.apply_pending(self.relay, slug=slug, board_path=board)
        active = dict(rh._parse_board_active(board))
        self.assertNotIn("evil/injected", active)   # newline stripped -> no forged active row

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


class CheckpointDurabilityTest(unittest.TestCase):
    """Slice 3 — checkpoint git-durability: the checkpoint is committed to the durable branch and
    pushed, so a pruned/foreign-machine worktree (or another device) still resumes. Local commit is
    the offline-safe floor; the push is best-effort. Built on a REAL repo with a REAL bare origin."""

    def setUp(self):
        self.parent = tempfile.mkdtemp()
        self.origin = os.path.join(self.parent, "origin.git")
        git(["init", "-q", "--bare", "-b", "main", self.origin], self.parent)
        self.repo = os.path.join(self.parent, "repo")
        os.makedirs(self.repo)
        git(["init", "-q", "-b", "main"], self.repo)
        git(["config", "user.email", "t@t"], self.repo); git(["config", "user.name", "t"], self.repo)
        git(["remote", "add", "origin", self.origin], self.repo)
        self.relay = os.path.join(self.repo, "relay")
        os.makedirs(os.path.join(self.relay, "handover"))
        with open(os.path.join(self.relay, "board.md"), "w") as fh:
            fh.write(BOARD)
        git(["add", "-A"], self.repo); git(["commit", "-q", "-m", "init"], self.repo)
        git(["push", "-q", "-u", "origin", "main"], self.repo)
        git(["remote", "set-head", "origin", "main"], self.repo)  # so refs/remotes/origin/HEAD resolves
        self.board = os.path.join(self.relay, "board.md")

    def tearDown(self):
        shutil.rmtree(self.parent, ignore_errors=True)

    def _topic_wip(self, slug, branch):
        """A topic worktree with an uncommitted-then-committed slice of work; return its head sha."""
        path = os.path.join(self.parent, "wt-" + branch)
        git(["worktree", "add", "-q", path, "-b", branch], self.repo)
        with open(os.path.join(path, "work.txt"), "w") as fh:
            fh.write("slice work")
        git(["add", "-A"], path); git(["commit", "-q", "-m", "wip"], path)
        return path, git(["rev-parse", "HEAD"], path)

    def _apply(self, slug, branch, lap, head, **kw):
        rh.emit_result(self.relay, make_result(slug, branch, lap, head))
        return rh.apply_pending(self.relay, slug=slug, board_path=self.board,
                                repo_root=self.repo, **kw)

    def _cp_rel(self, slug):
        return os.path.relpath(rh._checkpoint_path(self.relay, slug), self.repo)

    def test_checkpoint_recoverable_from_git_after_worktree_gone(self):
        # Acceptance: after a lap, the checkpoint is recoverable from git without the original worktree.
        slug, branch = "masterdata/import", "topic-md"
        path, head = self._topic_wip(slug, branch)
        summary = self._apply(slug, branch, "lap-1", head)
        rep = summary["replication"][0]
        self.assertTrue(rep["committed"])
        # committed to the durable branch with a marked message
        self.assertIn("Relay-Checkpoint: lap-1", git(["log", "-1", "--format=%B", "main"], self.repo))
        # now the topic worktree/branch is gone — the checkpoint must still be recoverable from git
        git(["worktree", "remove", "--force", path], self.repo)
        git(["branch", "-D", branch], self.repo)
        # even after wiping the working copy, git holds the checkpoint on main
        os.remove(rh._checkpoint_path(self.relay, slug))
        recovered = git(["show", f"main:{self._cp_rel(slug)}"], self.repo)
        self.assertEqual(json.loads(recovered)["work_item"], slug)

    def test_checkpoint_pushed_and_resumable_from_fresh_clone(self):
        # The cross-device proof: a fresh clone of origin (a different machine / a phone) carries the
        # checkpoint in its working tree, with no access to the original worktree or disk.
        slug, branch = "masterdata/import", "topic-md"
        _, head = self._topic_wip(slug, branch)
        summary = self._apply(slug, branch, "lap-1", head)
        self.assertTrue(summary["replication"][0]["replicated"])   # push landed
        clone = os.path.join(self.parent, "phone")
        git(["clone", "-q", self.origin, clone], self.parent)
        cp = json.load(open(os.path.join(clone, self._cp_rel(slug))))
        self.assertEqual(cp["work_item"], slug)
        self.assertEqual(cp["resume_delta"]["next_slice"], f"finish {slug} slice 2")

    def test_replication_offline_is_non_fatal(self):
        # No reachable remote: the local commit still lands (the floor), replicated is False with a
        # reason, and the apply itself does NOT fail — state is written regardless.
        slug, branch = "masterdata/import", "topic-md"
        _, head = self._topic_wip(slug, branch)
        git(["remote", "set-url", "origin", os.path.join(self.parent, "does-not-exist.git")], self.repo)
        summary = self._apply(slug, branch, "lap-1", head)
        rep = summary["replication"][0]
        self.assertTrue(rep["committed"])            # local floor holds
        self.assertFalse(rep["replicated"])          # push failed
        self.assertTrue(rep["reason"])               # ...with a reason
        self.assertEqual(summary["applied"], 1)      # apply succeeded anyway
        self.assertTrue(json.load(open(rh._applied_path(self.relay, slug)))["applied"])

    def test_replication_refuses_topic_branch(self):
        # Guard against the case-B trap: never commit the checkpoint onto a non-durable branch (it
        # would vanish on merge and be invisible to a fresh clone's working tree).
        slug, branch = "masterdata/import", "topic-md"
        _, head = self._topic_wip(slug, branch)
        git(["checkout", "-q", "-b", "some-feature"], self.repo)   # main checkout now off the durable branch
        summary = self._apply(slug, branch, "lap-1", head)
        rep = summary["replication"][0]
        self.assertFalse(rep["committed"])
        self.assertFalse(rep["replicated"])
        self.assertEqual(rep["current_branch"], "some-feature")    # structured, not a prose substring
        self.assertIn(f"'{rh._durable_branch(self.repo)}'", rep["reason"])  # names the durable branch
        self.assertEqual(git(["rev-list", "--count", "some-feature"], self.repo), "1")  # no checkpoint commit

    def test_reapply_makes_no_second_checkpoint_commit(self):
        # Idempotent: replaying an already-applied lap adds no new commit on the durable branch.
        slug, branch = "masterdata/import", "topic-md"
        _, head = self._topic_wip(slug, branch)
        self._apply(slug, branch, "lap-1", head)
        before = git(["rev-list", "--count", "main"], self.repo)
        again = rh.apply_pending(self.relay, slug=slug, board_path=self.board, repo_root=self.repo)
        self.assertEqual(again["applied"], 0)                      # nothing re-applied
        self.assertEqual(git(["rev-list", "--count", "main"], self.repo), before)  # no new commit

    def test_no_replicate_flag_writes_state_only(self):
        # replicate=False (the --no-replicate escape hatch): state is written, git is untouched.
        slug, branch = "masterdata/import", "topic-md"
        _, head = self._topic_wip(slug, branch)
        before = git(["rev-list", "--count", "main"], self.repo)
        summary = self._apply(slug, branch, "lap-1", head, replicate=False)
        self.assertEqual(summary["applied"], 1)
        self.assertNotIn("replication", summary)
        self.assertEqual(git(["rev-list", "--count", "main"], self.repo), before)  # no commit
        self.assertTrue(os.path.exists(rh._checkpoint_path(self.relay, slug)))     # ...but state exists

    def test_discover_reports_replicated(self):
        # discover_active tells the maintainer which threads are safe to pick up elsewhere.
        slug, branch = "masterdata/import", "topic-md"
        _, head = self._topic_wip(slug, branch)
        self._apply(slug, branch, "lap-1", head)
        a = {x["work_item"]: x for x in rh.discover_active(self.repo, self.relay)}
        self.assertTrue(a["masterdata/import"]["replicated"])      # pushed -> resumable elsewhere
        # an item with a checkpoint that was NOT pushed (untracked file) reads as not-replicated.
        # `git diff --cached` ignores untracked files, so a diff-based check would false-positive here;
        # the blob-hash compare in _checkpoint_on_remote correctly returns False.
        rh.emit_result(self.relay, make_result("platform/operator", "topic-op", "lap-2", head))
        rh.apply_pending(self.relay, slug="platform/operator", board_path=self.board)  # no repo_root -> no push
        a = {x["work_item"]: x for x in rh.discover_active(self.repo, self.relay)}
        self.assertFalse(a["platform/operator"]["replicated"])

    def test_checkpoint_commit_excludes_foreign_staged_files(self):
        # The isolation guarantee behind the scoped commit: apply runs in the SHARED main checkout,
        # so a sibling session's unrelated staged file must NOT be swept into (and pushed with) the
        # checkpoint commit, nor unstaged from under them.
        slug, branch = "masterdata/import", "topic-md"
        _, head = self._topic_wip(slug, branch)
        open(os.path.join(self.repo, "SECRET.txt"), "w").write("do-not-commit")
        git(["add", "SECRET.txt"], self.repo)                       # a foreign change "another session" staged
        self._apply(slug, branch, "lap-1", head)
        touched = git(["show", "--name-only", "--format=", "main"], self.repo).split()
        self.assertNotIn("SECRET.txt", touched)                    # not swept into the checkpoint commit
        self.assertTrue(any(f.startswith("relay/harvest/") for f in touched))  # our files were
        self.assertIn("SECRET.txt", git(["diff", "--cached", "--name-only"], self.repo).split())  # still staged, untouched

    def test_durable_branch_falls_back_to_main_without_origin_head(self):
        # A repo with a remote but no `git remote set-head` (origin/HEAD unresolvable) — the
        # fallback path _durable_branch takes when symbolic-ref fails. Every other test sets the
        # head, so this is the only coverage of the 'main' literal fallback.
        repo = os.path.join(self.parent, "nohead")
        git(["init", "-q", "-b", "main", repo], self.parent)
        git(["config", "user.email", "t@t"], repo); git(["config", "user.name", "t"], repo)
        bare = os.path.join(self.parent, "nohead-origin.git"); git(["init", "-q", "--bare", "-b", "main", bare], self.parent)
        git(["remote", "add", "origin", bare], repo)
        open(os.path.join(repo, "f.txt"), "w").write("x"); git(["add", "-A"], repo); git(["commit", "-qm", "init"], repo)
        git(["push", "-q", "-u", "origin", "main"], repo)   # origin/main exists, but NO set-head
        # origin/HEAD is genuinely unresolvable here — the precondition for the fallback path
        self.assertNotEqual(subprocess.run(["git", "symbolic-ref", "refs/remotes/origin/HEAD"],
                                           cwd=repo, capture_output=True).returncode, 0)
        self.assertEqual(rh._durable_branch(repo), "main")  # fallback holds

    def test_replicated_is_none_when_remote_ref_absent(self):
        # None (not False): the durable remote branch isn't fetched locally, so replication state is
        # undeterminable. A caller checking truthiness alone wouldn't catch a None->False collapse.
        slug, branch = "masterdata/import", "topic-md"
        _, head = self._topic_wip(slug, branch)
        self._apply(slug, branch, "lap-1", head)
        git(["update-ref", "-d", "refs/remotes/origin/main"], self.repo)  # drop the tracking ref
        self.assertIsNone(rh._checkpoint_on_remote(self.repo, self.relay, slug))
        a = {x["work_item"]: x for x in rh.discover_active(self.repo, self.relay)}
        self.assertIsNone(a["masterdata/import"]["replicated"])   # None, not False

    def test_replicated_false_after_local_drift(self):
        # The reason _checkpoint_on_remote compares blob hashes, not existence: a checkpoint edited on
        # disk after the push (no new commit) must flip to False, not stay True.
        slug, branch = "masterdata/import", "topic-md"
        _, head = self._topic_wip(slug, branch)
        self._apply(slug, branch, "lap-1", head)
        self.assertTrue(rh._checkpoint_on_remote(self.repo, self.relay, slug))
        cpp = rh._checkpoint_path(self.relay, slug)
        cp = json.load(open(cpp)); cp["resume_delta"]["next_slice"] = "drifted locally"
        with open(cpp, "w") as fh:
            json.dump(cp, fh)
        self.assertFalse(rh._checkpoint_on_remote(self.repo, self.relay, slug))   # content changed -> not replicated
        a = {x["work_item"]: x for x in rh.discover_active(self.repo, self.relay)}
        self.assertFalse(a["masterdata/import"]["replicated"])

    def test_multi_item_apply_replicates_each(self):
        # slug=None applies every pending item; each must get its OWN replication entry + commit.
        _, head = self._topic_wip("masterdata/import", "topic-md")
        rh.emit_result(self.relay, make_result("masterdata/import", "topic-md", "lap-a", head))
        rh.emit_result(self.relay, make_result("platform/operator", "topic-op", "lap-b", head))
        before = int(git(["rev-list", "--count", "main"], self.repo))
        summary = rh.apply_pending(self.relay, board_path=self.board, repo_root=self.repo)  # slug=None
        self.assertEqual(summary["applied"], 2)
        self.assertEqual(len(summary["replication"]), 2)
        self.assertTrue(all(r["committed"] and r["replicated"] for r in summary["replication"]))
        self.assertEqual(int(git(["rev-list", "--count", "main"], self.repo)), before + 2)  # two commits

    def test_reconcile_pushes_applied_but_undurable_checkpoint(self):
        # The crash-between-marker-and-commit case: a checkpoint applied locally but never committed
        # (lap already in applied.json, so a per-lap push would never retry). A later apply must
        # reconcile it to the remote, not leave it local-only forever.
        slug, branch = "masterdata/import", "topic-md"
        _, head = self._topic_wip(slug, branch)
        rh.emit_result(self.relay, make_result(slug, branch, "lap-1", head))
        rh.apply_pending(self.relay, slug=slug, board_path=self.board)  # NO replicate -> applied, not durable
        self.assertFalse(rh._checkpoint_on_remote(self.repo, self.relay, slug))  # applied, but not on remote
        summary = rh.apply_pending(self.relay, slug=slug, board_path=self.board, repo_root=self.repo)
        self.assertEqual(summary["applied"], 0)                    # nothing new to apply...
        self.assertTrue(summary["replication"][0]["committed"])    # ...but the stranded checkpoint is reconciled
        self.assertTrue(rh._checkpoint_on_remote(self.repo, self.relay, slug))   # now durable on the remote


if __name__ == "__main__":
    unittest.main(verbosity=2)
