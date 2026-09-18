#!/usr/bin/env node
// relay-memory-check.mjs — size-driven MEMORY.md compaction, the global sweep /persist runs at end-of-lap.
//
// WHY THIS EXISTS. MEMORY.md (the harness auto-memory index, one line per memory) grows
// append-only and hits its load cap every few laps. /persist's own retire scan only sweeps
// memories THIS lap's harvest superseded, so slow drift — stale pointers, orphaned files, facts
// long since promoted to a house rule on some other lap — never gets swept. This is that missing
// global sweep, keyed on size, independent of any one lap's harvest.
//
// DIVISION OF LABOUR. This script does only the DETERMINISTIC, SAFE parts itself:
//   • index an orphan  — a memory file on disk with no pointer line (additive, loses nothing)
//   • drop a stale pointer — an index line whose target file is gone (the file already left)
//   • report size against the working-set ceiling
// It NEVER retires a live memory. Retiring a memory BECAUSE its fact now lives in a durable
// surface (relay/knowledge/*, an ADR) is a judgment call, so when the index is over the ceiling
// this script SURFACES a ranked retire-candidate list and a byte budget for /persist's model pass
// to act on with judgment. A script must not blind-delete a fact that might have no other home.
//
// Ships INSIDE the plugin at plugins/relay/bin/ so it packages with Relay and lands on the Bash
// tool's PATH when the plugin is installed (Claude Code adds each plugin's bin/ to PATH). /persist
// resolves and runs it in Step 6.5 — it is NOT a hook and takes no config, because the MEMORY.md
// format, location and load cap are fixed by the harness and identical for every project, so there
// is no project-specific mechanic to plug in. Pure Node, no dependencies. (${CLAUDE_PLUGIN_ROOT} is
// deliberately NOT used: it is not expanded in a command's Bash calls — only in skill/agent markdown
// and hook/MCP configs — so the bin/-on-PATH mechanism is what makes this resolvable for consumers.)
//
// Usage (installed): relay-memory-check.mjs [--memory-dir <path>] [--dry-run] [--target-kb <n>] [--json]
//        (from source): node plugins/relay/bin/relay-memory-check.mjs [...same flags]
// Exit 0 on success (whether or not action is needed — read STATUS from stdout); non-zero only on
// a real error (no memory dir). The guided sweep is signalled by `STATUS: over`, never by exit code.

import fs from 'node:fs';
import path from 'node:path';
import os from 'node:os';

// --- Thresholds (decimal KB, matching the harness's own figures) ---------------------------------
// Cap ~25 KB / 200 lines; harness warns ~24.4 KB; wants < ~17.1 KB. We treat 17.1 KB as the
// working-set CEILING and trigger the guided sweep above it — proactively, before the warn line.
const KB = 1000;
const DEFAULTS = { targetBytes: 17.1 * KB, warnBytes: 24.4 * KB, capBytes: 25 * KB, lineCap: 200 };

// --- Args ----------------------------------------------------------------------------------------
function parseArgs(argv) {
  const a = { dryRun: false, json: false, memoryDir: null, targetKb: null };
  for (let i = 0; i < argv.length; i++) {
    const arg = argv[i];
    if (arg === '--dry-run') a.dryRun = true;
    else if (arg === '--json') a.json = true;
    else if (arg === '--memory-dir') {
      a.memoryDir = argv[++i];
      if (!a.memoryDir) return { error: '--memory-dir needs a path' };
    } else if (arg === '--target-kb') {
      const n = Number(argv[++i]);
      if (!Number.isFinite(n) || n <= 0) return { error: '--target-kb needs a positive number' };
      a.targetKb = n;
    } else if (arg === '-h' || arg === '--help') a.help = true;
  }
  return a;
}

// The harness stores a project's memory at ~/.claude/projects/<slug>/memory, where <slug> is the cwd
// with BOTH '/' and '.' folded to '-' (case preserved). The '.' matters: a parallel-worktree cwd like
// <repo>/.claude/worktrees/x becomes <repo>--claude-worktrees-x — fold only '/' and every worktree
// (Relay's whole reason to exist) would resolve to a non-existent dir and silently skip the sweep.
function defaultMemoryDir() {
  const slug = process.cwd().replace(/[/.]/g, '-');
  return path.join(os.homedir(), '.claude', 'projects', slug, 'memory');
}

// --- Frontmatter (minimal, no YAML dep) ----------------------------------------------------------
// We only need name, description, and the nested type / modified — a flat key: value scan of the
// frontmatter block is enough, and tolerant of the two nesting styles Relay memories use.
function readFrontmatter(file) {
  let text;
  try { text = fs.readFileSync(file, 'utf8'); } catch { return {}; }
  if (text.charCodeAt(0) === 0xFEFF) text = text.slice(1);   // strip a leading UTF-8 BOM
  const m = text.match(/^---\r?\n([\s\S]*?)\r?\n---/);
  if (!m) return {};
  const fm = {};
  for (const line of m[1].split(/\r?\n/)) {
    const kv = line.match(/^\s*([A-Za-z_][\w-]*)\s*:\s*(.*)$/);
    if (!kv) continue;
    const key = kv[1];
    let val = kv[2].trim().replace(/^["']|["']$/g, '');
    if (val === '') continue;
    // Last occurrence wins: the nested `metadata.type` we want appears after any top-level key of the
    // same name, so letting it overwrite is correct. A flat scan is enough — we only read scalar keys.
    fm[key] = val;
  }
  return fm;
}

// --- Index parsing -------------------------------------------------------------------------------
const ENTRY_RE = /^-\s*\[([^\]]*)\]\(([^)]+)\)\s*(?:—|--|-)?\s*(.*)$/;

// A bullet counts as a MEMORY pointer only when it links to a bare `<name>.md` basename — no path
// separator, no URL scheme, ignoring any #fragment. Any other list item (an external link, a
// see-also, a subdir path) is ordinary prose we preserve verbatim; classifying it as a pointer would
// mark it "stale" and delete it in the rewrite — silent, unrecoverable data loss.
function pointerMatch(line) {
  const m = line.match(ENTRY_RE);
  if (!m) return null;
  const target = m[2].split('#')[0].trim();
  if (!/^[^/:]+\.md$/.test(target)) return null;
  return { title: m[1], target, hook: (m[3] || '').trim() };
}

function slugToTitle(slug) {
  return slug.replace(/\.md$/, '').replace(/[-_]+/g, ' ').replace(/^\w/, c => c.toUpperCase());
}

function firstSentence(s, max = 140) {
  if (!s) return '';
  const one = s.replace(/\s+/g, ' ').trim();
  const cut = one.match(/^(.*?[.!?])(\s|$)/);
  const out = cut ? cut[1] : one;
  return out.length > max ? out.slice(0, max - 1).trimEnd() + '…' : out;
}

function run(opts) {
  const dir = opts.memoryDir || defaultMemoryDir();
  const indexPath = path.join(dir, 'MEMORY.md');
  if (!fs.existsSync(indexPath)) {
    return { error: `no MEMORY.md at ${indexPath}` };
  }

  const target = (opts.targetKb ? opts.targetKb * KB : DEFAULTS.targetBytes);
  const th = { ...DEFAULTS, targetBytes: target };

  let raw, onDisk;
  try {
    raw = fs.readFileSync(indexPath, 'utf8');
    if (raw.charCodeAt(0) === 0xFEFF) raw = raw.slice(1);   // drop a stray BOM (rewritten out below)
    // Memory files actually on disk (exclude the index itself).
    onDisk = fs.readdirSync(dir).filter(f => f.endsWith('.md') && f !== 'MEMORY.md');
  } catch (e) {
    return { error: `cannot read memory dir ${dir}: ${e.message}` };
  }
  const eol = raw.includes('\r\n') ? '\r\n' : '\n';
  const lines = raw.split(/\r?\n/);
  const onDiskSet = new Set(onDisk);

  // Walk the index: keep every non-entry line verbatim; classify each entry line.
  const referenced = new Set();
  const stale = [];
  const kept = [];
  for (const line of lines) {
    const pm = pointerMatch(line);
    if (!pm) { kept.push({ line }); continue; }
    if (onDiskSet.has(pm.target)) {
      referenced.add(pm.target);
      kept.push({ line, entry: { title: pm.title, file: pm.target, hook: pm.hook } });
    } else {
      stale.push({ line, file: pm.target });
    }
  }

  // Orphans: on disk but no pointer line.
  const orphans = onDisk.filter(f => !referenced.has(f)).sort();
  const orphanLines = orphans.map(f => {
    const fm = readFrontmatter(path.join(dir, f));
    const title = fm.name ? slugToTitle(fm.name) : slugToTitle(f);
    const hook = firstSentence(fm.description) || '(indexed automatically — refine this line)';
    return { file: f, line: `- [${title}](${f}) — ${hook}` };
  });

  // Rebuild the index: drop stale lines, append orphan lines after the last existing entry.
  let outLines = kept.map(k => k.line);
  if (orphanLines.length) {
    let lastEntryIdx = -1;
    for (let i = 0; i < outLines.length; i++) if (pointerMatch(outLines[i])) lastEntryIdx = i;
    const insertAt = lastEntryIdx >= 0 ? lastEntryIdx + 1 : outLines.length;
    outLines.splice(insertAt, 0, ...orphanLines.map(o => o.line));
  }
  let out = outLines.join(eol);
  if (raw.endsWith('\n') && !out.endsWith('\n')) out += eol;

  const changed = out !== raw;
  // Write atomically (temp + rename on the same dir) so two parallel /persist runs can't interleave
  // and leave MEMORY.md half-written — the multi-session case is Relay's norm, not an edge.
  if (changed && !opts.dryRun) {
    const tmp = path.join(dir, `.MEMORY.md.tmp-${process.pid}`);
    try {
      fs.writeFileSync(tmp, out, 'utf8');
      fs.renameSync(tmp, indexPath);
    } catch (e) {
      try { fs.rmSync(tmp, { force: true }); } catch { /* best effort */ }
      return { error: `cannot write ${indexPath}: ${e.message}` };
    }
  }

  // Measure the post-fix index (what the next session will actually load).
  const measured = opts.dryRun ? out : (changed ? out : raw);
  const bytes = Buffer.byteLength(measured, 'utf8');
  const entryCount = outLines.filter(l => pointerMatch(l)).length;
  const lineCount = outLines.length;

  const over = bytes > th.targetBytes || entryCount > th.lineCap;
  const status = over ? 'over' : 'ok';

  // Retire candidates (only computed when over) — ranked by staleness so the model reviews the
  // most-likely-superseded first. We DO NOT act on these; we surface them.
  let candidates = [];
  let budget = null;
  if (over) {
    const typeRank = { reference: 0, project: 1, feedback: 2, user: 3 };
    candidates = kept.filter(k => k.entry).map(k => {
      const fm = readFrontmatter(path.join(dir, k.entry.file));
      return {
        file: k.entry.file,
        title: k.entry.title,
        hook: k.entry.hook,
        // `type` is the memory's own kind (project/reference/feedback/user). Don't fall back to
        // `node_type`, which is the storage node kind (literally "memory") and would mis-rank.
        type: fm.type || 'unknown',
        modified: (fm.modified || '').slice(0, 10),
      };
    }).sort((a, b) => {
      // Oldest-modified first (blank/unknown sorts oldest — unknown age is itself suspicious),
      // then reference/project ahead of the house-rule-ish feedback/user memories.
      const am = a.modified || '0', bm = b.modified || '0';
      if (am !== bm) return am < bm ? -1 : 1;
      return (typeRank[a.type] ?? 9) - (typeRank[b.type] ?? 9);
    });

    const bytesToCut = Math.max(0, bytes - th.targetBytes);
    // Average over the ENTRY lines only (not headings/blank lines/prose), so the estimate reflects
    // what a retire actually reclaims rather than diluting per-entry cost with fixed overhead.
    const entryBytes = outLines.filter(pointerMatch).reduce((n, l) => n + Buffer.byteLength(l + eol, 'utf8'), 0);
    const avgEntry = entryCount ? entryBytes / entryCount : 0;
    const entriesToCut = avgEntry ? Math.ceil(bytesToCut / avgEntry) : 0;
    budget = { bytesToCut, entriesToCut };
  }

  return {
    dir, indexPath, dryRun: opts.dryRun,
    stale: stale.map(s => s.file),
    orphans: orphanLines.map(o => o.file),
    changed,
    size: { bytes, lineCount, entryCount },
    thresholds: th,
    status, candidates, budget,
  };
}

// --- Reporting -----------------------------------------------------------------------------------
function kb(n) { return (n / KB).toFixed(1); }

function report(r) {
  const out = [];
  out.push(`STATUS: ${r.status}`);
  out.push('');
  out.push(`MEMORY.md — ${r.indexPath}`);

  const did = [];
  if (r.orphans.length) did.push(`${r.dryRun ? 'index' : 'indexed'} ${r.orphans.length} orphan${r.orphans.length > 1 ? 's' : ''} (${r.orphans.join(', ')})`);
  if (r.stale.length) did.push(`${r.dryRun ? 'drop' : 'dropped'} ${r.stale.length} stale pointer${r.stale.length > 1 ? 's' : ''} (${r.stale.join(', ')})`);
  if (did.length) out.push(`Deterministic sweep${r.dryRun ? ' (dry-run — nothing written)' : ''}: ${did.join('; ')}.`);
  else out.push(`Deterministic sweep: nothing to fix (no orphans, no stale pointers).`);

  const { bytes, lineCount, entryCount } = r.size;
  const th = r.thresholds;
  out.push(`Size: ${kb(bytes)} KB / ${lineCount} lines / ${entryCount} entries — ` +
    `want < ${kb(th.targetBytes)} KB · warn ${kb(th.warnBytes)} KB · cap ${kb(th.capBytes)} KB / ${th.lineCap} lines.`);

  if (r.status === 'ok') {
    out.push('');
    out.push('Under the working-set ceiling — no guided sweep needed.');
    return out.join('\n');
  }

  // OVER — surface the sweep for the model.
  out.push('');
  out.push(`OVER the working-set ceiling by ${kb(r.budget.bytesToCut)} KB. ` +
    `Retire roughly ${r.budget.entriesToCut} entr${r.budget.entriesToCut === 1 ? 'y' : 'ies'} to get back under ${kb(th.targetBytes)} KB.`);
  out.push('');
  out.push('GUIDED SWEEP (model pass — do NOT delete blindly):');
  out.push('For each candidate below, open the memory file and check whether its fact now lives in a');
  out.push('durable surface (relay/knowledge/*, an ADR, a house rule). Retire ONLY those whose fact has');
  out.push('a home elsewhere — that memory is a second, weaker copy. Leave anything with no repo home');
  out.push('(a machine reality, a working agreement, a gotcha that belongs to no document). Removal is');
  out.push("/persist's job, through the same memory mechanism it writes with — remove the file AND its");
  out.push('index line. Candidates are ranked most-likely-superseded first (oldest / reference-ish):');
  out.push('');
  out.push('| # | Memory | Type | Modified | Hook |');
  out.push('|---|---|---|---|---|');
  const show = r.candidates.slice(0, Math.max(r.budget.entriesToCut * 2, 12));
  show.forEach((c, i) => {
    const hook = c.hook.length > 70 ? c.hook.slice(0, 69) + '…' : c.hook;
    out.push(`| ${i + 1} | ${c.file} | ${c.type} | ${c.modified || '—'} | ${hook.replace(/\|/g, '\\|')} |`);
  });
  if (r.candidates.length > show.length) {
    out.push('');
    out.push(`(+${r.candidates.length - show.length} more — widen the sweep if these don't free enough.)`);
  }
  return out.join('\n');
}

// --- Main ----------------------------------------------------------------------------------------
const opts = parseArgs(process.argv.slice(2));
if (opts.error) {
  console.error(`memory-check: ${opts.error}`);
  process.exit(2);
}
if (opts.help) {
  console.log('Usage: relay-memory-check.mjs [--memory-dir <path>] [--dry-run] [--target-kb <n>] [--json]');
  process.exit(0);
}
const result = run(opts);
if (result.error) {
  console.error(`memory-check: ${result.error}`);
  process.exit(2);
}
console.log(opts.json ? JSON.stringify(result, null, 2) : report(result));
process.exit(0);
