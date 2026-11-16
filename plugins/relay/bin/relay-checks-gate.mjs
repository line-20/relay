#!/usr/bin/env node
// relay-checks-gate.mjs — what do the PR's checks say about its CURRENT head commit?
//
// WHY THIS EXISTS. /ship's merge-queue hand-off already said "no check has failed → STOP", yet on
// castles-erp PR #2397 (2026-11-16) it queued a PR whose required "Repo guards" check had been red
// on that same head for 12 minutes; Mergify dequeued it two minutes later. A rule the model is
// asked to remember gets skipped. Like hooks.affects and hooks.claims, this is a DETERMINISTIC
// predicate: /ship reads the verdict from stdout + exit status and never judges the checks itself.
//
// VERDICTS (first stdout line, plus exit code):
//   green    (0)   every counted check on the head commit finished and passed
//   pending  (10)  something on the head commit is still queued/running (or not registered yet)
//   red      (20)  at least one check on the head commit failed — one `red:` line per check,
//                  each with the first failure line from its log
//   none     (30)  no checks at all for the head commit — blocked, never green (draft, or a PR
//                  that conflicts with its base, raises no pull_request run)
//   error    (2)   gh failed / bad args — callers treat it as blocked (fail closed)
//
// TRAPS IT HANDLES (seen for real in castles-erp):
//   • Stale greens. The PR-level rollup and plain `gh pr checks` keep listing the PREVIOUS
//     commit's results right after a push. So this reads the head SHA from the PR and asks the
//     commit's own check-runs/statuses/workflow-runs — nothing from another commit can count.
//   • The early scope job. Right after a push only a fast "Decide scope" job may exist; the real
//     jobs are created when it finishes (`gh pr checks --watch` exits early here). Its WORKFLOW
//     RUN is still in progress, so any unfinished workflow run on the head SHA reads `pending`.
//   • The queue's own check. Mergify's "Merge Queue" check (skipping/neutral) is not a CI result:
//     check-runs from the mergify app, and any skipped/neutral conclusion, are ignored.
//
// Usage (installed): relay-checks-gate.mjs <pr> [--wait-appear <seconds>] [--json]
//        (from source): node plugins/relay/bin/relay-checks-gate.mjs <pr> [...]
//   --wait-appear N  if the verdict is `none`, re-read every 15 s for up to N seconds before giving
//                    up (checks take a moment to register after a push or `gh pr ready`).
// Run it inside the repo (gh resolves {owner}/{repo} from the checkout). Pure Node + gh, no deps.

import { execFileSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';

export const EXIT = { green: 0, pending: 10, red: 20, none: 30, error: 2 };
const RED_CONCLUSIONS = new Set(['failure', 'timed_out', 'cancelled', 'action_required', 'startup_failure', 'stale']);
const IGNORED_CONCLUSIONS = new Set(['skipped', 'neutral']);
const IGNORED_APPS = new Set(['mergify']);

// Pure: decide the verdict from what the head commit carries.
//   checkRuns: [{ id, name, status, conclusion, app }]
//   statuses:  [{ context, state }]            (legacy commit statuses)
//   runs:      [{ name, status, conclusion }]  (workflow runs for the head SHA)
export function classify({ checkRuns = [], statuses = [], runs = [] }) {
  const counted = checkRuns.filter(c => !IGNORED_APPS.has(c.app) && !IGNORED_CONCLUSIONS.has(c.conclusion));
  const countedStatuses = statuses.filter(s => !/mergify/i.test(s.context || ''));
  const red = [
    ...counted.filter(c => c.status === 'completed' && RED_CONCLUSIONS.has(c.conclusion)),
    ...countedStatuses.filter(s => s.state === 'failure' || s.state === 'error').map(s => ({ name: s.context, conclusion: s.state })),
  ];
  const pending = [
    ...counted.filter(c => c.status !== 'completed').map(c => c.name),
    ...countedStatuses.filter(s => s.state === 'pending').map(s => s.context),
    ...runs.filter(r => r.status !== 'completed').map(r => `${r.name} (workflow)`),
  ];
  if (red.length) return { verdict: 'red', red, pending };
  if (pending.length) return { verdict: 'pending', pending };
  if (!counted.length && !countedStatuses.length) return { verdict: 'none' };
  return { verdict: 'green', count: counted.length + countedStatuses.length };
}

// Pure: the first line of a failed-job log worth showing a person (the assertion, not the boilerplate).
// `gh run view --log-failed` lines look like "<job>\t<step>\t<ISO timestamp> <message>".
export function firstFailureLine(log) {
  const lines = String(log || '').split('\n')
    .map(l => l.replace(/\x1b\[[0-9;]*[A-Za-z]/g, '').replace(/^[^\t]*\t[^\t]*\t/, '').replace(/^\uFEFF?\d{4}-\d\d-\d\dT[\d:.]+Z\s?/, '').trim())
    .filter(Boolean);
  // Real CI logs are noisy: passing test names say "fails", stderr dumps say "Error". So look for
  // markers in priority order — the assertion itself, then a runner's failure marker, then the
  // runner's own ##[error] line — and never take a line a runner marked as passing (✓).
  const clean = l => l.replace(/^##\[error\]/, '').trim().slice(0, 240);
  const passing = /✓|✔/;
  const tiers = [
    /AssertionError|Assertion failed/,
    /(^|\s)(FAIL|×|✖|✗|not ok)\s|\berror TS\d+:/,
  ];
  for (const re of tiers) {
    const hit = lines.find(l => re.test(l) && !passing.test(l));
    if (hit) return clean(hit);
  }
  const err = lines.find(l => l.startsWith('##[error]') && !/Process completed with exit code/.test(l));
  return err ? clean(err) : null;
}

function gh(args) {
  // Failed-job logs run to megabytes (a whole test suite's output), so the buffer is generous.
  return execFileSync('gh', args, { encoding: 'utf8', stdio: ['ignore', 'pipe', 'pipe'], maxBuffer: 256 * 1024 * 1024 });
}
const ndjson = s => s.split('\n').filter(Boolean).map(l => JSON.parse(l));

function readHead(pr) {
  const v = JSON.parse(gh(['pr', 'view', String(pr), '--json', 'headRefOid,isDraft,mergeable']));
  const sha = v.headRefOid;
  const checkRuns = ndjson(gh(['api', '--paginate', `repos/{owner}/{repo}/commits/${sha}/check-runs?per_page=100`,
    '--jq', '.check_runs[] | {id, name, status, conclusion, app: .app.slug, title: .output.title, summary: .output.summary, url: .html_url}']));
  const statuses = ndjson(gh(['api', `repos/{owner}/{repo}/commits/${sha}/status`,
    '--jq', '.statuses[] | {context, state, description}']));
  const runs = ndjson(gh(['api', `repos/{owner}/{repo}/actions/runs?head_sha=${sha}&per_page=100`,
    '--jq', '.workflow_runs[] | {name, status, conclusion}']));
  return { sha, isDraft: v.isDraft, mergeable: v.mergeable, checkRuns, statuses, runs };
}

function explainRed(c) {
  let line = null;
  if (c.app === 'github-actions' && c.id) {
    try { line = firstFailureLine(gh(['run', 'view', '--job', String(c.id), '--log-failed'])); } catch { /* log may be gone */ }
  }
  if (!line) line = (c.title || '').trim() || String(c.summary || '').split('\n').find(Boolean)?.trim() || null;
  return `red: ${c.name} — ${line || `${c.conclusion}, no failure text (see ${c.url || 'the PR checks tab'})`}`;
}

function noneReason(head) {
  if (head.isDraft) return 'none: the PR is a draft — many projects run no CI until `gh pr ready`';
  if (head.mergeable === 'CONFLICTING') return 'none: the PR conflicts with its base, so no CI run starts — merge the base in, push, then re-run';
  return `none: no checks registered for ${head.sha.slice(0, 9)} yet — if this persists, check \`gh pr view --json mergeable\` (a conflict raises no run) and whether the PR is a draft`;
}

const sleep = ms => new Promise(r => setTimeout(r, ms));

async function main(argv) {
  const json = argv.includes('--json');
  const wi = argv.indexOf('--wait-appear');
  const waitSec = wi >= 0 ? Number(argv[wi + 1]) : 0;
  const pr = argv.find((a, i) => /^\d+$/.test(a) && (wi < 0 || i !== wi + 1));
  if (!pr || Number.isNaN(waitSec)) {
    console.log('Usage: relay-checks-gate.mjs <pr> [--wait-appear <seconds>] [--json]');
    return EXIT.error;
  }
  let head, res;
  const deadline = Date.now() + waitSec * 1000;
  for (;;) {
    head = readHead(pr);
    res = classify(head);
    if (res.verdict !== 'none' || Date.now() >= deadline) break;
    await sleep(15000);
  }
  const lines = [];
  if (res.verdict === 'red') lines.push(...res.red.map(explainRed));
  else if (res.verdict === 'pending') lines.push(`pending: ${res.pending.length} not finished (${res.pending.slice(0, 5).join(', ')}${res.pending.length > 5 ? ', …' : ''})`);
  else if (res.verdict === 'none') lines.push(noneReason(head));
  else lines.push(`green: ${res.count} check(s) passed`);
  lines.push(`head: ${head.sha}`);
  if (json) console.log(JSON.stringify({ verdict: res.verdict, head: head.sha, lines }));
  else console.log(lines.join('\n'));
  return EXIT[res.verdict];
}

if (process.argv[1] && fileURLToPath(import.meta.url) === (await import('node:fs')).realpathSync(process.argv[1])) {
  main(process.argv.slice(2)).then(code => process.exit(code), err => {
    console.log(`error: ${String(err.stderr || err.message || err).split('\n')[0]}`);
    process.exit(EXIT.error);
  });
}
