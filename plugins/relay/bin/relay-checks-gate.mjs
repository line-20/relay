#!/usr/bin/env node
// relay-checks-gate.mjs — what do the PR's checks say about its CURRENT head commit?
//
// WHY THIS EXISTS. /ship's merge-queue hand-off already said "no check has failed → STOP", yet on
// castles-erp PR #2397 (2026-11-16) it queued a PR whose required "Repo guards" check had been red
// on that same head for 12 minutes; Mergify dequeued it two minutes later. A rule the model is
// asked to remember gets skipped. Like hooks.affects and hooks.claims, this is a DETERMINISTIC
// predicate: /ship reads the verdict from stdout + exit status and never judges the checks itself.
// This header is the one place the traps are explained; ship.md only points here.
//
// VERDICTS (first stdout line, plus exit code):
//   green    (0)   every counted check on the head commit finished and passed
//   pending  (10)  something on the head commit is still queued/running, or not registered yet
//   red      (20)  at least one check on the head commit failed — one `red:` line per check,
//                  each with the first failure line from its log (UNTRUSTED text: CI/PR-authored)
//   none     (30)  no checks at all for the head commit — blocked, never green (draft, or a PR
//                  that conflicts with its base, raises no pull_request run)
//   moved    (40)  with --expect-head: the PR head is still not that commit when the wait ends —
//                  someone else pushed, or GitHub never caught up. Blocked: the checks describe
//                  a commit nobody reviewed.
//   error    (2)   gh failed or timed out / bad args — callers treat it as blocked (fail closed)
//
// TRAPS IT HANDLES (seen for real in castles-erp):
//   • Stale greens. The PR-level rollup and plain `gh pr checks` keep listing the PREVIOUS
//     commit's results right after a push, and the PR's head can lag a `git push` by seconds.
//     So this reads the head SHA from the PR (and, with --expect-head, waits until it IS the
//     pushed commit) and asks that commit's own check-runs/statuses/workflow-runs.
//   • The early scope job. Right after a push only a fast "Decide scope" job may exist; the real
//     jobs are created when it finishes (`gh pr checks --watch` exits early here). Its WORKFLOW
//     RUN is still in progress, so any unfinished workflow run on the head SHA reads `pending`.
//   • Re-runs and concurrency cancels. The check-runs endpoint defaults to filter=latest (one per
//     name), and we also keep only the highest id per (app, name). A `cancelled` check while a
//     workflow run on the same commit is still going is a superseded run (push, then `gh pr
//     ready`, under cancel-in-progress) — that reads `pending`, not `red`.
//   • A workflow that never started (broken YAML → startup_failure) creates no jobs, so its run
//     conclusion counts as `red` too — otherwise a dodged guard would read green.
//   • The queue's own check. Mergify's "Merge Queue" check (skipping/neutral) is not a CI result:
//     check-runs from the mergify app, Mergify statuses, and skipped/neutral conclusions are ignored.
//
// Usage (installed): relay-checks-gate.mjs <pr> [--expect-head <sha>] [--wait-appear <seconds>]
//        (from source): node plugins/relay/bin/relay-checks-gate.mjs <pr> [...]
//   --expect-head SHA  the commit /ship pushed; the gate judges only that commit (else `moved`)
//   --wait-appear N    while the verdict is `none` (or the head isn't SHA yet), re-read every 15 s
//                      for up to N seconds (checks take a moment to register after a push/ready)
// Run it inside the repo (gh resolves {owner}/{repo} from the checkout). Pure Node + gh, no deps.

import { execFileSync } from 'node:child_process';
import fs from 'node:fs';
import { fileURLToPath } from 'node:url';

export const EXIT = { green: 0, pending: 10, red: 20, none: 30, moved: 40, error: 2 };
const RED_CONCLUSIONS = new Set(['failure', 'timed_out', 'cancelled', 'action_required', 'startup_failure', 'stale']);
const RED_RUN_CONCLUSIONS = new Set(['failure', 'timed_out', 'startup_failure']);
const IGNORED_CONCLUSIONS = new Set(['skipped', 'neutral']);
const isQueueApp = x => /mergify/i.test(x || '');
const POLL_MS = Number(process.env.RELAY_CHECKS_GATE_POLL_MS) || 15000;

// Keep only the newest check-run per (app, name): ids only go up, whatever the API's filter does.
function latestPerName(checkRuns) {
  const best = new Map();
  for (const c of checkRuns) {
    const k = `${c.app}\u0000${c.name}`;
    if (!best.has(k) || (c.id ?? 0) > (best.get(k).id ?? 0)) best.set(k, c);
  }
  return [...best.values()];
}

// Pure: decide the verdict from what the head commit carries.
//   checkRuns: [{ id, name, status, conclusion, app }]
//   statuses:  [{ context, state }]            (legacy commit statuses)
//   runs:      [{ name, status, conclusion }]  (workflow runs for the head SHA)
export function classify({ checkRuns = [], statuses = [], runs = [] }) {
  const counted = latestPerName(checkRuns).filter(c => !isQueueApp(c.app) && !IGNORED_CONCLUSIONS.has(c.conclusion));
  const countedStatuses = statuses.filter(s => !isQueueApp(s.context));
  const runsGoing = runs.some(r => r.status !== 'completed');
  const failed = counted.filter(c => c.status === 'completed' && RED_CONCLUSIONS.has(c.conclusion));
  const superseded = runsGoing ? failed.filter(c => c.conclusion === 'cancelled') : [];
  const red = [
    ...failed.filter(c => !superseded.includes(c)),
    ...countedStatuses.filter(s => s.state === 'failure' || s.state === 'error')
      .map(s => ({ name: s.context, conclusion: s.state, title: s.description, url: s.url })),
    ...runs.filter(r => r.status === 'completed' && RED_RUN_CONCLUSIONS.has(r.conclusion)
      && !failed.length)   // a failed job already speaks for its run
      .map(r => ({ name: `${r.name} (workflow)`, conclusion: r.conclusion, url: r.url })),
  ];
  const pending = [
    ...counted.filter(c => c.status !== 'completed').map(c => c.name),
    ...superseded.map(c => c.name),
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
    .map(l => l.replace(/\x1b\[[0-9;]*[A-Za-z]/g, '').replace(/^[^\t]*\t[^\t]*\t/, '').replace(/^﻿?\d{4}-\d\d-\d\dT[\d:.]+Z\s?/, '').trim())
    .filter(Boolean);
  // Real CI logs are noisy: passing test names say "fails", stderr dumps say "Error". So look for
  // markers in priority order — the assertion itself, then a runner's failure marker, then the
  // runner's own ##[error] line — and never take a line a runner marked as passing (✓).
  const passing = /✓|✔/;
  const tiers = [
    /AssertionError|Assertion failed/,
    /(^|\s)(FAIL|×|✖|✗|not ok)\s|\berror TS\d+:/,
  ];
  for (const re of tiers) {
    const hit = lines.find(l => re.test(l) && !passing.test(l));
    if (hit) return sanitize(hit);
  }
  const err = lines.find(l => l.startsWith('##[error]') && !/Process completed with exit code/.test(l));
  return err ? sanitize(err.replace(/^##\[error\]/, '')) : null;
}

// Pure: one printable line — no control characters (a name or title must not forge a second
// `green:`/`head:` line or drive the terminal), capped in length.
export function sanitize(s) {
  return String(s ?? '').replace(/\x1b\[[0-9;]*[A-Za-z]/g, '').replace(/[\x00-\x1f\x7f]+/g, ' ').trim().slice(0, 240);
}

function gh(args, timeout = 60_000) {
  // A hung gh call must become exit 2, not a frozen gate. Failed-job logs run to megabytes.
  return execFileSync('gh', args, { encoding: 'utf8', stdio: ['ignore', 'pipe', 'pipe'], timeout, maxBuffer: 64 * 1024 * 1024 });
}
const ndjson = s => s.split('\n').filter(Boolean).map(l => JSON.parse(l));

function readHead(pr) {
  const v = JSON.parse(gh(['pr', 'view', String(pr), '--json', 'headRefOid,isDraft,mergeable']));
  const sha = v.headRefOid;
  if (!/^[0-9a-f]{40}$/.test(sha || '')) throw new Error(`unexpected head SHA from gh: ${sanitize(sha)}`);
  const checkRuns = ndjson(gh(['api', '--paginate', `repos/{owner}/{repo}/commits/${sha}/check-runs?per_page=100`,
    '--jq', '.check_runs[] | {id, name, status, conclusion, app: .app.slug, title: .output.title, summary: .output.summary, url: .html_url}']));
  const statuses = ndjson(gh(['api', '--paginate', `repos/{owner}/{repo}/commits/${sha}/status?per_page=100`,
    '--jq', '.statuses[] | {context, state, description, url: .target_url}']));
  const runs = ndjson(gh(['api', '--paginate', `repos/{owner}/{repo}/actions/runs?head_sha=${sha}&per_page=100`,
    '--jq', '.workflow_runs[] | {name, status, conclusion, url: .html_url}']));
  return { sha, isDraft: v.isDraft, mergeable: v.mergeable, checkRuns, statuses, runs };
}

function explainRed(c) {
  let line = null;
  if (c.app === 'github-actions' && c.id) {
    try { line = firstFailureLine(gh(['run', 'view', '--job', String(c.id), '--log-failed'], 120_000)); } catch { /* log may be gone */ }
  }
  if (!line) line = sanitize(c.title) || sanitize(String(c.summary || '').split('\n').find(Boolean)) || null;
  return `red: ${sanitize(c.name)} — ${line || `${c.conclusion}, no failure text (see ${sanitize(c.url) || 'the PR checks tab'})`}`;
}

function noneReason(head) {
  if (head.isDraft) return 'none: the PR is a draft — many projects run no CI until `gh pr ready`';
  if (head.mergeable === 'CONFLICTING') return 'none: the PR conflicts with its base, so no CI run starts — merge the base in, push, then re-run';
  return `none: no checks registered for ${head.sha.slice(0, 9)} — check \`gh pr view --json mergeable\` (a conflict raises no run) and whether the project runs CI on this PR at all`;
}

// Pure: parse argv strictly — an ambiguous call must be a usage error, never a gate on the wrong PR.
export function parseArgs(argv) {
  const out = { pr: null, expectHead: null, waitSec: 0 };
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (a === '--wait-appear') {
      const n = argv[++i];
      if (!/^\d+$/.test(n || '')) return null;
      out.waitSec = Number(n);
    } else if (a === '--expect-head') {
      const s = argv[++i];
      if (!/^[0-9a-f]{7,40}$/.test(s || '')) return null;
      out.expectHead = s;
    } else if (/^\d+$/.test(a) && out.pr === null) out.pr = a;
    else return null;
  }
  return out.pr ? out : null;
}

const sleep = ms => new Promise(r => setTimeout(r, ms));

async function main(argv) {
  const args = parseArgs(argv);
  if (!args) {
    console.log('Usage: relay-checks-gate.mjs <pr> [--expect-head <sha>] [--wait-appear <seconds>]');
    return EXIT.error;
  }
  let head, res;
  const deadline = Date.now() + args.waitSec * 1000;
  for (;;) {
    head = readHead(args.pr);
    const headMoved = args.expectHead && !head.sha.startsWith(args.expectHead);
    res = headMoved ? { verdict: 'moved' } : classify(head);
    const keepWaiting = res.verdict === 'none' || res.verdict === 'moved';
    if (!keepWaiting || Date.now() >= deadline) break;
    await sleep(POLL_MS);
  }
  const lines = [];
  if (res.verdict === 'moved') lines.push(`moved: the PR head is ${head.sha.slice(0, 9)}, not the expected ${args.expectHead.slice(0, 9)} — someone else pushed, or GitHub has not caught up`);
  else if (res.verdict === 'red') lines.push(...res.red.map(explainRed));
  else if (res.verdict === 'pending') lines.push(`pending: ${res.pending.length} not finished (${res.pending.slice(0, 5).map(sanitize).join(', ')}${res.pending.length > 5 ? ', …' : ''})`);
  else if (res.verdict === 'none') lines.push(noneReason(head));
  else lines.push(`green: ${res.count} check(s) passed`);
  lines.push(`head: ${head.sha}`);
  console.log(lines.join('\n'));
  return EXIT[res.verdict];
}

if (process.argv[1] && fileURLToPath(import.meta.url) === fs.realpathSync(process.argv[1])) {
  main(process.argv.slice(2)).then(code => process.exit(code), err => {
    console.log(`error: ${sanitize(String(err.stderr || err.message || err).split('\n')[0])}`);
    process.exit(EXIT.error);
  });
}
