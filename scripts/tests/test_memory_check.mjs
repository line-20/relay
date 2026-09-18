// Tests for plugins/relay/bin/relay-memory-check.mjs — the size-driven MEMORY.md compaction sweep.
// Self-contained, no deps (node:test + node:assert). Run: node scripts/tests/test_memory_check.mjs
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const SCRIPT = path.join(path.dirname(fileURLToPath(import.meta.url)), '..', '..', 'plugins', 'relay', 'bin', 'relay-memory-check.mjs');

function mkdir() { return fs.mkdtempSync(path.join(os.tmpdir(), 'memcheck-')); }

function memFile(dir, name, { type = 'project', modified = '2026-01-01', desc = 'A durable fact.' } = {}) {
  fs.writeFileSync(path.join(dir, `${name}.md`),
    `---\nname: ${name}\ndescription: "${desc}"\nmetadata:\n  type: ${type}\n  modified: ${modified}T09:00:00.000Z\n---\n\nBody of ${name}.\n`);
}

function writeIndex(dir, entryFiles, extraLines = []) {
  const lines = ['# Memory index', ''];
  for (const f of entryFiles) lines.push(`- [${f}](${f}.md) — hook for ${f} explaining the fact briefly.`);
  lines.push(...extraLines);
  fs.writeFileSync(path.join(dir, 'MEMORY.md'), lines.join('\n') + '\n');
}

function runScript(dir, args = []) {
  return execFileSync('node', [SCRIPT, '--memory-dir', dir, ...args], { encoding: 'utf8' });
}

test('healthy index: STATUS ok, nothing to fix, no write', () => {
  const dir = mkdir();
  ['aaa', 'bbb'].forEach(n => memFile(dir, n));
  writeIndex(dir, ['aaa', 'bbb']);
  const before = fs.readFileSync(path.join(dir, 'MEMORY.md'), 'utf8');
  const out = runScript(dir);
  assert.match(out, /STATUS: ok/);
  assert.match(out, /nothing to fix/);
  assert.equal(fs.readFileSync(path.join(dir, 'MEMORY.md'), 'utf8'), before, 'index unchanged');
});

test('orphan on disk is indexed with a derived pointer line', () => {
  const dir = mkdir();
  ['aaa'].forEach(n => memFile(dir, n));
  memFile(dir, 'lonely', { desc: 'Nobody indexed me.' });
  writeIndex(dir, ['aaa']); // lonely.md exists but has no pointer
  const out = runScript(dir);
  assert.match(out, /indexed 1 orphan \(lonely\.md\)/);
  const idx = fs.readFileSync(path.join(dir, 'MEMORY.md'), 'utf8');
  assert.match(idx, /\(lonely\.md\)/, 'orphan now has a pointer');
  assert.match(idx, /Nobody indexed me\./, 'hook came from the frontmatter description');
});

test('stale pointer (target file gone) is dropped', () => {
  const dir = mkdir();
  ['aaa'].forEach(n => memFile(dir, n));
  writeIndex(dir, ['aaa'], ['- [Ghost](ghost.md) — points at a file that does not exist.']);
  const out = runScript(dir);
  assert.match(out, /dropped 1 stale pointer \(ghost\.md\)/);
  const idx = fs.readFileSync(path.join(dir, 'MEMORY.md'), 'utf8');
  assert.doesNotMatch(idx, /ghost\.md/, 'stale pointer removed');
  assert.match(idx, /\(aaa\.md\)/, 'live pointer kept');
});

test('dry-run reports actions but writes nothing', () => {
  const dir = mkdir();
  memFile(dir, 'aaa'); memFile(dir, 'lonely');
  writeIndex(dir, ['aaa'], ['- [Ghost](ghost.md) — stale.']);
  const before = fs.readFileSync(path.join(dir, 'MEMORY.md'), 'utf8');
  const out = runScript(dir, ['--dry-run']);
  assert.match(out, /dry-run — nothing written/);
  assert.match(out, /index 1 orphan/);
  assert.match(out, /drop 1 stale pointer/);
  assert.equal(fs.readFileSync(path.join(dir, 'MEMORY.md'), 'utf8'), before, 'no write in dry-run');
});

test('over ceiling: STATUS over, budget + ranked candidate table surfaced, no memory deleted', () => {
  const dir = mkdir();
  const names = [];
  // oldest first so we can assert the ranking; interleave types
  for (let i = 0; i < 12; i++) {
    const n = `fact${String(i).padStart(2, '0')}`;
    names.push(n);
    memFile(dir, n, { modified: `2026-01-${String(i + 1).padStart(2, '0')}`, type: ['project', 'reference', 'feedback', 'user'][i % 4] });
  }
  writeIndex(dir, names);
  const out = runScript(dir, ['--target-kb', '0.5']); // force over
  assert.match(out, /STATUS: over/);
  assert.match(out, /OVER the working-set ceiling/);
  assert.match(out, /Retire roughly \d+ entr/);
  assert.match(out, /GUIDED SWEEP/);
  assert.match(out, /\| # \| Memory \| Type \| Modified \| Hook \|/, 'GFM candidate table present');
  // oldest (fact00, 2026-01-01) ranks first
  assert.match(out, /\| 1 \| fact00\.md \|/);
  // the sweep must NOT delete any memory file — that is the model's job
  assert.equal(fs.readdirSync(dir).filter(f => f.endsWith('.md') && f !== 'MEMORY.md').length, 12,
    'no memory files removed by the script');
});

test('idempotent: a second run after a fix finds nothing to do', () => {
  const dir = mkdir();
  memFile(dir, 'aaa'); memFile(dir, 'lonely');
  writeIndex(dir, ['aaa'], ['- [Ghost](ghost.md) — stale.']);
  runScript(dir);               // first run fixes
  const out = runScript(dir);   // second run
  assert.match(out, /nothing to fix/);
});

test('missing MEMORY.md is a clean error (exit 2)', () => {
  const dir = mkdir();
  assert.throws(() => runScript(dir), (e) => {
    assert.equal(e.status, 2);
    assert.match(String(e.stderr), /no MEMORY\.md/);
    return true;
  });
});
