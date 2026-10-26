"""Offline migration tests; run with python -m unittest discover -s tests -v."""
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

SOURCE = Path(__file__).resolve().parents[1]


class StandaloneTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='media-archive-test-')
        self.root = Path(self.temp.name)
        self.skill = self.root / '新电脑 路径' / 'media-urls-batch-archive'
        shutil.copytree(SOURCE, self.skill, ignore=shutil.ignore_patterns('__pycache__', '.venv'))
        self.env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1', PYTHONUTF8='1',
                        HOME=str(self.root / 'empty-home'), CODEX_HOME=str(self.root / 'no-other-skills'),
                        MEDIA_URLS_RUNTIME=str(self.root / 'runtime'))
        self.env.pop('MEDIA_URLS_EXTRACTOR_PATH', None)
        self.env.pop('MEDIA_URLS_CONFIG', None)
        self.output = self.root / '归档 结果'

    def tearDown(self):
        self.temp.cleanup()

    def run_script(self, name, *args):
        path = self.skill / 'scripts' / name
        self.assertTrue(path.is_file(), f'独立包缺少运行脚本: {name}')
        return subprocess.run([sys.executable, str(path), *map(str, args)], cwd=self.root,
                              env=self.env, encoding='utf8', capture_output=True, timeout=60)

    def fixture_downloader(self, subtitles=True, asr=False):
        modules = self.root / 'fixture_modules'
        package = modules / 'yt_dlp'
        package.mkdir(parents=True)
        (package / '__init__.py').write_text('', encoding='utf8')
        (package / '__main__.py').write_text('''import json,sys
from pathlib import Path
args=sys.argv[1:]
if any(a.endswith('/fail') for a in args): sys.exit(1)
if '--version' in args: print('fixture-1')
elif '--dump-json' in args:
    if args[-1].endswith('/fail'): sys.exit(1)
    print(json.dumps({'id':'clip', 'title':'示例视频', 'uploader':'测试博主', 'duration':3}))
elif '--write-subs' in args:
    if SUBTITLES:
        pattern=args[args.index('-o')+1]
        Path(pattern.replace('%(id)s','clip').replace('%(ext)s','zh.vtt')).write_text('WEBVTT\\n\\n00:00:00.000 --> 00:00:02.000\\n可迁移字幕测试\\n', encoding='utf8')
elif '-f' in args and '-o' in args:
    pattern=args[args.index('-o')+1]
    Path(pattern.replace('%(ext)s','mp3')).write_bytes(b'fixture-audio')
'''.replace('SUBTITLES', repr(subtitles)), encoding='utf8')
        if asr:
            (modules / 'faster_whisper.py').write_text('''from types import SimpleNamespace
class WhisperModel:
    def __init__(self,*args,**kwargs): pass
    def transcribe(self,*args,**kwargs):
        return iter([SimpleNamespace(text='本地转录测试')]), None
''', encoding='utf8')
        self.env['PYTHONPATH'] = str(modules)

    def test_default_extractor_is_inside_the_copied_skill(self):
        self.assertTrue((self.skill / 'scripts/batch_archive_media_urls.py').is_file(), '缺少内置批处理器')
        result = subprocess.run([sys.executable, '-c',
            'import sys;sys.path.insert(0,sys.argv[1]);import batch_archive_media_urls as b;print(b.EXTRACTOR_PATH)',
            str(self.skill / 'scripts')], cwd=self.root, env=self.env, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(Path(result.stdout.strip()).is_relative_to(self.skill.resolve()))
        self.assertTrue(Path(result.stdout.strip()).is_file())

    def test_help_from_an_unrelated_directory(self):
        result = self.run_script('run.py', '--help')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('--input', result.stdout)

    def test_doctor_reports_missing_runtime_without_writing_into_skill(self):
        before = sorted(str(p.relative_to(self.skill)) for p in self.skill.rglob('*'))
        result = self.run_script('runtime.py', 'doctor')
        report = json.loads(result.stdout)
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(report['ready'])
        self.assertIn('setup', report['next_step'])
        self.assertEqual(before, sorted(str(p.relative_to(self.skill)) for p in self.skill.rglob('*')))

    def test_subtitle_archive_and_resume_with_bundled_parser(self):
        self.fixture_downloader()
        first = self.run_script('run.py', '--url', 'https://example.test/video', '--output-dir', self.output)
        self.assertEqual(first.returncode, 0, first.stderr)
        self.assertEqual(json.loads(first.stdout)['success'], 1)
        self.assertEqual((self.output / '测试博主/示例视频/transcript.txt').read_text(encoding='utf8'), '可迁移字幕测试\n')
        second = self.run_script('run.py', '--url', 'https://example.test/video', '--output-dir', self.output)
        self.assertEqual(json.loads(second.stdout)['skipped'], 1)

    def test_asr_fallback_uses_bundled_parser_without_other_skills(self):
        self.fixture_downloader(subtitles=False, asr=True)
        result = self.run_script('run.py', '--url', 'https://example.test/video', '--output-dir', self.output)
        self.assertEqual(result.returncode, 0, result.stderr)
        meta = json.loads((self.output / '测试博主/示例视频/metadata.json').read_text(encoding='utf8'))
        self.assertEqual(meta['source'], 'whisper_local')
        self.assertEqual(meta['subtitle_text'], '本地转录测试')

    def test_force_rerun_bypasses_parser_cache(self):
        self.fixture_downloader()
        args = ('--url', 'https://example.test/video', '--output-dir', self.output)
        self.assertEqual(self.run_script('run.py', *args).returncode, 0)
        downloader = self.root / 'fixture_modules/yt_dlp/__main__.py'
        downloader.write_text(downloader.read_text(encoding='utf8').replace('可迁移字幕测试', '更新后的字幕'), encoding='utf8')
        rerun = self.run_script('run.py', *args, '--no-skip-existing')
        self.assertEqual(rerun.returncode, 0, rerun.stderr)
        self.assertEqual((self.output / '测试博主/示例视频/transcript.txt').read_text(encoding='utf8'), '更新后的字幕\n')

    def test_ambiguous_directory_creates_no_output(self):
        folder = self.root / 'links'
        folder.mkdir()
        for name in ('one.txt','two.md'):
            (folder / name).write_text('https://example.test/video', encoding='utf8')
        result = self.run_script('run.py', '--input', folder, '--output-dir', self.output)
        self.assertEqual(result.returncode, 2)
        self.assertIn('one.txt', result.stderr)
        self.assertFalse(self.output.exists())

    def test_external_file_with_bom_and_duplicates(self):
        self.fixture_downloader()
        source = self.root / 'links.txt'
        original = '\ufeffhttps://example.test/video\nhttps://example.test/video\n'
        source.write_text(original, encoding='utf8')
        result = self.run_script('run.py', '--input', source, '--output-dir', self.output)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)['total'], 1)
        self.assertEqual(source.read_text(encoding='utf8'), original)

    def test_empty_transcript_is_failure_and_does_not_block_later_links(self):
        self.fixture_downloader(subtitles=False)
        config = self.root / 'config.json'
        config.write_text('{"whisper_mode":"disabled", "extract_frames":false}', encoding='utf8')
        result = self.run_script('run.py', '--config', config, '--url', 'https://example.test/fail',
                                 '--url', 'https://example.test/another', '--output-dir', self.output, '--retries', '0')
        self.assertEqual(result.returncode, 1, result.stderr)
        summary = json.loads(result.stdout)
        self.assertEqual(summary['failure'], 2)
        self.assertEqual(summary['success'], 0)

    def test_bad_config_stops_before_creating_output(self):
        config = self.root / 'bad.json'
        config.write_text('{broken', encoding='utf8')
        result = self.run_script('run.py', '--config', config, '--url', 'https://example.test/video', '--output-dir', self.output)
        self.assertEqual(result.returncode, 2)
        self.assertFalse(self.output.exists())

    def test_mixed_success_and_failure_return_nonzero_and_keep_success(self):
        self.fixture_downloader()
        result = self.run_script('run.py', '--url', 'https://example.test/fail', '--url', 'https://example.test/good',
                                 '--output-dir', self.output, '--retries', '0')
        self.assertEqual(result.returncode, 1)
        summary = json.loads(result.stdout)
        self.assertEqual((summary['success'],summary['failure']), (1,1))
        self.assertTrue((self.output / '测试博主/示例视频/transcript.txt').is_file())


class ParserContractTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        scripts = SOURCE / 'scripts'
        sys.path.insert(0, str(scripts))
        import batch_archive_media_urls
        self.batch = batch_archive_media_urls

    def tearDown(self):
        self.temp.cleanup()
        sys.path.pop(0)

    def test_archive_names_work_with_windows_reserved_names(self):
        self.assertEqual(self.batch.sanitize_path_component('CON'), '_CON')
        self.assertEqual(self.batch.sanitize_path_component('aux.txt'), '_aux.txt')

    def test_long_unicode_names_fit_a_portable_filename(self):
        name = self.batch.sanitize_path_component('很长的视频标题' * 50)
        self.assertLessEqual(len(name.encode('utf8')), 180)
        self.assertTrue(name)

    def test_frames_are_copied_inside_archive(self):
        frame = self.root / 'outside.jpg'
        frame.write_bytes(b'frame-fixture')
        item = self.batch.write_archive_files(self.root / 'out', 'https://example.test/video',
            {'author':'test', 'title':'clip', 'subtitle_text':'text', 'frames':[{'path':str(frame), 'timestamp':1}]}, 1)
        metadata = json.loads((item / 'metadata.json').read_text(encoding='utf8'))
        path = Path(metadata['frames'][0]['path'])
        self.assertFalse(path.is_absolute())
        self.assertEqual((item / path).read_bytes(), b'frame-fixture')

    def pipeline(self):
        path = SOURCE / 'scripts/media_pipeline.py'
        self.assertTrue(path.is_file(), '缺少本技能自己的解析流程实现')
        import media_pipeline
        return media_pipeline

    def test_no_other_skill_parser_is_bundled(self):
        self.assertFalse((SOURCE / 'scripts/vendor').exists(), '仍然随包复制了其他 skill 的解析实现')

    def test_srt_preserves_repeated_sentences_at_different_times(self):
        path = self.root / 'sub.srt'
        path.write_text('1\n00:00:00,000 --> 00:00:01,000\n同一句话\n\n2\n00:00:02,000 --> 00:00:03,000\n同一句话\n', encoding='utf8')
        self.assertEqual(self.pipeline().read_subtitle(path), '同一句话\n同一句话')

    def test_json3_subtitles_and_entities(self):
        path = self.root / 'sub.json3'
        path.write_text(json.dumps({'events':[{'segs':[{'utf8':'A &amp; B'}]}, {'segs':[{'utf8':'第二'}, {'utf8':'句'}]}]}))
        self.assertEqual(self.pipeline().read_subtitle(path), 'A & B\n第二句')

    def test_webvtt_ignores_styles_notes_and_cue_ids(self):
        path = self.root / 'sub.vtt'
        path.write_text('WEBVTT\n\nSTYLE\n::cue { color: lime; }\n\nNOTE comment\nnot speech\n\ncue-one\n00:00:00.000 --> 00:00:01.000\n<b>hello</b> &amp; world\n', encoding='utf8')
        self.assertEqual(self.pipeline().read_subtitle(path), 'hello & world')

    def test_xml_subtitles_use_only_paragraph_text(self):
        path = self.root / 'sub.ttml'
        path.write_text('<tt><head>not speech</head><body><p>第一<span>句</span></p><p>next</p></body></tt>', encoding='utf8')
        self.assertEqual(self.pipeline().read_subtitle(path), '第一句\nnext')

    def test_ttml_keeps_line_breaks_between_words(self):
        path = self.root / 'sub.ttml'
        path.write_text('<tt><body><p>Hello<br/>world</p></body></tt>', encoding='utf8')
        self.assertEqual(self.pipeline().read_subtitle(path), 'Hello\nworld')

    def test_partial_subtitle_download_keeps_the_successful_language(self):
        from unittest.mock import patch
        pipeline = self.pipeline().MediaPipeline({'whisper_mode':'disabled'}, self.root)
        def invoke(arguments, url, **kwargs):
            if '--dump-json' in arguments:
                return '{"title":"clip"}'
            pattern = Path(arguments[arguments.index('-o') + 1])
            pattern.with_name('subtitles.zh.vtt').write_text('WEBVTT\n\n00:00:00.000 --> 00:00:01.000\n可用中文字幕\n', encoding='utf8')
            raise RuntimeError('English subtitles HTTP 429')
        with patch.object(pipeline, 'invoke', invoke):
            result = pipeline.extract('https://example.test/video')
        self.assertEqual(result.get('subtitle_text'), '可用中文字幕')
        self.assertNotIn('error', result)

    def test_bilibili_query_is_passed_to_downloader_unchanged(self):
        from unittest.mock import patch
        pipeline = self.pipeline()
        url = 'https://www.bilibili.com/video/BV1234567890/?p=2'
        with patch.object(pipeline.subprocess, 'run', return_value=subprocess.CompletedProcess([], 0, '{}', '')) as run:
            pipeline.MediaPipeline({}, self.root).invoke(['--dump-json'], url)
        self.assertEqual(run.call_args.args[0][-1], url)
        self.assertIn('--ignore-config', run.call_args.args[0])

    def test_page_summary_is_not_treated_as_a_subtitle(self):
        path = self.root / 'sub.json3'
        path.write_text('{"description":"THIS IS A SUMMARY"}', encoding='utf8')
        self.assertEqual(self.pipeline().read_subtitle(path), '')

    def test_platform_host_matching_uses_domain_boundaries(self):
        pipeline = self.pipeline()
        self.assertEqual(pipeline.platform_name('https://youtube.com.evil.test/watch?v=abc'), 'generic')
        self.assertEqual(pipeline.platform_name('https://www.youtube.com/watch?v=abc'), 'youtube')



if __name__ == '__main__':
    unittest.main()
