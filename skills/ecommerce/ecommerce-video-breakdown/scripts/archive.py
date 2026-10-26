"""Local evidence archive. Never changes an upstream artifact."""
import hashlib
import json
import re
import shutil
import math
from datetime import datetime, timezone
from pathlib import Path, PureWindowsPath
from urllib.parse import parse_qs, urlsplit

SCHEMA_VERSION = 1
PLATFORMS = {'douyin', 'xiaohongshu', 'bilibili'}


def now():
    return datetime.now(timezone.utc).isoformat()


def digest(value):
    return hashlib.sha256(value.encode('utf-8')).hexdigest()


def read_json(path, default=None):
    return json.loads(path.read_text(encoding='utf-8')) if path.exists() else default


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + '.tmp')
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    temporary.replace(path)


def slug(value):
    return re.sub(r'[^\w\u4e00-\u9fff-]+', '-', str(value)).strip('-')[:65] or 'unknown'


def identity(url, hint=''):
    u = urlsplit(str(url).strip())
    host = (u.hostname or '').lower()
    platforms = {'douyin': ('douyin.com', 'iesdouyin.com'), 'bilibili': ('bilibili.com', 'b23.tv'),
                 'xiaohongshu': ('xiaohongshu.com', 'xhslink.com', 'xhslink.cn')}
    platform = next((p for p, domains in platforms.items() if any(host == d or host.endswith('.' + d) for d in domains)), '')
    if u.scheme not in ('http', 'https') or not platform:
        raise ValueError('只接受抖音、小红书和B站的 HTTP(S) 视频链接')
    if hint and hint in PLATFORMS and platform != hint:
        raise ValueError('链接平台与元数据平台冲突')
    patterns = {'douyin': r'/(?:video|share/video)/(\d+)', 'bilibili': r'/(BV[a-zA-Z0-9]+)',
                'xiaohongshu': r'/(?:explore|discovery/item)/(\w+)'}
    match = re.search(patterns[platform], u.path)
    video_id = match.group(1) if match else ''
    if platform == 'douyin' and not video_id:
        video_id = parse_qs(u.query).get('modal_id', [''])[0]
    if video_id and (len(video_id) > 128 or not re.fullmatch(r'\d+' if platform == 'douyin' else r'[A-Za-z0-9_]+',video_id)):
        raise ValueError('无效的视频ID')
    part = parse_qs(u.query).get('p', ['1'])[0] if platform == 'bilibili' else ''
    if part and (not part.isdigit() or int(part) < 1):
        raise ValueError('无效B站分P')
    part = str(int(part)) if part else ''
    # Short URLs remain resolvable identifiers, never pretend they are canonical IDs.
    stable = video_id or 'short-' + digest(host + u.path)[:16]
    key = platform + '--' + stable + ('--p' + part if part else '')
    return {'platform': platform, 'video_id': video_id, 'part': part, 'video_key': key}


def relative_file(workspace, relative):
    raw = str(relative)
    if PureWindowsPath(raw).drive or raw.startswith(('/', '\\')):
        raise ValueError('归档只允许工作区内相对路径')
    target = (workspace / raw.replace('\\', '/')).resolve()
    if not target.is_relative_to(workspace.resolve()):
        raise ValueError('产物路径超出工作区')
    return target


def paragraphs(text):
    # Preserve every original character; offsets are recoverable from transcript.txt.
    chunks = text.splitlines() or [text]
    return [{'id': f'p{i+1:04d}', 'text': line} for i, line in enumerate(chunks) if line.strip()]


def source_fingerprint(root, record):
    """Version all referenced evidence, including files changed outside the CLI."""
    raw = relative_file(Path(root), record['artifact_dir']).joinpath('transcript.txt').read_text(encoding='utf-8')
    fields = {k:record.get(k) for k in ('video_key','creator_key','creator_name','title','duration','published_at','transcript_source','segments','metrics','comments','is_synthetic')}
    fields['transcript_hash'] = digest(raw)
    if record.get('media'):
        media=record['media'];p=relative_file(Path(root),media['path'])
        fields['media']={**media,'sha256':hashlib.sha256(p.read_bytes()).hexdigest() if p.is_file() else 'missing'}
    for k in ('note_caption','caption_source','caption_observed_at','narration_quality','analysis_mode'):
        if k in record:
            fields[k]=record[k]
    fields['frames'] = []
    for frame in record['frames']:
        path = relative_file(Path(root), frame['path'])
        fields['frames'].append({'id':frame['id'],'timestamp':frame.get('timestamp'),
                                 'sha256':hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else 'missing'})
    return digest(json.dumps(fields, ensure_ascii=False, sort_keys=True))


class Archive:
    def __init__(self, workspace):
        self.root = Path(workspace).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.index_path = self.root / 'index.json'

    def index(self):
        return read_json(self.index_path, {'schema_version': SCHEMA_VERSION, 'videos': [], 'failures': []})

    def records(self):
        return self.index()['videos']

    def read_transcript(self, record):
        return relative_file(self.root, record['artifact_dir']).joinpath('transcript.txt').read_text(encoding='utf-8')

    def failure(self, url, reason):
        index = self.index()
        index['failures'] = [f for f in index['failures'] if f['url'] != url]
        index['failures'].append({'url': url, 'reason': reason, 'at': now()})
        write_json(self.index_path, index)

    def add(self, result, requested_url=None, source_dir=None, creator_override=None, refresh=False):
        if not isinstance(result,dict) or not isinstance(result.get('info',{}),dict):
            raise ValueError('解析元数据必须是对象')
        data = {**result.get('info', {}), **result}
        if not isinstance(data.get('metrics',{}),dict):
            raise ValueError('metrics必须是对象')
        for field in ('comments','segments','frames'):
            if data.get(field) is not None and (not isinstance(data[field],list) or any(not isinstance(item,dict) for item in data[field])):
                raise ValueError(field+'必须是对象数组')
        url = str(data.get('url') or data.get('source_url') or requested_url or '').strip()
        parsed = identity(url, data.get('platform', ''))
        submitted = identity(requested_url) if requested_url else parsed
        reasons = []
        explicit_id = next((str(data[k]) for k in ('video_id', 'bvid', 'aweme_id', 'note_id') if data.get(k)), '')
        if explicit_id and parsed['video_id'] and explicit_id != parsed['video_id']:
            reasons.append('元数据视频ID与链接冲突')
        if explicit_id and not parsed['video_id']:
            urls = {'douyin':'https://www.douyin.com/video/', 'bilibili':'https://www.bilibili.com/video/',
                    'xiaohongshu':'https://www.xiaohongshu.com/explore/'}
            canonical = identity(urls[parsed['platform']] + explicit_id + ('?p=' + parsed['part'] if parsed['part'] else ''))
            if canonical['video_id'] != explicit_id:
                raise ValueError('显式视频ID格式无效')
            parsed = canonical
        if submitted['platform'] != parsed['platform'] or (submitted['video_id'] and parsed['video_id'] and submitted['video_key'] != parsed['video_key']):
            reasons.append('提交链接与解析结果身份冲突')
        upstream_check = data.get('identity_check', {})
        if upstream_check.get('status') == 'needs_review':
            reasons.append(upstream_check.get('reason', '上游来源检查未通过'))
        # A short URL may map to a canonical URL. Both are retained for subsequent skips.
        index = self.index()
        aliases = list(dict.fromkeys([u for u in [url, requested_url, data.get('submitted_url')] if u]))
        existing = next((r for r in index['videos'] if r['video_key'] == parsed['video_key'] or any(u in r.get('source_urls', []) for u in aliases)), None)
        if existing and reasons:
            raise ValueError('已有归档遇到来源冲突，未绑定新别名：' + '；'.join(reasons))
        if existing and not refresh:
            existing['source_urls'] = list(dict.fromkeys(existing.get('source_urls', []) + aliases))
            write_json(self.index_path, index)
            return existing
        raw = str(data.get('subtitle_text') or data.get('transcript') or '')
        source = str(data.get('source') or data.get('extraction_method') or 'imported_transcript')
        override = dict(creator_override or {})
        if existing and existing.get('creator_confirmation') == 'manual':
            override = {'creator_id': existing['creator_id'], 'creator_name': existing['creator_name'], **{k:v for k,v in override.items() if v}}
        creator_id = str(override.get('creator_id') or data.get('creator_id') or data.get('author_id') or data.get('uploader_id') or '').strip()
        name = str(override.get('creator_name') or data.get('author') or data.get('creator_name') or '').strip()
        if not creator_id:
            reasons.append('缺少稳定博主账号ID，请人工确认后归集')
        if not name:
            reasons.append('未识别博主名称')
        if override.get('creator_name') and data.get('author') and override['creator_name'].strip() != str(data['author']).strip():
            reasons.append('指定博主与解析作者不一致，请人工确认')
        status = 'needs_transcript' if source in ('ai_conclusion', 'summary', 'ai_summary') or not raw.strip() else 'needs_review' if reasons else 'ready'
        if status == 'needs_transcript':
            reasons.append('缺少完整文字稿；AI摘要不能替代逐字稿' if raw else '文字稿为空')
        creator_key = parsed['platform'] + '--' + slug(creator_id or 'pending-' + digest(parsed['video_key'])[:12]) + '-' + digest(creator_id or parsed['video_key'])[:8]
        key = parsed['video_key']
        directory = self.root / 'creators' / (slug(name or '待确认') + '--' + creator_key) / 'videos' / (key + '--' + slug(data.get('title', '未命名')))
        if not directory.resolve().is_relative_to(self.root):
            raise ValueError('产物路径超出工作区')
        if existing:
            old_dir = relative_file(self.root, existing['artifact_dir'])
            backup = old_dir / 'revisions' / datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%f')
            backup.mkdir(parents=True, exist_ok=True)
            for old in old_dir.iterdir():
                if old.is_file():
                    shutil.copy2(old, backup / old.name)
            directory = old_dir
        directory.mkdir(parents=True, exist_ok=True)
        (directory / 'transcript.txt').write_text(raw, encoding='utf-8')
        clean = str(data.get('cleaned_transcript') or '\n'.join(line.strip() for line in raw.replace('\r\n', '\n').splitlines()))
        (directory / 'transcript-cleaned.txt').write_text(clean, encoding='utf-8')
        (directory / 'source-url.txt').write_text(url + '\n', encoding='utf-8')
        write_json(directory / 'metadata.json', result)
        frames = []
        for i, frame in enumerate(data.get('frames') or []):
            p = Path(str(frame.get('path', '')))
            if not p.is_absolute() and source_dir:
                p = Path(source_dir) / p
            if p.is_file() and p.suffix.lower() in ('.png', '.jpg', '.jpeg', '.webp'):
                target = directory / 'frames' / f'frame-{i+1:03d}{p.suffix.lower()}'
                target.parent.mkdir(exist_ok=True)
                if p.resolve() != target.resolve():
                    shutil.copy2(p, target)
                frames.append({'id': f'f{i+1:03d}', 'path': target.relative_to(self.root).as_posix(), 'timestamp': frame.get('timestamp'),
                               'timing_basis': 'upstream' if frame.get('timestamp') is not None else 'unknown'})
        record = {**parsed, 'creator_id': creator_id, 'creator_name': name, 'creator_key': creator_key,
                  'title': str(data.get('title', '未命名视频')), 'source_url': url, 'source_urls': list(dict.fromkeys((existing.get('source_urls', []) if existing else []) + aliases)),
                  'status': status, 'review_reasons': reasons, 'transcript_source': source,
                  'source_hash': digest(raw), 'artifact_dir': directory.relative_to(self.root).as_posix(),
                  'paragraphs': paragraphs(raw), 'segments': data.get('segments') or [], 'frames': frames,
                  'duration': data.get('duration'), 'published_at': data.get('published_at') or data.get('upload_date'),
                  'metrics': data.get('metrics') or {}, 'comments': data.get('comments') or [],
                  'performance_label': data.get('performance_label', 'unverified'), 'is_synthetic': bool(data.get('is_synthetic')),
                  'created_at': existing.get('created_at', now()) if existing else now(), 'updated_at': now()}
        from quality import assess
        record['note_caption']=str(data.get('note_caption') or data.get('desc') or '')
        record['caption_source']=str(data.get('caption_source') or url)
        record['caption_observed_at']=str(data.get('caption_observed_at') or now())
        record['narration_quality']=assess(raw,source)
        if existing:
            record['quality_reviews']=list(existing.get('quality_reviews',[]))
            if existing.get('narration_quality'):
                record['quality_reviews'].append(existing['narration_quality'])
        record['analysis_mode']='visual' if record['narration_quality']['status']!='usable' and frames else 'speech'
        # A missing narration is not a missing visual source. Identity conflicts still block publication.
        if record['analysis_mode']=='visual':
            record['review_reasons']=[r for r in reasons if r not in ('缺少完整文字稿；AI摘要不能替代逐字稿','文字稿为空')]
            record['status']='needs_review' if record['review_reasons'] else 'ready'
        if existing and existing.get('creator_confirmation'):
            record['creator_confirmation'] = existing['creator_confirmation']
        record['transcript_hash'] = digest(raw)
        record['source_hash'] = source_fingerprint(self.root, record)
        index['videos'] = [r for r in index['videos'] if not existing or r['video_key'] != existing['video_key']] + [record]
        index['failures'] = [f for f in index['failures'] if f['url'] not in aliases]
        write_json(self.index_path, index)
        return record

    def review_narration(self, key, status, analysis_mode, reason, basis):
        from quality import assess, is_asr
        if status not in ('usable','unusable','missing') or analysis_mode not in ('speech','visual','mixed'):
            raise ValueError('无效的口播质量或分析方式')
        if not reason.strip() or basis not in ('text_review','audio_review'):
            raise ValueError('需要复核理由与实际复核依据')
        index=self.index()
        record=next(r for r in index['videos'] if r['video_key']==key)
        raw=self.read_transcript(record)
        screened=assess(raw,record['transcript_source'])
        if status=='usable' and (not raw.strip() or record['transcript_source'] in ('ai_conclusion','summary','ai_summary')):
            raise ValueError('空稿或AI摘要不能确认为可用口播')
        if status=='usable' and is_asr(record['transcript_source']) and basis!='audio_review':
            raise ValueError('自动转录确认为可用口播前必须实际核听对应音轨')
        if analysis_mode in ('speech','mixed') and status!='usable':
            raise ValueError('口播分析要求可用且已核对的口播全文')
        if analysis_mode in ('visual','mixed') and not record.get('frames'):
            raise ValueError('画面分析需要已归档画面')
        history=record.setdefault('quality_reviews',[])
        if record.get('narration_quality'):
            history.append(record['narration_quality'])
        record['narration_quality']={**screened,'status':status,'reason':reason.strip(),'basis':basis,'reviewed_at':now()}
        record['analysis_mode']=analysis_mode
        if record.get('transcript_hash')!=digest(raw):
            record['segments']=[]  # Old timing cannot be attached to a changed full text.
        record['paragraphs']=paragraphs(raw)
        record['transcript_hash']=digest(raw)
        # Upgrade legacy records without touching source files or re-running extraction.
        metadata=read_json(relative_file(self.root,record['artifact_dir'])/'metadata.json',{})
        data={**metadata.get('info',{}),**metadata}
        record.setdefault('note_caption',str(data.get('note_caption') or data.get('desc') or ''))
        record.setdefault('caption_source',record['source_url'])
        record.setdefault('caption_observed_at',data.get('caption_observed_at') or record['updated_at'])
        record['review_reasons']=[r for r in record['review_reasons'] if r not in ('文字稿为空','缺少完整文字稿；AI摘要不能替代逐字稿') and not r.startswith('ASR未取得可靠商品口播')]
        record['status']='needs_review' if record['review_reasons'] else 'ready'
        record['updated_at']=now()
        record['source_hash']=source_fingerprint(self.root,record)
        write_json(self.index_path,index)
        return record

    def attach_media(self,key,source,duration):
        """Attach an existing local original video; never download or transcribe."""
        source=Path(source).resolve()
        if not source.is_file() or source.suffix.lower() not in ('.mp4','.mov','.webm','.mkv'):
            raise ValueError('需要已有本地视频文件')
        if not isinstance(duration,(int,float)) or isinstance(duration,bool) or not math.isfinite(duration) or duration<=0:
            raise ValueError('需要原媒体实际正数时长')
        index=self.index();record=next(r for r in index['videos'] if r['video_key']==key)
        target=relative_file(self.root,record['artifact_dir'])/('source-media'+source.suffix.lower())
        if source!=target.resolve():
            if target.exists():
                backup=target.parent/'revisions'/now().replace(':','-');backup.mkdir(parents=True,exist_ok=True)
                shutil.copy2(target,backup/target.name)
            shutil.copy2(source,target)
        record['media']={'path':target.relative_to(self.root).as_posix(),'duration':duration,'sha256':hashlib.sha256(target.read_bytes()).hexdigest()}
        record['updated_at']=now();record['source_hash']=source_fingerprint(self.root,record)
        write_json(self.index_path,index);return record

    def import_directory(self, source, creator_override=None, refresh=False):
        source = Path(source).resolve()
        paths = [source / 'metadata.json'] if (source / 'metadata.json').exists() else sorted(source.rglob('metadata.json'))
        records = []
        for path in paths:
            if 'revisions' in path.parts:
                continue
            try:
                data = read_json(path)
                transcript = path.parent / 'transcript.txt'
                if transcript.exists():
                    data['subtitle_text'] = transcript.read_text(encoding='utf-8')
                clean = path.parent / 'transcript-cleaned.txt'
                if clean.exists():
                    data['cleaned_transcript'] = clean.read_text(encoding='utf-8')
                records.append(self.add(data, source_dir=path.parent, creator_override=creator_override, refresh=refresh))
                index = self.index()
                index['failures'] = [f for f in index['failures'] if f['url'] != str(path)]
                write_json(self.index_path,index)
            except (ValueError, OSError, TypeError) as exc:
                self.failure(str(path), str(exc))
        return records

    def confirm_creator(self, key, creator_id, name):
        if not creator_id.strip() or not name.strip():
            raise ValueError('需要人工确认的账号ID和博主名称')
        index = self.index()
        record = next(r for r in index['videos'] if r['video_key'] == key)
        # Confirmation resolves creator ambiguity only, never a source mismatch or missing transcript.
        record['review_reasons'] = [r for r in record['review_reasons'] if not any(t in r for t in ('博主', '作者'))]
        record.update(creator_id=creator_id.strip(), creator_name=name.strip(), creator_confirmation='manual')
        record['creator_key'] = record['platform'] + '--' + slug(creator_id) + '-' + digest(creator_id)[:8]
        old_dir = relative_file(self.root, record['artifact_dir'])
        new_dir = self.root / 'creators' / (slug(name) + '--' + record['creator_key']) / 'videos' / old_dir.name
        if old_dir != new_dir:
            new_dir.parent.mkdir(parents=True, exist_ok=True)
            if new_dir.exists():
                raise ValueError('目标归档已存在，请先检查重复记录')
            old_prefix = record['artifact_dir'].replace('\\', '/')
            old_dir.rename(new_dir)
            record['artifact_dir'] = new_dir.relative_to(self.root).as_posix()
            for frame in record['frames']:
                frame['path'] = record['artifact_dir'] + frame['path'].replace('\\', '/')[len(old_prefix):]
            if record.get('media'):
                record['media']['path']=record['artifact_dir']+record['media']['path'].replace('\\', '/')[len(old_prefix):]
        if record['status'] != 'needs_transcript':
            record['status'] = 'needs_review' if record['review_reasons'] else 'ready'
        record['updated_at'] = now()
        record['source_hash'] = source_fingerprint(self.root, record)
        write_json(self.index_path, index)
        return record
