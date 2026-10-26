"""Input normalization, identity checks and the isolated anonymous worker."""
import json
import os
import re
import sys
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlsplit, urlunsplit

from archive import identity, digest, read_json, write_json, now
from portable import resolve_runtime, run_process

run_isolated = run_process


def bundled_parser_path():
    return Path(__file__).resolve().parent / 'public_media.py'


def xhs_metadata(page, url, expected_id):
    """Read only the note data already returned by the anonymous share page."""
    match = re.search(r'window\.__SETUP_SERVER_STATE__\s*=\s*', page or '')
    if not match:
        return {}
    try:
        state, _ = json.JSONDecoder().raw_decode(page[match.end():].lstrip())
        note = state['LAUNCHER_SSR_STORE_PAGE_DATA']['noteData']
        if str(note.get('noteId', '')) != str(expected_id):
            return {}
        result = {'note_caption': str(note.get('desc') or ''), 'caption_source': url, 'caption_observed_at': now()}
        if (note.get('user') or {}).get('userId'):
            result['creator_id'] = str(note['user']['userId'])
        if isinstance(note.get('time'), (int, float)):
            from datetime import datetime, timezone
            result['published_at'] = datetime.fromtimestamp(note['time'] / 1000, timezone.utc).isoformat()
        metrics = {}
        for key, field in {'likes':'likedCount', 'favorites':'collectedCount', 'comments':'commentCount', 'shares':'shareCount'}.items():
            raw = str((note.get('interactInfo') or {}).get(field, ''))
            value = re.fullmatch(r'([0-9,.]+)\s*([KkMm万]?)', raw)
            if value:
                unit = value[2]
                metrics[key] = {'value': float(value[1].replace(',', '')) * {'':1, 'k':1000, 'm':1000000, '万':10000}[unit.lower()],
                                'raw_display': raw, 'approximate': bool(unit), 'source': url, 'observed_at': result['caption_observed_at']}
        result['metrics'] = metrics
        return result
    except (ValueError, KeyError, TypeError, OverflowError):
        return {}


def parse_input_text(text):
    text = text.strip()
    if text.startswith(('[', '{')):
        data = json.loads(text)
        if isinstance(data, dict):
            data = data.get('videos', [data])
        if not isinstance(data, list):
            raise ValueError('输入JSON应为链接对象数组或 videos 数组')
        rows = [r if isinstance(r, dict) else {'url': r} for r in data]
    else:
        urls = re.findall(r'https?://[^\s<>\]\)"\'，。！？）》】]+', text)
        rows = [{'url': url.rstrip(',;:')} for url in urls]
    seen, output = set(), []
    for row in rows:
        url = str(row.get('url', '')).strip()
        if url not in seen:
            seen.add(url)
            output.append({**row, 'url': url})
    return output


def check_online_url(url):
    parsed = urlsplit(url)
    if parsed.username is not None or parsed.password is not None:
        raise ValueError('本Skill禁止登录态链接中的账号凭据')
    source = identity(url)
    if source['platform'] == 'bilibili' and source['part'] != '1':
        raise ValueError('当前匿名链路不解析多P视频；请导入对应分P的真实产物，避免跨P取稿')


def _normalized_url(url, platform):
    source = urlsplit(url)
    tracking = {'xiaohongshu': {'source', 'xhsshare', 'xsec_token', 'xsec_source'},
                'douyin': {'from', 'share_source'}, 'bilibili': {'share_source', 'vd_source', 'spm', 'from'}}
    pairs = [(k, v) for k, values in parse_qs(source.query, keep_blank_values=True).items()
             if k.lower() not in tracking.get(platform, set()) and not k.lower().startswith('utm_') for v in values]
    return urlunsplit((source.scheme, source.netloc, source.path.rstrip('/'), urlencode(pairs), ''))


def compare_identity(submitted_url, metadata):
    """Compare submitted and observed video identities without network access."""
    metadata = {**(metadata.get('info') or {}), **metadata}
    raw = next((metadata.get(k) for k in ('url', 'source_url', 'share_url') if isinstance(metadata.get(k), str) and metadata[k].strip()), '')
    try:
        submitted = identity(submitted_url)
        parsed = identity(raw)
    except ValueError:
        return {'status':'needs_review', 'reason':'无法确认提交链接与解析结果是否为同一视频。'}
    hinted = str(metadata.get('platform') or '')
    explicit = [(metadata.get(k), platform) for k, platform in [('bvid', 'bilibili'), ('note_id', 'xiaohongshu'),
                                                              ('aweme_id', 'douyin'), ('video_id', '')]
                if metadata.get(k)]
    platforms = {submitted['platform'], parsed['platform']} | ({hinted} if hinted else set()) | {p for _, p in explicit if p}
    if len(platforms) != 1:
        return {'status':'needs_review', 'reason':'解析元数据存在平台身份冲突。'}
    ids = {str(value) for value, _ in explicit}
    if parsed['video_id']:
        ids.add(parsed['video_id'])
    if len(ids) > 1:
        return {'status':'needs_review', 'reason':'解析元数据视频ID与链接冲突。'}
    parsed_id = next(iter(ids), '')
    if submitted['platform'] == 'bilibili':
        page = metadata.get('page', parsed['part'])
        if str(page) != parsed['part'] or (submitted['video_id'] and parsed_id and submitted['part'] != parsed['part']):
            return {'status':'needs_review', 'reason':'B站分P不一致，不能引用其它分P文字稿。'}
    if submitted['video_id'] and parsed_id:
        return {'status':'verified', 'reason':''} if submitted['video_id'] == parsed_id else {
            'status':'needs_review', 'reason':'提交链接与解析结果的视频身份不一致。'}
    if not submitted['video_id'] and not parsed_id and _normalized_url(submitted_url, submitted['platform']) == _normalized_url(raw, parsed['platform']):
        return {'status':'verified', 'reason':''}
    return {'status':'needs_review', 'reason':'无法确认提交链接与解析结果是否为同一视频。'}


def load_parser(workspace, runtime):
    from public_media import PublicMediaReader
    return PublicMediaReader(workspace, runtime)


def command_env(runtime, workspace):
    env = dict(os.environ)
    directories = [str(Path(runtime[k]).parent) for k in ('ffmpeg', 'ffprobe', 'whisperCli', 'python') if runtime.get(k)]
    env['PATH'] = os.pathsep.join(directories + [env.get('PATH', '')])
    if sys.platform == 'darwin' and runtime.get('ffprobeLibraryPath'):
        env['DYLD_LIBRARY_PATH'] = runtime['ffprobeLibraryPath']
    env.update(PYTHONUTF8='1', PYTHONIOENCODING='utf-8', PYTHONDONTWRITEBYTECODE='1')
    # An application's PYTHONPATH is not an implicit dependency of this skill.
    env['PYTHONPATH'] = os.pathsep.join(runtime.get('packagePaths') or [])
    temporary = Path(workspace) / 'parser-state/tmp'
    temporary.mkdir(parents=True, exist_ok=True)
    env.update(TMPDIR=str(temporary), TMP=str(temporary), TEMP=str(temporary))
    return env


def extract_url(url, workspace, config_path=None):
    check_online_url(url)
    workspace = Path(workspace).resolve()
    runtime = resolve_runtime(workspace, config_path)
    job = workspace / 'parser-state/attempts' / digest(url)[:16]
    job.mkdir(parents=True, exist_ok=True)
    runtime_path = job / 'runtime.json'
    write_json(runtime_path, runtime)
    log = workspace / 'logs' / (digest(url)[:16] + '.log')
    command = [runtime.get('python') or sys.executable, str(Path(__file__).resolve()), '--worker', str(workspace), str(runtime_path), url]
    result = json.loads(run_isolated(command, workspace, command_env(runtime, workspace), log))
    if (result.get('error') or not result.get('subtitle_text')) and not result.get('frames'):
        raise RuntimeError('匿名解析未取得可用资料；禁止登录态兜底，请检查日志或导入本地素材。原原因：' +
                           str(result.get('error') or '未取得文字稿或画面'))
    verification_url = url
    resolution = result.get('source_resolution') or {}
    if not identity(url)['video_id'] and resolution.get('input_url') == url:
        resolved = resolution.get('resolved_url', '')
        if resolved and identity(resolved)['platform'] == identity(url)['platform']:
            verification_url = resolved
    result['identity_check'] = compare_identity(verification_url, result)
    result['identity_check']['basis'] = '本次匿名请求展开的短链' if verification_url != url else '原链接'
    result['submitted_url'] = url
    write_json(job / 'result.json', result)
    return result


def worker(workspace, runtime_path, url):
    sys.dont_write_bytecode = True
    runtime = read_json(runtime_path, {})
    parser = load_parser(workspace, runtime)
    try:
        result = parser.extract(url)
    except (ValueError, OSError, RuntimeError) as exc:
        result = {'error': str(exc)}
    print(json.dumps(result or {'error':'内置解析器没有返回结果'}, ensure_ascii=False))


if __name__ == '__main__':
    if len(sys.argv) == 5 and sys.argv[1] == '--worker':
        worker(Path(sys.argv[2]), Path(sys.argv[3]), sys.argv[4])
    else:
        raise SystemExit('请通过 video_breakdown.py 调用内置解析器')
