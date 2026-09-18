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

// --- ranking: the type tiebreak (only fires when `modified` is equal) ----------------------------
function candidateOrder(out) {
  return out.split('\n')
    .map(l => l.match(/^\|\s*\d+\s*\|\s*([^|]+\.md)\s*\|/))
    .filter(Boolean).map(m => m[1].trim());
}

test('over ceiling: equal modified dates fall back to the type tiebreak (reference<project<feedback<user)', () => {
  const dir = mkdir();
  // Same modified date for all, so the sort is decided purely by typeRank.
  const specs = [
    ['u', 'user'], ['f', 'feedback'], ['p', 'project'], ['r', 'reference'], ['x', 'nonsense-type'],
  ];
  specs.forEach(([n, t]) => memFile(dir, n, { type: t, modified: '2026-05-05' }));
  writeIndex(dir, specs.map(s => s[0]));
  const order = candidateOrder(runScript(dir, ['--target-kb', '0.01']));
  // reference, project, feedback, user, then the unknown type last
  assert.deepEqual(order, ['r.md', 'p.md', 'f.md', 'u.md', 'x.md']);
});

// --- frontmatter tolerance / fallback paths ------------------------------------------------------
test('orphan with NO frontmatter is indexed with a slug title and the placeholder hook', () => {
  const dir = mkdir();
  memFile(dir, 'aaa');
  fs.writeFileSync(path.join(dir, 'no-frontmatter-here.md'), 'Just a body, no --- block.\n');
  writeIndex(dir, ['aaa']);
  const out = runScript(dir);
  assert.match(out, /indexed 1 orphan \(no-frontmatter-here\.md\)/);
  const idx = fs.readFileSync(path.join(dir, 'MEMORY.md'), 'utf8');
  assert.match(idx, /- \[No frontmatter here\]\(no-frontmatter-here\.md\) — \(indexed automatically — refine this line\)/);
});

test('orphan with frontmatter but no description uses the placeholder hook', () => {
  const dir = mkdir();
  memFile(dir, 'aaa');
  fs.writeFileSync(path.join(dir, 'nodesc.md'), '---\nname: nodesc\nmetadata:\n  type: project\n---\n\nBody.\n');
  writeIndex(dir, ['aaa']);
  runScript(dir);
  const idx = fs.readFileSync(path.join(dir, 'MEMORY.md'), 'utf8');
  assert.match(idx, /\(nodesc\.md\) — \(indexed automatically — refine this line\)/);
});

test('candidate with missing type/modified shows unknown / — in the table', () => {
  const dir = mkdir();
  fs.writeFileSync(path.join(dir, 'bare.md'), '---\nname: bare\ndescription: "A fact with no type or date."\n---\n\nBody.\n');
  writeIndex(dir, ['bare']);
  const out = runScript(dir, ['--target-kb', '0.01']);
  const row = out.split('\n').find(l => l.includes('bare.md') && l.startsWith('|'));
  assert.match(row, /\| unknown \| — \|/);
});

// --- EOL / trailing-newline round-trips ----------------------------------------------------------
test('a CRLF index stays CRLF after a rewrite', () => {
  const dir = mkdir();
  memFile(dir, 'aaa'); memFile(dir, 'orphan');
  fs.writeFileSync(path.join(dir, 'MEMORY.md'),
    '# Memory index\r\n\r\n- [aaa](aaa.md) — hook.\r\n');
  runScript(dir); // indexing the orphan forces a rewrite
  const idx = fs.readFileSync(path.join(dir, 'MEMORY.md'), 'utf8');
  assert.ok(idx.includes('\r\n'), 'still has CRLF');
  assert.ok(!/[^\r]\n/.test(idx), 'no bare LF introduced');
});

test('a no-trailing-newline index does not gain one on rewrite', () => {
  const dir = mkdir();
  memFile(dir, 'aaa'); memFile(dir, 'orphan');
  fs.writeFileSync(path.join(dir, 'MEMORY.md'), '# Memory index\n\n- [aaa](aaa.md) — hook.'); // no final \n
  runScript(dir);
  const idx = fs.readFileSync(path.join(dir, 'MEMORY.md'), 'utf8');
  assert.ok(!idx.endsWith('\n'), 'no trailing newline added');
  assert.match(idx, /\(orphan\.md\)/, 'orphan still indexed');
});

// --- pointer classification edge cases -----------------------------------------------------------
test('an anchored pointer (file.md#heading) is neither dropped nor re-indexed', () => {
  const dir = mkdir();
  memFile(dir, 'aaa');
  writeIndex(dir, [], ['- [Anchored](aaa.md#a-heading) — points at a live file with an anchor.']);
  const out = runScript(dir);
  assert.match(out, /nothing to fix/);
  const idx = fs.readFileSync(path.join(dir, 'MEMORY.md'), 'utf8');
  assert.match(idx, /aaa\.md#a-heading/, 'anchored live pointer kept');
});

test('a non-.md bullet (external link / subdir path) is preserved, never deleted as stale', () => {
  const dir = mkdir();
  memFile(dir, 'aaa');
  writeIndex(dir, ['aaa'], [
    '- [Docs](https://example.com/guide) — an external link, not a memory pointer.',
    '- [Sub](sub/dir/note.md) — a subdir path, not a bare memory basename.',
  ]);
  const out = runScript(dir);
  assert.match(out, /nothing to fix/);
  const idx = fs.readFileSync(path.join(dir, 'MEMORY.md'), 'utf8');
  assert.match(idx, /example\.com\/guide/);
  assert.match(idx, /sub\/dir\/note\.md/);
});

// --- --target-kb keeps an otherwise-over index at ok ---------------------------------------------
test('--target-kb can keep at ok an index that is over under the default', () => {
  const dir = mkdir();
  for (let i = 0; i < 40; i++) memFile(dir, `n${i}`);
  writeIndex(dir, Array.from({ length: 40 }, (_, i) => `n${i}`));
  assert.match(runScript(dir, ['--target-kb', '0.5']), /STATUS: over/); // over under a tiny ceiling
  const out = runScript(dir, ['--target-kb', '100']);                    // ok under a large one
  assert.match(out, /STATUS: ok/);
  assert.match(out, /want < 100\.0 KB/);
});

// --- the 🔴 fix: default memory-dir folds '.' as well as '/' (worktree cwd) -----------------------
test("defaultMemoryDir folds '.' so a dotted/worktree cwd resolves (not just '/')", () => {
  const base = mkdir();
  const dotted = path.join(base, 'a.b', 'c'); // a cwd containing a dot, like <repo>/.claude/...
  fs.mkdirSync(dotted, { recursive: true });
  // No --memory-dir → it derives from cwd; assert the derived path folded the dot to '-'.
  assert.throws(() => execFileSync('node', [SCRIPT], { cwd: dotted, encoding: 'utf8' }), (e) => {
    assert.equal(e.status, 2);
    assert.match(String(e.stderr), /-a-b-c\/memory\/MEMORY\.md/); // '.' and '/' both folded to '-'
    return true;
  });
});

test('a bad --target-kb is rejected with exit 2', () => {
  const dir = mkdir();
  memFile(dir, 'aaa'); writeIndex(dir, ['aaa']);
  assert.throws(() => runScript(dir, ['--target-kb', 'nope']), (e) => {
    assert.equal(e.status, 2);
    assert.match(String(e.stderr), /--target-kb needs a positive number/);
    return true;
  });
});
