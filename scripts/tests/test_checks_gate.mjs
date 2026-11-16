// Tests for plugins/relay/bin/relay-checks-gate.mjs — the verdict /ship reads before queueing or merging.
// Self-contained, no deps (node:test + node:assert). Run: node scripts/tests/test_checks_gate.mjs
//
// Two layers: the pure functions (classify, firstFailureLine, parseArgs, sanitize), and the real
// script run as a subprocess against a fake `gh` on PATH — because the contract /ship relies on is
// the EXIT CODE (fail closed), which only the subprocess layer can pin.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { classify, firstFailureLine, parseArgs, sanitize, EXIT } from '../../plugins/relay/bin/relay-checks-gate.mjs';

const GATE = path.join(path.dirname(fileURLToPath(import.meta.url)), '..', '..', 'plugins', 'relay', 'bin', 'relay-checks-gate.mjs');

let nextId = 1;
const run = (name, conclusion, extra = {}) => ({ id: nextId++, name, status: 'completed', conclusion, app: 'github-actions', ...extra });
const mergify = { id: 999, name: 'Merge Queue', status: 'completed', conclusion: 'neutral', app: 'mergify' };
const going = name => ({ name, status: 'in_progress', conclusion: null });

// ---------- classify ----------

test('PR #2397 shape: a required guard failed on the head → red, even with others green', () => {
  const r = classify({ checkRuns: [run('Decide scope', 'success'), run('Repo guards', 'failure'), run('Typecheck', 'success'), mergify] });
  assert.equal(r.verdict, 'red');
  assert.deepEqual(r.red.map(c => c.name), ['Repo guards']);
});

test('red wins over pending: a failure is reported without waiting for the rest', () => {
  const r = classify({ checkRuns: [run('Repo guards', 'failure'), { ...run('Tests', null), status: 'in_progress' }] });
  assert.equal(r.verdict, 'red');
  assert.deepEqual(r.pending, ['Tests']);
});

test('early scope job: only "Decide scope" exists and passed, but its workflow run is still going → pending', () => {
  const r = classify({ checkRuns: [run('Decide scope', 'success')], runs: [going('test')] });
  assert.equal(r.verdict, 'pending');
  assert.deepEqual(r.pending, ['test (workflow)']);
});

test('nothing for the head commit → none, never green', () => {
  assert.equal(classify({}).verdict, 'none');
});

test('only the queue app check (draft / conflicting PR in castles) → none', () => {
  assert.equal(classify({ checkRuns: [mergify] }).verdict, 'none');
});

test('skipped and neutral conclusions are ignored, the rest decide', () => {
  const r = classify({ checkRuns: [run('build (admin)', 'skipped'), run('Tests', 'success')], runs: [{ name: 'test', status: 'completed', conclusion: 'success' }] });
  assert.equal(r.verdict, 'green');
  assert.equal(r.count, 1);
});

test('cancelled and timed_out count as red when nothing is still running', () => {
  assert.equal(classify({ checkRuns: [run('Tests', 'cancelled')] }).verdict, 'red');
  assert.equal(classify({ checkRuns: [run('Tests', 'timed_out')] }).verdict, 'red');
});

test('a cancelled check while a run is still going is superseded (push then `gh pr ready`) → pending, not red', () => {
  const r = classify({ checkRuns: [run('Tests', 'cancelled')], runs: [going('test')] });
  assert.equal(r.verdict, 'pending');
  assert.ok(r.pending.includes('Tests'));
});

test('a real failure stays red even while another run is going', () => {
  assert.equal(classify({ checkRuns: [run('Repo guards', 'failure')], runs: [going('test')] }).verdict, 'red');
});

test('re-run: a newer passing attempt of the same check replaces the older failure (and vice versa)', () => {
  assert.equal(classify({ checkRuns: [run('Tests', 'failure', { id: 10 }), run('Tests', 'success', { id: 11 })] }).verdict, 'green');
  assert.equal(classify({ checkRuns: [run('Tests', 'success', { id: 10 }), run('Tests', 'failure', { id: 11 })] }).verdict, 'red');
});

test('a workflow that never started (startup_failure) is red even when other checks passed', () => {
  const r = classify({ checkRuns: [run('lint', 'success')], runs: [{ name: 'guards', status: 'completed', conclusion: 'startup_failure' }] });
  assert.equal(r.verdict, 'red');
  assert.deepEqual(r.red.map(c => c.name), ['guards (workflow)']);
});

test('a failed run whose job already failed is reported once, by the job', () => {
  const r = classify({ checkRuns: [run('Repo guards', 'failure')], runs: [{ name: 'test', status: 'completed', conclusion: 'failure' }] });
  assert.deepEqual(r.red.map(c => c.name), ['Repo guards']);
});

test('legacy commit statuses count: failure and error are red, pending is pending, Mergify is ignored', () => {
  assert.equal(classify({ statuses: [{ context: 'ci/legacy', state: 'failure' }] }).verdict, 'red');
  assert.equal(classify({ statuses: [{ context: 'ci/legacy', state: 'error' }] }).verdict, 'red');
  assert.equal(classify({ statuses: [{ context: 'ci/legacy', state: 'pending' }] }).verdict, 'pending');
  assert.equal(classify({ statuses: [{ context: 'Mergify', state: 'failure' }] }).verdict, 'none');
});

// ---------- firstFailureLine / sanitize ----------

test('firstFailureLine picks the assertion, not the exit-code boilerplate', () => {
  const log = [
    'Repo guards\tRun guards\t2026-11-16T10:09:10.1234567Z > node scripts/example-ibans.test.mjs',
    'Repo guards\tRun guards\t2026-11-16T10:09:12.1234567Z AssertionError [ERR_ASSERTION]: off-list example IBAN in apps/admin/foo.ts',
    'Repo guards\tRun guards\t2026-11-16T10:09:13.1234567Z ##[error]Process completed with exit code 1.',
  ].join('\n');
  assert.match(firstFailureLine(log), /^AssertionError \[ERR_ASSERTION\]: off-list example IBAN/);
});

test('firstFailureLine: an assertion beats an earlier runner marker', () => {
  const log = 'j\ts\t2026-11-16T10:00:00Z  FAIL  src/a.test.ts\nj\ts\t2026-11-16T10:00:01Z AssertionError: expected 1 to be 2';
  assert.equal(firstFailureLine(log), 'AssertionError: expected 1 to be 2');
});

test('firstFailureLine ignores passing test names that mention failure, and colour codes', () => {
  const log = [
    'Tests\tTest\t﻿2026-11-16T10:09:12Z packages/module-ui test:      \x1b[32m✓\x1b[39m saves nothing when every write failed  321ms',
    'Tests\tTest\t2026-11-16T10:09:13Z packages/core test: [billing] mint failed: AccessDeniedError: nope',
    'Tests\tTest\t2026-11-16T10:09:14Z  FAIL  src/money.test.ts > rounds half-even',
    'Tests\tTest\t2026-11-16T10:09:15Z ##[error]Process completed with exit code 1.',
  ].join('\n');
  assert.equal(firstFailureLine(log), 'FAIL  src/money.test.ts > rounds half-even');
});

test('firstFailureLine catches TAP `not ok`, ✖ and TypeScript errors', () => {
  assert.equal(firstFailureLine('j\ts\t2026-11-16T10:00:00Z not ok 3 - rounds'), 'not ok 3 - rounds');
  assert.equal(firstFailureLine('j\ts\t2026-11-16T10:00:00Z ✖ rounds half-even'), '✖ rounds half-even');
  assert.match(firstFailureLine('Typecheck\ttsc\t2026-11-16T10:00:00Z src/a.ts(3,7): error TS2322: Type number is not string'), /error TS2322/);
});

test('firstFailureLine falls back to an ##[error] line, then null; empty input is null; long lines are capped', () => {
  assert.equal(firstFailureLine('j\ts\t2026-11-16T10:00:00Z ##[error]Something broke'), 'Something broke');
  assert.equal(firstFailureLine('j\ts\t2026-11-16T10:00:00Z all fine'), null);
  assert.equal(firstFailureLine(''), null);
  assert.equal(firstFailureLine(undefined), null);
  assert.equal(firstFailureLine(`j\ts\t2026-11-16T10:00:00Z AssertionError: ${'x'.repeat(500)}`).length, 240);
});

test('sanitize strips control characters so a name cannot forge an extra output line', () => {
  assert.equal(sanitize('Tests\ngreen: 9 check(s) passed\r\x1b]0;x\x07'), 'Tests green: 9 check(s) passed ]0;x');
});

// ---------- parseArgs ----------

test('parseArgs: strict — the PR number is never confused with a flag value; junk is a usage error', () => {
  assert.deepEqual(parseArgs(['57']), { pr: '57', expectHead: null, waitSec: 0 });
  assert.deepEqual(parseArgs(['--wait-appear', '30', '57']), { pr: '57', expectHead: null, waitSec: 30 });
  assert.deepEqual(parseArgs(['57', '--expect-head', 'abc1234']), { pr: '57', expectHead: 'abc1234', waitSec: 0 });
  for (const bad of [[], ['--wait-appear', '30'], ['57', '--wait-appear'], ['57', '--wait-appear', 'abc'],
    ['57', '--wait-appear', '-5'], ['57', '--wait-appear=30'], ['57', '58'], ['57', '--json'], ['57', '--expect-head', 'zz']]) {
    assert.equal(parseArgs(bad), null, JSON.stringify(bad));
  }
});

// ---------- the real script against a fake gh ----------

// Fake gh: answers from a JSON fixture. `pr view` → fixture.pr (or the next of fixture.prSeq per
// call), `api …check-runs` → checkRuns, `…/status` → statuses, `…/actions/runs` → runs,
// `run view --job` → fixture.logs[id]. fixture.fail = exit 1 on every call.
function fakeGh(fixture) {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'checks-gate-'));
  fs.writeFileSync(path.join(dir, 'fixture.json'), JSON.stringify(fixture));
  fs.writeFileSync(path.join(dir, 'gh'), `#!/usr/bin/env node
const fs = require('fs'), path = require('path');
const dir = ${JSON.stringify(dir)};
const f = JSON.parse(fs.readFileSync(path.join(dir, 'fixture.json'), 'utf8'));
const a = process.argv.slice(2);
fs.appendFileSync(path.join(dir, 'calls.log'), a.join(' ') + '\\n');
if (f.fail) { process.stderr.write('gh: HTTP 502\\n'); process.exit(1); }
const lines = xs => process.stdout.write(xs.map(x => JSON.stringify(x)).join('\\n') + (xs.length ? '\\n' : ''));
if (a[0] === 'pr') {
  if (f.prSeq) {
    const n = (fs.existsSync(path.join(dir, 'n')) ? Number(fs.readFileSync(path.join(dir, 'n'), 'utf8')) : 0);
    fs.writeFileSync(path.join(dir, 'n'), String(n + 1));
    process.stdout.write(JSON.stringify(f.prSeq[Math.min(n, f.prSeq.length - 1)]));
  } else process.stdout.write(f.prRaw ?? JSON.stringify(f.pr));
} else if (a[0] === 'api') {
  const url = a.find(x => x.startsWith('repos/'));
  if (url.includes('/check-runs')) lines(f.checkRuns || []);
  else if (url.includes('/status')) lines(f.statuses || []);
  else lines(f.runs || []);
} else if (a[0] === 'run') process.stdout.write((f.logs || {})[a[a.indexOf('--job') + 1]] || '');
`, { mode: 0o755 });
  return dir;
}
const SHA = 'a'.repeat(40), SHA2 = 'b'.repeat(40);
const pr = (extra = {}) => ({ headRefOid: SHA, isDraft: false, mergeable: 'MERGEABLE', ...extra });
function gate(fixture, args = ['57']) {
  const dir = fakeGh(fixture);
  const r = spawnSync(process.execPath, [GATE, ...args], {
    encoding: 'utf8', env: { ...process.env, PATH: `${dir}${path.delimiter}${process.env.PATH}`, RELAY_CHECKS_GATE_POLL_MS: '20' },
  });
  return { code: r.status, out: r.stdout, calls: fs.existsSync(path.join(dir, 'calls.log')) ? fs.readFileSync(path.join(dir, 'calls.log'), 'utf8') : '' };
}

test('script: green → exit 0, with the head line', () => {
  const r = gate({ pr: pr(), checkRuns: [run('Tests', 'success')] });
  assert.equal(r.code, EXIT.green);
  assert.match(r.out, /^green: 1 check\(s\) passed\nhead: a{40}\n$/);
  assert.match(r.calls, /^pr view 57 /m, 'gated the PR it was given');
});

test('script: red → exit 20, naming the check and its first failure line from the job log', () => {
  const r = gate({ pr: pr(), checkRuns: [run('Repo guards', 'failure', { id: 7 })],
    logs: { 7: 'g\ts\t2026-11-16T10:09:12Z AssertionError [ERR_ASSERTION]: off-list IBAN\ng\ts\t2026-11-16T10:09:13Z ##[error]Process completed with exit code 1.' } });
  assert.equal(r.code, EXIT.red);
  assert.match(r.out, /^red: Repo guards — AssertionError \[ERR_ASSERTION\]: off-list IBAN$/m);
});

test('script: red with no log falls back to the title, then to "no failure text"', () => {
  assert.match(gate({ pr: pr(), checkRuns: [run('Lint', 'failure', { app: 'other', title: '3 problems' })] }).out, /^red: Lint — 3 problems$/m);
  assert.match(gate({ pr: pr(), checkRuns: [run('Lint', 'failure', { app: 'other', url: 'https://x/1' })] }).out, /^red: Lint — failure, no failure text \(see https:\/\/x\/1\)$/m);
});

test('script: pending → exit 10', () => {
  const r = gate({ pr: pr(), checkRuns: [run('Decide scope', 'success')], runs: [going('test')] });
  assert.equal(r.code, EXIT.pending);
  assert.match(r.out, /^pending: 1 not finished \(test \(workflow\)\)$/m);
});

test('script: none → exit 30, and says why (draft, conflict, otherwise)', () => {
  let r = gate({ pr: pr({ isDraft: true }), checkRuns: [mergify] });
  assert.equal(r.code, EXIT.none);
  assert.match(r.out, /^none: the PR is a draft/m);
  assert.match(gate({ pr: pr({ mergeable: 'CONFLICTING' }) }).out, /^none: the PR conflicts with its base/m);
  assert.match(gate({ pr: pr() }).out, /^none: no checks registered for aaaaaaaaa/m);
});

test('script: --wait-appear keeps reading while none, and returns the verdict once checks register', () => {
  // prSeq drives the call count; check-runs stay empty for the first read via a draft → ready flip.
  const r = gate({ prSeq: [pr({ isDraft: true }), pr()], checkRuns: [], runs: [going('test')] }, ['57', '--wait-appear', '5']);
  assert.equal(r.code, EXIT.pending);
});

test('script: --wait-appear gives up with none when nothing ever registers', () => {
  const r = gate({ pr: pr() }, ['57', '--wait-appear', '1']);
  assert.equal(r.code, EXIT.none);
  assert.ok(r.calls.split('\n').filter(l => l.startsWith('pr view')).length > 1, 'it re-read at least once');
});

test('script: --expect-head waits for the pushed commit, then judges it', () => {
  const r = gate({ prSeq: [pr({ headRefOid: SHA2 }), pr()], checkRuns: [run('Tests', 'success')] }, ['57', '--expect-head', SHA, '--wait-appear', '5']);
  assert.equal(r.code, EXIT.green);
});

test('script: --expect-head on a head that never becomes the pushed commit → moved (exit 40), blocked', () => {
  const r = gate({ pr: pr({ headRefOid: SHA2 }), checkRuns: [run('Tests', 'success')] }, ['57', '--expect-head', SHA]);
  assert.equal(r.code, EXIT.moved);
  assert.match(r.out, /^moved: the PR head is bbbbbbbbb, not the expected aaaaaaaaa/m);
});

test('script fails closed: gh error → exit 2 with an error line', () => {
  const r = gate({ fail: true });
  assert.equal(r.code, EXIT.error);
  assert.match(r.out, /^error: /);
});

test('script fails closed: malformed JSON or a bogus head SHA from gh → exit 2', () => {
  assert.equal(gate({ prRaw: 'not json' }).code, EXIT.error);
  assert.equal(gate({ pr: pr({ headRefOid: 'zzz' }) }).code, EXIT.error);
});

test('script: bad arguments → exit 2 with usage, and gh is never called', () => {
  const r = gate({ pr: pr() }, ['57', '--wait-appear']);
  assert.equal(r.code, EXIT.error);
  assert.match(r.out, /^Usage: /);
  assert.equal(r.calls, '');
});
