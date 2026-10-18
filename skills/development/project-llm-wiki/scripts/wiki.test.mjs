import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import test from 'node:test';

const script = fileURLToPath(new URL('./wiki.mjs', import.meta.url));
const date = '2026-10-16';

function fixture(t) {
  const root = fs.mkdtempSync(path.join(fs.realpathSync(os.tmpdir()), 'project-llm-wiki-test-'));
  t.after(() => {
    assert.equal(path.dirname(root), fs.realpathSync(os.tmpdir()));
    assert.ok(path.basename(root).startsWith('project-llm-wiki-test-'));
    fs.rmSync(root, { recursive: true, force: true });
  });
  return root;
}

function run(root, command, args = []) {
  const result = spawnSync(process.execPath, [script, command, '--project-root', root, ...args], { encoding: 'utf8' });
  assert.ifError(result.error);
  return { status: result.status, output: result.stdout + result.stderr, stdout: result.stdout };
}

function init(root, extra = []) {
  return run(root, 'init', ['--name', '演示 project', '--date', date, ...extra]);
}

function write(root, relative, content) {
  const file = path.join(root, relative);
  fs.mkdirSync(path.dirname(file), { recursive: true });
  fs.writeFileSync(file, content, 'utf8');
}

function append(root, relative, content) {
  fs.appendFileSync(path.join(root, relative), content, 'utf8');
}

function page(type, sources, body, extra = '') {
  return `---\ntype: ${type}\nupdated: ${date}\nsources: [${sources}]\n${extra}---\n\n${body}\n`;
}

function ingest(root, status = 'ingested') {
  const source = 'docs/wiki/raw/notes.md';
  write(root, source, '# Demo notes\nThis project organizes reusable reading notes.\n');
  write(root, 'docs/wiki/overview.md', page('overview', source,
    '# Reading notes\n\nThis project organizes reusable reading notes. Evidence: `docs/wiki/raw/notes.md:2`.\n\n[Summary](summaries/notes.md)'));
  write(root, 'docs/wiki/glossary.md', page('glossary', source, '# Terms\n\nReading note: a reusable note. [Overview](overview.md)'));
  write(root, 'docs/wiki/open-questions.md', page('open-questions', source, '# Questions\n\nNo additional questions from this source. [Overview](overview.md)'));
  write(root, 'docs/wiki/summaries/notes.md', page('summary', source,
    '# Source notes\n\nOne supplied note, dated 2026-10-16.\n\n## 知识去向\n\n[Overview](../overview.md) and [terms](../glossary.md).'));
  append(root, 'docs/wiki/index.md', '\n- [Notes summary](summaries/notes.md) — scope and contributions.\n');
  append(root, 'docs/wiki/sources.md', `\n| notes | \`${source}\` | ${status} | [Notes](summaries/notes.md) | ${date} | All supplied statements; no code behavior inferred. |\n`);
  append(root, 'docs/wiki/log.md', `\n## [${date}] ingest | Ingest supplied notes\n\nSummary and overview updated.\n`);
}

test('dry-run creates no wiki and normal init preserves root instructions', t => {
  const root = fixture(t);
  write(root, 'AGENTS.md', 'Existing project rules.\r\n');
  const preview = init(root, ['--dry-run']);
  assert.equal(preview.status, 0, preview.output);
  assert.equal(JSON.parse(preview.stdout).files.length, 11);
  assert.equal(fs.existsSync(path.join(root, 'docs')), false);
  assert.equal(init(root).status, 0);
  assert.equal(fs.readFileSync(path.join(root, 'AGENTS.md'), 'utf8'), 'Existing project rules.\r\n');
  const overview = fs.readFileSync(path.join(root, 'docs/wiki/overview.md'), 'utf8');
  assert.ok(overview.includes('演示 project'));
  assert.ok(!overview.includes('{{'));
  assert.ok(!fs.readFileSync(path.join(root, 'docs/wiki/index.md')).subarray(0, 3).equals(Buffer.from([0xef, 0xbb, 0xbf])));
});

test('fresh skeleton passes structure but warns about missing evidence', t => {
  const root = fixture(t);
  assert.equal(init(root).status, 0);
  const result = run(root, 'lint');
  assert.equal(result.status, 0, result.output);
  const report = JSON.parse(result.stdout);
  assert.equal(report.pages, 7);
  assert.equal(report.errors.length, 0);
  assert.equal(report.warnings.filter(item => item.includes('no evidence')).length, 3);
});

test('repeat init refuses to overwrite a changed wiki', t => {
  const root = fixture(t);
  assert.equal(init(root).status, 0);
  append(root, 'docs/wiki/index.md', '\nUser content.\n');
  const before = fs.readFileSync(path.join(root, 'docs/wiki/index.md'));
  assert.equal(init(root).status, 2);
  assert.deepEqual(fs.readFileSync(path.join(root, 'docs/wiki/index.md')), before);
});

test('custom location and project path containing spaces and Unicode work', t => {
  const parent = fixture(t);
  const root = path.join(parent, '资料 project');
  fs.mkdirSync(root);
  assert.equal(init(root, ['--wiki-path', 'knowledge/wiki']).status, 0);
  const copied = path.join(root, 'knowledge/wiki/tools/wiki.mjs');
  const result = spawnSync(process.execPath, [copied, 'lint', '--project-root', root, '--wiki-path', 'knowledge/wiki'], { encoding: 'utf8' });
  assert.equal(result.status, 0, result.stderr + result.stdout);
});

test('rejects traversal, absolute paths and invalid calendar dates before writing', t => {
  const root = fixture(t);
  for (const value of ['../escape', '.', path.join(root, 'absolute'), 'nested/../../../escape', 'C:/escape']) {
    assert.equal(init(root, ['--wiki-path', value]).status, 2, value);
  }
  const result = run(root, 'init', ['--name', 'Demo', '--date', '2026-02-30']);
  assert.equal(result.status, 2);
  assert.equal(fs.readdirSync(root).length, 0);
});

test('rejects symlink or junction parent without writing outside target', t => {
  const root = fixture(t);
  const outside = fixture(t);
  try { fs.symlinkSync(outside, path.join(root, 'shortcut'), process.platform === 'win32' ? 'junction' : 'dir'); }
  catch (failure) {
    if (['EPERM', 'EACCES', 'ENOSYS'].includes(failure.code)) { t.skip('Host does not permit symlink/junction creation'); return; }
    throw failure;
  }
  assert.equal(init(root, ['--wiki-path', 'shortcut/wiki']).status, 2);
  assert.equal(fs.readdirSync(outside).length, 0);
});

test('real source ingestion yields a covered wiki with no warnings and lint is read-only', t => {
  const root = fixture(t);
  assert.equal(init(root).status, 0);
  ingest(root);
  const before = fs.readFileSync(path.join(root, 'docs/wiki/sources.md'));
  const result = run(root, 'lint');
  assert.equal(result.status, 0, result.output);
  const report = JSON.parse(result.stdout);
  assert.deepEqual(report.errors, []);
  assert.deepEqual(report.warnings, []);
  assert.deepEqual(fs.readFileSync(path.join(root, 'docs/wiki/sources.md')), before);
});

test('unregistered raw material warns and partial source remains incomplete', t => {
  const root = fixture(t);
  assert.equal(init(root).status, 0);
  write(root, 'docs/wiki/raw/unread.txt', 'Unprocessed notes.');
  assert.match(run(root, 'lint').output, /pending ingest/);
  ingest(root, 'partial');
  assert.match(run(root, 'lint').output, /coverage incomplete/);
});

test('missing summary prevents false ingested coverage', t => {
  const root = fixture(t);
  assert.equal(init(root).status, 0);
  append(root, 'docs/wiki/sources.md', `\n| absent | \`README.md\` | ingested | — | ${date} | Claimed all. |\n`);
  const result = run(root, 'lint');
  assert.equal(result.status, 1);
  assert.match(result.output, /requires a summary/);
});

test('broken links, orphan pages and invalid log events produce errors', t => {
  const root = fixture(t);
  assert.equal(init(root).status, 0);
  write(root, 'docs/wiki/concepts/orphan.md', page('concept', '', '# Orphan'));
  append(root, 'docs/wiki/overview.md', '\n[missing](concepts/missing.md)\n');
  append(root, 'docs/wiki/log.md', '\n## [2026-02-30] lint | Invalid date\n');
  const result = run(root, 'lint');
  assert.equal(result.status, 1);
  assert.match(result.output, /broken link/);
  assert.match(result.output, /not registered in index/);
  assert.match(result.output, /invalid log/);
});

test('reference links are checked while fenced and inline examples are ignored', t => {
  const root = fixture(t);
  assert.equal(init(root).status, 0);
  append(root, 'docs/wiki/overview.md', '\n```markdown\n[example](missing.md)\n```\n~~~text\n[example](missing.md)\n~~~\n`[example](missing.md)`\n[Terms][terms]\n[terms]: glossary.md\n');
  assert.equal(run(root, 'lint').status, 0);
  append(root, 'docs/wiki/overview.md', '\n[broken][absent]\n');
  const result = run(root, 'lint');
  assert.equal(result.status, 1);
  assert.match(result.output, /undefined reference/);
});

test('library-escaping links and invalid related targets fail validation', t => {
  const root = fixture(t);
  write(root, 'outside.md', 'Outside.');
  assert.equal(init(root).status, 0);
  append(root, 'docs/wiki/overview.md', '\n[outside](../../outside.md)\n');
  write(root, 'docs/wiki/concepts/linked.md', page('concept', '', '# Linked', 'related: [../missing.md]\n'));
  append(root, 'docs/wiki/index.md', '\n[Linked](concepts/linked.md)\n');
  const result = run(root, 'lint');
  assert.equal(result.status, 1);
  assert.match(result.output, /link escapes wiki/);
  assert.match(result.output, /broken link to missing.md/);
});

test('normative and domain pages require their semantic sections', t => {
  const root = fixture(t);
  assert.equal(init(root).status, 0);
  write(root, 'docs/wiki/checklists/sample.md', page('checklist', '', '# Checklist'));
  write(root, 'docs/wiki/domains/sample.md', page('domain', '', '# Domain'));
  append(root, 'docs/wiki/index.md', '\n[Checklist](checklists/sample.md)\n[Domain](domains/sample.md)\n');
  const result = run(root, 'lint');
  assert.equal(result.status, 1);
  assert.match(result.output, /任务视角/);
  assert.match(result.output, /关联知识单元/);
});

test('BOM, invalid frontmatter dates and unclosed YAML are detected', t => {
  const root = fixture(t);
  assert.equal(init(root).status, 0);
  write(root, 'docs/wiki/overview.md', '\ufeff' + page('overview', '', '# Overview'));
  write(root, 'docs/wiki/glossary.md', page('glossary', '', '# Terms').replace(date, '2026-02-30'));
  write(root, 'docs/wiki/open-questions.md', '---\ntype: open-questions\n');
  const result = run(root, 'lint');
  assert.equal(result.status, 1);
  assert.match(result.output, /UTF-8 BOM/);
  assert.match(result.output, /invalid updated date/);
  assert.match(result.output, /unclosed frontmatter/);
});

test('sensitive findings in raw or pages never echo the matched value', t => {
  const root = fixture(t);
  assert.equal(init(root).status, 0);
  const synthetic = ['SYNTHETIC', 'CREDENTIAL', 'FOR', 'TEST'].join('_');
  write(root, 'docs/wiki/raw/unsafe.txt', `api_key: ${synthetic}\n`);
  append(root, 'docs/wiki/overview.md', `\npassword: ${synthetic}\n`);
  const result = run(root, 'lint');
  assert.equal(result.status, 1);
  assert.match(result.output, /suspected credential/);
  assert.ok(!result.output.includes(synthetic));
});

test('init can connect a project entry while preserving all existing CRLF instructions', t => {
  const root = fixture(t);
  const original = '# Project rules\r\n\r\nKeep existing conventions.\r\n';
  write(root, 'AGENTS.md', original);
  const result = init(root, ['--entry-file', 'AGENTS.md']);
  assert.equal(result.status, 0, result.output);
  const entry = fs.readFileSync(path.join(root, 'AGENTS.md'), 'utf8');
  assert.ok(entry.startsWith(original));
  assert.equal((entry.match(/<!-- project-llm-wiki:begin -->/g) || []).length, 1);
  assert.ok(entry.includes('docs/wiki/agent-workflow.md'));
  assert.ok(!entry.replace(/\r\n/g, '').includes('\n'));
  assert.equal(run(root, 'connect', ['--entry-file', 'AGENTS.md']).status, 0);
  assert.equal(fs.readFileSync(path.join(root, 'AGENTS.md'), 'utf8'), entry);
  assert.ok(fs.existsSync(path.join(root, 'docs/wiki/agent-workflow.md')));
  assert.equal(run(root, 'lint').status, 0);
});

test('connection dry-run plans entry and wiki without mutating either', t => {
  const root = fixture(t);
  write(root, 'AGENTS.md', 'Keep this unchanged.\n');
  const before = fs.readFileSync(path.join(root, 'AGENTS.md'));
  const result = init(root, ['--entry-file', 'AGENTS.md', '--dry-run']);
  assert.equal(result.status, 0, result.output);
  assert.ok(JSON.parse(result.stdout).files.includes('AGENTS.md'));
  assert.deepEqual(fs.readFileSync(path.join(root, 'AGENTS.md')), before);
  assert.equal(fs.existsSync(path.join(root, 'docs')), false);
});

test('connect creates a selected Markdown entry and repeated connection is byte-for-byte idempotent', t => {
  const root = fixture(t);
  assert.equal(init(root).status, 0);
  const entry = '.github/copilot-instructions.md';
  assert.equal(run(root, 'connect', ['--entry-file', entry]).status, 0);
  const before = fs.readFileSync(path.join(root, entry));
  const result = run(root, 'connect', ['--entry-file', entry]);
  assert.equal(result.status, 0, result.output);
  assert.deepEqual(fs.readFileSync(path.join(root, entry)), before);
  assert.ok(!before.subarray(0, 3).equals(Buffer.from([0xef, 0xbb, 0xbf])));
});

test('connect updates only its marked block when the selected wiki path changes', t => {
  const root = fixture(t);
  assert.equal(init(root, ['--entry-file', 'AGENTS.md']).status, 0);
  append(root, 'AGENTS.md', '\n## Other rules\nKeep these unchanged.\n');
  assert.equal(init(root, ['--wiki-path', 'knowledge/wiki']).status, 0);
  const result = run(root, 'connect', ['--entry-file', 'AGENTS.md', '--wiki-path', 'knowledge/wiki']);
  assert.equal(result.status, 0, result.output);
  const entry = fs.readFileSync(path.join(root, 'AGENTS.md'), 'utf8');
  assert.equal((entry.match(/<!-- project-llm-wiki:begin -->/g) || []).length, 1);
  assert.ok(entry.includes('knowledge/wiki/agent-workflow.md'));
  assert.ok(!entry.includes('docs/wiki/agent-workflow.md'));
  assert.ok(entry.endsWith('\n## Other rules\nKeep these unchanged.\n'));
});

test('init refuses malformed managed markers before creating any wiki files', t => {
  const root = fixture(t);
  const original = '# Rules\n<!-- project-llm-wiki:begin -->\nUnfinished block.\n';
  write(root, 'AGENTS.md', original);
  assert.equal(init(root, ['--entry-file', 'AGENTS.md']).status, 2);
  assert.equal(fs.existsSync(path.join(root, 'docs')), false);
  assert.equal(fs.readFileSync(path.join(root, 'AGENTS.md'), 'utf8'), original);
});

test('entry path escapes and entry/wiki collisions are rejected before initialization', t => {
  const root = fixture(t);
  for (const entry of ['../outside.md', 'docs/wiki/AGENTS.md', 'docs/wiki', 'docs', '.git/rules.md', '.GIT/rules.md', 'package.json']) {
    const result = init(root, ['--entry-file', entry]);
    assert.equal(result.status, 2, `${entry}: ${result.output}`);
    assert.equal(fs.readdirSync(root).length, 0);
  }
});

test('existing invalid UTF-8 or BOM entry remains untouched and init does not partially scaffold', t => {
  const root = fixture(t);
  for (const bytes of [Buffer.from([0xff, 0xfe, 0x23, 0]), Buffer.from('\ufeff# Existing rules\r\n')]) {
    fs.writeFileSync(path.join(root, 'AGENTS.md'), bytes);
    assert.equal(init(root, ['--entry-file', 'AGENTS.md']).status, 2);
    assert.deepEqual(fs.readFileSync(path.join(root, 'AGENTS.md')), bytes);
    assert.equal(fs.existsSync(path.join(root, 'docs')), false);
  }
});

test('connect refuses missing wiki workflow and dry-run is read-only for an existing wiki', t => {
  const root = fixture(t);
  assert.equal(run(root, 'connect', ['--entry-file', 'AGENTS.md']).status, 2);
  assert.equal(init(root).status, 0);
  const result = run(root, 'connect', ['--entry-file', 'AGENTS.md', '--dry-run']);
  assert.equal(result.status, 0, result.output);
  assert.equal(fs.existsSync(path.join(root, 'AGENTS.md')), false);
  fs.unlinkSync(path.join(root, 'docs/wiki/agent-workflow.md'));
  assert.equal(run(root, 'connect', ['--entry-file', 'AGENTS.md']).status, 2);
  assert.equal(fs.existsSync(path.join(root, 'AGENTS.md')), false);
});
