"""Behavioral tests; the HTTP transport is replaced, never the billing service."""
import base64
import importlib
import io
import json
import os
from pathlib import Path
import struct
import sys
import tempfile
import unittest
from unittest.mock import patch
import urllib.error
import wave

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def load_module(name):
    try:
        return importlib.import_module(name)
    except ModuleNotFoundError as error:
        if error.name == name:
            return None
        raise


prep = load_module('prepare_script')
tts = load_module('synthesize_narration')


def stream(pcm=None, code=20000000, usage=12):
    pcm = pcm if pcm is not None else struct.pack('<h', 1000) * 2400
    packets = [{'code': 0, 'data': base64.b64encode(pcm).decode()},
               {'code': 0, 'data': None, 'sentence': {'text': '测试'}},
               {'code': code, 'data': None, 'usage': {'text_words': usage}}]
    return io.BytesIO(('\n'.join(json.dumps(p, ensure_ascii=False) for p in packets)).encode())


class ManuscriptTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(prep, 'prepare_script capability is missing')
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def test_markdown_keeps_content_and_math(self):
        text = '# 标题\n\n**中文**与 [API](https://example.com)。\n\n- 数字 2026，2*3，C++。\n> 引用。\n\n```python\nprint(1)\n```'
        result = prep.clean_markdown(text)
        for part in ['标题', '中文与 API。', '2026', '2*3', 'C++', '引用。', 'print(1)']:
            self.assertIn(part, result)
        self.assertNotIn('https://example.com', result)
        self.assertNotIn('```', result)

    def test_chunks_preserve_text_and_paragraphs(self):
        first = '这是第一句。' * 65
        second = 'API 2.0 supports 中文，数字 2026。'
        chunks = prep.split_chunks([first, second], 300)
        self.assertEqual(''.join(chunks), first + second)
        self.assertTrue(all(0 < len(c) <= 300 for c in chunks))
        self.assertEqual(chunks[-1], second)

    def test_markdown_keeps_identifiers_math_and_fenced_content(self):
        result = prep.clean_markdown('**重点**，2*3+4*5，api_key_name。\n\n```\n# literal_heading\na_b_c * 2\n```')
        self.assertIn('重点', result)
        self.assertIn('2*3+4*5', result)
        self.assertIn('api_key_name', result)
        self.assertIn('# literal_heading\na_b_c * 2', result)

    def test_english_unit_boundaries_keep_word_spacing(self):
        text = 'First sentence. Another API sentence! 最后一句。'
        script = prep.prepare(text, self.root)
        self.assertEqual(''.join(u['text'] for u in script['units']), text)

    def test_preserves_original_and_stable_unit_ids(self):
        raw = '# 原始标题\n\n第一句话。第二句话。\n\n最后一句。'
        script = prep.prepare(raw, self.root, title='演示', markdown=True)
        self.assertEqual((self.root / 'manuscript.original.md').read_text(), raw)
        before = {u['text']: u['id'] for u in script['units']}
        changed = prep.prepare(raw.replace('第一句话', '修改第一句'), self.root,
                               title='演示', markdown=True, replace=True)
        after = {u['text']: u['id'] for u in changed['units']}
        self.assertEqual(before['第二句话。'], after['第二句话。'])
        self.assertEqual(before['最后一句。'], after['最后一句。'])
        self.assertTrue(all(s['anchorUnit'] in after.values() for s in changed['scenes']))
        self.assertTrue((self.root / 'narration.json').exists())

    def test_empty_and_overwrite_are_rejected(self):
        with self.assertRaises(ValueError):
            prep.prepare('  ', self.root)
        prep.prepare('保留这句话。', self.root)
        old = (self.root / 'script.json').read_bytes()
        with self.assertRaisesRegex(ValueError, 'replace'):
            prep.prepare('另外一句话。', self.root)
        self.assertEqual((self.root / 'script.json').read_bytes(), old)


class ProtocolTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(tts, 'Doubao synthesis capability is missing')

    def test_complete_stream_returns_pcm_and_final_usage(self):
        pcm, metadata = tts.read_stream(stream())
        self.assertEqual(len(pcm), 4800)
        self.assertEqual(metadata['usage']['text_words'], 12)
        self.assertEqual(metadata['completionCode'], 20000000)

    def test_partial_stream_and_empty_audio_cannot_succeed(self):
        for body in [b'{"code":0,"data":"AQI="}\n',
                     b'{"code":20000000,"data":null}\n']:
            with self.subTest(body=body):
                with self.assertRaises(tts.SynthesisError):
                    tts.read_stream(io.BytesIO(body))

    def test_invalid_packet_or_base64_cannot_succeed(self):
        for body in [b'not json\n', b'{"code":0,"data":"!!!"}\n',
                     b'{"code":0,"data":"AQ=="}\n{"code":20000000}\n',
                     b'{"data":null}\n', b'[]\n']:
            with self.subTest(body=body):
                with self.assertRaises(tts.SynthesisError):
                    tts.read_stream(io.BytesIO(body))

    def test_usage_is_last_snapshot_not_sum(self):
        body = b'{"code":0,"data":"AQI=","usage":{"text_words":3}}\n{"code":20000000,"usage":{"text_words":9}}'
        _, metadata = tts.read_stream(io.BytesIO(body))
        self.assertEqual(metadata['usage']['text_words'], 9)

    def test_auth_quota_and_speaker_errors_are_not_retryable(self):
        for message in ['Unauthorized', 'quota exhausted', 'invalid speaker',
                        'resource ID is mismatched with speaker related resource']:
            body = json.dumps({'code': 55000000, 'message': message}).encode()
            with self.subTest(message=message):
                with self.assertRaises(tts.SynthesisError) as raised:
                    tts.read_stream(io.BytesIO(body))
                self.assertFalse(raised.exception.retryable)

    def test_retryable_http_503_retries_twice_and_changes_request_id(self):
        requests = []
        def transport(request, timeout):
            requests.append(request)
            if len(requests) < 3:
                raise urllib.error.HTTPError(request.full_url, 503, 'busy', {}, None)
            return stream()
        pcm, meta = tts.request_audio('中文 API。', tts.DEFAULT_CONFIG.copy(),
                                      'private-key', transport=transport, sleep=lambda _: None)
        self.assertTrue(pcm)
        self.assertEqual(meta['attempts'], 3)
        self.assertEqual(len({r.get_header('X-api-request-id') for r in requests}), 3)
        payload = json.loads(requests[-1].data)
        self.assertEqual(payload['req_params']['audio_params']['format'], 'pcm')
        self.assertEqual(requests[-1].get_header('X-api-key'), 'private-key')

    def test_http_401_stops_once_and_does_not_echo_secret(self):
        calls = []
        def transport(request, timeout):
            calls.append(request)
            raise urllib.error.HTTPError(request.full_url, 401, 'private-key', {}, None)
        with self.assertRaises(tts.SynthesisError) as raised:
            tts.request_audio('正文', tts.DEFAULT_CONFIG.copy(), 'private-key',
                              transport=transport, sleep=lambda _: None)
        self.assertEqual(len(calls), 1)
        self.assertNotIn('private-key', str(raised.exception))

    def test_missing_completion_retries_at_most_twice(self):
        calls = []
        def transport(request, timeout):
            calls.append(request)
            return io.BytesIO(b'{"code":0,"data":"AQI="}\n')
        with self.assertRaises(tts.SynthesisError):
            tts.request_audio('正文', tts.DEFAULT_CONFIG.copy(), 'key',
                              transport=transport, sleep=lambda _: None)
        self.assertEqual(len(calls), 3)

    def test_invalid_header_key_is_rejected_without_echo_or_network(self):
        calls = []
        def transport(request, timeout):
            calls.append(request)
            raise ValueError('Invalid header value: ' + request.get_header('X-api-key'))
        with self.assertRaises(tts.SynthesisError) as raised:
            tts.request_audio('正文', tts.DEFAULT_CONFIG.copy(), 'private-key\ninjected',
                              transport=transport, sleep=lambda _: None)
        self.assertNotIn('private-key', str(raised.exception))
        self.assertEqual(calls, [])


class CacheTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(tts, 'Doubao synthesis capability is missing')
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.script_path = self.root / 'script.json'
        self.config_path = self.root / 'narration.json'
        self.output = self.root / 'out' / 'narration'
        self.config_path.write_text(json.dumps(tts.DEFAULT_CONFIG))
        self.write_script(['第一段中文。', 'API 2.0 在 2026 年运行。'])
        self.calls = []

    def write_script(self, texts):
        self.script_path.write_text(json.dumps({'title': '测试', 'fps': 30,
            'units': [{'id': f'u{i}', 'text': text, 'paragraphId': f'p{i}'}
                      for i, text in enumerate(texts)],
            'scenes': [{'id': 's1', 'anchorUnit': 'u0', 'label': '测试'}]}))

    def transport(self, request, timeout):
        self.calls.append(json.loads(request.data)['req_params']['text'])
        return stream()

    def synthesize(self, transport=None):
        return tts.synthesize(self.script_path, self.config_path, self.output,
            api_key='private-key', transport=transport or self.transport, sleep=lambda _: None)

    def test_wav_and_usage_manifest_are_complete_without_secret(self):
        result = self.synthesize()
        with wave.open(str(self.output / 'voice.wav')) as audio:
            self.assertEqual(audio.getnframes(), 4800)
            self.assertEqual(audio.getframerate(), 24000)
        self.assertEqual(result['newlyBilledTextWords'], 24)
        self.assertEqual(result['cachedSegments'], 0)
        self.assertTrue(result['aiGenerated'])
        for path in self.output.rglob('*.json'):
            self.assertNotIn('private-key', path.read_text())

    def test_rerun_is_cached_and_edit_only_regenerates_changed_paragraph(self):
        self.synthesize()
        self.synthesize()
        self.assertEqual(len(self.calls), 2)
        self.write_script(['第一段中文。', '修改了第二段。'])
        result = self.synthesize()
        self.assertEqual(self.calls[-1], '修改了第二段。')
        self.assertEqual(len(self.calls), 3)
        self.assertEqual(result['cachedSegments'], 1)

    def test_changed_speaker_invalidates_cache(self):
        self.synthesize()
        config = {**tts.DEFAULT_CONFIG, 'speaker': 'another_voice'}
        self.config_path.write_text(json.dumps(config))
        self.synthesize()
        self.assertEqual(len(self.calls), 4)

    def test_corrupt_cache_is_not_reused(self):
        result = self.synthesize()
        cache_path = Path(result['segments'][0]['audioPath'])
        cache_path.write_bytes(b'broken')
        self.synthesize()
        self.assertEqual(len(self.calls), 3)

    def test_failure_preserves_completed_segments_and_removes_stale_final(self):
        self.synthesize()
        self.write_script(['第一段中文。', '新的第二段。'])
        def fail(request, timeout):
            return io.BytesIO(b'{"code":45000001,"message":"invalid speaker"}\n')
        with self.assertRaises(tts.SynthesisError):
            self.synthesize(fail)
        self.assertFalse((self.output / 'voice.wav').exists())
        self.assertFalse((self.output / 'narration.manifest.json').exists())
        self.assertEqual(json.loads((self.output / 'progress.json').read_text())['status'], 'failed')
        result = self.synthesize()
        self.assertEqual(result['cachedSegments'], 1)

    def test_missing_key_can_reuse_full_cache_but_cannot_call_service(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(tts.SynthesisError, 'DOUBAO_TTS_API_KEY'):
                tts.synthesize(self.script_path, self.config_path, self.output)
            self.synthesize()
            result = tts.synthesize(self.script_path, self.config_path, self.output)
        self.assertEqual(result['cachedSegments'], 2)

    def test_invalid_configuration_fails_before_network(self):
        for field, value in [('speechRate', True), ('speechRate', 101),
                             ('sampleRate', 12345), ('maxChunkChars', 0),
                             ('apiKey', 'secret')]:
            with self.subTest(field=field):
                config = {**tts.DEFAULT_CONFIG, field: value}
                self.config_path.write_text(json.dumps(config))
                with self.assertRaises(ValueError):
                    self.synthesize()
        self.assertEqual(self.calls, [])

    def test_cache_metadata_sample_count_must_match_decoded_wav(self):
        report = self.synthesize()
        meta = self.output / 'cache' / (report['segments'][0]['cacheKey'] + '.json')
        data = json.loads(meta.read_text())
        data.pop('sampleCount')
        meta.write_text(json.dumps(data))
        self.synthesize()
        self.assertEqual(len(self.calls), 3)

    def test_invalid_input_removes_previous_success_and_records_failed_status(self):
        self.synthesize()
        self.config_path.write_text('{broken json')
        with self.assertRaises(ValueError):
            self.synthesize()
        self.assertFalse((self.output / 'voice.wav').exists())
        self.assertFalse((self.output / 'narration.manifest.json').exists())
        self.assertEqual(json.loads((self.output / 'progress.json').read_text())['status'], 'failed')


if __name__ == '__main__':
    unittest.main()
