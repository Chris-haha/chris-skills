import fs from 'node:fs/promises';
import path from 'node:path';
import {pathToFileURL} from 'node:url';
import {createRequire} from 'node:module';

// Resolve an optional caller-provided module directory without symlinks or
// Windows Developer Mode / administrator privileges.
const moduleDirectory = process.env.CODEX_NODE_MODULES;
const artifactModule = moduleDirectory
  ? pathToFileURL(createRequire(path.join(moduleDirectory, '..', '_video_breakdown_resolver.cjs')).resolve('@oai/artifact-tool')).href
  : '@oai/artifact-tool';
const {FileBlob, SpreadsheetFile, Workbook} = await import(artifactModule);

process.on('uncaughtException', error => { console.error(error.message || String(error)); process.exit(1); });
process.on('unhandledRejection', error => { console.error(error?.message || String(error)); process.exit(1); });

// Read the exported file back for visual QA; this mode never writes a workbook.
if (process.argv[2] === '--render-saved') {
  const [, , , filename, directory] = process.argv;
  const saved = await SpreadsheetFile.importXlsx(await FileBlob.load(filename));
  await fs.mkdir(directory, {recursive: true});
  const ends = {'博主汇总':'F9', '视频索引':'D8', '博主分析':'C8', '视频拆解':'E8', '拍法库':'F8', '拍摄脚本':'G8', '拍前准备':'E8'};
  for (const [sheetName, end] of Object.entries(ends)) {
    const image = await saved.render({sheetName, range: `A2:${end}`, scale: 1, format: 'png'});
    await fs.writeFile(path.join(directory, sheetName + '.png'), new Uint8Array(await image.arrayBuffer()));
  }
  const comparisons = saved.worksheets.getItem('博主分析').getRange('A6:C1000').values;
  let number = 0;
  for (let i = 0; i < comparisons.length; i++) {
    if (!String(comparisons[i][1] || '').startsWith('拍摄建议与比较方法')) continue;
    const start = i + 6;
    while (i + 1 < comparisons.length && comparisons[i + 1][0] === comparisons[i][0] &&
           String(comparisons[i + 1][1] || '').startsWith('拍摄建议与比较方法')) i++;
    const image = await saved.render({sheetName: '博主分析', range: 'A' + start + ':C' + (i + 6), scale: 1, format: 'png'});
    await fs.writeFile(path.join(directory, '比较方案-' + (++number) + '.png'), new Uint8Array(await image.arrayBuffer()));
  }
  console.log(JSON.stringify({read_only: true, workbook: filename, sheets: Object.keys(ends)}));
  process.exit(0);
}

const [input, existing, output, ...args] = process.argv.slice(2);
const previewAt = args.indexOf('--previews');
const previewDir = previewAt >= 0 ? args[previewAt + 1] : null;
const payload = JSON.parse(await fs.readFile(input, 'utf8'));
const present = await fs.access(existing).then(() => true, () => false);
const workbook = present ? await SpreadsheetFile.importXlsx(await FileBlob.load(existing)) : Workbook.create();
const HEADER = 5;
const stats = {added: {}, updated: {}, retained: {}, counts: {}, failures: payload.failures.length};
const currentVideos = new Set(payload.current_video_keys);
const currentCreators = new Set(payload.current_creator_keys);
const managed = new Map();
const links = [];
const literal = value => typeof value === 'string' && value.startsWith('=') ? "'" + value : value ?? '';

function col(n) {
  let s = '';
  for (n++; n > 0; n = Math.floor((n - 1) / 26)) s = String.fromCharCode(65 + (n - 1) % 26) + s;
  return s;
}
function cell(sheet, row, column) { return sheet.getRange(`${col(column)}${row}`); }
function rowHeight(spec, values) {
  let lines = 1;
  for (const column of spec.columns) {
    const text = String(values[column.name] ?? '');
    const capacity = Math.max(4, column.width * 0.58);
    const wrapped = text.split('\n').reduce((n, part) => n + Math.max(1, Math.ceil([...part].reduce((m, c) => m + (c.charCodeAt(0) > 255 ? 1 : .55), 0) / capacity)), 0);
    lines = Math.max(lines, wrapped);
  }
  return Math.min(400, Math.max(34, lines * 17 + 14));
}
function styleRows(sheet, first, last, columns) {
  if (last < first) return;
  const range = sheet.getRange(`A${first}:${col(columns - 1)}${last}`);
  range.format.font = {name: 'Arial', size: 11, color: '#24344A'};
  range.format.wrapText = true;
  range.format.verticalAlignment = 'top';
}
function readRows(sheet, headers) {
  const approximateEnd = Math.max(6, sheet.getUsedRange().values.length + 5);
  return sheet.getRange(`A6:${col(headers.length - 1)}${approximateEnd}`).values;
}
function writeValue(sheet, row, column, name, value) {
  const range = cell(sheet, row, column);
  if (name === '原视频链接' && /^https?:\/\//.test(value || '')) {
    range.values = [['打开原视频']];
    links.push({sheet: sheet.name, cell: `${col(column)}${row}`, target: value});
    range.format.font.color = '#265DAD';
  } else if (name === '详细报告' && value) {
    range.values = [['查看图文与原片']];
    links.push({sheet: sheet.name, cell: `${col(column)}${row}`, target: pathToFileURL(value).href});
    range.format.font.color = '#265DAD';
  } else range.values = [[literal(value)]];
}

// Reject unrelated or renamed workbooks before changing anything in memory.
if (present) {
  for (const spec of payload.sheets) {
    let sheet;
    try { sheet = workbook.worksheets.getItem(spec.name); }
    catch { throw Error(`现有Excel缺少“${spec.name}”，请使用本Skill生成的总表；没有覆盖原文件。`); }
    if (!sheet) throw Error(`现有Excel缺少“${spec.name}”。`);
    const header = sheet.getRange('A5:ZZ5').values[0];
    for (const column of spec.columns) if (!header.includes(column.name)) throw Error(`“${spec.name}”缺少列“${column.name}”，请恢复表头后重试。`);
  }
}

for (const [index, spec] of payload.sheets.entries()) {
  const fresh = !present;
  const sheet = fresh ? workbook.worksheets.add(spec.name) : workbook.worksheets.getItem(spec.name);
  let headers;
  if (fresh) {
    headers = spec.columns.map(c => c.name);
    sheet.showGridLines = false;
    sheet.tabColor = index < 2 ? '#304C74' : '#94A9C6';
    sheet.getRange('A2').values = [[spec.name]];
    sheet.getRange('A2').format.font = {name: 'Arial', size: 16, bold: true, color: '#253E5D'};
    sheet.getRange('A3').values = [[index === 0 ? '新增链接后更新同一文件。“我的备注”和自行增加的列会保留。' : '按博主或视频筛选。新脚本为拍摄建议，方括号内容按自己的实物填写。']];
    sheet.getRange('A3').format.font = {name: 'Arial', size: 10, color: '#66758A'};
    sheet.getRange(`A5:${col(headers.length - 1)}5`).values = [headers];
    const hr = sheet.getRange(`A5:${col(headers.length - 1)}5`);
    hr.format = {fill: '#304C74', font: {name: 'Arial', size: 11, bold: true, color: '#FFFFFF'}, wrapText: true, rowHeight: 32, verticalAlignment: 'center', horizontalAlignment: 'center'};
    for (const [i, column] of spec.columns.entries()) sheet.getRange(`${col(i)}1:${col(i)}6`).format.columnWidth = column.width;
    sheet.freezePanes.freezeRows(5);
    sheet.freezePanes.freezeColumns(index === 0 ? 1 : 2);
  } else {
    headers = sheet.getRange('A5:ZZ5').values[0];
    while (headers.length && !headers.at(-1)) headers.pop();
    if (new Set(headers.filter(Boolean)).size !== headers.filter(Boolean).length) throw Error(`“${spec.name}”存在重复表头，请先修正。`);
  }
  sheet.getRange('A2').format.rowHeight = 26;
  const positions = new Map(headers.map((name, i) => [name, i]));
  const keyName = spec.name === '博主汇总' ? '账号编号' : '记录编号';
  const keyColumn = positions.get(keyName);
  const rawRows = fresh ? [] : readRows(sheet, headers);
  const keys = new Map(); let last = HEADER;
  for (const [i, values] of rawRows.entries()) {
    if (values.some(v => v !== '' && v !== null)) last = i + 6;
    const key = values[keyColumn];
    if (!key) {
      const hasManagedData = spec.columns.filter(c => c.name !== '我的备注' && c.name !== keyName)
        .some(c => values[positions.get(c.name)] !== '' && values[positions.get(c.name)] != null);
      if (hasManagedData) throw Error(`“${spec.name}”第${i + 6}行缺少${keyName}，停止更新以保护原记录和备注。`);
      continue;
    }
    if (keys.has(String(key))) throw Error(`“${spec.name}”有重复记录编号，停止更新以保护备注：${key}`);
    keys.set(String(key), i + 6);
  }
  const incoming = new Set();
  for (const data of spec.rows) {
    const key = String(data[keyName]);
    if (!data[keyName] || incoming.has(key)) throw Error(`导出数据“${spec.name}”编号为空或重复：${key}`);
    incoming.add(key);
  }
  stats.added[spec.name] = spec.rows.filter(r => !keys.has(String(r[keyName]))).length;
  stats.updated[spec.name] = spec.rows.length - stats.added[spec.name];
  const finalRow = last + stats.added[spec.name];
  const tableName = 'EcommerceVideo' + index;
  if (fresh) {
    styleRows(sheet, 6, Math.max(6, finalRow), headers.length);
    const table = sheet.tables.add(`A5:${col(headers.length - 1)}${Math.max(6, finalRow)}`, true, tableName);
    table.showFilterButton = true;
    table.style = 'TableStyleLight9';
  } else {
    const tables = sheet.tables.items;
    const table = tables.find(t => t.name === tableName);
    if (!table) throw Error(`“${spec.name}”的数据表已被删除，请恢复后重试。`);
    const rows = table.getDataRows();
    const existingCount = Array.isArray(rows) ? rows.length : rows.values.length;
    const needed = Math.max(0, finalRow - HEADER - existingCount);
    // A user's adjacent columns need not be part of the native Excel Table.
    const nativeHeaders = table.getHeaderRowRange().values[0];
    if (needed) table.rows.add(null, Array.from({length: needed}, () => nativeHeaders.map(() => '')));
    styleRows(sheet, last + 1, finalRow, headers.length);
  }
  // Old detail rows stay addressable with their notes, but cannot masquerade as current results.
  if (positions.has('记录状态')) {
    for (const [key, row] of keys) {
      const video = cell(sheet, row, positions.get('视频编号')).values[0][0];
      const creator = cell(sheet, row, positions.get('账号编号')).values[0][0];
      const inScope = (spec.name === '博主分析' ? currentCreators.has(creator) : currentVideos.has(video)) || key.startsWith(payload.failure_scope + '::');
      if (inScope && !incoming.has(key)) cell(sheet, row, positions.get('记录状态')).values = [['历史保留，本次不采用']];
    }
  }
  for (const data of spec.rows) {
    const key = String(data[keyName]);
    const row = keys.get(key) || ++last;
    const newRow = !keys.has(key);
    for (const column of spec.columns) {
      if (column.name === '我的备注' && !newRow) continue;
      writeValue(sheet, row, positions.get(column.name), column.name, data[column.name]);
    }
    const note = positions.get('我的备注');
    if (newRow && note !== undefined) {
      cell(sheet, row, note).format.fill = '#FFF6DB';
      cell(sheet, row, note).format.font.color = '#265DAD';
    }
    sheet.getRange(`A${row}:${col(headers.length - 1)}${row}`).format.rowHeight = rowHeight(spec, data);
    keys.set(key, row);
  }
  if (positions.has('记录状态')) {
    const status = sheet.getRange(`${col(positions.get('记录状态'))}6:${col(positions.get('记录状态'))}${Math.max(6, last)}`);
    if (fresh) status.conditionalFormats.add('containsText', {text: '历史', format: {fill: '#FFF0DF', font: {color: '#8A4E14'}}});
  }
  stats.retained[spec.name] = keys.size - incoming.size;
  stats.counts[spec.name] = keys.size;
  managed.set(spec.name, {sheet, headers, positions, keys, last});
}

// Count the union already present in this workbook, including previous imports.
const creators = managed.get('博主汇总'), videos = managed.get('视频索引');
const totals = new Map();
for (const row of videos.keys.values()) {
  const key = cell(videos.sheet, row, videos.positions.get('账号编号')).values[0][0];
  const status = cell(videos.sheet, row, videos.positions.get('分析状态')).values[0][0];
  const t = totals.get(key) || {all: 0, done: 0}; t.all++; if (status === '已分析') t.done++; totals.set(key, t);
}
for (const [key, row] of creators.keys) {
  const t = totals.get(key) || {all: 0, done: 0};
  for (const [field, value] of [['归档视频数', t.all], ['已分析视频数', t.done], ['待补视频数', t.all - t.done]]) {
    const range = cell(creators.sheet, row, creators.positions.get(field));range.values = [[value]];range.setNumberFormat('#,##0');
  }
}
workbook.recalculate();
const inspection = await workbook.inspect({kind: 'table', range: '博主汇总!A5:F10', include: 'values,formulas', tableMaxRows: 6, tableMaxCols: 6, maxChars: 2500});
const errors = await workbook.inspect({kind: 'match', searchTerm: '#REF!|#DIV/0!|#VALUE!|#NAME\\?|#NUM!|#NULL!|#SPILL!|#CALC!', options: {useRegex: true, maxResults: 30}, maxChars: 2000});
stats.inspection = inspection.ndjson; stats.formula_scan = errors.ndjson; stats.links = links;
if (previewDir) {
  await fs.mkdir(previewDir, {recursive: true});
  for (const spec of payload.sheets) {
    const end = Math.min(spec.name === '博主汇总' ? 9 : 8, Math.max(6, managed.get(spec.name).last));
    const lastCol = spec.name === '拍摄脚本' ? 'G' : spec.name === '拍法库' ? 'F' : spec.name === '博主汇总' ? 'F' : spec.name === '视频索引' ? 'D' : spec.name === '博主分析' ? 'C' : 'E';
    const blob = await workbook.render({sheetName: spec.name, range: `A2:${lastCol}${end}`, scale: 1, format: 'png'});
    await fs.writeFile(path.join(previewDir, spec.name + '.png'), new Uint8Array(await blob.arrayBuffer()));
  }
}
const blob = await SpreadsheetFile.exportXlsx(workbook);
await blob.save(output);
await fs.writeFile(path.join(path.dirname(output), 'result.json'), JSON.stringify(stats, null, 2));
console.log(JSON.stringify({counts: stats.counts, added: stats.added, updated: stats.updated}));
