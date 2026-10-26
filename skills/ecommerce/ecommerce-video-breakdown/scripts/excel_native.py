"""Small portable XLSX writer used only when the optional Artifact Tool is absent.

No office application, Node package or third-party Python module is required.
Updates keep each unrelated ZIP member, user cell, formula and worksheet intact.
"""
import copy
import html
import math
import posixpath
import re
import zipfile
import xml.etree.ElementTree as ET
from collections import defaultdict
from pathlib import Path

NS = 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'
REL = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'
PKG = 'http://schemas.openxmlformats.org/package/2006/relationships'
CT = 'http://schemas.openxmlformats.org/package/2006/content-types'
tag = lambda name: f'{{{NS}}}{name}'


def xml_bytes(root, original=None):
    # Retain declarations referenced by mc:Ignorable, even if ElementTree sees
    # that prefix only in an attribute value rather than a node's namespace.
    namespace = root.tag[1:].split('}', 1)[0] if root.tag.startswith('{') else NS
    ET.register_namespace('', namespace)
    ET.register_namespace('r', REL)
    data = ET.tostring(root, encoding='utf-8', xml_declaration=True)
    if original:
        namespaces = re.findall(rb'xmlns:([A-Za-z_][\w.-]*)=["\']([^"\']+)["\']', original)
        for prefix, uri in namespaces:
            if b'xmlns:' + prefix + b'=' not in data:
                root.set('xmlns:' + prefix.decode(), uri.decode())
        data = ET.tostring(root, encoding='utf-8', xml_declaration=True)
    return data


def col(n):
    result = ''
    n += 1
    while n:
        n, rem = divmod(n - 1, 26)
        result = chr(65 + rem) + result
    return result


def col_index(name):
    result = 0
    for char in name:
        result = result * 26 + ord(char) - 64
    return result - 1


def part_path(owner, target):
    return target.lstrip('/') if target.startswith('/') else posixpath.normpath(posixpath.dirname(owner) + '/' + target)


def load_workbook(filename):
    with zipfile.ZipFile(filename) as source:
        entries = {name: source.read(name) for name in source.namelist()}
    workbook = ET.fromstring(entries['xl/workbook.xml'])
    relationships = {r.get('Id'): r.get('Target') for r in ET.fromstring(entries['xl/_rels/workbook.xml.rels'])}
    parts = {sheet.get('name'): part_path('xl/workbook.xml', relationships[sheet.get(f'{{{REL}}}id')])
             for sheet in workbook.find(tag('sheets'))}
    strings = []
    if 'xl/sharedStrings.xml' in entries:
        strings = [''.join(t.text or '' for t in s.findall('.//' + tag('t')))
                   for s in ET.fromstring(entries['xl/sharedStrings.xml'])]
    return entries, parts, strings


def value(cell, strings):
    if cell is None:
        return ''
    if cell.get('t') == 's':
        return strings[int(cell.findtext(tag('v')))]
    if cell.get('t') == 'inlineStr':
        return ''.join(t.text or '' for t in cell.findall('.//' + tag('t')))
    raw = cell.findtext(tag('v'), '')
    return raw


def row_values(row, strings):
    return {re.sub(r'\d+$', '', c.get('r')): value(c, strings) for c in row.findall(tag('c'))}


def get_row(data, number):
    row = data.find(f'{tag("row")}[@r="{number}"]')
    if row is None:
        row = ET.Element(tag('row'), {'r':str(number)})
        at = next((i for i, current in enumerate(data) if int(current.get('r')) > number), len(data))
        data.insert(at, row)
    return row


def set_cell(row, column, data, style=None):
    address = column + row.get('r')
    cell = row.find(f'{tag("c")}[@r="{address}"]')
    if cell is None:
        cell = ET.Element(tag('c'), {'r':address})
        at = next((i for i, current in enumerate(row) if col_index(re.sub(r'\d+$', '', current.get('r'))) > col_index(column)), len(row))
        row.insert(at, cell)
    for child in list(cell):
        cell.remove(child)
    if style is not None and cell.get('s') is None:
        cell.set('s', str(style))
    if isinstance(data, bool):
        cell.set('t', 'b')
        ET.SubElement(cell, tag('v')).text = '1' if data else '0'
    elif isinstance(data, (int, float)) and not isinstance(data, bool):
        if not math.isfinite(data):
            raise ValueError('Excel数值必须是有限数字')
        cell.attrib.pop('t', None)
        ET.SubElement(cell, tag('v')).text = str(data)
    else:
        # Text beginning '=' stays text, never an executable formula.
        text = '' if data is None else str(data)
        if len(text) > 32767:
            raise ValueError('单元格超过Excel文字上限，请拆成相邻续行')
        if re.search(r'[\x00-\x08\x0b\x0c\x0e-\x1f]',text):
            raise ValueError('单元格含不支持的控制字符，请复核原文后再导出')
        cell.set('t', 'inlineStr')
        t = ET.SubElement(ET.SubElement(cell, tag('is')), tag('t'))
        t.set('{http://www.w3.org/XML/1998/namespace}space', 'preserve')
        t.text = text
    return cell


def row_height(spec, data):
    lines = 1
    for c in spec['columns']:
        width = max(4, c.get('width', 20) * .58)
        text = str(data.get(c['name'], ''))
        wrapped = sum(max(1, math.ceil(sum(1 if ord(ch) > 255 else .55 for ch in part) / width))
                      for part in text.split('\n'))
        lines = max(lines, wrapped)
    return min(400, max(34, lines * 17 + 14))


def default_body_styles(entries):
    """An initially empty table must wrap text when its first record arrives."""
    part = 'xl/styles.xml'
    original = entries[part]
    root = ET.fromstring(original)
    xfs = root.find(tag('cellXfs')); fills = root.find(tag('fills'))
    body = next((i for i, xf in enumerate(xfs)
                 if xf.get('fillId','0') == '0' and xf.find(tag('alignment')) is not None
                 and xf.find(tag('alignment')).get('wrapText') in ('1','true')
                 and xf.find(tag('alignment')).get('vertical') == 'top'), None)
    if body is None:
        xf = copy.deepcopy(xfs[0])
        old = xf.find(tag('alignment'))
        if old is not None: xf.remove(old)
        xf.set('applyAlignment','1')
        ET.SubElement(xf,tag('alignment'),{'vertical':'top','wrapText':'1'})
        body = len(xfs); xfs.append(xf)
    note_fill = next((i for i, fill in enumerate(fills)
                      if fill.find('.//' + tag('fgColor')) is not None
                      and fill.find('.//' + tag('fgColor')).get('rgb') == 'FFFFF6DB'), None)
    if note_fill is None:
        note_fill = len(fills)
        fill = ET.SubElement(fills,tag('fill'))
        pattern = ET.SubElement(fill,tag('patternFill'),{'patternType':'solid'})
        ET.SubElement(pattern,tag('fgColor'),{'rgb':'FFFFF6DB'})
        ET.SubElement(pattern,tag('bgColor'),{'indexed':'64'})
    note = next((i for i,xf in enumerate(xfs) if xf.get('fillId') == str(note_fill)
                 and xf.find(tag('alignment')) is not None
                 and xf.find(tag('alignment')).get('wrapText') in ('1','true')), None)
    if note is None:
        xf=copy.deepcopy(xfs[body]);xf.set('fillId',str(note_fill));xf.set('applyFill','1')
        note=len(xfs);xfs.append(xf)
    xfs.set('count',str(len(xfs)));fills.set('count',str(len(fills)))
    entries[part]=xml_bytes(root,original)
    return body,note


def fresh_sheet(spec, index):
    root = ET.Element(tag('worksheet'))
    ET.SubElement(root, tag('dimension'), {'ref':'A2:' + col(len(spec['columns'])-1) + str(max(6, len(spec['rows'])+5))})
    views = ET.SubElement(root, tag('sheetViews'))
    view = ET.SubElement(views, tag('sheetView'), {'workbookViewId':'0', 'showGridLines':'0'})
    frozen = 1 if index == 0 else 2
    ET.SubElement(view, tag('pane'), {'xSplit':str(frozen), 'ySplit':'5', 'topLeftCell':col(frozen)+'6', 'activePane':'bottomRight', 'state':'frozen'})
    ET.SubElement(view, tag('selection'), {'pane':'bottomRight', 'activeCell':col(frozen)+'6', 'sqref':col(frozen)+'6'})
    ET.SubElement(root, tag('sheetFormatPr'), {'defaultRowHeight':'15'})
    widths = ET.SubElement(root, tag('cols'))
    for i, c in enumerate(spec['columns'], 1):
        ET.SubElement(widths, tag('col'), {'min':str(i), 'max':str(i), 'width':str(c['width']), 'customWidth':'1'})
    data = ET.SubElement(root, tag('sheetData'))
    title = get_row(data, 2); title.set('ht','26'); title.set('customHeight','1')
    set_cell(title, 'A', spec['name'], 1)
    set_cell(get_row(data, 3), 'A', '新增链接后更新同一文件。个人备注、自建列及工作表保留。', 0)
    header = get_row(data, 5); header.set('ht','32'); header.set('customHeight','1')
    for i, c in enumerate(spec['columns']):
        set_cell(header, col(i), c['name'], 2)
    ET.SubElement(root, tag('pageMargins'), {'left':'.3', 'right':'.3', 'top':'.4', 'bottom':'.4', 'header':'.2', 'footer':'.2'})
    parts = ET.SubElement(root, tag('tableParts'), {'count':'1'})
    ET.SubElement(parts, tag('tablePart'), {f'{{{REL}}}id':'table'})
    return root


STYLES = f'''<styleSheet xmlns="{NS}">
<fonts count="3"><font><sz val="11"/><color rgb="FF24344A"/><name val="Arial"/></font><font><b/><sz val="16"/><color rgb="FF253E5D"/><name val="Arial"/></font><font><b/><sz val="11"/><color rgb="FFFFFFFF"/><name val="Arial"/></font></fonts>
<fills count="4"><fill><patternFill patternType="none"/></fill><fill><patternFill patternType="gray125"/></fill><fill><patternFill patternType="solid"><fgColor rgb="FF304C74"/><bgColor indexed="64"/></patternFill></fill><fill><patternFill patternType="solid"><fgColor rgb="FFFFF6DB"/><bgColor indexed="64"/></patternFill></fill></fills>
<borders count="1"><border><left/><right/><top/><bottom/><diagonal/></border></borders><cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>
<cellXfs count="5"><xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/><xf numFmtId="0" fontId="1" fillId="0" borderId="0" xfId="0" applyFont="1"/><xf numFmtId="0" fontId="2" fillId="2" borderId="0" xfId="0" applyFont="1" applyFill="1" applyAlignment="1"><alignment horizontal="center" vertical="center" wrapText="1"/></xf><xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0" applyAlignment="1"><alignment vertical="top" wrapText="1"/></xf><xf numFmtId="0" fontId="0" fillId="3" borderId="0" xfId="0" applyFill="1" applyAlignment="1"><alignment vertical="top" wrapText="1"/></xf></cellXfs>
<cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles><tableStyles count="0" defaultTableStyle="TableStyleLight9" defaultPivotStyle="PivotStyleLight16"/></styleSheet>'''


def new_workbook(payload):
    entries = {'xl/styles.xml':STYLES.encode()}
    workbook = ET.Element(tag('workbook')); sheets = ET.SubElement(workbook, tag('sheets'))
    rels = ET.Element(f'{{{PKG}}}Relationships')
    types = ET.Element(f'{{{CT}}}Types')
    ET.SubElement(types, f'{{{CT}}}Default', {'Extension':'rels','ContentType':'application/vnd.openxmlformats-package.relationships+xml'})
    ET.SubElement(types, f'{{{CT}}}Default', {'Extension':'xml','ContentType':'application/xml'})
    for part, kind in [('workbook','application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml'),
                       ('styles','application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml')]:
        ET.SubElement(types, f'{{{CT}}}Override', {'PartName':'/xl/'+part+'.xml','ContentType':kind})
    parts = {}
    for index, spec in enumerate(payload['sheets'], 1):
        name = spec['name']; rid = 'sheet'+str(index); part = f'xl/worksheets/sheet{index}.xml'
        ET.SubElement(sheets, tag('sheet'), {'name':name,'sheetId':str(index),f'{{{REL}}}id':rid})
        ET.SubElement(rels, f'{{{PKG}}}Relationship', {'Id':rid,'Type':REL+'/worksheet','Target':f'worksheets/sheet{index}.xml'})
        ET.SubElement(types, f'{{{CT}}}Override', {'PartName':'/'+part,'ContentType':'application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml'})
        ET.SubElement(types, f'{{{CT}}}Override', {'PartName':f'/xl/tables/table{index}.xml','ContentType':'application/vnd.openxmlformats-officedocument.spreadsheetml.table+xml'})
        entries[part] = xml_bytes(fresh_sheet(spec, index-1))
        sheet_rels = ET.Element(f'{{{PKG}}}Relationships')
        ET.SubElement(sheet_rels, f'{{{PKG}}}Relationship', {'Id':'table','Type':REL+'/table','Target':f'../tables/table{index}.xml'})
        entries[f'xl/worksheets/_rels/sheet{index}.xml.rels'] = xml_bytes(sheet_rels)
        table = ET.Element(tag('table'), {'id':str(index),'name':'EcommerceVideo'+str(index-1),'displayName':'EcommerceVideo'+str(index-1),
                'ref':f'A5:{col(len(spec["columns"])-1)}6','totalsRowShown':'0'})
        ET.SubElement(table, tag('autoFilter'), {'ref':table.get('ref')})
        columns = ET.SubElement(table, tag('tableColumns'), {'count':str(len(spec['columns']))})
        for i, c in enumerate(spec['columns'], 1):
            ET.SubElement(columns, tag('tableColumn'), {'id':str(i),'name':c['name']})
        ET.SubElement(table, tag('tableStyleInfo'), {'name':'TableStyleLight9','showFirstColumn':'0','showLastColumn':'0','showRowStripes':'1','showColumnStripes':'0'})
        entries[f'xl/tables/table{index}.xml'] = xml_bytes(table)
        parts[name] = part
    ET.SubElement(rels, f'{{{PKG}}}Relationship', {'Id':'styles','Type':REL+'/styles','Target':'styles.xml'})
    entries['xl/workbook.xml'] = xml_bytes(workbook)
    entries['xl/_rels/workbook.xml.rels'] = xml_bytes(rels)
    entries['[Content_Types].xml'] = xml_bytes(types)
    package = ET.Element(f'{{{PKG}}}Relationships')
    ET.SubElement(package, f'{{{PKG}}}Relationship', {'Id':'workbook','Type':REL+'/officeDocument','Target':'xl/workbook.xml'})
    entries['_rels/.rels'] = xml_bytes(package)
    return entries, parts, []


def write_workbook(payload, existing, output):
    fresh = not existing or not Path(existing).is_file()
    entries, parts, strings = new_workbook(payload) if fresh else load_workbook(existing)
    body_style,note_style = default_body_styles(entries)
    stats = {'engine':'portable-ooxml', 'added':{},'updated':{},'retained':{},'counts':{},'failures':len(payload.get('failures',[])), 'links':[]}
    managed = {}
    current_videos = set(payload['current_video_keys']); current_creators = set(payload['current_creator_keys'])
    for index, spec in enumerate(payload['sheets']):
        name = spec['name']
        if name not in parts:
            raise ValueError(f'现有Excel缺少“{name}”，未覆盖原文件')
        part = parts[name]; original = entries[part]; sheet = ET.fromstring(original); data = sheet.find(tag('sheetData'))
        header = data.find(f'{tag("row")}[@r="5"]')
        if header is None:
            raise ValueError(f'“{name}”缺少第5行表头')
        headers = {v:k for k,v in row_values(header,strings).items() if v}
        if len(headers) != sum(bool(v) for v in row_values(header,strings).values()):
            raise ValueError(f'“{name}”存在重复表头')
        for c in spec['columns']:
            if c['name'] not in headers: raise ValueError(f'“{name}”缺少列“{c["name"]}”')
        key_name = '账号编号' if name == '博主汇总' else '记录编号'; key_col = headers[key_name]
        rows = {}; last = 5; styles = {}
        for row in data:
            number = int(row.get('r'))
            if number < 6: continue
            values = row_values(row, strings)
            if any(v != '' for v in values.values()): last = max(last,number)
            key = values.get(key_col)
            if not key:
                owned = [c['name'] for c in spec['columns'] if c['name'] not in ('我的备注',key_name)]
                if any(values.get(headers[c]) not in ('',None) for c in owned):
                    raise ValueError(f'“{name}”第{number}行缺少{key_name}，未覆盖原文件')
                continue
            if key in rows: raise ValueError(f'“{name}”记录编号重复：{key}')
            rows[key] = row
            if not styles:
                styles = {re.sub(r'\d+$','',c.get('r')):c.get('s') for c in row}
        incoming = [str(r.get(key_name,'')) for r in spec['rows']]
        if any(not k for k in incoming) or len(set(incoming)) != len(incoming):
            raise ValueError(f'“{name}”导出编号为空或重复')
        incoming_set = set(incoming)
        for key,row in rows.items():
            values = row_values(row,strings)
            scoped = ((values.get(headers.get('账号编号')) in current_creators) if name == '博主分析'
                      else values.get(headers.get('视频编号')) in current_videos) or key.startswith(payload.get('failure_scope','')+'::')
            if '记录状态' in headers and scoped and key not in incoming_set:
                set_cell(row,headers['记录状态'],'历史保留，本次不采用',styles.get(headers['记录状态'],3 if fresh else 0))
        stats['added'][name] = sum(k not in rows for k in incoming)
        stats['updated'][name] = len(incoming)-stats['added'][name]
        for item in spec['rows']:
            key = str(item[key_name]); new = key not in rows
            if new:
                last += 1; rows[key] = get_row(data,last)
            row = rows[key]
            for c in spec['columns']:
                title = c['name']; column = headers[title]
                if title == '我的备注' and not new: continue
                raw = item.get(title,'')
                if title == '原视频链接' and str(raw).startswith(('https://','http://')):
                    stats['links'].append({'sheet':name,'cell':column+row.get('r'),'target':raw}); raw='打开原视频'
                elif title == '详细报告' and raw:
                    stats['links'].append({'sheet':name,'cell':column+row.get('r'),'target':Path(raw).resolve().as_uri()}); raw='查看图文与原片'
                default_style = note_style if title == '我的备注' else body_style
                set_cell(row,column,raw,styles.get(column) or default_style)
            height_values = dict(item)
            saved_values = row_values(row, strings)
            height_columns = list(spec['columns'])
            known = {c['name'] for c in height_columns}
            for title,column in headers.items():
                if title == '我的备注' or title not in known:
                    height_values[title] = saved_values.get(column,'')
                    if title not in known: height_columns.append({'name':title,'width':30})
            height = max(float(row.get('ht','0')), row_height({'columns':height_columns},height_values))
            row.set('ht',str(min(400,height))); row.set('customHeight','1')
        stats['counts'][name]=len(rows);stats['retained'][name]=len(rows)-len(incoming)
        # Update only our native table bounds, keeping additional user columns
        # outside the table and all custom cells/formulas untouched.
        relfile=posixpath.dirname(part)+'/_rels/'+posixpath.basename(part)+'.rels'
        relationships=ET.fromstring(entries[relfile]) if relfile in entries else None
        table_part=None
        if relationships is not None:
            for relationship in relationships:
                if relationship.get('Type') != REL+'/table':continue
                path=part_path(part,relationship.get('Target'))
                table=ET.fromstring(entries[path])
                if table.get('name') == 'EcommerceVideo'+str(index):
                    table_part=(path,table);break
        if table_part is None: raise ValueError(f'“{name}”的数据表已删除或改名，未覆盖原文件')
        path,table=table_part; old_range=table.get('ref'); end_column=re.search(r':([A-Z]+)\d+$',old_range).group(1)
        table.set('ref',f'A5:{end_column}{max(6,last)}')
        auto=table.find(tag('autoFilter'))
        if auto is not None:auto.set('ref',table.get('ref'))
        entries[path]=xml_bytes(table,entries[path])
        dimension=sheet.find(tag('dimension'))
        if dimension is not None:dimension.set('ref',f'A2:{col(max(col_index(c) for c in headers.values()))}{max(6,last)}')
        entries[part]=xml_bytes(sheet,original)
        managed[name]=(sheet,data,headers,rows,part,original)
    totals=defaultdict(lambda:{'all':0,'done':0})
    sheet,data,headers,rows,_,_=managed['视频索引']
    for row in rows.values():
        values=row_values(row,strings); creator=values.get(headers['账号编号']); totals[creator]['all']+=1
        if values.get(headers['分析状态'])=='已分析':totals[creator]['done']+=1
    sheet,data,headers,rows,part,original=managed['博主汇总']
    for key,row in rows.items():
        total=totals[key]
        for name,number in [('归档视频数',total['all']),('已分析视频数',total['done']),('待补视频数',total['all']-total['done'])]:
            set_cell(row,headers[name],number)
    entries[part]=xml_bytes(sheet,original)
    Path(output).parent.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(output,'w',zipfile.ZIP_DEFLATED) as target:
        for name,content in entries.items():target.writestr(name,content)
    return stats


def render_html_previews(filename, directory):
    """Read saved native data; do not claim a PNG preview without its renderer."""
    entries, parts, strings = load_workbook(filename)
    directory=Path(directory);directory.mkdir(parents=True,exist_ok=True);links=[]
    css='body{font:16px/1.6 system-ui,sans-serif;color:#24344a;margin:24px}a{color:#265dad}table{border-collapse:collapse}th,td{padding:10px;border:1px solid #d2dbe7;text-align:left;vertical-align:top;white-space:pre-wrap;min-width:100px;max-width:640px;overflow-wrap:anywhere}th{background:#304c74;color:white}.scroll{overflow:auto}h1{font-size:24px}'
    def page(title,body):return '<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><style>'+css+'</style><title>'+html.escape(title)+'</title><body>'+body+'</body></html>'
    for index,(name,part) in enumerate(parts.items(),1):
        sheet=ET.fromstring(entries[part]); data=sheet.find(tag('sheetData')); header=data.find(f'{tag("row")}[@r="5"]')
        if header is None:continue
        headers=row_values(header,strings);columns=sorted(headers,key=col_index);body='<h1>'+html.escape(name)+'</h1><p>从最终保存的Excel读取。重复的隐藏行未展开。</p><div class="scroll"><table><thead><tr>'+''.join('<th>'+html.escape(headers[c])+'</th>' for c in columns)+'</tr></thead><tbody>'
        for row in data:
            if int(row.get('r'))<6 or row.get('hidden') in ('1','true'):continue
            values=row_values(row,strings)
            if not any(values.values()):continue
            body+='<tr>'+''.join('<td>'+html.escape(str(values.get(c,'')))+'</td>' for c in columns)+'</tr>'
        filename_part=f'sheet-{index}.html'; (directory/filename_part).write_text(page(name,body+'</tbody></table></div>'),encoding='utf-8')
        links.append((name,filename_part))
    index='<h1>Excel数据预览</h1><p>当前电脑没有可用的图片表格渲染器。本页展示最终Excel中的真实文字数据，不冒充Excel软件截图。</p><ul>'+''.join('<li><a href="'+file+'">'+html.escape(name)+'</a></li>' for name,file in links)+'</ul>'
    (directory/'index.html').write_text(page('Excel数据预览',index),encoding='utf-8')
    return {'preview_format':'html','preview_directory':str(directory.resolve()),'preview_sheets':len(links)}
