"""Project validated reports into keyed tables and update a local Excel workbook."""
import hashlib
import json
import os
import ntpath
import shutil
import subprocess
import tempfile
import posixpath
import re
import zipfile
import xml.etree.ElementTree as ET
from collections import defaultdict
from pathlib import Path
from archive import digest, now, read_json, write_json
from analysis import MODULES, CREATOR_MODULES
from quality import MODE_LABELS, mode
from editorial import check_report, check_workspace, experiment_text
from portable import resolve_runtime, file_lock
from excel_native import xml_bytes

FILENAME = '电商视频分析总表.xlsx'
PLATFORMS = {'douyin': '抖音', 'xiaohongshu': '小红书', 'bilibili': 'B站'}
STATE = {'complete': '已分析', 'ready': '待分析', 'pending': '待分析', 'invalid': '分析待复核',
         'needs_review': '来源待确认', 'needs_transcript': '待补资料'}
COMMON = [('记录状态', 16), ('我的备注', 30), ('记录编号', 30), ('视频编号', 32), ('账号编号', 32)]


def report_digest(report):
    return digest(json.dumps({k: v for k, v in report.items() if k != 'generated_at'}, ensure_ascii=False, sort_keys=True))


def text_chunks(text, limit=500):
    chunks = []
    while len(text) > limit:
        boundaries = [m.end() for m in re.finditer(r'\n\n|[。！？][”」]?|\n', text[:limit])]
        end = next((p for p in reversed(boundaries) if p >= limit // 2), limit)
        chunks.append(text[:end])
        text = text[end:]
    return chunks + [text] if text or not chunks else chunks


def project(report, report_dir):
    """No summarization here: export authored text and its actual evidence intact."""
    errors = check_report(report)
    if errors:
        raise ValueError('成品文字检查未通过：\n' + '\n'.join(errors))
    specs = [
        ('博主汇总', [('博主', 22), ('平台', 12), ('归档视频数', 14), ('已分析视频数', 16),
                  ('待补视频数', 14), ('值得学什么', 76), ('我的备注', 30), ('账号编号', 32)]),
        ('视频索引', [('博主', 22), ('视频标题', 34), ('分析状态', 16), ('结论与待补信息', 80),
                  ('原视频链接', 40), ('详细报告', 25), ('我的备注', 30), ('记录编号', 32),
                  ('视频编号', 32), ('账号编号', 32)]),
        ('博主分析', [('博主', 22), ('分析项目', 24), ('分析内容', 90), ('涉及视频', 35)] + COMMON),
        ('视频拆解', [('博主', 22), ('视频标题', 34), ('分析项目', 24), ('分析内容', 88), ('依据', 50)] + COMMON),
        ('拍法库', [('博主', 22), ('视频标题', 34), ('拍法', 36), ('内容项目', 22),
                 ('内容', 88), ('依据', 50)] + COMMON),
        ('拍摄脚本', [('博主', 22), ('视频标题', 34), ('镜头', 12), ('开始秒', 10),
                   ('结束秒', 10), ('画面与台词', 78), ('开拍前准备', 50)] + COMMON),
        ('拍前准备', [('博主', 22), ('视频标题', 34), ('准备项目', 30), ('内容', 90), ('依据', 50)] + COMMON),
    ]
    sheets = {name: {'name': name, 'columns': [{'name': n, 'width': w} for n, w in cols], 'rows': []}
              for name, cols in specs}

    def add(sheet, key, data, body=None):
        # Excel row height and text limits must never silently hide long source text.
        text = str(data.get(body, '')) if body else ''
        chunks = text_chunks(text)
        for i, chunk in enumerate(chunks):
            row = {'记录状态': '当前分析', '我的备注': '', **data, '记录编号': f'{key}::part{i+1}'}
            if body:
                row[body] = chunk
            if len(chunks) > 1:
                label = {'博主分析':'分析项目', '视频拆解':'分析项目', '拍法库':'内容项目', '拍前准备':'准备项目'}.get(sheet)
                if label:
                    row[label] += f'（第{i+1}/{len(chunks)}段）'
            sheets[sheet]['rows'].append(row)

    groups = defaultdict(list)
    current_keys = []
    for item in report['videos']:
        r = item['record']; key = r['video_key']; creator = r['creator_key']
        groups[creator].append(item); current_keys.append(key)
        good = item.get('report_status') == 'complete' and not item.get('validation_errors')
        a = item.get('analysis', {}) if good else {}
        c = a.get('creation', {})
        base = {'博主': r.get('creator_name') or '待确认博主', '视频标题': r.get('title') or key,
                '视频编号': key, '账号编号': creator}
        verdict = c.get('verdict', {})
        summary = '\n'.join(v for v in [verdict.get('transfer_value'), verdict.get('sales_gap')] if v)
        if good:
            summary = '分析依据：' + MODE_LABELS[mode(r)] + '\n' + summary
        if r.get('is_synthetic'):
            base['视频标题'] = '[合成测试] ' + base['视频标题']
        add('视频索引', key + '::index', {**base, '分析状态': STATE.get(item.get('report_status'), '待分析'),
            '结论与待补信息': summary or '；'.join(item.get('validation_errors', [])) or '尚未完成分析。',
            '原视频链接': r.get('source_url', ''), '详细报告': str(Path(report_dir) / 'videos' / (key + '.html'))})
        if not good:
            continue
        evidence = {e['id']: e for e in a.get('evidence', [])}

        def refs(ids):
            lines = []
            for ref in ids:
                e = evidence.get(ref, {})
                kind = e.get('type')
                label = {'title':'原标题', 'caption':'笔记正文', 'clip':'原视频片段', 'frame':'截图',
                         'metric':'页面数据', 'comment':'评论原文', 'transcript':'核实后的口播'}.get(kind, '来源资料')
                seconds = lambda n: f'{n:.2f}'.rstrip('0').rstrip('.') if isinstance(n, (int, float)) else str(n)
                location = (f'约{seconds(e.get("start"))}—{seconds(e.get("end"))}秒' if kind == 'clip'
                            else e.get('paragraph_id') or '')
                if kind == 'frame':
                    match = re.search(r'(\d+)$', e.get('frame_id', ''))
                    location = '第' + str(int(match.group(1))) + '张' if match else ''
                description = e.get('quote') or e.get('inspection_note') or ''
                if kind == 'metric':
                    m = r.get('metrics', {}).get(e.get('metric_key'), {})
                    description = f'{m.get("raw_display", m.get("value", ""))}；观察时间：{m.get("observed_at", "未提供")}'
                lines.append(' '.join(str(v) for v in (label, location, description) if v))
            return '\n'.join(lines)

        for module, label in MODULES.items():
            section = a.get('modules', {}).get(module, {})
            summary = section.get('summary', '')
            observations = [('观察：' if f.get('kind') == 'observation' else '推测／建议：') + f.get('text', '')
                            for f in section.get('findings', []) if f.get('text') != summary]
            text = '\n'.join([summary] + observations)
            ids = list(dict.fromkeys(ref for f in section.get('findings', []) for ref in f.get('evidence_ids', [])))
            add('视频拆解', f'{key}::module:{module}', {**base, '分析项目': label,
                '分析内容': text, '依据': refs(ids)}, '分析内容')
        for b in c.get('source_beats', []):
            token = b.get('export_id') or digest(b['locator'])[:16]
            add('视频拆解', f'{key}::source:{token}', {**base, '分析项目': '原视频 ' + b['locator'],
                '分析内容': f'画面：{b["action"]}\n观众可能会想：{b["viewer_question"]}\n这一段讲清：{b["new_information"]}',
                '依据': refs(b['evidence_ids'])}, '分析内容')
        for m in c.get('mechanisms', []):
            for field, label in [('observation', '原视频怎么拍'), ('interpretation', '为什么值得学'),
                                 ('transfer_rule', '我们可以怎么拍'), ('conditions', '什么情况下能用'),
                                 ('counterfactual', '换一种拍法会怎样'), ('test', '怎么试拍比较')]:
                add('拍法库', f'{key}::method:{m["id"]}:{field}', {**base, '拍法': m['name'],
                    '内容项目': label, '内容': m[field], '依据': refs(m['evidence_ids'])}, '内容')
        for e in a.get('elements', []):
            parts = [('template', '拍摄顺序'), ('variables', '换成自己的信息'), ('applies_to', '什么情况下能用'),
                     ('excludes', '换一种拍法'), ('materials', '所需素材'), ('performance_relation', '目前知道的效果'),
                     ('counterexamples', '还缺什么比较资料'), ('experiment', '怎么试拍比较')]
            for field, label in parts:
                value = e.get(field)
                if not value:
                    continue
                text = '\n'.join(value) if isinstance(value, list) else value
                add('拍法库', f'{key}::element:{e["id"]}:{field}', {**base, '拍法': e['name'],
                    '内容项目': label, '内容': text, '依据': refs(e.get('evidence_ids', []))}, '内容')
        script = c.get('script', {})
        method_names = {m['id']: m['name'] for m in c.get('mechanisms', [])}
        for i, b in enumerate(script.get('beats', []), 1):
            text = f'画面：{b["shot"]}\n口播：{b["spoken_text"] or "无口播"}\n字幕：{b["on_screen_text"] or "无字幕"}\n这一镜要讲清：{b["viewer_job"]}'
            text += '\n参考拍法：' + '、'.join(method_names.get(mid, mid) for mid in b['mechanism_ids'])
            add('拍摄脚本', f'{key}::shot:{i}', {**base, '镜头': i, '开始秒': b['start'], '结束秒': b['end'],
                '画面与台词': text, '开拍前准备': b['proof_needed']}, '画面与台词')
        if script:
            items = [('脚本说明', f'{script["title"]}\n目标：{script["objective"]}\n形式：{script["format"]}\n拟拍{script["duration_seconds"]}秒，属于新创作建议。'),
                     ('结尾行动提示', script['cta']), ('拍摄素材', '\n'.join(script['materials'])),
                     ('发布前核对', '\n'.join(script['claim_checks']))]
            for label, text in items:
                add('拍前准备', f'{key}::prep:{label}', {**base, '准备项目': label, '内容': text}, '内容')
        for requirement in c.get('product_requirements', []):
            text = ('已确认' if requirement['status'] == 'verified' else '待确认') + '\n'
            text += requirement['needed_for'] + '\n怎么确认：' + requirement['verification']
            add('拍前准备', f'{key}::need:{requirement.get("export_id") or digest(requirement["field"])[:16]}',
                {**base, '准备项目': requirement['field'], '内容': text}, '内容')
        for b in c.get('purchase_bridge', []):
            add('拍前准备', f'{key}::question:{b.get("export_id") or digest(b["objection"])[:16]}', {**base, '准备项目': b['objection'],
                '内容': f'加拍：{b["recommended_shot"]}\n可以这样说：{b["conditional_copy"]}\n先确认：{b["release_condition"]}',
                '依据': refs(b['evidence_ids'])}, '内容')
        for e in c.get('experiments', []):
            text = experiment_text(e)
            add('拍前准备', f'{key}::compare:{e.get("export_id") or digest(e["variable"])[:16]}',
                {**base, '准备项目': '比较拍摄效果：' + e['variable'], '内容': text}, '内容')
    creator_reports = {i['creator_key']: i for i in report.get('creators', [])}
    for key, videos in groups.items():
        r = videos[0]['record']; entry = creator_reports.get(key, {})
        a = entry.get('analysis', {}) if not entry.get('validation_errors') else {}
        label = r.get('creator_name') or '待确认博主'
        profile = a.get('modules', {}).get('profile', {}).get('summary') or '博主综合分析待完成。'
        sheets['博主汇总']['rows'].append({'博主': label, '平台': PLATFORMS.get(r['platform'], r['platform']),
            '值得学什么': profile, '账号编号': key, '我的备注': ''})
        if a.get('status') != 'complete':
            continue
        base = {'博主': label, '账号编号': key, '涉及视频': '\n'.join(a.get('covered_video_keys', []))}
        for module, title in CREATOR_MODULES.items():
            section = a.get('modules', {}).get(module, {})
            text = section.get('summary', '')
            text += ''.join('\n' + f['text'] for f in section.get('findings', []) if f.get('text') != section.get('summary'))
            add('博主分析', f'{key}::creator:{module}', {**base, '分析项目': title, '分析内容': text}, '分析内容')
        for pattern in a.get('patterns', []):
            count = pattern.get('frequency', {})
            text = '\n'.join(str(v) for v in [pattern['mechanism'],
                f'出现于{count.get("support_count", "未知")}条，参与分析{count.get("denominator", "未知")}条。',
                pattern.get('boundaries', ''), '怎么比较：' + pattern.get('experiment', '')])
            add('博主分析', f'{key}::pattern:{pattern.get("export_id") or digest(pattern["name"])[:16]}',
                {**base, '分析项目': pattern['name'], '分析内容': text}, '分析内容')
    failure_scope = 'failure:' + digest(str(Path(report_dir).resolve()))[:16]
    for failure in report.get('failures', []):
        url = failure.get('url', '')
        key = failure_scope + '::' + digest(url)[:16]
        add('拍前准备', key, {'博主': '待确认', '视频标题': url, '准备项目': '链接解析失败',
            '内容': failure.get('reason', '未取得资料'), '依据': url, '记录状态': '解析失败，待重试',
            '视频编号': key, '账号编号': ''}, '内容')
    return {'schema_version': 1, 'generated_at': now(), 'report_digest': report_digest(report), 'failure_scope': failure_scope,
            'current_video_keys': current_keys, 'current_creator_keys': list(groups),
            'sheets': list(sheets.values()), 'failures': report.get('failures', [])}


def runtime(workspace=None):
    settings = resolve_runtime(workspace)
    node = Path(settings['node']) if settings.get('node') else None
    packages = Path(settings['nodeModules']) if settings.get('nodeModules') else None
    if node is None or packages is None or not node.is_file() or not (packages / '@oai/artifact-tool/package.json').is_file():
        return None, None
    return node, packages


def output_path(root, explicit, state):
    root = Path(root).resolve()
    if explicit:
        return Path(explicit).expanduser()
    relative = state.get('output_relative')
    if relative:
        # POSIX separators make the saved location portable in either direction.
        if ntpath.isabs(relative) or Path(relative).is_absolute():
            raise ValueError('Excel相对路径无效，请显式指定 --output')
        target = root / Path(str(relative).replace('\\', '/'))
        if not target.resolve().is_relative_to(root):
            raise ValueError('Excel相对路径不能移出工作区')
        return target
    old = state.get('output')
    if old:
        normalized = str(old).replace('\\', '/')
        # Legacy manifests had only an absolute default path. Relocate that
        # known path with the workspace instead of writing back to an old disk.
        if normalized.endswith('/reports/' + FILENAME):
            return root / 'reports' / FILENAME
        path = Path(old).expanduser()
        foreign_absolute = ntpath.isabs(old) and not path.is_absolute()
        if not foreign_absolute and path.is_file():
            return path
        raise ValueError('原Excel位于此电脑不可用的外部位置，请用 --output 指定要继续更新的文件')
    return root / 'reports' / FILENAME


def organize_rows(filename, payload, previously_folded=None):
    """Keep continuation rows together and fold exact repeated auto prose.

    The authoring library does not expose row sorting. Move whole native rows,
    including personal notes and custom text columns, only for simple tables.
    Complex user objects/formulas stop the write rather than lose references.
    """
    ns = 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'
    rel = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'
    tag = lambda name: f'{{{ns}}}{name}'
    with zipfile.ZipFile(filename) as source:
        entries = {name: source.read(name) for name in source.namelist()}
    workbook = ET.fromstring(entries['xl/workbook.xml'])
    relationships = {r.attrib['Id']: r.attrib['Target'] for r in ET.fromstring(entries['xl/_rels/workbook.xml.rels'])}
    paths = {}
    for sheet in workbook.find(tag('sheets')):
        target = relationships[sheet.attrib[f'{{{rel}}}id']]
        paths[sheet.attrib['name']] = target.lstrip('/') if target.startswith('/') else posixpath.normpath('xl/' + target)
    strings = []
    if 'xl/sharedStrings.xml' in entries:
        strings = [''.join(x.itertext()) if not x.findall('.//' + tag('t')) else ''.join(t.text or '' for t in x.findall('.//' + tag('t')))
                   for x in ET.fromstring(entries['xl/sharedStrings.xml'])]

    def value(cell):
        if cell.attrib.get('t') == 's':
            return strings[int(cell.findtext(tag('v')))]
        if cell.attrib.get('t') == 'inlineStr':
            return ''.join(t.text or '' for t in cell.findall('.//' + tag('t')))
        return cell.findtext(tag('v'), '')

    formulas = [(name, f.text or '') for name, part in paths.items()
                for f in ET.fromstring(entries[part]).findall('.//' + tag('f'))]
    refers = lambda text, name: re.search(r"(?:" + re.escape(name) + r"|'"+re.escape(name)+r"')!", text) is not None
    folded, reordered = {}, []
    for spec in payload['sheets']:
        name = spec['name']
        if name in ('博主汇总', '视频索引'):
            continue
        filename_part = paths[name]
        sheet = ET.fromstring(entries[filename_part]); data = sheet.find(tag('sheetData'))
        header = next(row for row in data if row.attrib['r'] == '5')
        columns = {value(c): re.sub(r'\d+$', '', c.attrib['r']) for c in header}
        row_values = lambda row: {re.sub(r'\d+$', '', c.attrib['r']): value(c) for c in row}
        rows = [row for row in data if int(row.attrib['r']) >= 6]
        key_col = columns['记录编号']
        by_key = {row_values(row).get(key_col): row for row in rows if row_values(row).get(key_col)}
        order = [row['记录编号'] for row in spec['rows']]
        ordered = [by_key[key] for key in order if key in by_key]
        chosen = set(order)
        ordered += [row for row in rows if row_values(row).get(key_col) not in chosen]
        changed = any(int(row.attrib['r']) != i for i, row in enumerate(ordered, 6))
        if changed:
            complex_parts = any(sheet.find(tag(part)) is not None for part in ('drawing', 'legacyDrawing', 'dataValidations', 'mergeCells'))
            names = workbook.find(tag('definedNames'))
            affected_formulas = any(owner == name or refers(formula, name) for owner, formula in formulas)
            affected_names = names is not None and any(refers(n.text or '', name) for n in names)
            if affected_formulas or complex_parts or affected_names:
                raise ValueError(f'“{name}”需要将续文移到前文之后，但现有Excel含公式或自建对象。已保留原文件，请勿删除个人内容。')
            reordered.append(name)
            mapping = {int(row.attrib['r']): i for i, row in enumerate(ordered, 6)}
            for row in rows:
                data.remove(row)
            for i, row in enumerate(ordered, 6):
                row.attrib['r'] = str(i)
                for c in row:
                    c.attrib['r'] = re.sub(r'\d+$', str(i), c.attrib['r'])
                data.append(row)
            for link in sheet.findall('.//' + tag('hyperlink')):
                old = int(re.search(r'\d+$', link.attrib['ref']).group())
                link.attrib['ref'] = re.sub(r'\d+$', str(mapping.get(old, old)), link.attrib['ref'])
        if name == '拍法库':
            old_folds = set((previously_folded or {}).get(name, []))
            owned = {c['name'] for c in spec['columns']}
            private = [column for title, column in columns.items() if title == '我的备注' or title not in owned]
            seen = set(); keys = []
            for row in ordered:
                values = row_values(row); key = values.get(key_col, '')
                if key in old_folds:
                    row.attrib.pop('hidden', None)
                signature = (values.get(columns['视频编号']), values.get(columns['内容']))
                has_private = any(values.get(c) for c in private)
                if signature[1] and signature in seen and not has_private and key in chosen:
                    row.attrib['hidden'] = '1'; keys.append(key)
                else:
                    seen.add(signature)
            folded[name] = keys
            # Explain the native collapsed rows directly in the delivered workbook.
            for row in data:
                if row.attrib['r'] == '3':
                    for cell in row:
                        if cell.attrib['r'] == 'A3':
                            for child in list(cell):
                                cell.remove(child)
                            cell.attrib['t'] = 'inlineStr'
                            ET.SubElement(ET.SubElement(cell, tag('is')), tag('t')).text = '同一视频的重复说明已折叠，可展开行查看。含个人备注或自建列内容的行始终保留显示。'
        entries[filename_part] = xml_bytes(sheet, entries[filename_part])
    with zipfile.ZipFile(filename, 'w', zipfile.ZIP_DEFLATED) as target:
        for name, content in entries.items():
            target.writestr(name, content)
    return {'reordered_sheets': reordered, 'folded_rows': folded}


def finalize_links(filename, links):
    """Artifact Tool cannot calculate HYPERLINK. Add native links instead of error caches."""
    ns = 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'
    relns = 'http://schemas.openxmlformats.org/package/2006/relationships'
    docrel = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'
    with zipfile.ZipFile(filename) as source:
        entries = {name: source.read(name) for name in source.namelist()}
    workbook = ET.fromstring(entries['xl/workbook.xml'])
    rels = {r.attrib['Id']: r.attrib['Target'] for r in ET.fromstring(entries['xl/_rels/workbook.xml.rels'])}
    paths = {}
    for sheet in workbook.find(f'{{{ns}}}sheets'):
        target = rels[sheet.attrib[f'{{{docrel}}}id']]
        paths[sheet.attrib['name']] = target.lstrip('/') if target.startswith('/') else posixpath.normpath('xl/' + target)
    grouped = defaultdict(list)
    for link in links:
        grouped[paths[link['sheet']]].append(link)
    later = {'printOptions', 'pageMargins', 'pageSetup', 'headerFooter', 'rowBreaks', 'colBreaks',
             'customProperties', 'cellWatches', 'ignoredErrors', 'smartTags', 'drawing', 'legacyDrawing',
             'legacyDrawingHF', 'picture', 'oleObjects', 'controls', 'webPublishItems', 'tableParts', 'extLst'}
    for name, items in grouped.items():
        sheet = ET.fromstring(entries[name])
        relfile = posixpath.dirname(name) + '/_rels/' + posixpath.basename(name) + '.rels'
        relationships = ET.fromstring(entries[relfile]) if relfile in entries else ET.Element(f'{{{relns}}}Relationships')
        hyperlinks = sheet.find(f'{{{ns}}}hyperlinks')
        if hyperlinks is None:
            hyperlinks = ET.Element(f'{{{ns}}}hyperlinks')
            insert_at = next((i for i, child in enumerate(sheet) if child.tag.split('}')[-1] in later), len(sheet))
            sheet.insert(insert_at, hyperlinks)
        used = {r.attrib['Id'] for r in relationships}
        for item in items:
            for old in list(hyperlinks):
                if old.attrib.get('ref') == item['cell']:
                    hyperlinks.remove(old)
                    old_id = old.attrib.get(f'{{{docrel}}}id')
                    still_used = {h.attrib.get(f'{{{docrel}}}id') for h in hyperlinks}
                    if old_id not in still_used:
                        for rel in list(relationships):
                            if rel.attrib.get('Id') == old_id and rel.attrib.get('Type') == docrel + '/hyperlink':
                                relationships.remove(rel)
                                used.discard(old_id)
            n = 1
            while f'link{n}' in used:
                n += 1
            rid = f'link{n}'; used.add(rid)
            ET.SubElement(relationships, f'{{{relns}}}Relationship', {'Id': rid, 'Type': docrel + '/hyperlink',
                'Target': item['target'], 'TargetMode': 'External'})
            ET.SubElement(hyperlinks, f'{{{ns}}}hyperlink', {'ref': item['cell'], f'{{{docrel}}}id': rid})
        entries[name] = xml_bytes(sheet, entries[name])
        entries[relfile] = xml_bytes(relationships, entries.get(relfile))
    # Check owned link cells; unrelated user formulas are outside this export's scope.
    owned_cells = {name: {item['cell'] for item in items} for name, items in grouped.items()}
    for name, content in entries.items():
        if name.startswith('xl/worksheets/') and name.endswith('.xml'):
            for cell in ET.fromstring(content).iter(f'{{{ns}}}c'):
                if cell.attrib.get('t') == 'e' and cell.attrib.get('r') in owned_cells.get(name, set()):
                    raise ValueError('Excel存在公式错误，未覆盖原文件：' + name + ' ' + cell.attrib.get('r', ''))
    with zipfile.ZipFile(filename, 'w', compression=zipfile.ZIP_DEFLATED) as dest:
        for name, content in entries.items():
            dest.writestr(name, content)


def export_excel(workspace, output=None, previews=None):
    from reports import render
    root = Path(workspace).resolve()
    state = read_json(root / '.excel-export.json', {})
    target = output_path(root, output, state)
    if target.is_symlink():
        raise ValueError('Excel目标不能是符号链接')
    target = target.resolve()
    if target.suffix.lower() != '.xlsx':
        raise ValueError('Excel输出文件需要使用.xlsx扩展名')
    if target.is_symlink():
        raise ValueError('Excel目标不能是符号链接')
    target.parent.mkdir(parents=True, exist_ok=True)
    owner_files = [target.parent / ('~$' + target.name), target.parent / ('.~lock.' + target.name + '#')]
    if any(p.exists() for p in owner_files):
        raise ValueError('Excel正在被表格软件占用，请先保存并关闭后重试；原文件未被覆盖')
    errors = check_workspace(root)
    if errors:
        raise ValueError('成品文字检查未通过，Excel未改动：\n' + '\n'.join(errors))
    node, packages = runtime(root)
    with file_lock(target.parent / ('.' + target.name + '.lock'), message='这份Excel正在更新，请稍后重试'):
        render(root)
        report = read_json(root / 'reports/report.json')
        payload = project(report, root / 'reports')
        old_hash = hashlib.sha256(target.read_bytes()).hexdigest() if target.exists() else None
        cache = root / 'cache/excel'; cache.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix='build-', dir=cache) as temp:
            build = Path(temp)
            writer = build / 'excel_writer.mjs'
            shutil.copy2(Path(__file__).with_name('excel_writer.mjs'), writer)
            write_json(build / 'input.json', payload)
            if node is not None:
                env = {**os.environ, 'CODEX_NODE_MODULES':str(packages)}
                command = [str(node), str(writer), str(build / 'input.json'), str(target), str(build / 'result.xlsx')]
                result = subprocess.run(command, capture_output=True, text=True, timeout=240, encoding='utf-8', env=env)
                if result.returncode:
                    raise ValueError('Excel未更新，原文件已保留：' + (result.stderr or result.stdout)[-2500:])
                stats = {'engine':'artifact-tool', **read_json(build / 'result.json')}
            else:
                from excel_native import write_workbook
                stats = write_workbook(payload, target if target.exists() else None, build / 'result.xlsx')
            finalize_links(build / 'result.xlsx', stats.pop('links', []))
            stats.update(organize_rows(build / 'result.xlsx', payload, state.get('folded_rows')))
            current_hash = hashlib.sha256(target.read_bytes()).hexdigest() if target.exists() else None
            if current_hash != old_hash:
                raise ValueError('生成期间原Excel发生变化，已停止写入，请保存并关闭文件后重试')
            backup = None
            if target.exists():
                backup = root / 'backups/excel' / (now().replace(':', '').replace('.', '-') + '--' + target.name)
                backup.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(target, backup)
            # Stage in the target directory so the final replacement stays atomic across volumes.
            handle, stage = tempfile.mkstemp(prefix='.' + target.stem + '-', suffix='.xlsx', dir=target.parent)
            os.close(handle)
            try:
                shutil.copyfile(build / 'result.xlsx', stage)
                os.replace(stage, target)
            finally:
                Path(stage).unlink(missing_ok=True)
            state = {'output': str(target), 'updated_at': now(), 'report_digest': payload['report_digest'],
                     'sha256': hashlib.sha256(target.read_bytes()).hexdigest(), 'backup': str(backup) if backup else None,
                     **stats}
            if target.is_relative_to(root):
                state['output_relative'] = target.relative_to(root).as_posix()
            write_json(root / '.excel-export.json', state)
            if previews:
                if node is not None:
                    result = subprocess.run([str(node), str(writer), '--render-saved', str(target), str(Path(previews).resolve())],
                                            capture_output=True, text=True, timeout=120, encoding='utf-8', env=env)
                    if result.returncode:
                        raise ValueError('Excel已保存，但最终文件预览未通过：' + (result.stderr or result.stdout)[-1500:])
                    state.update(preview_format='png', preview_directory=str(Path(previews).resolve()))
                else:
                    from excel_native import render_html_previews
                    state.update(render_html_previews(target, previews))
                write_json(root / '.excel-export.json', state)
        render(root)
        return {'ok': True, **state}
