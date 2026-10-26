"""Anonymous media acquisition, with workspace-owned state and prepared local ASR.

Each provider returns evidence and identity together. Transport, downloader and
media tools are separate boundaries so failures cannot silently change identity.
"""
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import sys
import threading
import time
from urllib.parse import parse_qs, urlencode, urlsplit
from urllib.request import Request, urlopen

from archive import digest, identity, now, read_json, write_json
from portable import _stop_process_tree
from subtitle_formats import read_subtitle


class PublicMediaReader:
    def __init__(self, workspace, runtime):
        self.workspace = Path(workspace).resolve()
        self.runtime = dict(runtime)
        self.state = self.workspace / 'parser-state'
        self.state.mkdir(parents=True, exist_ok=True)
        self.CACHE_DIR = self.state / 'results'
        self.__file__ = __file__
        self.problems = []
        self.user_agent = ('Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) '
                           'AppleWebKit/605.1.15 Version/16.6 Mobile/15E148 Safari/604.1')

    def request(self, url, referer=''):
        parsed = urlsplit(url)
        if parsed.scheme not in ('http', 'https') or not parsed.hostname:
            raise ValueError('只接受 HTTP(S) 媒体地址')
        if parsed.username is not None or parsed.password is not None:
            raise ValueError('禁止带账号凭据的地址')
        headers = {'User-Agent': self.user_agent, 'Accept': '*/*'}
        if referer:
            headers['Referer'] = referer
        return Request(url, headers=headers)

    def fetch(self, url, referer=''):
        with urlopen(self.request(url, referer), timeout=30) as response:
            return response.read(), response.geturl()

    def json_api(self, endpoint, parameters=None):
        url = endpoint + ('?' + urlencode(parameters) if parameters else '')
        payload, _ = self.fetch(url, 'https://www.bilibili.com/')
        response = json.loads(payload)
        if response.get('code', 0) != 0:
            raise RuntimeError('匿名接口拒绝请求：' + str(response.get('message') or response.get('code')))
        return response.get('data') or {}

    def embedded(self, page, variable):
        marker = re.search(re.escape(variable) + r'\s*=\s*', page)
        if not marker:
            raise ValueError('匿名分享页没有返回可用数据；请导入本地素材，不使用登录态')
        try:
            return json.JSONDecoder().raw_decode(page[marker.end():].lstrip())[0]
        except ValueError as exc:
            raise ValueError('匿名分享页的数据格式无法读取') from exc

    def guarded(self, label, action):
        try:
            return action()
        except (ValueError, OSError, RuntimeError, ImportError, KeyError, IndexError, TypeError) as exc:
            self.problems.append(label + ': ' + str(exc))
            return None

    def resolve_page(self, url, platform):
        content, actual = self.fetch(url)
        expected = identity(url, platform)
        resolved = identity(actual, platform)
        self.request(actual)  # Reject credentials in a redirect as well.
        if expected['video_id'] and resolved['video_id'] != expected['video_id']:
            raise ValueError('分享页与提交链接的视频身份不一致')
        if not resolved['video_id']:
            raise ValueError('匿名分享链接未解析出目标视频身份')
        return content.decode('utf-8', errors='replace'), actual, resolved['video_id']

    def result_shell(self, platform, url, video_id, creator_id, title, author, duration, description):
        return {'platform': platform, 'url': url, 'video_id': str(video_id),
                'creator_id': str(creator_id or ''),
                'info': {'title': title or '', 'author': author or '', 'duration': duration or 0,
                         'description': description or ''},
                'subtitle_text': '', 'source': '', 'frames': []}

    def xiaohongshu_page(self, url):
        page, actual, note_id = self.resolve_page(url, 'xiaohongshu')
        state = self.embedded(page, 'window.__SETUP_SERVER_STATE__')
        note = (state.get('LAUNCHER_SSR_STORE_PAGE_DATA') or {}).get('noteData') or {}
        if not note:
            raise ValueError('匿名分享页未返回目标笔记数据')
        if str(note.get('noteId', '')) != note_id:
            raise ValueError('小红书页面与请求笔记身份不一致')
        person = note.get('user') or {}
        video = note.get('video') or {}
        media = video.get('media') or {}
        seconds = (video.get('capa') or {}).get('duration') or (media.get('video') or {}).get('duration') or 0
        seconds = float(seconds)
        if seconds > 10000:
            seconds /= 1000
        result = self.result_shell('xiaohongshu', actual, note_id, person.get('userId'),
                                   note.get('title'), person.get('nickName'), seconds, note.get('desc'))
        # Metadata comes from this same validated response, with no extra request.
        from upstream import xhs_metadata
        result.update(xhs_metadata(page, actual, note_id), note_id=note_id)
        streams = media.get('stream') or {}
        for codec in ('h264', 'h265', 'av1', 'h266'):
            for stream in streams.get(codec) or []:
                address = stream.get('masterUrl') or next(iter(stream.get('backupUrls') or []), '')
                if address:
                    result['_media_url'] = address
                    return result
        return result

    def douyin_page(self, url):
        page, actual, video_id = self.resolve_page(url, 'douyin')
        if not re.search(r'_ROUTER_DATA\s*=', page):
            payload, _ = self.fetch('https://www.iesdouyin.com/share/video/' + video_id + '/')
            page = payload.decode('utf-8', errors='replace')
        state = self.embedded(page, '_ROUTER_DATA')
        candidates = []
        for entry in (state.get('loaderData') or {}).values():
            if isinstance(entry, dict):
                candidates.extend((entry.get('videoInfoRes') or entry).get('item_list') or [])
        item = next((entry for entry in candidates if str(entry.get('aweme_id', '')) == video_id), None)
        if item is None:
            raise ValueError('抖音匿名分享页没有返回目标视频，身份未通过核对')
        person, video = item.get('author') or {}, item.get('video') or {}
        result = self.result_shell('douyin', actual, video_id, person.get('uid') or person.get('sec_uid'),
                                   item.get('desc'), person.get('nickname'),
                                   float(video.get('duration') or 0) / 1000, item.get('desc'))
        for key in ('play_addr', 'play_addr_h264', 'download_addr'):
            addresses = (video.get(key) or {}).get('url_list') or []
            if addresses:
                result['_media_url'] = addresses[0]
                break
        return result

    def bili_signature(self, parameters):
        # This permutation and digest are the platform's WBI wire protocol.
        images = self.json_api('https://api.bilibili.com/x/web-interface/nav').get('wbi_img') or {}
        material = ''.join(Path(urlsplit(images[name]).path).stem for name in ('img_url', 'sub_url'))
        order = (46,47,18,2,53,8,23,32,15,50,10,31,58,3,45,35,27,43,5,49,33,9,42,19,
                 29,28,14,39,12,38,41,13,37,48,7,16,24,55,40,61,26,17,0,1,60,51,30,4,
                 22,25,54,21,56,59,6,63,57,62,11,36,20,34,44,52)
        secret = ''.join(material[index] for index in order[:32])
        signed = {key: re.sub(r"[!'()*]", '', str(value))
                  for key, value in {**parameters, 'wts': int(time.time())}.items()}
        query = urlencode(sorted(signed.items()))
        signed['w_rid'] = hashlib.md5((query + secret).encode('utf-8')).hexdigest()
        return signed

    def bilibili_page(self, url):
        source = identity(url)
        actual = url
        if not source['video_id'] or (urlsplit(url).hostname or '').endswith('b23.tv'):
            _, actual, _ = self.resolve_page(url, 'bilibili')
            source = identity(actual)
        parts = parse_qs(urlsplit(actual).query).get('p', ['1'])
        if len(parts) != 1 or parts[0] != '1':
            raise ValueError('当前匿名链路不解析多P视频')
        video_id = source['video_id']
        video = self.json_api('https://api.bilibili.com/x/web-interface/view', {'bvid': video_id})
        if video.get('bvid') and str(video['bvid']) != video_id:
            raise ValueError('B站接口返回的视频身份不一致')
        if len(video.get('pages') or []) > 1:
            raise ValueError('多P视频暂不在线解析，请导入对应分P产物')
        cid = ((video.get('pages') or [{}])[0]).get('cid') or video.get('cid')
        if not cid:
            raise ValueError('B站匿名接口缺少目标视频CID')
        person = video.get('owner') or {}
        result = self.result_shell('bilibili', actual, video_id, person.get('mid'), video.get('title'),
                                   person.get('name'), video.get('duration'), video.get('desc'))
        result.update(bvid=video_id, page=1)
        parameters = {'bvid': video_id, 'cid': cid}
        subtitles = (video.get('subtitle') or {}).get('list') or []
        if not subtitles:
            signed = self.guarded('字幕签名', lambda: self.bili_signature(parameters)) or parameters
            player = self.guarded('读取字幕清单', lambda: self.json_api(
                'https://api.bilibili.com/x/player/wbi/v2', signed)) or {}
            subtitles = (player.get('subtitle') or {}).get('subtitles') or []
        if not subtitles:
            def page_subtitles():
                body, _ = self.fetch(actual, 'https://www.bilibili.com/')
                addresses = re.findall(r'"subtitle_url"\s*:\s*("(?:[^"\\]|\\.)*")', body.decode('utf-8', errors='replace'))
                return [{'subtitle_url': json.loads(value), 'lan': 'zh'} for value in addresses]
            subtitles = self.guarded('读取页面字幕地址', page_subtitles) or []
        preferred = str(self.runtime.get('language') or 'zh')
        for entry in sorted(subtitles, key=lambda row: not str(row.get('lan', '')).startswith((preferred, 'ai-' + preferred))):
            address = entry.get('subtitle_url') or ''
            if not address:
                continue
            if address.startswith('//'):
                address = 'https:' + address
            def caption():
                payload, _ = self.fetch(address, 'https://www.bilibili.com/')
                lines = json.loads(payload).get('body') or []
                return '\n'.join(str(row.get('content') or '').strip() for row in lines if str(row.get('content') or '').strip())
            text = self.guarded('下载完整字幕', caption)
            if text:
                result.update(subtitle_text=text, source='subtitle')
                break
        if not result['subtitle_text']:
            play = self.guarded('读取公开音轨', lambda: self.json_api(
                'https://api.bilibili.com/x/player/playurl', {**parameters, 'fnval': 16, 'fnver': 0, 'fourk': 1})) or {}
            tracks = (play.get('dash') or {}).get('audio') or []
            for track in sorted(tracks, key=lambda row: float(row.get('bandwidth') or 0), reverse=True):
                address = track.get('baseUrl') or track.get('base_url') or next(iter(track.get('backupUrl') or []), '')
                if address:
                    result['_audio_url'] = address
                    break
        return result

    def page_details(self, url):
        self.request(url)
        platform = identity(url)['platform']
        adapters = {'xiaohongshu': self.xiaohongshu_page, 'douyin': self.douyin_page, 'bilibili': self.bilibili_page}
        result = adapters[platform](url)
        result['source_resolution'] = {'input_url': url, 'resolved_url': result['url']}
        return result

    def execute(self, argv, timeout=300):
        environment = dict(os.environ)
        environment.update(PYTHONUTF8='1', PYTHONIOENCODING='utf-8', PYTHONDONTWRITEBYTECODE='1')
        if self.runtime.get('ffprobeLibraryPath') and sys.platform == 'darwin':
            environment['DYLD_LIBRARY_PATH'] = self.runtime['ffprobeLibraryPath']
        options = ({'creationflags': subprocess.CREATE_NEW_PROCESS_GROUP} if os.name == 'nt'
                   else {'start_new_session': True})
        with (self.state / 'tools.log').open('a', encoding='utf-8') as log:
            process = subprocess.Popen([str(value) for value in argv], cwd=str(self.workspace),
                                       env=environment, stdout=subprocess.PIPE, stderr=log,
                                       text=True, encoding='utf-8', errors='replace', **options)
            handlers = {}
            def cancel(signum, frame):
                # The outer worker owns a different group. Reap this tool group
                # immediately, before the outer worker's short kill deadline.
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                raise SystemExit(128 + signum)
            if os.name != 'nt' and threading.current_thread() is threading.main_thread():
                for signum in (signal.SIGTERM, signal.SIGINT):
                    handlers[signum] = signal.signal(signum, cancel)
            try:
                output, _ = process.communicate(timeout=timeout)
            except subprocess.TimeoutExpired as exc:
                _stop_process_tree(process)
                raise RuntimeError('媒体工具超时，已清理子进程') from exc
            except BaseException:
                _stop_process_tree(process)
                raise
            finally:
                for signum, handler in handlers.items():
                    signal.signal(signum, handler)
                if process.stdout:
                    process.stdout.close()
            if process.returncode:
                raise RuntimeError('媒体工具失败，详情见：' + str(self.state / 'tools.log'))
            return output

    def download_cli(self, arguments, url, timeout=300):
        # Only operations generated by this reader can cross the CLI boundary.
        valued = {'--sub-langs', '--sub-format', '-o', '-f'}
        switches = {'--skip-download', '--write-subs', '--write-auto-subs'}
        offset = 0
        while offset < len(arguments):
            option = arguments[offset]
            if option in switches:
                offset += 1
            elif option in valued and offset + 1 < len(arguments) and not str(arguments[offset + 1]).startswith('-'):
                offset += 2
            else:
                raise ValueError('禁止账号／Cookie／用户配置或未知下载器参数：' + str(option))
        self.request(url)
        if importlib.util.find_spec('yt_dlp'):
            command = [sys.executable, '-m', 'yt_dlp']
        elif shutil.which('yt-dlp'):
            command = [shutil.which('yt-dlp')]
        else:
            raise RuntimeError('缺少 yt-dlp，请先运行 setup')
        command.extend(['--ignore-config', '--no-playlist', '--socket-timeout', '20',
                        '--retries', '1', '--fragment-retries', '1'])
        if self.runtime.get('ffmpeg'):
            command.extend(['--ffmpeg-location', self.runtime['ffmpeg']])
        return self.execute(command + list(arguments) + ['--', url], timeout)

    def download_asset(self, url, target, referer):
        target = Path(target)
        temporary = target.with_suffix(target.suffix + '.partial')
        with urlopen(self.request(url, referer), timeout=120) as response, temporary.open('wb') as output:
            shutil.copyfileobj(response, output, length=1024 * 1024)
        if not temporary.stat().st_size:
            raise ValueError('公开媒体地址未返回文件内容')
        temporary.replace(target)
        return target

    def cli_asset(self, url, folder, kind):
        selector = 'bestaudio/best' if kind == 'audio' else 'best[ext=mp4]/best'
        self.download_cli(['-f', selector, '-o', str(folder / (kind + '.%(ext)s'))], url, 900)
        matches = sorted(path for path in folder.glob(kind + '.*') if path.suffix not in ('.part', '.ytdl') and path.stat().st_size)
        if not matches:
            raise RuntimeError('下载器没有产生可用的' + kind + '文件')
        return matches[0]

    def cli_captions(self, url, folder):
        language = self.runtime.get('language') or 'zh'
        languages = 'zh.*,en.*' if language in ('zh', 'auto') else language + '.*,en.*'
        self.guarded('下载字幕', lambda: self.download_cli([
            '--skip-download', '--write-subs', '--write-auto-subs', '--sub-langs', languages,
            '--sub-format', 'json3/vtt/srt/srv3/ttml/best', '-o', str(folder / 'caption.%(ext)s')], url))
        # A later language can fail after an earlier subtitle has already landed.
        paths = [path for path in folder.glob('caption.*') if path.suffix in ('.vtt', '.srt', '.json3', '.srv3', '.ttml', '.xml')]
        for path in sorted(paths, key=lambda path: ('.' + language not in path.name, path.suffix != '.json3', path.name)):
            text = self.guarded('读取字幕文件', lambda: read_subtitle(path))
            if text:
                return text
        return ''

    def transcribe(self, path):
        model = self.runtime.get('fasterWhisperModel') or self.runtime.get('whisperModel') or ''
        if not model or not Path(model).exists():
            raise ValueError('本地转录模型未准备；请运行 setup --with-transcription')
        language = self.runtime.get('language') or 'zh'
        if Path(model).is_dir():
            from faster_whisper import WhisperModel
            engine = WhisperModel(model, device='cpu', compute_type='int8', local_files_only=True)
            segments, _ = engine.transcribe(str(path), language=None if language == 'auto' else language)
            return '\n'.join(segment.text.strip() for segment in segments if segment.text.strip())
        binary, ffmpeg = self.runtime.get('whisperCli'), self.runtime.get('ffmpeg')
        if not binary or not ffmpeg:
            raise ValueError('whisper.cpp转录需要配置 whisperCli 和 ffmpeg')
        wave = Path(path).parent / 'recognition.wav'
        self.execute([ffmpeg, '-v', 'error', '-y', '-i', str(path), '-ar', '16000', '-ac', '1', str(wave)])
        output = wave.with_suffix('')
        self.execute([binary, '-m', model, '-f', str(wave), '-l', language, '-otxt', '-of', str(output)], 1800)
        return output.with_suffix('.txt').read_text(encoding='utf-8').strip()

    def sample_frames(self, video, folder, count=6):
        ffmpeg = self.runtime.get('ffmpeg') or shutil.which('ffmpeg')
        ffprobe = self.runtime.get('ffprobe') or shutil.which('ffprobe')
        if not ffmpeg or not ffprobe:
            raise RuntimeError('抽帧需要 FFmpeg 和 FFprobe，请先运行 setup')
        probe = self.execute([ffprobe, '-v', 'error', '-show_entries', 'format=duration', '-of', 'json', str(video)], 30)
        seconds = float(json.loads(probe).get('format', {}).get('duration') or 0)
        if not math.isfinite(seconds) or seconds <= 0:
            raise ValueError('无法确定原始媒体真实时长，不能推测帧时间戳')
        folder = Path(folder)
        folder.mkdir(parents=True, exist_ok=True)
        frames = []
        for index in range(count):
            timestamp = seconds * (index + 0.5) / count
            image = folder / ('%04d.jpg' % (index + 1))
            self.execute([ffmpeg, '-v', 'error', '-y', '-ss', '%.6f' % timestamp,
                          '-i', str(video), '-frames:v', '1', str(image)], 60)
            if image.is_file() and image.stat().st_size:
                frames.append({'path': str(image), 'timestamp': timestamp})
        return frames, seconds

    def result_path(self, url):
        settings = {key: self.runtime.get(key) for key in ('language', 'whisperModel', 'fasterWhisperModel')}
        return self.CACHE_DIR / (digest(json.dumps([url, settings, 1], sort_keys=True)) + '.json')

    def save_result(self, url, result):
        if result.get('subtitle_text') or result.get('frames'):
            write_json(self.result_path(url), result)

    def extract(self, url):
        self.problems = []
        cache = self.result_path(url)
        if cache.is_file() and time.time() - cache.stat().st_mtime < 7 * 86400:
            saved = self.guarded('读取缓存', lambda: read_json(cache))
            if isinstance(saved, dict) and (saved.get('subtitle_text') or saved.get('frames')):
                files = [frame.get('path', '') for frame in saved.get('frames') or []]
                if saved.get('media_file'):
                    files.append(saved['media_file'])
                if all(Path(path).is_file() and Path(path).resolve().is_relative_to(self.workspace) for path in files):
                    return saved
        # Identity errors stop here; they cannot be hidden by another downloader.
        result = self.page_details(url)
        folder = self.state / 'media' / digest(url)[:20]
        folder.mkdir(parents=True, exist_ok=True)
        media_address = result.pop('_media_url', '')
        audio_address = result.pop('_audio_url', '')
        referer = {'xiaohongshu': 'https://www.xiaohongshu.com/', 'douyin': 'https://www.douyin.com/',
                   'bilibili': 'https://www.bilibili.com/'}[result['platform']]
        video = self.guarded('下载公开视频', lambda: self.download_asset(media_address, folder / 'original.mp4', referer)) if media_address else None
        if not result.get('subtitle_text'):
            text = self.guarded('提取平台字幕', lambda: self.cli_captions(result['url'], folder))
            if text:
                result.update(subtitle_text=text, source='yt_dlp_subs')
        if not result.get('subtitle_text') and (self.runtime.get('fasterWhisperModel') or self.runtime.get('whisperModel')):
            audio = video
            if audio is None and audio_address:
                audio = self.guarded('下载公开音轨', lambda: self.download_asset(audio_address, folder / 'sound.m4s', referer))
            if audio is None:
                audio = self.guarded('下载转录素材', lambda: self.cli_asset(result['url'], folder, 'audio'))
            if audio:
                text = self.guarded('本地语音识别', lambda: self.transcribe(audio))
                if text:
                    result.update(subtitle_text=text, source='whisper_local')
        if video is None:
            video = self.guarded('下载抽帧素材', lambda: self.cli_asset(result['url'], folder, 'video'))
        if video:
            sampled = self.guarded('提取关键帧', lambda: self.sample_frames(video, folder / 'frames'))
            if sampled:
                result['frames'], result['media_duration'] = sampled
                result['media_file'] = str(video.resolve())
        if not result.get('subtitle_text'):
            result['source'] = 'visual_only'
            if not result.get('frames'):
                result['error'] = '匿名访问未取得完整文字稿或可用画面；请导入本地素材'
        if self.problems:
            result['warnings'] = list(self.problems)
        self.save_result(url, result)
        return result
