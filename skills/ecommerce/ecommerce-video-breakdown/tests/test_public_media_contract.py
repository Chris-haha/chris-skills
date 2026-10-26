"""Behavior contracts for the independently implemented anonymous reader.
Run only with fixture HTTP/tool boundaries. No real sites, dependencies or models.
"""
from pathlib import Path
import json
import os
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

SCRIPTS = Path(__file__).resolve().parents[1] / 'scripts'
sys.path.insert(0, str(SCRIPTS))
from public_media import PublicMediaReader
FIXTURES = Path(__file__).with_name('public-contract-fixtures')


def flattened(result):
    return {**(result.get('info') or {}), **result}


class PublicMediaContractTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='public-media-contract-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.runtime = {'python': sys.executable, 'language': 'zh', 'ffmpeg':'fixture-ffmpeg', 'ffprobe':'fixture-ffprobe'}
        self.reader = PublicMediaReader(self.root, self.runtime)
        self.no_network = patch('public_media.urlopen', side_effect=AssertionError('Contract tests forbid real network'))
        self.no_network.start();self.addCleanup(self.no_network.stop)

    def html(self, name):
        return (FIXTURES / name).read_bytes()

    def test_xhs_preserves_real_identity_caption_and_media(self):
        url='https://www.xiaohongshu.com/explore/abc123?xsec_token=keep&xsec_source=pc_share'
        with patch.object(self.reader, 'fetch', return_value=(self.html('xhs-match.html'), url)):
            value=flattened(self.reader.page_details(url))
        self.assertEqual(str(value.get('creator_id')), 'uid')
        self.assertEqual(value.get('note_caption'), '标题之外的正文')
        self.assertEqual(value.get('_media_url'), 'https://cdn.example/video.mp4')
        self.assertIn('abc123', str(value.get('note_id') or value.get('video_id') or value.get('url')))

    def check_stops(self, html, final, submitted, word):
        with patch.object(self.reader, 'fetch', return_value=(html, final)):
            try:
                result=self.reader.page_details(submitted)
            except (ValueError, RuntimeError) as exc:
                self.assertRegex(str(exc), word);return
        self.assertTrue(result.get('error'), result)
        self.assertRegex(result['error'], word)
        self.assertFalse(result.get('_media_url'))
        self.assertFalse(result.get('_audio_url'))

    def test_xhs_login_is_explicit_failure(self):
        self.check_stops(self.html('xhs-login.html'), 'https://www.xiaohongshu.com/login', 'https://xhslink.cn/o/short', '匿名|登录|身份')

    def test_xhs_mismatched_note_stops_before_media_download(self):
        self.check_stops(self.html('xhs-wrong.html'), 'https://www.xiaohongshu.com/explore/abc123', 'https://www.xiaohongshu.com/explore/abc123', '身份')

    def test_douyin_share_preserves_creator_and_video_id(self):
        url='https://www.douyin.com/video/12345'
        with patch.object(self.reader,'fetch',return_value=(self.html('douyin.html'),url)):
            value=flattened(self.reader.page_details(url))
        self.assertEqual(str(value.get('creator_id')),'creator-fixture')
        self.assertEqual(str(value.get('video_id') or value.get('aweme_id')),'12345')
        self.assertEqual(value.get('duration'),15)
        self.assertEqual(value.get('_media_url'),'https://cdn.example/video.mp4')

    def bili_fetch(self, calls, multi=False):
        def fetch(url,referer=''):
            calls.append(url)
            if 'subtitle.json' in url:
                return self.html('bili-subtitle.json'),url
            payload=json.loads(self.html('bili-view.json'))
            if multi: payload['data']['pages'].append({'page':2,'cid':3,'duration':12})
            return json.dumps(payload).encode(),url
        return fetch

    def test_bilibili_returns_full_subtitles_not_page_summary(self):
        calls=[]
        with patch.object(self.reader,'fetch',side_effect=self.bili_fetch(calls)):
            result=self.reader.page_details('https://www.bilibili.com/video/BVabc123')
        value=flattened(result)
        self.assertEqual(result.get('subtitle_text'),'第一句。\n第二句。')
        self.assertEqual(str(value.get('creator_id')),'88')
        self.assertEqual(result.get('source'),'subtitle')
        self.assertTrue(any('subtitle.json' in url for url in calls))

    def test_bilibili_multipart_stops_before_subtitle_request(self):
        calls=[]
        with patch.object(self.reader,'fetch',side_effect=self.bili_fetch(calls,multi=True)):
            try:
                result=self.reader.page_details('https://www.bilibili.com/video/BVabc123')
            except (ValueError,RuntimeError) as exc:
                self.assertIn('多P',str(exc))
            else:
                self.assertIn('多P',str(result.get('error')))
        self.assertFalse(any('subtitle.json' in url for url in calls))

    def test_downloader_ignores_configuration_and_blocks_auth_arguments(self):
        with patch.object(self.reader,'execute',return_value='{}') as execute, patch('public_media.importlib.util.find_spec',return_value=object()):
            self.reader.download_cli(['--skip-download'],'https://www.douyin.com/video/12345')
        self.assertIn('--ignore-config',execute.call_args.args[0])
        for args in (['--cookies-from-browser','chrome'],['--cookies','sentinel'],
                     ['--add-header','Cookie: secret'],['--add-headers','Authorization: secret'],
                     ['--add-header=Cookie: secret'],['--add-headers=Authorization: secret'],
                     ['--netrc'],['--username','user'],['--config-locations','config']):
            with self.subTest(args=args),patch.object(self.reader,'execute') as execute:
                with self.assertRaisesRegex(ValueError,'登录态|凭据|禁止|匿名'):
                    self.reader.download_cli(args,'https://www.douyin.com/video/12345')
                execute.assert_not_called()

    def test_local_model_uses_local_files_only_and_preserves_original_words(self):
        model=self.root/'prepared-model';model.mkdir()
        (model/'model.bin').write_bytes(b'local model fixture')
        runtime=dict(self.runtime,fasterWhisperModel=str(model),whisperModel=str(model))
        reader=PublicMediaReader(self.root,runtime)
        constructor=Mock(return_value=SimpleNamespace(transcribe=lambda *a,**k:([SimpleNamespace(text='包包原话，没有纠错替换。')],None)))
        with patch.dict(sys.modules,{'faster_whisper':SimpleNamespace(WhisperModel=constructor)}):
            result=reader.transcribe(self.root/'already-local.mp4')
        self.assertEqual(result,'包包原话，没有纠错替换。')
        self.assertTrue(constructor.call_args.kwargs.get('local_files_only'))
        self.assertEqual(str(constructor.call_args.args[0]),str(model))


    def test_frame_times_and_cached_actual_duration_use_ffprobe_precision(self):
        video=self.root/'original.mp4';video.write_bytes(b'fixture-video')
        def execute(argv,timeout=300):
            if '-show_entries' in argv:
                return json.dumps({'format':{'duration':'8.57'}})
            Path(argv[-1]).write_bytes(b'fixture-jpeg')
            return ''
        with patch.object(self.reader,'execute',side_effect=execute):
            frames,seconds=self.reader.sample_frames(video,self.root/'frames',count=3)
        self.assertEqual(seconds,8.57)
        self.assertEqual(len(frames),3)
        self.assertAlmostEqual(frames[0]['timestamp'],8.57*.5/3)
        self.assertAlmostEqual(frames[-1]['timestamp'],8.57*2.5/3)
        url='https://www.xiaohongshu.com/explore/abc123'
        result={'platform':'xiaohongshu','url':url,'video_id':'abc123','creator_id':'uid',
                'info':{'title':'fixture','duration':8},'subtitle_text':'','source':'visual_only',
                'frames':frames,'media_file':str(video),'media_duration':seconds}
        self.reader.save_result(url,result)
        with patch.object(self.reader,'page_details',side_effect=AssertionError('must use saved valid media cache')):
            cached=self.reader.extract(url)
        self.assertEqual(cached['media_duration'],8.57)
        self.assertAlmostEqual(cached['frames'][-1]['timestamp'],8.57*2.5/3)

    def test_missing_cached_frame_causes_acquisition_instead_of_reusing_bad_result(self):
        url='https://www.xiaohongshu.com/explore/abc123'
        self.reader.save_result(url,{'platform':'xiaohongshu','url':url,'subtitle_text':'old',
            'frames':[{'path':str(self.root/'missing.jpg'),'timestamp':1}]})
        with patch.object(self.reader,'page_details',side_effect=ValueError('cache miss reacquires')) as page:
            with self.assertRaisesRegex(ValueError,'reacquires'):self.reader.extract(url)
        page.assert_called_once_with(url)

    def test_visual_only_material_is_success_without_fabricated_transcript(self):
        url='https://www.xiaohongshu.com/explore/abc123'
        video=self.root/'original.mp4';video.write_bytes(b'fixture-video')
        frame=self.root/'frame.jpg';frame.write_bytes(b'fixture-jpeg')
        seed={'platform':'xiaohongshu','url':url,'video_id':'abc123','creator_id':'uid',
              'info':{'title':'visual-only fixture','duration':8},'subtitle_text':'','frames':[],
              '_media_url':'https://cdn.example/video.mp4'}
        with patch.object(self.reader,'page_details',return_value=seed), \
             patch.object(self.reader,'download_asset',return_value=video), \
             patch.object(self.reader,'cli_captions',return_value=''), \
             patch.object(self.reader,'sample_frames',return_value=([{'path':str(frame),'timestamp':1}],8.57)):
            result=self.reader.extract(url)
        self.assertFalse(result.get('error'))
        self.assertEqual(result['source'],'visual_only')
        self.assertFalse(result.get('subtitle_text'))
        self.assertEqual(result['frames'][0]['path'],str(frame))
        self.assertEqual(result['media_duration'],8.57)
        self.assertNotIn('_media_url',result)

    def test_later_subtitle_download_error_does_not_discard_existing_valid_caption(self):
        def download(arguments,url,timeout=300):
            output=Path(arguments[arguments.index('-o')+1]).parent
            (output/'caption.zh.vtt').write_text('WEBVTT\n\n00:00:00.000 --> 00:00:01.000\n已落地中文有效字幕\n',encoding='utf8')
            raise RuntimeError('English subtitle request failed: HTTP 429')
        folder=self.root/'captions';folder.mkdir()
        with patch.object(self.reader,'download_cli',side_effect=download):
            text=self.reader.cli_captions('https://www.douyin.com/video/12345',folder)
        self.assertEqual(text,'已落地中文有效字幕')
        self.assertTrue(any('429' in warning for warning in self.reader.problems))

    def test_anonymous_request_contains_no_cookie_or_authorization(self):
        request=self.reader.request('https://www.douyin.com/video/12345')
        self.assertFalse(any(key.lower() in ('cookie','authorization') for key,_ in request.header_items()))
        for url in ('https://name:secret@www.douyin.com/video/12345','file:///private.txt'):
            with self.subTest(url=url),self.assertRaises(ValueError):self.reader.request(url)


if __name__=='__main__':unittest.main()
