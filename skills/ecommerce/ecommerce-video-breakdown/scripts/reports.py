"""Evidence-first static reports. Analysis is authored by Codex, never fabricated here."""
import html
import hashlib
import json
import shutil
from collections import defaultdict
from pathlib import Path
from datetime import datetime, timezone, timedelta
from urllib.parse import urlsplit, urlunsplit
from archive import Archive, digest, now, read_json, relative_file, write_json
from analysis import MODULES, CREATOR_MODULES, validate_video, validate_creator, read_analysis
from quality import mode, quality, narration_allowed, MODE_LABELS, QUALITY_LABELS
from creation_reports import NAV as CREATION_NAV, STYLE as CREATION_STYLE, INTERACTIONS, available as creation_available, creation_html, creation_markdown, collection, md

STATUS = {'ready': '可分析', 'needs_review': '待确认来源／博主', 'needs_transcript': '待补全文',
          'complete': '拆解与创作包已完成', 'pending': '待分析', 'invalid': '分析待复核'}
PLATFORM_LABELS = {'douyin':'抖音','bilibili':'B站','xiaohongshu':'小红书'}
SOURCE_LABELS = {'imported_transcript':'导入文字稿','whisper_local':'本地Whisper转录','browser_media_audio_plus_local_whisper':'浏览器真实音频＋本地Whisper',
                 'subtitle':'平台字幕','yt_dlp_subs':'平台字幕','ai_conclusion':'平台AI摘要（非全文）'}


def esc(value):
    return html.escape(str(value), quote=True)


def public_url(raw):
    u = urlsplit(raw)
    if u.scheme not in ('http', 'https'):
        return '#'
    from urllib.parse import parse_qs, urlencode
    part = parse_qs(u.query).get('p') if 'bilibili.com' in (u.hostname or '') else None
    return urlunsplit((u.scheme, u.netloc, u.path, urlencode({'p': part[0]}) if part else '', ''))


def local_time(value):
    try:
        return datetime.fromisoformat(value.replace('Z','+00:00')).astimezone(timezone(timedelta(hours=8))).strftime('%Y-%m-%d %H:%M:%S（上海）')
    except (ValueError,TypeError):
        return str(value or '未提供')


STYLE = '''
:root{--ink:#142f2e;--muted:#5e7270;--line:#d6e3de;--paper:#f4f7f3;--accent:#126958;--warm:#ad612b}*{box-sizing:border-box}html{scroll-behavior:smooth}body{margin:0;background:var(--paper);color:var(--ink);font:16px/1.75 -apple-system,BlinkMacSystemFont,"PingFang SC","Microsoft YaHei",sans-serif}a{color:var(--accent);text-underline-offset:4px;overflow-wrap:anywhere}header{padding:28px max(24px,calc((100vw - 1180px)/2));background:#143e36;color:#f4f7ef}header a{color:#d7ebbd}header .eyebrow{font-size:12px;letter-spacing:.15em;color:#cadcb5}h1{font-size:clamp(25px,3.6vw,42px);line-height:1.3;max-width:960px;margin:10px 0 14px}h2{font-size:24px;line-height:1.4;margin:0 0 16px}h3{font-size:19px;margin:16px 0 8px}p{margin:8px 0 14px}main{max-width:1228px;margin:32px auto;padding:0 24px}.layout{display:grid;grid-template-columns:205px minmax(0,1fr);gap:36px}aside{align-self:start;position:sticky;top:20px;font-size:14px}aside a{display:block;padding:7px 0;text-decoration:none}article{min-width:0}section{background:#fff;padding:28px;margin-bottom:22px;border-top:2px solid var(--line);scroll-margin-top:20px}section:target, p:target,figure:target{outline:3px solid #d2b76f;outline-offset:5px}.muted,.small{color:var(--muted)}.small{font-size:13px}.stats{display:flex;gap:32px;flex-wrap:wrap;padding:22px 0;border-bottom:1px solid var(--line);margin-bottom:24px}.stats strong{font-size:32px;display:block;line-height:1.3}.badge{display:inline-block;padding:2px 10px;border:1px solid var(--line);border-radius:3px;font-size:12px;margin:2px 4px 2px 0;background:#f0f6f0}.warning{border-left:4px solid #bd8d46;padding:12px 16px;background:#fff7e7;color:#684b22}.filters{display:flex;gap:12px;margin:24px 0;flex-wrap:wrap}input,select,button{font:inherit;border:1px solid #b3c9be;background:#fff;padding:9px 12px;max-width:100%;border-radius:3px}input{flex:1;min-width:180px}button{cursor:pointer;color:var(--accent)}.table-scroll{overflow:auto}table{border-collapse:collapse;width:100%;font-size:14px}td,th{text-align:left;padding:14px 12px;border-bottom:1px solid var(--line);vertical-align:top}th{color:var(--muted);font-weight:500}td.title{min-width:230px}ul{padding-left:22px}.finding{padding:14px 0;border-bottom:1px solid #edf1ed}.finding:last-child{border:0}.refs a{display:inline-block;margin-right:12px;font-size:13px}.gallery{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:16px}figure{margin:0;min-width:0}figure img{width:100%;max-height:480px;object-fit:contain;background:#f0f3ed;border:1px solid var(--line)}figcaption{font-size:13px;color:var(--muted);overflow-wrap:anywhere}.transcript p{white-space:pre-wrap;padding:10px 0;border-bottom:1px solid #edf1ed}.pid{display:inline-block;min-width:60px;color:var(--muted);font:12px monospace}pre{white-space:pre-wrap;overflow-wrap:anywhere;background:#f3f6f0;padding:16px}code{font-size:13px;overflow-wrap:anywhere}details summary{cursor:pointer;color:var(--accent)}footer{max-width:1180px;margin:35px auto;padding:24px;border-top:1px solid var(--line);font-size:12px;color:var(--muted)}[hidden]{display:none!important}.empty{padding:24px;color:var(--muted)}@media(max-width:700px){header{padding:22px 18px}main{padding:0 14px;margin:20px auto}.layout{display:block}aside{position:static;display:flex;gap:14px;overflow-x:auto;margin-bottom:18px;padding-bottom:10px;white-space:nowrap;border-bottom:1px solid var(--line)}aside a{display:inline-block}section{padding:20px 16px}h2{font-size:21px}.stats{gap:20px}.stats strong{font-size:26px}.gallery{grid-template-columns:1fr}.filters{gap:8px}td.title{min-width:190px}}@media print{aside,.filters,button{display:none}header{background:white;color:black}.layout{display:block}section{break-inside:avoid}}
'''
STYLE += '''@media(max-width:700px){.table-scroll{overflow:visible}table,tbody,tr,td{display:block;width:100%}thead{display:none}tr{padding:14px 0;border-bottom:1px solid var(--line)}td{border:0;padding:5px 0}.table-scroll td.title{min-width:0;font-size:16px;font-weight:600}td:nth-child(3)::before{content:"状态：";color:var(--muted)}td:nth-child(4)::before{content:"资料：";color:var(--muted)}}'''


STYLE += 'article,section,footer{overflow-wrap:anywhere}figure img{height:420px}' + CREATION_STYLE


def page(title, body, generated, depth=0, subtitle='商品种草 · 测评 · 带货 | 以证据拆解内容'):
    prefix = '../' * depth
    return f'''<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{esc(title)} · 电商视频拆解</title><link rel="stylesheet" href="{prefix}style.css"></head><body><header><div class="eyebrow">ECOMMERCE / CONTENT DISTILLERY</div><h1>{esc(title)}</h1><p>{esc(subtitle)}</p><a href="{prefix}index.html">视频与博主索引</a></header><main>{body}</main><footer>生成于 {esc(local_time(generated))} · 报告版本 {digest(generated)[:10]} · 画面里看到的、分析提出的建议和实际成交数据分别说明。</footer></body></html>'''


def section_html(key, label, section, evidence):
    findings = ''
    for f in section.get('findings', []):
        refs = ''.join(f'<a href="#e-{esc(ref)}">证据 {esc(ref)}</a>' for ref in f.get('evidence_ids', []) if ref in evidence)
        findings += f'<div class="finding"><span class="badge">{esc("观察" if f.get("kind")=="observation" else "假设")}</span><span class="badge">置信程度：{esc({"high":"高","medium":"中","low":"低"}.get(f.get("confidence"),"待判断"))}</span><p>{esc(f.get("text", ""))}</p><div class="refs">{refs}</div></div>'
    summary=section.get('summary','')
    summary_html='' if any(f.get('text')==summary for f in section.get('findings',[])) else f'<p>{esc(summary)}</p>'
    return f'<section id="{key}"><h2>{label}</h2>{summary_html}{findings}</section>'


def element_html(element, references='', coverage='这一条里出现过；同一博主其它视频是否也用，见博主归档。'):
    labels = {'problem':'解决的问题', 'template':'照着这个顺序拍', 'variables':'换成自己商品的哪些信息', 'applies_to':'什么情况下能用',
              'excludes':'换一种拍法会怎样', 'materials':'所需素材', 'experiment':'怎么试拍比较',
              'performance_relation':'是否知道效果更好', 'counterexamples':'还缺什么比较资料'}
    fields = ''
    values={**element,'performance_relation':element.get('performance_relation') or '还没有其它视频的数据能说明这种拍法效果更好。',
            'counterexamples':element.get('counterexamples') or '还没有表现较差的视频作比较，建议先用自己的商品试拍。'}
    fields += f'<p><strong>出现范围</strong>：{esc(coverage)}</p>'
    for k,label in labels.items():
        if k in values:
            value = values[k]
            fields += f'<p><strong>{label}</strong>：{esc("、".join(str(x) for x in value) if isinstance(value,list) else value)}</p>'
    return f'<section><h2>复用元素 · {esc(element["name"])}</h2>{fields}<div class="refs">{references}</div></section>'


def video_body(record, analysis, errors, out):
    valid = analysis.get('status') == 'complete' and not errors
    marker = '<p class="warning">合成电商验收示例：文字、商品、指标均为测试素材，不能作为真实爆款案例。</p>' if record.get('is_synthetic') else ''
    creative = creation_available(analysis, errors)
    warning = '' if valid else '<div class="warning">当前为资料／草稿页，证据与创作包尚待核对。以下仅展示原始资料。</div>'
    if not creative and (valid or not analysis.get('creation')):
        warning += '<p class="warning">旧版分析资料：尚无通过校验的创作包，请补齐机制、商品条件与逐镜头脚本后再用于创作。</p>'
    nav = ''.join(f'<a href="#{key}">{label}</a>' for key,label in CREATION_NAV) if creative else ''
    nav += ''.join(f'<a href="#{k}">{label}</a>' for k, label in MODULES.items()) if valid else ''
    adopted=narration_allowed(record)
    narration_label='完整文字稿' if adopted else '未采用的语音识别结果'
    nav += f'<a href="#evidence">证据索引</a><a href="#caption">笔记正文</a><a href="#transcript">{narration_label}</a>'
    source_link = '合成示例无原视频链接' if record.get('is_synthetic') else f'<a href="{esc(public_url(record["source_url"]))}" target="_blank" rel="noreferrer">打开原视频</a>'
    metadata = f'<section><span class="badge">{esc(PLATFORM_LABELS.get(record["platform"],record["platform"]))}</span><span class="badge">{esc(STATUS.get(record["status"],record["status"]))}</span><p>博主：{esc(record["creator_name"] or "待确认")} · 转录：{esc(SOURCE_LABELS.get(record["transcript_source"],record["transcript_source"]))}</p><p>{source_link} · <a href="../creators/{esc(record["creator_key"])}.html">博主全部归档</a> · <a href="{esc(record["video_key"])}.md">Markdown</a> · <a href="{esc(record["video_key"])}.json">JSON</a></p><p class="small">{"已有原始口播时间轴，边界仍需复核。" if record["segments"] else "没有可靠的口播时间记录；下文标清原视频位置和新脚本时间，两者不同。"}</p></section>'
    evidence = {e['id']: e for e in analysis.get('evidence', [])} if valid else {}
    q=quality(record)
    analysis_basis = f'<section id="analysis-basis"><h2>本次分析依据</h2><span class="badge">{esc(MODE_LABELS[mode(record)])}</span><p>口播状态：{esc(QUALITY_LABELS.get(q["status"],q["status"]))}</p><p>{esc(q["reason"])}</p><p class="small">截图时间方便回看原视频，不代表每次剪辑的时间。没有听辨声音时，不评价配乐和语速。</p></section>'
    sections = ''.join(section_html(k, label, analysis['modules'][k], evidence) for k, label in MODULES.items()) if valid else ''
    media_html = ''
    media = record.get('media')
    if isinstance(media, dict):
        try:
            src = relative_file(out.parent, media['path'])
            if src.is_file() and hashlib.sha256(src.read_bytes()).hexdigest() == media.get('sha256'):
                suffix = src.suffix.lower()
                if suffix not in ('.mp4','.webm','.mov','.m4v','.ogv'):
                    suffix = '.mp4'
                target = out / 'media' / (record['video_key'] + '--source' + suffix)
                target.parent.mkdir(exist_ok=True)
                shutil.copy2(src, target)
                media_html = f'<h3 id="source-media">原片本地视频</h3><p class="small">原片附件 · 时长 {esc(media.get("duration", "待确认"))} 秒。此播放器用于核对原片证据，拟拍脚本使用独立时间轴。</p><video id="source-player" class="source-player" controls playsinline preload="metadata" tabindex="0" src="../media/{esc(target.name)}">浏览器无法播放时，可通过下方链接打开本地附件。</video><p><a href="../media/{esc(target.name)}">打开原片本地附件</a></p><p id="source-player-status" class="small" role="status" aria-live="polite">使用片段定位按钮后，手动播放核对；到片段末尾会暂停。</p>'
        except (KeyError, ValueError, OSError):
            media_html = ''
    refs = ''
    for eid, e in evidence.items():
        kind = e['type']
        if kind == 'transcript':
            location = f'<a href="#{esc(e["paragraph_id"])}">原文 {esc(e["paragraph_id"])}</a>：“{esc(e["quote"])}”'
        elif kind == 'frame':
            location = f'<a href="#{esc(e["frame_id"])}">查看画面 {esc(e["frame_id"])}</a> · {esc(e.get("inspection_note", ""))}'
        elif kind == 'clip':
            channels='、'.join({'visual':'画面','audio':'音轨'}.get(c,c) for c in e.get('channels',[]))
            location = f'原片片段 {esc(e.get("start"))}–{esc(e.get("end"))} 秒 · 已检查：{esc(channels)} · {esc(e.get("inspection_note", ""))}'
            if media_html:
                location += f'<p><a href="#source-player">查看原片播放器</a> <button class="clip-button" type="button" data-clip-start="{esc(e["start"])}" data-clip-end="{esc(e["end"])}">定位此原片片段</button></p>'
        elif kind == 'metric':
            metric = record['metrics'][e['metric_key']]
            label = {'views':'播放量','likes':'点赞','comments':'评论数','favorites':'收藏','shares':'分享'}.get(e['metric_key'],e['metric_key'])
            display=metric.get('raw_display') or metric['value']
            location = f'{esc(label)}：{esc(display)}{"（约数）" if metric.get("approximate") else ""} · 来源：{esc(public_url(metric["source"]))} · 观察时间：{esc(local_time(metric["observed_at"]))}'
        elif kind in ('title','caption'):
            location=f'<a href="#{"caption" if kind=="caption" else "analysis-basis"}">{"笔记正文" if kind=="caption" else "原始标题"}</a>：“{esc(e["quote"])}”'
        else:
            location = esc(e.get('quote', ''))
        refs += f'<div class="finding" id="e-{esc(eid)}"><strong>{esc(eid)}</strong> · {location}</div>'
    gallery = ''
    for frame in record['frames']:
        src = relative_file(out.parent, frame['path'])
        target = out / 'media' / (record['video_key'] + '--' + frame['id'] + src.suffix)
        target.parent.mkdir(exist_ok=True)
        if src.is_file():
            shutil.copy2(src, target)
            gallery += f'<figure id="{esc(frame["id"])}"><a href="../media/{esc(target.name)}"><img src="../media/{esc(target.name)}" alt="原解析器关键帧 {esc(frame["id"])}" loading="lazy"></a><figcaption>{esc(frame["id"])} · 上游时间：{esc(frame.get("timestamp") if frame.get("timestamp") is not None else "未提供")}</figcaption></figure>'
    evidence_section = f'<section id="evidence"><h2>证据索引</h2>{media_html}{refs or "<p class=muted>尚未登记分析证据。</p>"}<div class="gallery">{gallery}</div></section>'
    raw = ''.join(f'<p id="{esc(p["id"])}"><span class="pid">{esc(p["id"])}</span>{esc(p["text"])}</p>' for p in record['paragraphs'])
    caption=f'<section id="caption"><h2>笔记正文</h2><p style="white-space:pre-wrap">{esc(record.get("note_caption") or "未取得笔记正文。")}</p><p class="small">标题与正文是发布者的书面表达，不能冒充视频口播。来源：{esc(public_url(record.get("caption_source",record["source_url"])))} · 采集：{esc(local_time(record.get("caption_observed_at")))}</p></section>'
    note='保留原文，不套用其他领域的纠错词库。作者声称仍需独立核验。' if adopted else '以下仅为原始识别记录，不作为商品口播或完整文字稿引用。不可用转录不等于已证明视频没有人声。'
    transcript = f'<section id="transcript" class="transcript"><h2>{narration_label}</h2><p class="warning">{note}</p>{raw or "未取得识别文字。"}</section>'
    elements = ''
    if valid and analysis.get('elements'):
        for element in analysis['elements']:
            links=' '.join(f'<a href="#e-{esc(ref)}">原始证据 {esc(ref)}</a>' for ref in element['evidence_ids'])
            elements += element_html(element, links)
    creation = creation_html(analysis['creation']) if creative else ''
    return f'{marker}{warning}<div class="layout"><aside>{nav}</aside><article>{metadata}{creation}{analysis_basis}{sections}{elements}{evidence_section}{caption}{transcript}</article></div>{INTERACTIONS}'


def markdown_video(record, analysis, errors):
    lines = [f'# {md(record["title"])}', '', f'博主：{md(record["creator_name"] or "待确认")} / {md(record["platform"])}',
             f'来源：{public_url(record["source_url"])}', '']
    if record.get('is_synthetic'):
        lines += ['**合成验收示例，不能作为真实爆款案例。**', '']
    if errors or analysis.get('status') != 'complete':
        lines += ['**资料／草稿页：证据与创作包尚待核对，以下仅展示原始资料。**', '']
    else:
        if creation_available(analysis, errors):
            lines += [creation_markdown(analysis['creation'], record['video_key']+'.html'), '']
        else:
            lines += ['**旧版分析资料：尚无通过校验的创作包，不能作为脚本创作交付。**', '']
        for key,label in MODULES.items():
            section = analysis['modules'][key]
            lines += [f'## {label}', '', md(section['summary']), '']
            for f in section.get('findings', []):
                lines += [f'- [{md(f["kind"])}/{md(f["confidence"])}] {md(f["text"])}（证据：{md(", ".join(f["evidence_ids"]))}）']
        lines += ['## 证据', '']
        for e in analysis.get('evidence',[]):
            location=(f'原片片段 {e.get("start")}–{e.get("end")} 秒' if e.get('type')=='clip' else e.get('paragraph_id') or e.get('frame_id') or e.get('metric_key') or e.get('comment_id') or '原始标题／正文')
            lines += [f'- **{md(e["id"])}** · {md(location)}：{md(e.get("quote") or e.get("inspection_note") or "指标值、来源和观察时间见JSON证据快照。")}']
        lines += ['', '## 可复用元素', '']
        for element in analysis.get('elements',[]):
            lines += [element_markdown(element)]
    lines += ['', '## 分析方式', '', MODE_LABELS[mode(record)], md(quality(record)['reason']),
              '', '## 笔记正文（书面表达，不是口播）', '',md(record.get('note_caption') or '未取得'),
              '', '## '+('完整原文' if narration_allowed(record) else '未采用的语音识别结果（不得作为口播引用）'), ''] + [f'[{md(p["id"])}] {md(p["text"])}' for p in record['paragraphs']]
    return '\n'.join(lines) + '\n'


def element_markdown(element):
    lines = [f'### {md(element["name"])}', '']
    labels = {'problem':'解决的问题','template':'照着这个顺序拍','variables':'换成自己商品的哪些信息','applies_to':'什么情况下能用',
              'excludes':'换一种拍法会怎样','materials':'所需素材','experiment':'怎么试拍比较',
              'performance_relation':'是否知道效果更好','counterexamples':'还缺什么比较资料'}
    for key,label in labels.items():
        if key in element:
            value=element[key]
            lines += [f'- **{label}**：' + md('、'.join(str(v) for v in value) if isinstance(value,list) else str(value))]
    lines += ['', '证据：' + md(', '.join(element.get('evidence_ids',[])))] if element.get('evidence_ids') else []
    return '\n'.join(lines)+'\n'


def excel_navigation(root, result):
    """Expose only the workbook matching the current validated report."""
    from excel_export import report_digest
    from urllib.parse import quote
    state = read_json(root / '.excel-export.json', {})
    if not state:
        return ''
    target = Path(state.get('output', '')).expanduser().resolve()
    if not target.is_file():
        return '<section id="excel-delivery"><h2>Excel总表待更新</h2><p>尚未找到已有文件，请重新生成。</p></section>'
    if state.get('report_digest') != report_digest(result):
        return '<section id="excel-delivery"><h2>Excel总表待更新</h2><p>已有分析发生变化，重新生成后再下载总表。</p></section>'
    try:
        href = quote(str(target.relative_to(root / 'reports')), safe='/')
        link = f'<a id="download-excel" href="{esc(href)}" download>下载Excel总表</a>'
    except ValueError:
        link = 'Excel已更新到你指定的文件。'
    return '<section id="excel-delivery"><h2>全部博主分析，一份Excel</h2><p>'+link+'</p><p>包含博主归纳、视频拆解、拍法库和拍摄脚本。以后新增链接继续更新这份文件，保留“我的备注”。</p></section>'


def skill_navigation(root):
    """Offer only the standalone package matching its local receipt."""
    state = read_json(root / '.skill-export.json', {})
    name = state.get('filename', '')
    if name != 'ecommerce-video-breakdown.zip':
        return ''
    package = root / 'reports' / name
    if not package.is_file() or package.is_symlink() or hashlib.sha256(package.read_bytes()).hexdigest() != state.get('sha256'):
        return ''
    return '<section id="skill-delivery"><h2>带到另一台电脑使用</h2><p><a id="download-skill" href="ecommerce-video-breakdown.zip" download>下载独立Skill安装包</a></p><p>包含解析、归档、分析方法和Excel生成工具。无需原自媒体项目；在新电脑上先检查并准备运行环境。仅使用匿名公开内容和本地素材。</p></section>'


def render(workspace):
    archive = Archive(workspace)
    records = archive.records()
    out = archive.root / 'reports'
    for part in ('videos', 'creators', 'media'):
        (out / part).mkdir(parents=True, exist_ok=True)
    (out / 'style.css').write_text(STYLE,encoding='utf-8')
    generated = now()
    result = {'schema_version': 1, 'generated_at': generated, 'videos': [], 'creators': [], 'failures': archive.index()['failures']}
    library=[]
    by_creator = defaultdict(list)
    rows = ''
    for r in records:
        a = read_analysis(archive.root / 'analyses' / (r['video_key'] + '.json'))
        errors = validate_video(archive.root,r,a) if r['status']=='ready' else r['review_reasons']
        state = 'complete' if not errors else r['status'] if r['status']!='ready' else 'pending' if a.get('status')!='complete' else 'invalid'
        public_record={**r,'source_url':public_url(r['source_url']),'source_urls':[public_url(u) for u in r['source_urls']]}
        published_analysis=a if not errors else {'status':'withheld','reason':'当前资料或分析未通过校验；历史修订保留在工作区analyses，不通过报告导出。'}
        report = {'record': public_record, 'analysis': published_analysis, 'validation_errors':errors, 'report_status':state}
        result['videos'].append(report)
        by_creator[r['creator_key']].append(report)
        filename = r['video_key']
        (out / 'videos' / (filename+'.html')).write_text(page(r['title'],video_body(r,a,errors,out),generated,1),encoding='utf-8')
        (out / 'videos' / (filename+'.md')).write_text(markdown_video(r,a,errors),encoding='utf-8')
        write_json(out / 'videos' / (filename+'.json'),report)
        if not errors:
            for element in a.get('elements',[]):
                library.append({'element':element,'creator_key':r['creator_key'],'video_key':r['video_key'],
                                'source_title':r['title'],'is_synthetic':r.get('is_synthetic',False),
                                'coverage':{'support_video_count':1,'corpus_video_count':sum(v['creator_key']==r['creator_key'] and v['status']=='ready' for v in records)}})
        platform_label=PLATFORM_LABELS.get(r['platform'],r['platform'])
        rows += f'<tr data-search="{esc(r["title"]+" "+r["creator_name"]+" "+r["platform"]+" "+platform_label)}" data-status="{state}"><td class="title"><a href="videos/{filename}.html">{esc(r["title"])}</a>{"<span class=badge>合成示例</span>" if r.get("is_synthetic") else ""}</td><td><a href="creators/{esc(r["creator_key"])}.html">{esc(r["creator_name"] or "待确认")}</a><br><span class="small">{esc(platform_label)}</span></td><td>{esc(STATUS[state])}<br><span class="small">{esc(MODE_LABELS[mode(r)])}</span></td><td>{len(r["paragraphs"]) if narration_allowed(r) else 0} 段可用口播 / {len(r["frames"])} 帧</td></tr>'
    for key, items in by_creator.items():
        synthesis = read_analysis(archive.root / 'analyses/creators' / (key+'.json'))
        errors = validate_creator(archive.root,key,synthesis)
        valid = not errors
        ready = [v for v in items if v['record']['status']=='ready']
        complete = [v for v in ready if v['report_status']=='complete']
        coverage = f'归档 {len(items)} · 可分析 {len(ready)} · 逐条已验证 {len(complete)} · 待确认/待补 {len(items)-len(ready)}'
        body = f'<section><h2>语料覆盖</h2><p>{esc(coverage)}</p><p class="small">仅代表已归档语料，不代表博主主页全部历史视频。</p></section>'
        if len(ready)==1:
            body += '<p class="warning">单样本归纳：该博主仅归档1条有效视频，不能确认稳定风格、高频规律或爆款原因。</p>'
        if not valid:
            body += '<p class="warning">博主蒸馏待完成或待复核：' + esc('；'.join(errors)) + '</p>'
        else:
            for module,label in CREATOR_MODULES.items():
                section = synthesis['modules'][module]
                findings=''
                for f in section.get('findings',[]):
                    links=' '.join(f'<a href="../videos/{esc(v)}.html">{esc(v)}</a>' for v in f.get('video_keys',[]))
                    text='' if f.get('text')==section['summary'] else f'<p>{esc(f.get("text",""))}</p>'
                    findings+=text+f'<div class="refs">{links}</div>'
                summary=''.join(f'<p>{esc(part)}</p>' for part in section['summary'].split('\n\n'))
                body += f'<section><h2>{label}</h2>{summary}{findings}</section>'
            for pattern in synthesis.get('patterns',[]):
                refs=' '.join(f'<a href="../videos/{esc(ref["video_key"])}.html#e-{esc(ref["evidence_id"])}">{esc(ref["video_key"])} / {esc(ref["evidence_id"])}</a>' for ref in pattern['evidence_refs'])
                body += f'<section><h2>{esc(pattern["name"])}</h2><span class="badge">覆盖 {len(set(pattern["support_video_keys"]))} / {len(ready)} 条有效视频</span><p>{esc(pattern["mechanism"])}</p><p>边界：{esc(pattern["boundaries"])}</p><p>反例视频：{esc(", ".join(pattern.get("counterexample_video_keys",[])) or "当前样本未提供；不能据此认定普遍有效")}</p><p>验证：{esc(pattern["experiment"])}</p><div class="refs">{refs}</div></section>'
            for element in synthesis.get('elements',[]):
                refs=' '.join(f'<a href="../videos/{esc(ref["video_key"])}.html#e-{esc(ref["evidence_id"])}">原始案例 {esc(ref["video_key"])}</a>' for ref in element['evidence_refs'])
                body+=element_html(element,refs)
                library.append({'element':element,'creator_key':key,'is_synthetic':all(v['record'].get('is_synthetic',False) for v in ready),
                                'coverage':{'support_video_count':len({ref['video_key'] for ref in element['evidence_refs']}),'corpus_video_count':len(ready)}})
        links=''.join(f'<li><a href="../videos/{esc(v["record"]["video_key"])}.html">{esc(v["record"]["title"])}</a> · {esc(STATUS[v["report_status"]])}</li>' for v in items)
        body+=f'<section><h2>全部归档视频</h2><ul>{links}</ul></section>'
        name=items[0]['record']['creator_name'] or '待确认博主'
        (out/'creators'/(key+'.html')).write_text(page(name+' · 内容蒸馏',body,generated,1,coverage),encoding='utf-8')
        export={'creator_key':key,'analysis':synthesis if valid else {'status':'withheld','reason':'博主综合尚未通过来源与覆盖校验，历史修订保留在工作区analyses。'},'validation_errors':errors,'coverage':coverage}
        write_json(out/'creators'/(key+'.json'),export)
        creator_md=[f'# {md(name)} · 内容蒸馏','',coverage,'','只覆盖已归档语料；不代表主页全部历史视频。','']
        if not valid:
            creator_md+=['**蒸馏待完成／待复核**：'+md('；'.join(errors)),'']
        else:
            for module,label in CREATOR_MODULES.items():
                section=synthesis['modules'][module]
                creator_md += ['## '+label,'',md(section['summary']),'']
                for finding in section.get('findings',[]):
                    if finding['text']!=section['summary']:
                        creator_md += ['- '+md(finding['text'])+'（样本：'+md(', '.join(finding['video_keys']))+'）']
            for pattern in synthesis.get('patterns',[]):
                creator_md += ['', '## 模式 · '+md(pattern['name']),'',f'覆盖 {len(set(pattern["support_video_keys"]))} / {len(ready)} 条有效视频。',
                       '',md(pattern['mechanism']),'','边界：'+md(pattern['boundaries']),'','验证：'+md(pattern['experiment'])]
                creator_md += ['','证据：']+[f'- [{ref["video_key"]} / {ref["evidence_id"]}](../videos/{ref["video_key"]}.html#e-{ref["evidence_id"]})' for ref in pattern['evidence_refs']]
            creator_md += ['','## 可复用元素','']+[element_markdown(e) for e in synthesis.get('elements',[])]
        creator_md += ['','## 全部归档视频','']+[f'- [{md(v["record"]["title"])}](../videos/{v["record"]["video_key"]}.md) · {STATUS[v["report_status"]]}' for v in items]
        (out/'creators'/(key+'.md')).write_text('\n'.join(creator_md)+'\n',encoding='utf-8')
        result['creators'].append(export)
    total=len(records)
    complete=sum(v['report_status']=='complete' for v in result['videos'])
    synthetic=sum(r.get('is_synthetic',False) for r in records)
    stats=f'<div class="stats"><div><strong>{total}</strong>已归档视频</div><div><strong>{len(by_creator)}</strong>博主／待确认身份</div><div><strong>{complete}</strong>逐条证据校验通过</div><div><strong>{synthetic}</strong>合成验收示例</div></div>'
    usable=sum(narration_allowed(r) for r in records)
    visual=sum(v['report_status']=='complete' and mode(v['record'])=='visual' for v in result['videos'])
    stats += f'<p class="small">可用口播 {usable} / {total} · 已完成画面／正文分析 {visual} / {total}。分析完成不代表口播提取成功。</p>'
    filters='<div class="filters"><input id="search" type="search" aria-label="搜索标题、博主或平台" placeholder="搜索标题、博主或平台"><select id="status" aria-label="筛选状态"><option value="">全部状态</option>'+''.join(f'<option value="{s}">{STATUS[s]}</option>' for s in ('complete','pending','needs_review','needs_transcript','invalid'))+'</select><button id="reset" type="button">重置</button></div>'
    failures=''.join(f'<li>{esc(f["reason"])}</li>' for f in archive.index()['failures'])
    script_navigation, script_collection, script_markdown = collection(result['videos'])
    (out/'scripts.html').write_text(page('脚本创作合集',script_collection+INTERACTIONS,generated),encoding='utf-8')
    (out/'scripts.md').write_text(script_markdown,encoding='utf-8')
    body=excel_navigation(archive.root,result)+skill_navigation(archive.root)+stats+script_navigation+'<p>先看每条视频拍了什么，再归纳同一博主的做法。报告提供拍摄思路；没有成交数据时，不判断哪种拍法卖得更多。</p><p><a href="elements.html">浏览可复用元素库</a> · <a href="report.json">结构化报告</a></p>'+filters+'<section><div class="table-scroll"><table><thead><tr><th>视频</th><th>博主／平台</th><th>状态</th><th>证据资料</th></tr></thead><tbody>'+rows+'</tbody></table></div><p id="empty" class="empty" hidden>没有匹配的视频。</p></section>'
    if failures:
        body+='<section><h2>解析失败记录</h2><ul>'+failures+'</ul></section>'
    body+='''<script>const input=document.querySelector('#search'),select=document.querySelector('#status');function filter(){let count=0;for(const row of document.querySelectorAll('tr[data-search]')){const show=row.dataset.search.toLowerCase().includes(input.value.toLowerCase())&&(!select.value||select.value===row.dataset.status);row.hidden=!show;if(show)count++;}document.querySelector('#empty').hidden=count>0;}input.addEventListener('input',filter);select.addEventListener('change',filter);document.querySelector('#reset').addEventListener('click',()=>{input.value='';select.value='';filter();});</script>'''
    (out/'index.html').write_text(page('电商视频 · 证据与复用',body,generated),encoding='utf-8')
    cards=''
    for item in library:
        element=item['element']
        if item.get('video_key'):
            refs=' '.join(f'<a href="videos/{esc(item["video_key"])}.html#e-{esc(ref)}">原始案例 · {esc(item["source_title"])}</a>' for ref in element['evidence_ids'])
        else:
            refs=' '.join(f'<a href="videos/{esc(ref["video_key"])}.html#e-{esc(ref["evidence_id"])}">原始证据 · {esc(ref["video_key"])}</a>' for ref in element['evidence_refs'])
        if item['is_synthetic']:
            refs='<span class="badge">合成验收示例</span>'+refs
        coverage=item['coverage']
        cards+=element_html(element,refs,f'本卡已登记出处覆盖 {coverage["support_video_count"]} / {coverage["corpus_video_count"]} 条有效视频；不等同于全语料实际出现频次或有效性。')
    (out/'elements.html').write_text(page('可复用元素库',cards or '<section><p>尚无通过证据校验的元素卡。完成逐条分析与蒸馏后再更新。</p></section>',generated),encoding='utf-8')
    write_json(out/'elements.json',library)
    library_md=['# 可复用元素库','']
    for item in library:
        library_md += [element_markdown(item['element'])]
        coverage=item['coverage']
        library_md += [f'登记出处覆盖：{coverage["support_video_count"]} / {coverage["corpus_video_count"]} 条有效视频；实际出现频次及表现关联见博主综合。','',
                       '表现关联：'+md(item['element'].get('performance_relation') or '未建立可比效果数据，不能认定真实高表现。'),'',
                       '反例与限制：'+md(item['element'].get('counterexamples') or '未登记反例，不代表普遍有效。'),'']
        if item['is_synthetic']:
            library_md += ['**合成验收示例，不能视作真实爆款案例。**','']
        refs=item['element'].get('evidence_refs') or [{'video_key':item['video_key'],'evidence_id':ref} for ref in item['element'].get('evidence_ids',[])]
        library_md += [f'- [原始案例 {ref["video_key"]} / {ref["evidence_id"]}](videos/{ref["video_key"]}.html#e-{ref["evidence_id"]})' for ref in refs]+['']
    (out/'elements.md').write_text('\n'.join(library_md)+'\n',encoding='utf-8')
    (out/'index.md').write_text('# 电商视频 · 证据与复用\n\n'+f'归档 {total} 条，逐条证据校验通过 {complete} 条，合成示例 {synthetic} 条。\n\n'+
        '\n'.join(f'- [{md(r["title"])}](videos/{r["video_key"]}.md)' for r in records)+'\n\n[脚本创作合集](scripts.md) · [可复用元素库](elements.md)\n',encoding='utf-8')
    write_json(out/'report.json',result)
    return out
