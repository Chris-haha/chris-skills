"""Video archive pipeline: downloader CLI, subtitle formats, local ASR and frames."""
from __future__ import annotations

import hashlib
import html
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import time
from urllib.parse import urlsplit
import xml.etree.ElementTree as ET


DOMAINS = {
    'bilibili': ('bilibili.com', 'b23.tv'),
    'youtube': ('youtube.com', 'youtu.be'),
    'douyin': ('douyin.com', 'iesdouyin.com'),
    'xiaohongshu': ('xiaohongshu.com', 'xhslink.com', 'xhslink.cn'),
    'tiktok': ('tiktok.com',),
}


def platform_name(url: str) -> str:
    host = (urlsplit(url).hostname or '').lower()
    return next((name for name, domains in DOMAINS.items()
                 if any(host == domain or host.endswith('.' + domain) for domain in domains)), 'generic')


def plain_text(value: str) -> str:
    return html.unescape(re.sub(r'<[^>]*>', '', value)).strip()


def xml_caption(node) -> str:
    parts = [node.text or '']
    for child in node:
        parts.append('\n' if child.tag.rsplit('}', 1)[-1] == 'br' else xml_caption(child))
        parts.append(child.tail or '')
    return ''.join(parts)


def read_subtitle(path: Path) -> str:
    content = path.read_text(encoding='utf-8-sig')
    if path.suffix.lower() == '.json3':
        data = json.loads(content)
        lines = [''.join(segment.get('utf8', '') for segment in event.get('segs', []))
                 for event in data.get('events', [])]
    elif path.suffix.lower() in ('.srv3', '.ttml', '.xml'):
        tree = ET.fromstring(content)
        lines = [xml_caption(node) for node in tree.iter()
                 if node.tag.rsplit('}', 1)[-1] in ('p', 'text')]
    else:
        lines = []
        for block in re.split(r'\n\s*\n', content.replace('\r\n', '\n')):
            block_lines = block.strip().splitlines()
            if not block_lines or block_lines[0].startswith(('WEBVTT', 'NOTE', 'STYLE', 'REGION')):
                continue
            timing = next((i for i, line in enumerate(block_lines) if '-->' in line), None)
            if timing is not None:
                lines.extend(line for line in block_lines[timing + 1:] if '-->' not in line)
    # Repeated sentences in separate cues are real content; keep them.
    return '\n'.join(text for line in lines if (text := plain_text(line)))


def duration_label(value) -> str:
    try:
        seconds = max(0, int(float(value or 0)))
    except (ValueError, TypeError, OverflowError):
        return '00:00'
    hours, remainder = divmod(seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f'{hours:02d}:{minutes:02d}:{seconds:02d}' if hours else f'{minutes:02d}:{seconds:02d}'


class MediaPipeline:
    def __init__(self, config: dict, state: Path):
        self.config = config
        self.state = Path(state)
        self.problems: list[str] = []

    def invoke(self, arguments: list[str], url: str, timeout: int = 300) -> str:
        command = [sys.executable, '-m', 'yt_dlp', '--ignore-config', '--no-playlist',
                   '--socket-timeout', '20', '--retries', '1', '--fragment-retries', '1']
        if self.config.get('ffmpeg'):
            command += ['--ffmpeg-location', self.config['ffmpeg']]
        if self.config.get('cookies_file'):
            command += ['--cookies', self.config['cookies_file']]
        command += [*arguments, url]
        process = subprocess.run(command, capture_output=True, encoding='utf8',
                                 errors='replace', timeout=timeout, check=False)
        if process.returncode:
            raise RuntimeError(process.stderr.strip()[-1800:] or f'下载器退出码 {process.returncode}')
        return process.stdout

    def attempt(self, label: str, action):
        try:
            return action()
        except Exception as exc:
            self.problems.append(f'{label}: {exc}')
            return None

    def metadata(self, url: str) -> dict:
        data = json.loads(self.invoke(['--dump-json', '--no-download'], url))
        if not isinstance(data, dict) or data.get('_type') == 'playlist':
            raise ValueError('请提供单条视频链接，不支持把播放列表作为一条视频归档')
        return data

    def subtitles(self, url: str, folder: Path) -> str:
        language = self.config.get('language', 'zh')
        languages = 'zh.*,en.*' if language in ('zh', 'auto') else f'{language}.*,en.*'
        self.attempt('下载字幕', lambda: self.invoke(['--skip-download', '--write-subs', '--write-auto-subs',
                     '--sub-langs', languages, '--sub-format', 'json3/vtt/srt/srv3/ttml/best',
                     '-o', str(folder / 'subtitles.%(ext)s')], url))
        files = [p for p in folder.iterdir() if p.suffix.lower() in ('.json3', '.vtt', '.srt', '.srv3', '.ttml')]
        files.sort(key=lambda p: (f'.{language}' not in p.name, p.suffix != '.json3', p.name))
        for path in files:
            text = self.attempt(f'读取字幕 {path.name}', lambda: read_subtitle(path))
            if text:
                return text
        return ''

    def youtube_subtitles(self, video_id: str) -> str:
        from youtube_transcript_api import YouTubeTranscriptApi
        language = self.config.get('language', 'zh')
        languages = ['zh-Hans', 'zh-CN', 'zh', 'en'] if language in ('zh', 'auto') else [language, 'en']
        transcript = YouTubeTranscriptApi().fetch(video_id, languages=list(dict.fromkeys(languages)))
        return '\n'.join(snippet.text.strip() for snippet in transcript if snippet.text.strip())

    def download(self, url: str, folder: Path, kind: str) -> Path:
        # A direct media URL can have a muxed stream and no standalone audio.
        format_selector = 'bestaudio/best' if kind == 'audio' else 'best[ext=mp4]/best'
        self.invoke(['-f', format_selector, '-o', str(folder / (kind + '.%(ext)s'))], url, timeout=900)
        files = sorted(p for p in folder.glob(kind + '.*')
                       if p.is_file() and p.stat().st_size and p.suffix not in ('.part', '.ytdl'))
        if not files:
            raise RuntimeError('下载器未生成可用媒体文件')
        return files[0]

    def transcribe(self, path: Path) -> str:
        from faster_whisper import WhisperModel
        model = WhisperModel(self.config.get('whisper_model', 'base'), device='cpu', compute_type='int8',
                             download_root=self.config.get('model_download_root'))
        language = self.config.get('language', 'zh')
        segments, _ = model.transcribe(str(path), language=None if language == 'auto' else language)
        return '\n'.join(segment.text.strip() for segment in segments if segment.text.strip())

    def frames(self, url: str, folder: Path, key: str, duration) -> list[dict]:
        ffmpeg = self.config.get('ffmpeg') or shutil.which('ffmpeg')
        ffprobe = self.config.get('ffprobe') or shutil.which('ffprobe')
        if not ffmpeg or not ffprobe:
            raise RuntimeError('抽帧需要 FFmpeg 和 FFprobe，请运行 runtime.py setup')
        video = self.download(url, folder, 'video')
        probe = subprocess.run([ffprobe, '-v', 'error', '-show_entries', 'format=duration',
                                '-of', 'json', str(video)], capture_output=True, encoding='utf8',
                               check=True, timeout=30)
        duration = float(json.loads(probe.stdout).get('format', {}).get('duration') or duration or 0)
        if duration <= 0:
            raise ValueError('无法确定媒体真实时长，未生成推测时间戳')
        output = self.state / 'frames' / key
        output.mkdir(parents=True, exist_ok=True)
        count = max(1, min(30, int(self.config.get('frames_per_video', 6))))
        images = []
        for index in range(count):
            timestamp = duration * (index + 1) / (count + 1)
            path = output / f'{index + 1:04d}.jpg'
            subprocess.run([ffmpeg, '-v', 'error', '-y', '-ss', f'{timestamp:.3f}',
                            '-i', str(video), '-frames:v', '1', str(path)], check=True,
                           capture_output=True, timeout=60)
            if path.is_file() and path.stat().st_size:
                images.append({'path': str(path), 'timestamp': timestamp})
        return images

    def cache_key(self, url: str) -> str:
        settings = {name: self.config.get(name) for name in
                    ('language', 'whisper_mode', 'whisper_model', 'extract_frames', 'frames_per_video')}
        identity = json.dumps({'url': url, 'settings': settings, 'format': 1}, sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(identity.encode('utf8')).hexdigest()

    def cached(self, path: Path) -> dict | None:
        if os.environ.get('MEDIA_URLS_BYPASS_CACHE') == '1' or not path.is_file():
            return None
        try:
            ttl = float(self.config.get('cache_ttl_days', 7))
            if ttl > 0 and time.time() - path.stat().st_mtime > ttl * 86400:
                return None
            data = json.loads(path.read_text(encoding='utf8'))
            if data.get('subtitle_text') and not data.get('error') and all(
                    Path(frame['path']).is_file() for frame in data.get('frames', [])):
                return dict(data, _cached=True)
        except (OSError, ValueError, KeyError, TypeError):
            pass
        return None

    def extract(self, url: str) -> dict:
        key = self.cache_key(url)
        cache = self.state / 'results' / (key + '.json')
        saved = self.cached(cache)
        if saved:
            return saved
        self.problems = []
        data = self.attempt('读取视频信息', lambda: self.metadata(url)) or {}
        result = {
            'title': data.get('title') or data.get('fulltitle') or '',
            'author': data.get('uploader') or data.get('channel') or data.get('creator') or '',
            'description': data.get('description') or '',
            'duration': duration_label(data.get('duration')),
            'platform': platform_name(url),
            'url': data.get('webpage_url') or url,
            'subtitle_text': '',
            'source': '',
        }
        with tempfile.TemporaryDirectory(prefix='media-archive-extract-') as temporary:
            folder = Path(temporary)
            text = self.attempt('提取字幕', lambda: self.subtitles(url, folder))
            if text:
                result.update(subtitle_text=text, source='yt_dlp_subs')
            if not text and result['platform'] == 'youtube' and data.get('id'):
                text = self.attempt('获取 YouTube 字幕', lambda: self.youtube_subtitles(data['id']))
                if text:
                    result.update(subtitle_text=text, source='youtube_transcript_api')
            if not text and self.config.get('whisper_mode', 'local') == 'local':
                media = self.attempt('下载转录音频', lambda: self.download(url, folder, 'audio'))
                text = self.attempt('本地语音识别', lambda: self.transcribe(media)) if media else None
                if text:
                    result.update(subtitle_text=text, source='whisper_local')
            if not result['subtitle_text']:
                result['error'] = '未取得字幕或有效转录文字稿。' + '\n' + '\n'.join(self.problems)
                if self.config.get('whisper_mode') == 'disabled':
                    result['error'] += '\n本地转录未启用，请运行 scripts/runtime.py setup。'
                return result
            if self.config.get('extract_frames'):
                images = self.attempt('提取关键帧', lambda: self.frames(url, folder, key, data.get('duration')))
                if images:
                    result['frames'] = images
                else:
                    result['warnings'] = self.problems[-1:]
        cache.parent.mkdir(parents=True, exist_ok=True)
        pending = cache.with_suffix('.tmp')
        pending.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf8')
        pending.replace(cache)
        return result
