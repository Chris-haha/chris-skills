"""Prepare full-corpus work for Codex and validate evidence references."""
from collections import defaultdict
from pathlib import Path
from archive import Archive, SCHEMA_VERSION, read_json, relative_file, write_json, source_fingerprint
from quality import mode, quality, narration_allowed
from creation import template as creation_template, validate_creation, number
from editorial import check_analysis

MODULES = {
    'source_quality': '来源与质量', 'performance': '表现依据', 'product_audience': '商品与人群',
    'title_cover': '标题与封面', 'hook': '钩子设计', 'structure': '内容结构', 'pacing': '叙事节奏',
    'selling_points': '卖点呈现', 'pain_pleasure': '痛点与爽点', 'trust_proof': '信任与证明',
    'audiovisual': '视听表达', 'conversion': '转化设计', 'comments': '评论反馈',
    'hypotheses_reuse': '原因假设与复用',
}
CREATOR_MODULES = {'profile': '这位博主的视频特点', 'structure_map': '视频怎么展开', 'pain_pleasure_map': '观众可能在意什么',
                   'performance_comparison': '已有表现数据', 'boundaries': '哪些情况不能照着拍', 'experiments': '拍摄建议与比较方法'}


def read_analysis(path):
    try:
        value = read_json(path, {})
        return value if isinstance(value, dict) else {'_read_error': '分析JSON根节点必须是对象'}
    except (ValueError, OSError) as exc:
        return {'_read_error': '分析JSON读取失败：' + str(exc)}


def shape_errors(data, creator=False):
    if not isinstance(data, dict):
        return ['分析JSON必须是对象']
    if data.get('_read_error'):
        return [data['_read_error']]
    errors = []
    modules = data.get('modules', {})
    if not isinstance(modules, dict):
        errors.append('modules必须是对象')
    else:
        for key, value in modules.items():
            if not isinstance(value, dict) or not isinstance(value.get('summary', ''), str) or not isinstance(value.get('findings', []), list) or any(not isinstance(f, dict) for f in value.get('findings', [])):
                errors.append(key + ': 模块需要summary文本和findings对象数组')
            else:
                for f in value.get('findings', []):
                    refs = f.get('video_keys' if creator else 'evidence_ids', [])
                    if not isinstance(refs, list) or any(not isinstance(ref, str) for ref in refs):
                        errors.append(key + ': 引用必须是字符串数组')
    for key in (('patterns', 'elements') if creator else ('evidence', 'elements')):
        items = data.get(key, [])
        if not isinstance(items, list) or any(not isinstance(item, dict) for item in items):
            errors.append(key + '必须是对象数组')
    if errors:
        return errors
    for e in data.get('elements', []):
        refs = e.get('evidence_refs' if creator else 'evidence_ids', [])
        if not isinstance(refs, list) or any(not isinstance(ref, dict if creator else str) for ref in refs):
            errors.append('元素卡证据引用类型错误')
    for e in data.get('evidence', []):
        for field in ('id','type','paragraph_id','frame_id','metric_key','comment_id','quote','inspection_note'):
            if field in e and not isinstance(e[field],str):
                errors.append(field+'必须是字符串')
    if creator:
        if not isinstance(data.get('covered_video_keys', []), list) or any(not isinstance(k, str) for k in data.get('covered_video_keys', [])):
            errors.append('covered_video_keys必须是字符串数组')
        if not isinstance(data.get('source_hashes', {}), dict):
            errors.append('source_hashes必须是对象')
        for pattern in data.get('patterns', []):
            for key in ('support_video_keys', 'counterexample_video_keys'):
                if not isinstance(pattern.get(key, []), list) or any(not isinstance(k, str) for k in pattern.get(key, [])):
                    errors.append('模式视频引用必须是字符串数组')
            if not isinstance(pattern.get('evidence_refs', []), list) or any(not isinstance(r, dict) for r in pattern.get('evidence_refs', [])):
                errors.append('模式证据引用必须是对象数组')
        for item in data.get('patterns',[]) + data.get('elements',[]):
            if isinstance(item.get('evidence_refs',[]),list):
                for ref in item.get('evidence_refs',[]):
                    if isinstance(ref,dict) and any(not isinstance(ref.get(k,''),str) for k in ('video_key','evidence_id')):
                        errors.append('跨视频证据ID必须是字符串')
    return errors


def prepare(workspace, group_size=10):
    if group_size < 1:
        raise ValueError('分组数量必须大于0')
    archive = Archive(workspace)
    root = archive.root
    tasks = {'schema_version': SCHEMA_VERSION, 'videos': [], 'groups': [], 'creators': [], 'excluded': [], 'failures': archive.index()['failures']}
    creators = defaultdict(list)
    for record in archive.records():
        key = record['video_key']
        if record['status'] != 'ready':
            tasks['excluded'].append({'video_key': key, 'status': record['status'], 'reasons': record['review_reasons']})
            continue
        analysis_path = Path('analyses') / (key + '.json')
        if not (root / analysis_path).exists():
            write_json(root / analysis_path, {
                'schema_version': SCHEMA_VERSION, 'video_key': key, 'source_hash': record['source_hash'], 'status': 'pending',
                'analysis_mode':mode(record), 'creation':creation_template(), 'modules': {k: {'summary': '', 'findings': []} for k in MODULES}, 'evidence': [], 'elements': [],
            })
        task = {'video_key': key, 'creator_key': record['creator_key'],
                'analysis_mode':mode(record), 'narration_quality':quality(record),
                'caption':record.get('note_caption',''), 'narration_evidence_allowed':narration_allowed(record),
                'media':record.get('media'), 'creation_required':True,
                'transcript_path': record['artifact_dir'] + '/transcript.txt',
                'metadata_path': record['artifact_dir'] + '/metadata.json',
                'analysis_path': str(analysis_path), 'frames': record['frames'], 'source_hash': record['source_hash'],
                'timing_available': bool(record['segments']), 'is_synthetic': record.get('is_synthetic', False)}
        tasks['videos'].append(task)
        creators[record['creator_key']].append(task)
    for creator_key, videos in creators.items():
        group_ids = []
        for start in range(0, len(videos), group_size):
            group_id = creator_key + '--g' + str(start // group_size + 1)
            group = {'id': group_id, 'creator_key': creator_key, 'video_keys': [v['video_key'] for v in videos[start:start+group_size]],
                     'instruction': '先完整阅读各视频原文与可用画面，完成逐条分析，再归纳本组；不得仅阅读摘要或截取前几条。'}
            tasks['groups'].append(group)
            group_ids.append(group_id)
        creator_path = Path('analyses/creators') / (creator_key + '.json')
        if not (root / creator_path).exists():
            write_json(root / creator_path, {'schema_version': SCHEMA_VERSION, 'creator_key': creator_key, 'status': 'pending',
                'covered_video_keys': [], 'source_hashes': {}, 'modules': {k: {'summary': '', 'findings': []} for k in CREATOR_MODULES},
                'patterns': [], 'elements': []})
        tasks['creators'].append({'creator_key': creator_key, 'analysis_path': str(creator_path), 'groups': group_ids,
                                  'required_video_keys': [v['video_key'] for v in videos]})
    write_json(root / 'analysis/tasks.json', tasks)
    return tasks


def compact(text):
    return ''.join(str(text).split())


def validate_video(workspace, record, analysis):
    errors = shape_errors(analysis)
    if errors:
        return errors
    if analysis.get('status') != 'complete':
        return ['分析尚未完成']
    if record['status'] != 'ready':
        errors.append('来源或博主仍待确认，不能发布完成分析')
    if analysis.get('analysis_mode', 'speech') != mode(record):
        errors.append('分析方式与当前已确认资料不一致')
    if mode(record) in ('speech','mixed') and not narration_allowed(record):
        errors.append('自动转录尚未核听或不可用，不能发布口播分析；可复核后改用画面／正文分析')
    if mode(record) in ('visual','mixed') and not record['frames']:
        errors.append('画面分析缺少已归档画面')
    if analysis.get('schema_version') != SCHEMA_VERSION:
        errors.append('不支持的分析版本')
    if analysis.get('video_key') != record['video_key']:
        errors.append('分析视频身份不一致')
    try:
        fingerprint=source_fingerprint(Path(workspace),record)
    except (OSError,ValueError) as exc:
        return ['原始证据文件缺失或路径无效：'+str(exc)]
    if analysis.get('source_hash') != record['source_hash'] or fingerprint != record['source_hash']:
        errors.append('文字稿或证据资料发生变化，需要复核分析')
    if not analysis.get('evidence') or not any(section.get('findings') for section in analysis.get('modules',{}).values() if isinstance(section,dict)):
        errors.append('完成分析至少需要一条有证据的实质性判断，空模板不能作为完成报告')
    evidence_ids = set()
    evidence_types = {}
    ps = {p['id']: p['text'] for p in record['paragraphs']}
    frames = {f['id']: f for f in record['frames']}
    for evidence in analysis.get('evidence', []):
        eid = evidence.get('id')
        if not eid or eid in evidence_ids:
            errors.append('证据ID缺失或重复')
        evidence_ids.add(eid)
        kind = evidence.get('type')
        evidence_types[eid] = kind
        if kind == 'transcript':
            if not narration_allowed(record):
                errors.append(f'{eid}: 未核实或未采用的ASR不能作为商品口播证据')
            text = ps.get(evidence.get('paragraph_id'), '')
            if not evidence.get('quote') or not text or compact(evidence['quote']) not in compact(text):
                errors.append(f'{eid}: 引文不存在于指定原文段落')
            if 'start' in evidence or 'end' in evidence:
                matching = [s for s in record['segments'] if s.get('start') == evidence.get('start') and s.get('end') == evidence.get('end')]
                if not matching:
                    errors.append(f'{eid}: 时间戳没有对应原始时间轴')
        elif kind in ('title','caption'):
            text=record.get('title' if kind=='title' else 'note_caption','')
            if not evidence.get('quote') or compact(evidence['quote']) not in compact(text):
                errors.append(f'{eid}: 引文不存在于标题或笔记正文')
            if kind=='caption' and (not record.get('caption_source') or not record.get('caption_observed_at')):
                errors.append(f'{eid}: 笔记正文缺少来源或采集时间')
        elif kind == 'clip':
            media=record.get('media') or {}
            start,end=evidence.get('start'),evidence.get('end')
            if not media.get('path') or not relative_file(Path(workspace),media['path']).is_file():
                errors.append(f'{eid}: 本地原视频缺失，不能引用连续片段')
            if not number(start) or not number(end) or not number(media.get('duration')) or start<0 or end<=start or end>media['duration']:
                errors.append(f'{eid}: 片段时间超出实际原视频范围')
            if evidence.get('channels')!=['visual'] or not evidence.get('inspection_note'):
                errors.append(f'{eid}: 当前连续片段证据需明确静音视觉检查内容，不能冒充已核听音轨')
        elif kind == 'frame':
            f = frames.get(evidence.get('frame_id'))
            if not f or not relative_file(Path(workspace), f['path']).is_file():
                errors.append(f'{eid}: 画面证据不存在')
            if not evidence.get('inspection_note'):
                errors.append(f'{eid}: 需要记录实际查看到的画面内容')
        elif kind == 'metric':
            metric = record['metrics'].get(evidence.get('metric_key'))
            if not isinstance(metric, dict) or metric.get('value') is None or not metric.get('source') or not metric.get('observed_at'):
                errors.append(f'{eid}: 指标缺少真实数值、来源或观察时间')
        elif kind == 'comment':
            comment = next((c for c in record['comments'] if c.get('id') == evidence.get('comment_id')), None)
            if not comment or not comment.get('source') or not comment.get('observed_at') or not evidence.get('quote') or compact(evidence['quote']) not in compact(comment.get('text', '')):
                errors.append(f'{eid}: 评论引文无出处')
        else:
            errors.append(f'{eid}: 不支持的证据类型')
    if mode(record) in ('visual','mixed') and not any(e.get('type') in ('frame','clip') for e in analysis.get('evidence',[])):
        errors.append('画面分析至少需要一条实际查看的画面证据')
    for module in MODULES:
        section = analysis.get('modules', {}).get(module)
        if not isinstance(section, dict) or not str(section.get('summary', '')).strip():
            errors.append(f'{module}: 模块缺失或未填写（无证据时应明确写缺失）')
            continue
        for finding in section.get('findings', []):
            refs = finding.get('evidence_ids', [])
            if not finding.get('text') or not refs or not set(refs).issubset(evidence_ids):
                errors.append(f'{module}: 结论缺少有效证据引用')
            if finding.get('kind') not in ('observation', 'hypothesis') or finding.get('confidence') not in ('high', 'medium', 'low'):
                errors.append(f'{module}: 需要标注观察/假设及置信程度')
            if module == 'audiovisual' and finding.get('kind') == 'observation' and not any(evidence_types.get(ref) in ('frame','clip') for ref in refs):
                errors.append('audiovisual: 画面观察需要实际查看的画面证据')
    for element in analysis.get('elements', []):
        for field in ('id', 'name', 'problem', 'template', 'variables', 'evidence_ids', 'applies_to', 'excludes', 'materials', 'experiment'):
            if not element.get(field):
                errors.append(f'元素卡缺少 {field}')
        if not set(element.get('evidence_ids', [])).issubset(evidence_ids):
            errors.append('元素卡引用了不存在的证据')
    errors.extend(validate_creation(analysis.get('creation'),evidence_ids))
    errors.extend(check_analysis(analysis))
    return errors


def validate_creator(workspace, creator_key, synthesis):
    records = [r for r in Archive(workspace).records() if r['creator_key'] == creator_key and r['status'] == 'ready']
    keys = {r['video_key'] for r in records}
    errors = shape_errors(synthesis, creator=True)
    if errors:
        return errors
    covered = synthesis.get('covered_video_keys', [])
    if synthesis.get('status') != 'complete':
        return ['博主蒸馏尚未完成']
    if not keys:
        errors.append('没有可分析视频，不能标记博主蒸馏完成')
    if synthesis.get('creator_key') != creator_key or synthesis.get('schema_version') != SCHEMA_VERSION:
        errors.append('博主身份或版本不一致')
    if set(covered) != keys or len(covered) != len(keys):
        errors.append('博主报告未完整覆盖全部有效视频，或重复/混入其他博主')
    for r in records:
        if synthesis.get('source_hashes', {}).get(r['video_key']) != r['source_hash']:
            errors.append(r['video_key'] + ': 蒸馏来源版本过期或未登记')
        a = read_analysis(Path(workspace) / 'analyses' / (r['video_key'] + '.json'))
        if validate_video(workspace, r, a):
            errors.append(r['video_key'] + ': 逐条分析未通过')
    for name in CREATOR_MODULES:
        section = synthesis.get('modules', {}).get(name)
        if not isinstance(section, dict) or not section.get('summary'):
            errors.append(name + ': 未填写')
        elif any(not f.get('text') or f.get('kind') not in ('observation', 'hypothesis') or f.get('confidence') not in ('high', 'medium', 'low') or not f.get('video_keys') or not set(f['video_keys']).issubset(keys) for f in section.get('findings', [])):
            errors.append(name + ': 归纳结论缺少本博主视频出处')
    for pattern in synthesis.get('patterns', []):
        support = pattern.get('support_video_keys', [])
        counter = pattern.get('counterexample_video_keys', [])
        if not support or len(support) != len(set(support)) or len(counter) != len(set(counter)) or not (set(support) | set(counter)).issubset(keys) or set(support) & set(counter):
            errors.append('模式支持/反例视频不合法')
        if 'frequency' in pattern and pattern['frequency'] != {'support_count': len(set(support)), 'denominator': len(keys)}:
            errors.append('模式频次必须按独立视频数和全部有效样本统计')
        if not pattern.get('name') or not pattern.get('mechanism') or not pattern.get('boundaries') or not pattern.get('experiment'):
            errors.append('模式需要名称、机制假设、边界与验证方法')
        for ref in pattern.get('evidence_refs', []):
            if ref.get('video_key') not in keys:
                errors.append('模式包含失效的跨视频证据引用')
                continue
            a = read_analysis(Path(workspace) / 'analyses' / (ref['video_key'] + '.json'))
            if shape_errors(a) or ref.get('evidence_id') not in {e.get('id') for e in a.get('evidence', [])}:
                errors.append('模式包含失效的跨视频证据引用')
        if not pattern.get('evidence_refs'):
            errors.append('模式需要跨视频证据引用')
    for element in synthesis.get('elements', []):
        for field in ('id', 'name', 'problem', 'template', 'variables', 'evidence_refs', 'applies_to', 'excludes', 'materials', 'experiment'):
            if not element.get(field):
                errors.append(f'综合元素卡缺少 {field}')
        for ref in element.get('evidence_refs', []):
            video_key = ref.get('video_key', '')
            if video_key not in keys:
                errors.append('综合元素卡引用其他博主或无效视频')
                continue
            a = read_analysis(Path(workspace) / 'analyses' / (video_key + '.json'))
            if shape_errors(a) or ref.get('evidence_id') not in {e.get('id') for e in a.get('evidence', [])}:
                errors.append('综合元素卡引用不存在的证据')
    errors.extend(check_analysis(synthesis))
    return errors


def validate_workspace(workspace):
    root = Path(workspace)
    records = Archive(root).records()
    videos = {}
    for r in records:
        a = read_analysis(root / 'analyses' / (r['video_key'] + '.json'))
        videos[r['video_key']] = validate_video(root, r, a) if r['status'] == 'ready' else r['review_reasons']
    creators = {}
    for key in sorted({r['creator_key'] for r in records if r['status'] == 'ready'}):
        creators[key] = validate_creator(root, key, read_analysis(root / 'analyses/creators' / (key + '.json')))
    result = {'ok': bool(videos) and not any(videos.values()) and not any(creators.values()) and not Archive(root).index()['failures'],
              'videos': videos, 'creators': creators, 'failures': Archive(root).index()['failures']}
    write_json(root / 'analysis/validation.json', result)
    return result
