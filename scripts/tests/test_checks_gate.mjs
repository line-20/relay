// Tests for plugins/relay/bin/relay-checks-gate.mjs — the verdict /ship reads before queueing or merging.
// Self-contained, no deps (node:test + node:assert). Run: node scripts/tests/test_checks_gate.mjs
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { classify, firstFailureLine } from '../../plugins/relay/bin/relay-checks-gate.mjs';

const run = (name, conclusion, extra = {}) => ({ id: 1, name, status: 'completed', conclusion, app: 'github-actions', ...extra });
const mergify = { id: 9, name: 'Merge Queue', status: 'completed', conclusion: 'neutral', app: 'mergify' };

test('PR #2397 shape: a required guard failed on the head → red, even with others green', () => {
  const r = classify({ checkRuns: [run('Decide scope', 'success'), run('Repo guards', 'failure'), run('Typecheck', 'success'), mergify] });
  assert.equal(r.verdict, 'red');
  assert.deepEqual(r.red.map(c => c.name), ['Repo guards']);
});

test('red wins over pending: a failure is reported without waiting for the rest', () => {
  const r = classify({ checkRuns: [run('Repo guards', 'failure'), { ...run('Tests', null), status: 'in_progress' }] });
  assert.equal(r.verdict, 'red');
});

test('early scope job: only "Decide scope" exists and passed, but its workflow run is still going → pending', () => {
  const r = classify({ checkRuns: [run('Decide scope', 'success')], runs: [{ name: 'test', status: 'in_progress', conclusion: null }] });
  assert.equal(r.verdict, 'pending');
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

test('cancelled and timed_out count as red (not green)', () => {
  assert.equal(classify({ checkRuns: [run('Tests', 'cancelled')] }).verdict, 'red');
  assert.equal(classify({ checkRuns: [run('Tests', 'timed_out')] }).verdict, 'red');
});

test('legacy commit statuses count: error is red, pending is pending', () => {
  assert.equal(classify({ statuses: [{ context: 'ci/legacy', state: 'error' }] }).verdict, 'red');
  assert.equal(classify({ statuses: [{ context: 'ci/legacy', state: 'pending' }] }).verdict, 'pending');
  assert.equal(classify({ statuses: [{ context: 'Mergify', state: 'pending' }] }).verdict, 'none');
});

test('firstFailureLine picks the assertion, not the exit-code boilerplate', () => {
  const log = [
    'Repo guards\tRun guards\t2026-11-16T10:09:10.1234567Z > node scripts/example-ibans.test.mjs',
    'Repo guards\tRun guards\t2026-11-16T10:09:12.1234567Z AssertionError [ERR_ASSERTION]: off-list example IBAN BE68 5390 0754 7034 in apps/admin/foo.ts',
    'Repo guards\tRun guards\t2026-11-16T10:09:13.1234567Z ##[error]Process completed with exit code 1.',
  ].join('\n');
  assert.match(firstFailureLine(log), /^AssertionError \[ERR_ASSERTION\]: off-list example IBAN/);
});

test('firstFailureLine ignores passing test names that mention failure, and colour codes', () => {
  const log = [
    'Tests\tTest\t\uFEFF2026-11-16T10:09:12Z packages/module-ui test:      \x1b[32m✓\x1b[39m saves nothing when every write failed  321ms',
    'Tests\tTest\t2026-11-16T10:09:13Z packages/core test: [billing] mint failed: AccessDeniedError: nope',
    'Tests\tTest\t2026-11-16T10:09:14Z  FAIL  src/money.test.ts > rounds half-even',
    'Tests\tTest\t2026-11-16T10:09:15Z ##[error]Process completed with exit code 1.',
  ].join('\n');
  assert.equal(firstFailureLine(log), 'FAIL  src/money.test.ts > rounds half-even');
});

test('firstFailureLine catches a TypeScript error', () => {
  assert.match(firstFailureLine('Typecheck\ttsc\t2026-11-16T10:00:00Z src/a.ts(3,7): error TS2322: Type number is not string'), /error TS2322/);
});

test('firstFailureLine falls back to an ##[error] line, then null', () => {
  assert.equal(firstFailureLine('j\ts\t2026-11-16T10:00:00Z ##[error]Something broke'), 'Something broke');
  assert.equal(firstFailureLine('j\ts\t2026-11-16T10:00:00Z all fine'), null);
});
