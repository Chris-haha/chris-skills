#!/usr/bin/env node
// Optional, dependency-free helper for the bundled schema. Node.js >= 18.
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const TYPES = new Set(['meta', 'overview', 'glossary', 'open-questions', 'module',
  'domain', 'capability', 'entity', 'concept', 'summary', 'comparison', 'decision',
  'recipe', 'lesson', 'checklist', 'template', 'methodology']);
const REQUIRED = ['AGENTS.md', 'index.md', 'overview.md', 'glossary.md',
  'sources.md', 'open-questions.md', 'log.md', 'raw/README.md', 'raw/.gitignore'];
const ENTRY_START = '<!-- project-llm-wiki:begin -->';
const ENTRY_END = '<!-- project-llm-wiki:end -->';
const EVENTS = 'seed|ingest|query|update|lint|feedback';
const SELF = fileURLToPath(import.meta.url);
const slash = value => value.split(path.sep).join('/');
const unquote = value => value.replace(/^(["'])(.*)\1$/, '$2');

function inside(root, target) {
  const relative = path.relative(root, target);
  return relative === '' || (!path.isAbsolute(relative)
    && relative !== '..' && !relative.startsWith(`..${path.sep}`));
}

function safePath(root, relative) {
  if (path.isAbsolute(relative) || /^[A-Za-z]:/.test(relative)
      || relative.includes('\\') || /[\x00-\x1f`]/.test(relative)) {
    throw new Error('Use a project-relative path with forward slashes.');
  }
  const resolved = path.resolve(root, relative);
  if (!inside(root, resolved) || resolved === root) throw new Error('Path must stay below project root.');
  let current = root;
  for (const part of path.relative(root, resolved).split(path.sep)) {
    current = path.join(current, part);
    try {
      if (fs.lstatSync(current).isSymbolicLink()) throw new Error('Symlink/junction paths are not supported.');
    } catch (failure) { if (failure.code !== 'ENOENT') throw failure; }
  }
  return resolved;
}

function validDate(value) {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(value)) return false;
  const parsed = new Date(`${value}T00:00:00Z`);
  return !Number.isNaN(parsed.valueOf()) && parsed.toISOString().slice(0, 10) === value;
}

function options(args) {
  const result = {};
  for (let index = 0; index < args.length; index += 1) {
    const key = args[index];
    if (!['--project-root', '--wiki-path', '--entry-file', '--name', '--date', '--dry-run'].includes(key)) {
      throw new Error(`Unknown argument: ${key}`);
    }
    if (Object.hasOwn(result, key)) throw new Error(`Duplicate argument: ${key}`);
    if (key === '--dry-run') result[key] = true;
    else {
      const value = args[++index];
      if (!value || value.startsWith('--')) throw new Error(`Missing value: ${key}`);
      result[key] = value;
    }
  }
  return result;
}

function walk(root, skipTools = true) {
  const files = [];
  function visit(directory) {
    for (const entry of fs.readdirSync(directory, { withFileTypes: true })) {
      if (entry.name === '.git' || (skipTools && entry.name === 'tools')) continue;
      const file = path.join(directory, entry.name);
      if (entry.isSymbolicLink()) throw new Error('Symlink/junction entries are not supported.');
      if (entry.isDirectory()) visit(file);
      else if (entry.isFile()) files.push(file);
    }
  }
  visit(root);
  return files.sort();
}

function planEntry(root, wikiPath, entryPath) {
  const wiki = safePath(root, wikiPath);
  const file = safePath(root, entryPath);
  const relative = slash(path.relative(root, file));
  if (inside(wiki, file) || inside(file, wiki)
      || relative.split('/').some(part => part.toLowerCase() === '.git') || !/\.(md|mdc)$/i.test(file)) {
    throw new Error('Entry must be a Markdown rule file outside the wiki and .git directory.');
  }
  const template = path.resolve(path.dirname(SELF), '../assets/project-entry.md');
  if (!fs.existsSync(template)) throw new Error('Entry connection requires the complete skill package with assets/project-entry.md.');
  let original = null;
  let text = '';
  if (fs.existsSync(file)) {
    if (!fs.statSync(file).isFile() || fs.statSync(file).size > 1024 * 1024) {
      throw new Error('Existing entry must be a text file no larger than 1 MiB.');
    }
    original = fs.readFileSync(file);
    if (original.subarray(0, 3).equals(Buffer.from([0xef, 0xbb, 0xbf]))) {
      throw new Error('Entry has a BOM; preserve it and merge manually instead of converting.');
    }
    try { text = new TextDecoder('utf-8', { fatal: true }).decode(original); }
    catch { throw new Error('Entry is not UTF-8; preserve it and merge manually instead of converting.'); }
  }
  const newline = text.match(/\r?\n/)?.[0] || '\n';
  const normalizedWiki = slash(path.relative(root, wiki));
  const block = fs.readFileSync(template, 'utf8').trimEnd()
    .replace(/\{\{WIKI_PATH\}\}/g, () => normalizedWiki).replace(/\r?\n/g, newline);
  const starts = [...text.matchAll(/^<!-- project-llm-wiki:begin -->\r?$/gm)];
  const ends = [...text.matchAll(/^<!-- project-llm-wiki:end -->\r?$/gm)];
  if (starts.length > 1 || ends.length > 1 || starts.length !== ends.length
      || (starts.length && starts[0].index >= ends[0].index)
      || (text.includes(ENTRY_START) && !starts.length)
      || (text.includes(ENTRY_END) && !ends.length)) {
    throw new Error('Malformed or duplicate entry markers; merge manually.');
  }
  let content;
  if (starts.length) {
    content = text.slice(0, starts[0].index) + block
      + text.slice(ends[0].index + ENTRY_END.length);
  } else {
    const separator = !text ? '' : text.endsWith('\n') ? newline : newline + newline;
    content = text + separator + block + newline;
  }
  return { root, file, relative, original, content, changed: content !== text };
}

function writeEntry(plan) {
  if (!plan.changed) return;
  safePath(plan.root, plan.relative);
  if (plan.original !== null) {
    if (!fs.existsSync(plan.file) || !fs.readFileSync(plan.file).equals(plan.original)) {
      throw new Error('Entry changed during planning; retry after reviewing current content.');
    }
  } else if (fs.existsSync(plan.file)) throw new Error('Entry appeared during planning; refusing overwrite.');
  fs.mkdirSync(path.dirname(plan.file), { recursive: true });
  fs.writeFileSync(plan.file, plan.content, { encoding: 'utf8', flag: plan.original === null ? 'wx' : 'w' });
}

function connect(root, wikiPath, opts) {
  if (!opts['--entry-file']) throw new Error('connect requires --entry-file selected for the actual host.');
  const wiki = safePath(root, wikiPath);
  for (const required of ['AGENTS.md', 'index.md', 'agent-workflow.md']) {
    const file = safePath(root, `${wikiPath}/${required}`);
    if (!fs.existsSync(file) || !fs.statSync(file).isFile()) {
      throw new Error('Wiki schema, index and agent-workflow.md must exist before connecting.');
    }
  }
  const plan = planEntry(root, slash(path.relative(root, wiki)), opts['--entry-file']);
  if (opts['--dry-run']) {
    console.log(JSON.stringify({ dryRun: true, files: plan.changed ? [plan.relative] : [], connected: plan.relative }, null, 2));
    return;
  }
  writeEntry(plan);
  console.log(`${plan.changed ? 'Connected' : 'Already connected'}: ${plan.relative}. Verify the host loads this rule file.`);
}

function initialize(root, wikiPath, opts) {
  const name = opts['--name'];
  const date = opts['--date'];
  if (!name || /[\r\n\x00-\x1f]/.test(name) || name.length > 200) {
    throw new Error('init requires a single-line --name (1-200 characters).');
  }
  if (!validDate(date || '')) throw new Error('init requires a valid --date YYYY-MM-DD.');
  const target = safePath(root, wikiPath);
  if (fs.existsSync(target)
      && (!fs.statSync(target).isDirectory() || fs.readdirSync(target).length > 0)) {
    throw new Error('Wiki target is not empty; read and merge existing content manually.');
  }
  const entry = opts['--entry-file'] ? planEntry(root, wikiPath, opts['--entry-file']) : null;
  const templates = path.resolve(path.dirname(SELF), '../assets/wiki');
  if (!fs.existsSync(templates)) throw new Error('init requires the complete skill package with assets/wiki.');
  const replacements = { PROJECT_NAME: name.replace(/[\\`*_[\]<>#]/g, '\\$&'), WIKI_PATH: wikiPath, DATE: date };
  const planned = walk(templates, false).map(file => ({
    relative: slash(path.relative(templates, file)),
    content: fs.readFileSync(file, 'utf8').replace(/\{\{(PROJECT_NAME|WIKI_PATH|DATE)\}\}/g,
      (_, key) => replacements[key]),
  }));
  planned.push({ relative: 'tools/wiki.mjs', content: fs.readFileSync(SELF, 'utf8') });
  for (const item of planned) {
    if (/\{\{[A-Z_]+\}\}/.test(item.content)) throw new Error('Unresolved template variable.');
    safePath(root, `${wikiPath}/${item.relative}`);
  }
  if (opts['--dry-run']) {
    const files = planned.map(item => `${wikiPath}/${item.relative}`);
    if (entry?.changed) files.push(entry.relative);
    console.log(JSON.stringify({ dryRun: true, files, entry: entry?.relative || null }, null, 2));
    return;
  }
  for (const item of planned) {
    const output = safePath(root, `${wikiPath}/${item.relative}`);
    fs.mkdirSync(path.dirname(output), { recursive: true });
    fs.writeFileSync(output, item.content, { encoding: 'utf8', flag: 'wx' });
  }
  if (entry) writeEntry(entry);
  console.log(`Created ${planned.length} files in ${wikiPath}. Skeleton only; ingest real sources next.`);
  console.log(entry ? `Project entry connected: ${entry.relative}. Verify the host loads it.`
    : 'Project entry not connected. Select a host rule file and run connect, or merge the entry manually.');
}

function frontmatter(text) {
  const match = text.match(/^---\r?\n([\s\S]*?)\r?\n---(?:\r?\n|$)/);
  if (!match) throw new Error('Missing or unclosed frontmatter.');
  const fields = {};
  let active = null;
  for (const line of match[1].split(/\r?\n/)) {
    if (!line.trim() || line.trim().startsWith('#')) continue;
    const field = line.match(/^([a-z-]+):\s*(.*?)\s*$/);
    if (field) {
      active = field[1];
      if (Object.hasOwn(fields, active)) throw new Error(`Duplicate frontmatter field: ${active}`);
      const value = field[2];
      if (!value) fields[active] = [];
      else if (value.startsWith('[') && value.endsWith(']')) {
        fields[active] = value.slice(1, -1).split(',').map(item => unquote(item.trim())).filter(Boolean);
      } else fields[active] = unquote(value);
    } else {
      const item = line.match(/^\s+-\s+(.+)$/);
      if (!item || !active || !Array.isArray(fields[active])) {
        throw new Error('Unsupported frontmatter syntax; use simple scalars or lists.');
      }
      fields[active].push(unquote(item[1].trim()));
    }
  }
  return { fields, body: text.slice(match[0].length) };
}

function prose(text) {
  let marker = null;
  let length = 0;
  const lines = [];
  for (const line of text.split(/\r?\n/)) {
    const fence = line.match(/^\s*(`{3,}|~{3,})(.*)$/);
    if (fence) {
      if (!marker) { marker = fence[1][0]; length = fence[1].length; }
      else if (fence[1][0] === marker && fence[1].length >= length && !fence[2].trim()) marker = null;
      continue;
    }
    if (!marker) lines.push(line.replace(/(`+)[^`\n]*?\1/g, ''));
  }
  return lines.join('\n');
}

function links(body, report) {
  const text = prose(body);
  const targets = [];
  const definitions = new Map();
  const id = value => value.trim().replace(/\s+/g, ' ').toLowerCase();
  const reference = /^\s{0,3}\[([^\]]+)\]:\s*(<[^>]+>|\S+)/gm;
  for (const match of text.matchAll(reference)) definitions.set(id(match[1]), match[2]);
  for (const match of text.matchAll(/!?\[[^\]\n]*\]\(\s*(<[^>]+>|[^\s)]+)(?:\s+["'][^\n]*?["'])?\s*\)/g)) targets.push(match[1]);
  for (const match of text.matchAll(/!?\[([^\]\n]+)\]\[([^\]\n]*)\]/g)) {
    const label = id(match[2] || match[1]);
    if (!definitions.has(label)) report('undefined reference link');
    else targets.push(definitions.get(label));
  }
  for (const match of text.matchAll(/!?\[([^\]\n]+)\](?![(:\[])/g)) {
    if (definitions.has(id(match[1]))) targets.push(definitions.get(id(match[1])));
  }
  return targets.map(target => target.replace(/^<|>$/g, ''));
}

function lint(root, wikiPath) {
  const wiki = safePath(root, wikiPath);
  if (!fs.existsSync(wiki) || !fs.statSync(wiki).isDirectory()) throw new Error('Wiki directory does not exist.');
  const errors = [];
  const warnings = [];
  const label = file => slash(path.relative(wiki, file));
  const error = (file, message) => errors.push(`${label(file)}: ${message}`);
  const warning = (file, message) => warnings.push(`${label(file)}: ${message}`);
  for (const relative of REQUIRED) {
    if (!fs.existsSync(path.join(wiki, relative))) error(path.join(wiki, relative), 'required file missing');
  }
  const files = walk(wiki);
  const pages = new Map();
  const graph = new Map();
  for (const file of files) {
    const relative = label(file);
    const raw = relative.startsWith('raw/');
    const textual = /\.(md|txt|json|ya?ml|xml|sql|csv|ini|conf|env)$/i.test(file) || path.basename(file) === '.gitignore';
    if (!textual) {
      if (raw) warning(file, 'binary/unsupported raw attachment not scanned');
      continue;
    }
    if (fs.statSync(file).size > 4 * 1024 * 1024) {
      warning(file, 'text exceeds 4 MiB scan limit; review with bounded/streaming tools');
      continue;
    }
    const buffer = fs.readFileSync(file);
    if (buffer.subarray(0, 3).equals(Buffer.from([0xef, 0xbb, 0xbf]))) error(file, 'UTF-8 BOM is forbidden');
    let text;
    try { text = new TextDecoder('utf-8', { fatal: true }).decode(buffer); }
    catch { error(file, 'invalid UTF-8'); continue; }
    const sensitive = /(?:app[-_]?key|app[-_]?secret|api[-_]?key|password|passwd|access[-_]?token|token|secret)["']?\s*[:=]\s*["']?[A-Za-z0-9_\-/+=]{12,}|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----/i;
    text.split(/\r?\n/).forEach((line, index) => {
      if (sensitive.test(line)) error(file, `suspected credential at line ${index + 1}; value suppressed`);
    });
    if (!file.endsWith('.md') || raw || path.basename(file) === 'AGENTS.md') continue;
    try {
      const page = frontmatter(text);
      pages.set(file, page);
      const { fields, body } = page;
      if (!TYPES.has(fields.type)) error(file, 'unknown or missing page type');
      if (typeof fields.updated !== 'string' || !validDate(fields.updated)) error(file, 'invalid updated date');
      const allowed = new Set(['type', 'updated', 'sources', 'related', 'tags', 'confidence']);
      for (const field of Object.keys(fields)) if (!allowed.has(field)) error(file, `unknown frontmatter field: ${field}`);
      if (fields.confidence && !['high', 'medium', 'low'].includes(fields.confidence)) error(file, 'invalid confidence');
      if (fields.type !== 'meta') {
        if (!Object.hasOwn(fields, 'sources')) error(file, 'sources field required');
        else if (!fields.sources.length) warning(file, 'no evidence sources; skeleton/unconfirmed content');
      }
      if (fields.type === 'domain' && !/^## 关联知识单元\s*$/m.test(body)) error(file, 'domain requires 关联知识单元 section');
      if (['checklist', 'template', 'methodology'].includes(fields.type)
          && !/^## 任务视角\s*$/m.test(body)) error(file, 'normative page requires 任务视角 section');
      const targets = links(body, message => error(file, message));
      const related = fields.related || [];
      targets.push(...(Array.isArray(related) ? related : [related]));
      const resolved = new Set();
      for (const target of targets) {
        if (typeof target !== 'string') { error(file, 'invalid link value'); continue; }
        if (/^[a-z][a-z0-9+.-]*:/i.test(target) || target.startsWith('//')) {
          error(file, 'navigation must use wiki-internal relative links'); continue;
        }
        const base = target.split('#')[0];
        if (!base) continue;
        let decoded;
        try { decoded = decodeURIComponent(base); }
        catch { error(file, 'invalid link encoding'); continue; }
        const destination = path.resolve(path.dirname(file), decoded);
        if (path.isAbsolute(decoded) || decoded.includes('\\') || !inside(wiki, destination)) {
          error(file, 'link escapes wiki or uses an absolute path'); continue;
        }
        if (!fs.existsSync(destination)) error(file, `broken link to ${slash(path.relative(wiki, destination))}`);
        else resolved.add(destination);
      }
      graph.set(file, resolved);
    } catch (failure) { error(file, failure.message); }
  }
  const index = path.join(wiki, 'index.md');
  const coverage = graph.get(index) || new Set();
  for (const file of pages.keys()) {
    if (file !== index && !coverage.has(file)) error(file, 'page not registered in index.md');
  }
  const log = path.join(wiki, 'log.md');
  const logBody = pages.get(log)?.body || '';
  for (const line of logBody.split(/\r?\n/)) {
    if (!line.startsWith('## ')) continue;
    const match = line.match(new RegExp(`^## \\[(\\d{4}-\\d{2}-\\d{2})\\] (${EVENTS}) \\| \\S.*$`));
    if (!match || !validDate(match[1])) error(log, 'invalid log event heading');
  }
  const sourceFile = path.join(wiki, 'sources.md');
  const records = new Map();
  const ids = new Set();
  for (const line of (pages.get(sourceFile)?.body || '').split(/\r?\n/)) {
    if (!line.startsWith('|')) continue;
    const cells = line.split(/(?<!\\)\|/).slice(1, -1).map(cell => cell.trim().replace(/\\\|/g, '|'));
    if (cells[0] === 'ID' || /^:?-+/.test(cells[0] || '')) continue;
    if (cells.length !== 6) { error(sourceFile, 'source row must have six columns'); continue; }
    const [sourceId, location, status, summary, verified, scope] = cells;
    const source = location.replace(/^`|`$/g, '');
    if (!/^[a-z0-9]+(?:-[a-z0-9]+)*$/.test(sourceId) || ids.has(sourceId)) error(sourceFile, 'invalid/duplicate source ID');
    ids.add(sourceId);
    if (records.has(source)) error(sourceFile, 'duplicate source location');
    records.set(source, status);
    if (!['pending', 'partial', 'ingested', 'excluded'].includes(status)) error(sourceFile, 'invalid source status');
    if (!validDate(verified)) error(sourceFile, 'invalid source verification date');
    if (!scope || scope === '—') error(sourceFile, 'source scope/reason required');
    if (status === 'pending' || status === 'partial') warning(sourceFile, `${sourceId}: source coverage incomplete (${status})`);
    if (status === 'partial' || status === 'ingested') {
      const targets = links(summary, message => error(sourceFile, message));
      const summaries = targets.map(target => path.resolve(wiki, target));
      if (summaries.length !== 1 || pages.get(summaries[0])?.fields.type !== 'summary') {
        error(sourceFile, `${sourceId}: ingested/partial source requires a summary page`);
      } else {
        const summarySources = pages.get(summaries[0]).fields.sources || [];
        if (!(Array.isArray(summarySources) ? summarySources : [summarySources]).includes(source)) {
          error(sourceFile, `${sourceId}: summary must name the registered source`);
        }
        const contributions = [...(graph.get(summaries[0]) || [])].filter(file => {
          const type = pages.get(file)?.fields.type;
          return type && !['meta', 'summary', 'open-questions'].includes(type);
        });
        if (!contributions.length) error(sourceFile, `${sourceId}: summary has no knowledge contribution links`);
      }
    }
    if (!/^https?:\/\//i.test(source)) {
      try {
        if (!fs.existsSync(safePath(root, source))) warning(sourceFile, `${sourceId}: original source missing`);
      } catch { error(sourceFile, `${sourceId}: original source path is unsafe`); }
    }
  }
  for (const [file, page] of pages) {
    const sources = page.fields.sources || [];
    for (const source of (Array.isArray(sources) ? sources : [sources])) {
      if (!records.has(source)) warning(file, 'evidence source not registered in sources.md');
    }
  }
  for (const file of files.filter(file => label(file).startsWith('raw/'))) {
    if (['raw/README.md', 'raw/.gitignore'].includes(label(file))) continue;
    const relative = slash(path.relative(root, file));
    if (!records.has(relative)) warning(file, 'raw material not registered (pending ingest)');
  }
  console.log(JSON.stringify({ pages: pages.size, errors, warnings }, null, 2));
  return errors.length ? 1 : 0;
}

try {
  const [command, ...args] = process.argv.slice(2);
  if (!['init', 'connect', 'lint'].includes(command)) throw new Error('Usage: wiki.mjs init|connect|lint --project-root PATH [--wiki-path docs/wiki] [--entry-file AGENTS.md] [--name NAME --date YYYY-MM-DD --dry-run]');
  const opts = options(args);
  if (!opts['--project-root']) throw new Error('--project-root is required.');
  const root = fs.realpathSync(path.resolve(opts['--project-root']));
  if (!fs.statSync(root).isDirectory()) throw new Error('Project root must be a directory.');
  const wikiPath = opts['--wiki-path'] || 'docs/wiki';
  if (command === 'init') initialize(root, wikiPath, opts);
  else if (command === 'connect') {
    if (opts['--name'] || opts['--date']) throw new Error('connect does not accept --name or --date.');
    connect(root, wikiPath, opts);
  }
  else {
    if (opts['--name'] || opts['--date'] || opts['--dry-run'] || opts['--entry-file']) throw new Error('lint does not accept init/connect-only options.');
    process.exitCode = lint(root, wikiPath);
  }
} catch (failure) {
  // Do not echo arbitrary file contents or credentials from exceptions.
  console.error(`Wiki command failed: ${failure.code || failure.message}`);
  process.exitCode = 2;
}
