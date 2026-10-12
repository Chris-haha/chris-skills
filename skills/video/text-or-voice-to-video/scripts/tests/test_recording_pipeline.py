import hashlib
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import wave

import numpy as np

PIPELINE = Path(__file__).resolve().parents[1]


def write_wav(path, seconds, rate=48000):
    n = round(seconds * rate)
    t = np.arange(n) / rate
    # A changing frequency and envelope make a wrong shift distinguishable.
    signal = 0.22 * np.sin(2 * np.pi * (211 * t + 7 * t * t))
    signal *= 0.55 + 0.45 * np.sin(2 * np.pi * 1.73 * t) ** 2
    with wave.open(str(path), 'wb') as f:
        f.setnchannels(1)
        f.setsampwidth(2)
        f.setframerate(rate)
        f.writeframes((signal * 32767).astype('<i2').tobytes())


def asr_fixture(shift=0):
    tokens = []
    for i, char in enumerate('学习研究逻辑记录逐字稿'):
        start = 100 + i * 240 + (shift if i >= 4 else 0)
        tokens.append({'text': char, 'offsets': {'from': start, 'to': start + 180},
                       'p': 0.99, 't_dtw': -1})
    return {'transcription': [{'text': ''.join(t['text'] for t in tokens),
                              'offsets': {'from': 100, 'to': tokens[-1]['offsets']['to']},
                              'tokens': tokens}]}


def script_fixture():
    return {'title': '测试', 'fps': 30,
            'units': [{'id': 'early', 'text': '学习研究'},
                      {'id': 'late', 'text': '逻辑记录'},
                      {'id': 'end', 'text': '逐字稿'}],
            'scenes': [{'id': 'opening', 'anchorUnit': 'early', 'label': '学习'},
                       {'id': 'record', 'anchorUnit': 'late', 'label': '记录'}]}


class PipelineTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.voice = self.root / 'voice.wav'
        write_wav(self.voice, 4.21)
        self.asr = self.root / 'asr.json'
        self.script = self.root / 'script.json'
        self.output = self.root / 'timeline.json'
        self.asr.write_text(json.dumps(asr_fixture(), ensure_ascii=False))
        self.script.write_text(json.dumps(script_fixture(), ensure_ascii=False))

    def tearDown(self):
        self.tmp.cleanup()

    def cli(self, file, *args):
        return subprocess.run([sys.executable, str(PIPELINE / file), *map(str, args)],
                              text=True, capture_output=True)

    def manifest(self, asr_audio_path=None):
        asr_audio_path = asr_audio_path or self.voice
        manifest = self.root / 'asr.manifest.json'
        manifest.write_text(json.dumps({'schemaVersion': 1,
            'audioSha256': hashlib.sha256(self.voice.read_bytes()).hexdigest(),
            'asrSha256': hashlib.sha256(self.asr.read_bytes()).hexdigest(),
            'asrAudioSha256': hashlib.sha256(asr_audio_path.read_bytes()).hexdigest(),
            'asrAudioPath': str(asr_audio_path), 'association': 'whisper_cli_run'}))
        return manifest

    def align(self):
        result = self.cli('align_narration.py', '--audio', self.voice, '--asr', self.asr,
                          '--script', self.script, '--output', self.output, '--asr-manifest', self.manifest(),
                          '--timing-policy', 'token')
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(self.output.read_text())

    def test_pause_moves_later_anchors_without_moving_earlier_caption(self):
        before = self.align()
        self.asr.write_text(json.dumps(asr_fixture(900), ensure_ascii=False))
        after = self.align()
        self.assertEqual(before['captions'][0]['startMs'], after['captions'][0]['startMs'])
        self.assertEqual(before['captions'][0]['endMs'], after['captions'][0]['endMs'])
        self.assertEqual(after['scenes'][1]['startMs'] - before['scenes'][1]['startMs'], 900)
        self.assertEqual(after['scenes'][1]['startFrame'] - before['scenes'][1]['startFrame'], 27)

    def test_audio_longer_than_thirty_seconds_drives_duration_and_waveform(self):
        write_wav(self.voice, 31.217)
        timeline = self.align()
        self.assertEqual(timeline['durationFrames'], math.ceil(31.217 * 30))
        self.assertAlmostEqual(timeline['durationMs'], 31217, places=4)
        self.assertEqual(len(timeline['waveform']), timeline['durationFrames'])
        self.assertTrue(all(0 <= peak <= 1 for peak in timeline['waveform']))
        self.assertEqual(timeline['scenes'][-1]['endMs'], timeline['durationMs'])

    def test_unrelated_script_stops_and_writes_review_report(self):
        script = script_fixture()
        script['units'] = [{'id': 'early', 'text': '星球宇宙飞船火箭太空探索'}]
        script['scenes'] = [{'id': 'opening', 'anchorUnit': 'early', 'label': '宇宙'}]
        self.script.write_text(json.dumps(script, ensure_ascii=False))
        result = self.cli('align_narration.py', '--audio', self.voice, '--asr', self.asr,
                          '--script', self.script, '--output', self.output, '--asr-manifest', self.manifest())
        self.assertNotEqual(result.returncode, 0)
        report = self.root / 'timeline.review.json'
        self.assertTrue(report.exists(), result.stderr)
        self.assertEqual(json.loads(report.read_text())['status'], 'blocked_script_mismatch')
        self.assertFalse(self.output.exists())

    def test_alignment_output_collisions_preserve_successful_run_inputs(self):
        recognition_source = self.root / 'recognition_source.wav'
        recognition_source.write_bytes(self.voice.read_bytes())
        manifest = self.manifest(recognition_source)
        inputs = (self.voice, self.asr, self.script, manifest, recognition_source)
        originals = {path: path.read_bytes() for path in inputs}
        for target in inputs:
            with self.subTest(target=target.name):
                try:
                    result = self.cli('align_narration.py', '--audio', self.voice, '--asr', self.asr,
                                      '--script', self.script, '--output', target, '--asr-manifest', manifest)
                    self.assertNotEqual(result.returncode, 0)
                    self.assertIn('collision', result.stderr.lower())
                    for path, original in originals.items():
                        self.assertTrue(path.exists(), str(path))
                        self.assertEqual(hashlib.sha256(path.read_bytes()).digest(), hashlib.sha256(original).digest())
                finally:
                    for path, original in originals.items():
                        path.write_bytes(original)

    def test_failed_alignment_collision_cannot_delete_voice_or_overwrite_review_input(self):
        script = script_fixture()
        script['units'] = [{'id': 'early', 'text': '星球宇宙飞船火箭太空探索'}]
        script['scenes'] = [{'id': 'opening', 'anchorUnit': 'early', 'label': '宇宙'}]
        self.script.write_text(json.dumps(script, ensure_ascii=False))
        manifest = self.manifest()
        originals = {path: path.read_bytes() for path in (self.voice, self.asr, self.script, manifest)}
        result = self.cli('align_narration.py', '--audio', self.voice, '--asr', self.asr,
                          '--script', self.script, '--output', self.voice, '--asr-manifest', manifest)
        self.assertNotEqual(result.returncode, 0)
        for path, original in originals.items():
            self.assertTrue(path.exists(), str(path))
            self.assertEqual(path.read_bytes(), original)
        self.assertFalse(self.voice.with_suffix('.review.json').exists())

    def test_alignment_review_output_cannot_alias_manuscript(self):
        self.script = self.root / 'result.review.json'
        self.script.write_text(json.dumps(script_fixture(), ensure_ascii=False))
        original = self.script.read_bytes()
        manifest = self.manifest()
        result = self.cli('align_narration.py', '--audio', self.voice, '--asr', self.asr,
                          '--script', self.script, '--output', self.root/'result.json', '--asr-manifest', manifest)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.script.read_bytes(), original)
        self.assertFalse((self.root/'result.json').exists())

    def test_alignment_symlink_and_hardlink_output_aliases_are_untouched(self):
        original = self.script.read_bytes()
        manifest = self.manifest()
        for kind in ('symlink', 'hardlink'):
            output = self.root / (kind + '.json')
            if kind == 'symlink':
                output.symlink_to(self.script)
            else:
                os.link(self.script, output)
            with self.subTest(kind=kind):
                result = self.cli('align_narration.py', '--audio', self.voice, '--asr', self.asr,
                                  '--script', self.script, '--output', output, '--asr-manifest', manifest)
                self.assertNotEqual(result.returncode, 0)
                self.assertTrue(output.samefile(self.script))
                self.assertEqual(output.read_bytes(), original)
                self.assertEqual(self.script.read_bytes(), original)

    def test_alignment_default_manifest_collision_is_rejected(self):
        manifest = self.manifest()
        original = manifest.read_bytes()
        result = self.cli('align_narration.py', '--audio', self.voice, '--asr', self.asr,
                          '--script', self.script, '--output', manifest)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(manifest.read_bytes(), original)
        self.assertFalse(manifest.with_suffix('.review.json').exists())

    def test_invalid_script_schema_clears_old_timeline_without_traceback_or_input_mutation(self):
        old_timeline = self.align()
        valid_script = script_fixture()
        variants = [[], {'units': {}}, {'units': [123], 'scenes': valid_script['scenes']}]
        for update in (
                {'units': [{'id': 'early', 'text': 123}]},
                {'units': [{'id': [], 'text': '学习研究'}]},
                {'units': [{'id': '', 'text': '学习研究'}]},
                {'scenes': {}}, {'scenes': [123]},
                {'scenes': [{'id': 'opening', 'anchorUnit': [], 'label': '学习'}]},
                {'scenes': [{'id': 'opening', 'anchorUnit': 'early', 'label': 123}]},
                {'reviewedUnits': []}, {'reviewedUnits': {'early': []}}):
            variants.append({**valid_script, **update})
        for index, invalid in enumerate(variants):
            with self.subTest(index=index):
                self.output.write_text(json.dumps(old_timeline, ensure_ascii=False))
                self.script.write_text(json.dumps(invalid, ensure_ascii=False))
                original = self.script.read_bytes()
                result = self.cli('align_narration.py', '--audio', self.voice, '--asr', self.asr,
                                  '--script', self.script, '--output', self.output, '--asr-manifest', self.manifest())
                self.assertNotEqual(result.returncode, 0)
                self.assertNotIn('Traceback', result.stderr)
                self.assertFalse(self.output.exists())
                self.assertEqual(self.script.read_bytes(), original)
                report = json.loads(self.output.with_suffix('.review.json').read_text())
                self.assertEqual(report['status'], 'blocked_invalid_input')

    def test_changed_audio_hash_rejects_stale_timeline(self):
        self.align()
        write_wav(self.voice, 4.22)
        result = self.cli('validate_timeline.py', '--voice', self.voice, '--timeline', self.output)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('hash', result.stderr.lower())

    def test_split_utf8_tokens_are_reassembled_and_traditional_normalized(self):
        script = {'title': '测试', 'fps': 30, 'units': [{'id': 'step', 'text': '步骤'}],
                  'scenes': [{'id': 'opening', 'anchorUnit': 'step', 'label': '步骤'}]}
        self.script.write_text(json.dumps(script, ensure_ascii=False))
        # Old whisper.cpp may output invalid UTF-8 because a codepoint spans tokens.
        self.asr.write_bytes(b'{"transcription":[{"text":"\xe6\xad\xa5\xe9\xa9\x9f",'
                            b'"offsets":{"from":100,"to":800},"tokens":['
                            b'{"text":"\xe6\xad\xa5","offsets":{"from":100,"to":350},"p":0.99,"t_dtw":-1},'
                            b'{"text":"\xe9\xa9","offsets":{"from":400,"to":600},"p":0.99,"t_dtw":-1},'
                            b'{"text":"\x9f","offsets":{"from":600,"to":800},"p":0.99,"t_dtw":-1}]}]}')
        timeline = self.align()
        self.assertEqual(timeline['captions'][0]['text'], '步骤')
        self.assertEqual(timeline['captions'][0]['startMs'], 100)
        self.assertEqual(timeline['captions'][0]['endMs'], 800)
        self.assertEqual(timeline['alignment']['matchedCharacterRatio'], 1)

    def test_dtw_centiseconds_can_anchor_tokens_without_offsets(self):
        asr = asr_fixture()
        for token in asr['transcription'][0]['tokens']:
            token['t_dtw'] = token.pop('offsets')['from'] / 10
        self.asr.write_text(json.dumps(asr, ensure_ascii=False))
        timeline = self.align()
        self.assertEqual(timeline['captions'][1]['startMs'], 1060)
        self.assertIn('dtw', timeline['captions'][1]['timingSource'])
        self.assertTrue(timeline['captions'][1]['needsReview'])

    def test_whisper_control_tokens_are_not_transcribed_speech(self):
        asr = asr_fixture()
        asr['transcription'][0]['tokens'].append({'text': '[_EOT_]', 'id': 50257,
            'offsets': {'from': 4210, 'to': 4210}, 'p': 0.99, 't_dtw': -1})
        asr['transcription'].append({'text': '[_BEG_]', 'offsets': {'from': 4210, 'to': 4210},
                                    'tokens': [{'text': '[_BEG_]', 'id': 50258, 't_dtw': -1}]})
        self.asr.write_text(json.dumps(asr, ensure_ascii=False))
        timeline = self.align()
        self.assertNotIn('eot', timeline['alignment']['normalizedAsr'])
        self.assertNotIn('beg', timeline['alignment']['normalizedAsr'])
        self.assertEqual(timeline['alignment']['asrCharacterCoverage'], 1)

    def test_reviewed_override_records_reason_and_rejects_overlap(self):
        script = script_fixture()
        script['reviewedUnits'] = {'late': {'startMs': 1150, 'endMs': 1990,
                                         'reason': 'Listened to onset and ending in waveform preview'}}
        self.script.write_text(json.dumps(script, ensure_ascii=False))
        timeline = self.align()
        self.assertEqual(timeline['captions'][1]['startMs'], 1150)
        self.assertEqual(timeline['captions'][1]['timingSource'], 'reviewed_override')
        self.assertIn('reviewReason', timeline['captions'][1])
        script['reviewedUnits']['late']['startMs'] = 100
        self.script.write_text(json.dumps(script, ensure_ascii=False))
        result = self.cli('align_narration.py', '--audio', self.voice, '--asr', self.asr,
                          '--script', self.script, '--output', self.output, '--asr-manifest', self.manifest())
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('overlap', result.stderr.lower())

    def test_prepare_preserves_source_length_without_silence_trim(self):
        write_wav(self.voice, 31.217, rate=44100)
        prepared = self.root / 'prepared'
        result = self.cli('prepare_audio.py', '--input', self.voice, '--output-dir', prepared)
        self.assertEqual(result.returncode, 0, result.stderr)
        metadata = json.loads((prepared / 'metadata.json').read_text())
        with wave.open(str(self.voice)) as f:
            original_seconds = f.getnframes() / f.getframerate()
        with wave.open(str(prepared / 'canonical.wav')) as f:
            self.assertEqual(f.getframerate(), 48000)
            self.assertAlmostEqual(f.getnframes() / f.getframerate(), original_seconds, delta=1/48000)
        with wave.open(str(prepared / 'asr16k.wav')) as f:
            self.assertEqual(f.getframerate(), 16000)
        expected_hash = hashlib.sha256((prepared / 'canonical.wav').read_bytes()).hexdigest()
        self.assertEqual(metadata['canonical']['sha256'], expected_hash)

    def test_segment_policy_uses_phrase_bounds_over_early_token_estimates(self):
        asr = asr_fixture()
        tokens = asr['transcription'][0]['tokens']
        asr['transcription'] = [
            {'text': '学习研究', 'offsets': {'from': 100, 'to': 1300}, 'tokens': tokens[:4]},
            {'text': '逻辑记录', 'offsets': {'from': 1600, 'to': 2600}, 'tokens': tokens[4:8]},
            {'text': '逐字稿', 'offsets': {'from': 2800, 'to': 3600}, 'tokens': tokens[8:]}]
        self.asr.write_text(json.dumps(asr, ensure_ascii=False))
        result = self.cli('align_narration.py', '--audio', self.voice, '--asr', self.asr,
                          '--script', self.script, '--output', self.output,
                          '--timing-policy', 'segment', '--asr-manifest', self.manifest())
        self.assertEqual(result.returncode, 0, result.stderr)
        timeline = json.loads(self.output.read_text())
        self.assertEqual(timeline['captions'][0]['endMs'], 1300)
        self.assertEqual(timeline['captions'][1]['startMs'], 1600)
        self.assertEqual(timeline['scenes'][1]['startMs'], 1600)
        self.assertEqual(timeline['captions'][1]['timingSource'], 'segment_character_interpolation')

    def test_segment_policy_keeps_mismatched_unit_tail_in_its_phrase(self):
        asr = {'transcription': [
            {'text': '学习常识', 'offsets': {'from': 100, 'to': 1300}},
            {'text': '哎逻辑记录', 'offsets': {'from': 1600, 'to': 2600}},
            {'text': '逐字稿', 'offsets': {'from': 2800, 'to': 3600}}]}
        self.asr.write_text(json.dumps(asr, ensure_ascii=False))
        result = self.cli('align_narration.py', '--audio', self.voice, '--asr', self.asr,
                          '--script', self.script, '--output', self.output,
                          '--timing-policy', 'segment', '--asr-manifest', self.manifest())
        self.assertEqual(result.returncode, 0, result.stderr)
        timeline = json.loads(self.output.read_text())
        self.assertEqual(timeline['captions'][0]['endMs'], 1300)
        self.assertIn('asr_gap_bounded_to_phrase', timeline['captions'][0]['reviewFlags'])

    def test_long_leading_pcm_pause_refines_caption_onset_without_changing_audio(self):
        baseline = self.align()
        baseline_early = baseline['captions'][0]
        write_wav(self.voice, 33.0)
        with wave.open(str(self.voice), 'rb') as f:
            rate = f.getframerate()
            pcm = np.frombuffer(f.readframes(f.getnframes()), dtype='<i2').copy()
        pcm[round(6.34*rate):round(9.34*rate)] = 0
        with wave.open(str(self.voice), 'wb') as f:
            f.setnchannels(1); f.setsampwidth(2); f.setframerate(rate); f.writeframes(pcm.tobytes())
        script = script_fixture()
        script['units'] = [{'id': 'early', 'text': '学习研究'}, {'id': 'after', 'text': '那么这一步之后'},
                           {'id': 'late', 'text': '逻辑记录'}, {'id': 'end', 'text': '逐字稿'}]
        script['scenes'][1]['anchorUnit'] = 'after'
        self.script.write_text(json.dumps(script, ensure_ascii=False))
        self.asr.write_text(json.dumps({'transcription': [
            {'text': '学习研究', 'offsets': {'from': baseline_early['startMs'], 'to': baseline_early['endMs']}},
            {'text': '那么这一步之后', 'offsets': {'from': 6360, 'to': 10080}},
            {'text': '逻辑记录', 'offsets': {'from': 10080, 'to': 13160}},
            {'text': '逐字稿', 'offsets': {'from': 28300, 'to': 32860}}]}, ensure_ascii=False))
        source_hash = hashlib.sha256(self.voice.read_bytes()).hexdigest()
        result = self.cli('align_narration.py', '--audio', self.voice, '--asr', self.asr,
                          '--script', self.script, '--output', self.output,
                          '--timing-policy', 'segment', '--asr-manifest', self.manifest())
        self.assertEqual(result.returncode, 0, result.stderr)
        timeline = json.loads(self.output.read_text())
        early, after = timeline['captions'][:2]
        self.assertEqual((early['startMs'],early['endMs']),
                         (baseline_early['startMs'],baseline_early['endMs']))
        self.assertEqual(after['startMs'], 9340)
        self.assertEqual(after['endMs'], 10080)
        self.assertEqual(timeline['scenes'][1]['startMs'], 9340)
        self.assertTrue(after['needsReview'])
        self.assertIn('leading_silence_boundary_refined', after['reviewFlags'])
        self.assertEqual(after['boundaryRefinement']['priorStartMs'], 6360)
        self.assertEqual(timeline['durationFrames'], 990)
        self.assertEqual(timeline['durationMs'], 33000)
        self.assertEqual(source_hash, hashlib.sha256(self.voice.read_bytes()).hexdigest())

    def test_subtitle_estimate_wholly_inside_long_quiet_run_blocks_for_review(self):
        with wave.open(str(self.voice), 'rb') as f:
            rate = f.getframerate()
            pcm = np.frombuffer(f.readframes(f.getnframes()), dtype='<i2').copy()
        pcm[round(.05*rate):round(1.05*rate)] = 0
        with wave.open(str(self.voice), 'wb') as f:
            f.setnchannels(1); f.setsampwidth(2); f.setframerate(rate); f.writeframes(pcm.tobytes())
        result = self.cli('align_narration.py', '--audio', self.voice, '--asr', self.asr,
                          '--script', self.script, '--output', self.output,
                          '--timing-policy', 'token', '--asr-manifest', self.manifest())
        self.assertNotEqual(result.returncode, 0)
        report = json.loads(self.root.joinpath('timeline.review.json').read_text())
        self.assertEqual(report['status'], 'blocked_silent_unit_interval')
        self.assertEqual(report['unitId'], 'early')
        self.assertFalse(self.output.exists())

    def test_asr_spans_outside_audio_are_clipped_and_reviewed(self):
        asr = asr_fixture()
        asr['transcription'][0]['offsets']['to'] = 5000
        asr['transcription'].append({'text': '无关幻觉', 'offsets': {'from': 4500, 'to': 5500}})
        self.asr.write_text(json.dumps(asr, ensure_ascii=False))
        result = self.cli('align_narration.py', '--audio', self.voice, '--asr', self.asr,
                          '--script', self.script, '--output', self.output,
                          '--timing-policy', 'segment', '--asr-manifest', self.manifest())
        self.assertEqual(result.returncode, 0, result.stderr)
        timeline = json.loads(self.output.read_text())
        self.assertEqual(timeline['captions'][-1]['endMs'], 4210)
        self.assertIn('asr_spans_outside_audio', timeline['alignment']['reviewFlags'])
        self.assertEqual(timeline['alignment']['discardedSegments'][0]['text'], '无关幻觉')

    def test_asr_segment_mostly_outside_audio_is_discarded(self):
        asr = asr_fixture()
        asr['transcription'].append({'text': '无关幻觉', 'offsets': {'from': 4100, 'to': 5100}})
        self.asr.write_text(json.dumps(asr, ensure_ascii=False))
        timeline = self.align()
        self.assertNotIn('无关幻觉', timeline['alignment']['normalizedAsr'])
        discarded = timeline['alignment']['discardedSegments'][0]
        self.assertEqual(discarded['reason'], 'majority_of_segment_outside_audio')

    def test_unbound_asr_is_rejected(self):
        result = self.cli('align_narration.py', '--audio', self.voice, '--asr', self.asr,
                          '--script', self.script, '--output', self.output)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('ASR', result.stderr)
        self.assertIn('manifest', result.stderr.lower())

    def test_old_asr_audio_cannot_be_associated_with_new_voice(self):
        old_voice = self.root / 'old_voice.wav'
        old_voice.write_bytes(self.voice.read_bytes())
        write_wav(self.voice, 4.22)
        result = self.cli('align_narration.py', '--audio', self.voice, '--asr', self.asr,
                          '--script', self.script, '--output', self.output, '--asr-manifest', self.manifest(old_voice))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('ASR audio', result.stderr)

    def test_old_asr_manifest_cannot_be_used_with_new_voice(self):
        manifest = self.root / 'asr.manifest.json'
        manifest.write_text(json.dumps({'audioSha256': hashlib.sha256(self.voice.read_bytes()).hexdigest(),
                                       'asrSha256': hashlib.sha256(self.asr.read_bytes()).hexdigest(),
                                       'asrAudioSha256': hashlib.sha256(self.voice.read_bytes()).hexdigest(),
                                       'asrAudioPath': str(self.voice), 'association': 'whisper_cli_run'}))
        write_wav(self.voice, 4.22)
        result = self.cli('align_narration.py', '--audio', self.voice, '--asr', self.asr,
                          '--script', self.script, '--output', self.output, '--asr-manifest', manifest)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('hash', result.stderr.lower())

    def test_old_asr_cannot_be_rebound_by_supplying_current_voice_as_asr_audio(self):
        # Even with a genuine old manifest nearby, a fallback association cannot
        # establish that the existing JSON was transcribed from the new voice.
        self.manifest()
        write_wav(self.voice, 4.22)
        result = self.cli('align_narration.py', '--audio', self.voice, '--asr', self.asr,
                          '--script', self.script, '--output', self.output, '--asr-audio', self.voice)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('run_asr.py', result.stderr)
        self.assertFalse(self.output.exists())

    def test_non_engine_manifest_is_not_a_renderable_binding(self):
        path = self.manifest()
        data = json.loads(path.read_text())
        data['association'] = 'explicit_cli_source_association'
        path.write_text(json.dumps(data))
        result = self.cli('align_narration.py', '--audio', self.voice, '--asr', self.asr,
                          '--script', self.script, '--output', self.output, '--asr-manifest', path)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('run_asr.py', result.stderr)

    def test_render_validation_rejects_older_explicit_source_binding(self):
        timeline = self.align()
        timeline['provenance']['asrBinding']['association'] = 'explicit_cli_source_association'
        self.output.write_text(json.dumps(timeline, ensure_ascii=False))
        result = self.cli('validate_timeline.py', '--voice', self.voice, '--timeline', self.output)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('manifest', result.stderr.lower())

    def test_touching_caption_frame_ranges_follow_ms_visibility_without_overlap(self):
        script = script_fixture()
        script['reviewedUnits'] = {
            'early': {'startMs': 100, 'endMs': 1150, 'reason': 'Fixture boundary'},
            'late': {'startMs': 1150, 'endMs': 1990, 'reason': 'Fixture boundary'}}
        self.script.write_text(json.dumps(script, ensure_ascii=False))
        timeline = self.align()
        early, late = timeline['captions'][:2]
        self.assertLessEqual(early['endFrame'], late['startFrame'])
        for caption in timeline['captions']:
            visible = [frame for frame in range(timeline['durationFrames'])
                       if caption['startMs'] <= frame*1000/timeline['fps'] < caption['endMs']]
            self.assertEqual(list(range(caption['startFrame'], caption['endFrame'])), visible)

    def test_asr_runner_records_source_hashes_at_transcription_time(self):
        model = self.root / 'model.bin'
        model.write_bytes(b'test model fixture')
        # Stub only the nondeterministic external recognition engine. Resampling,
        # invocation, JSON parsing and source provenance remain real operations.
        recognizer = self.root / 'fixture_recognizer'
        recognizer.write_text('#!' + sys.executable + '\n' +
                              'import json,pathlib,sys,wave\n' +
                              'args=sys.argv; audio=args[args.index("-f")+1]\n' +
                              'with wave.open(audio) as f: assert f.getframerate()==16000\n' +
                              'out=args[args.index("-of")+1]+".json"\n' +
                              'pathlib.Path(out).write_text(' + repr(json.dumps(asr_fixture(), ensure_ascii=False)) + ')\n')
        recognizer.chmod(0o755)
        prefix = self.root / 'recognized'
        result = self.cli('run_asr.py', '--audio', self.voice, '--model', model,
                          '--output-prefix', prefix, '--whisper-cli', recognizer)
        self.assertEqual(result.returncode, 0, result.stderr)
        manifest_path = self.root / 'recognized.manifest.json'
        self.assertTrue(manifest_path.exists(), result.stderr)
        manifest = json.loads(manifest_path.read_text())
        self.assertEqual(manifest['audioSha256'], hashlib.sha256(self.voice.read_bytes()).hexdigest())
        self.assertEqual(manifest['asrSha256'], hashlib.sha256((self.root/'recognized.json').read_bytes()).hexdigest())
        self.assertEqual(manifest['association'], 'whisper_cli_run')
        result = self.cli('align_narration.py', '--audio', self.voice,
                          '--asr', self.root/'recognized.json', '--script', self.script,
                          '--output', self.output)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_mux_preserves_long_voice_and_decoded_alignment(self):
        write_wav(self.voice, 30.117)
        timeline = self.align()
        silent = self.root / 'silent.mp4'
        subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 'lavfi', '-i',
                        'color=c=black:s=96x96:r=30', '-frames:v', str(timeline['durationFrames']),
                        '-c:v', 'libx264', '-pix_fmt', 'yuv420p', str(silent)], check=True)
        final = self.root / 'final.mp4'
        result = self.cli('mux_audio.py', '--video', silent, '--voice', self.voice,
                          '--output', final, '--timeline', self.output)
        self.assertEqual(result.returncode, 0, result.stderr)
        report_dir = self.root / 'verified'
        result = self.cli('verify_media.py', '--video', final, '--voice', self.voice,
                          '--output-dir', report_dir)
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads((report_dir / 'verification.json').read_text())
        self.assertTrue(report['passed'], report)
        self.assertGreaterEqual(report['audio']['decodedDurationMs'], 30117)
        self.assertEqual(report['video']['decodedFrames'], timeline['durationFrames'])
        self.assertLessEqual(max(abs(w['offsetMs']) for w in report['alignment']['windows']), 2)

    def test_mux_rejects_a_video_shorter_than_voice(self):
        timeline = self.align()
        silent = self.root / 'short.mp4'
        subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 'lavfi', '-i',
                        'color=c=black:s=96x96:r=30', '-frames:v', '30',
                        '-c:v', 'libx264', '-pix_fmt', 'yuv420p', str(silent)], check=True)
        result = self.cli('mux_audio.py', '--video', silent, '--voice', self.voice,
                          '--output', self.root / 'final.mp4', '--timeline', self.output)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('frame', result.stderr.lower())

    def test_verification_detects_a_known_audio_offset(self):
        timeline = self.align()
        shifted = self.root / 'shifted.mp4'
        subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 'lavfi', '-i',
                        'color=c=black:s=96x96:r=30', '-i', str(self.voice),
                        '-frames:v', str(timeline['durationFrames']), '-c:v', 'libx264',
                        '-af', 'adelay=80', '-c:a', 'aac', str(shifted)], check=True)
        report_dir = self.root / 'shift_report'
        result = self.cli('verify_media.py', '--video', shifted, '--voice', self.voice,
                          '--output-dir', report_dir)
        self.assertNotEqual(result.returncode, 0)
        self.assertTrue((report_dir / 'verification.json').exists(), result.stderr)
        report = json.loads((report_dir / 'verification.json').read_text())
        self.assertFalse(report['passed'])
        self.assertTrue(any('offset' in failure for failure in report['failures']), report)
        self.assertTrue(all(75 <= w['offsetMs'] <= 85 for w in report['alignment']['windows']))

    def test_verification_rejects_corrupt_aac_tail_even_with_complete_voice(self):
        write_wav(self.voice, 30.117)
        silent = self.root / 'silent.mp4'
        subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 'lavfi', '-i',
                        'color=c=black:s=96x96:r=30', '-frames:v', '904',
                        '-c:v', 'libx264', '-pix_fmt', 'yuv420p', str(silent)], check=True)
        final = self.root / 'final.mp4'
        result = self.cli('mux_audio.py', '--video', silent, '--voice', self.voice, '--output', final)
        self.assertEqual(result.returncode, 0, result.stderr)
        probe = subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'a:0',
                                '-show_packets', '-of', 'json', str(final)],
                               capture_output=True, text=True, check=True)
        packet = json.loads(probe.stdout)['packets'][-1]
        position, size = int(packet['pos']), int(packet['size'])
        damaged_bytes = bytearray(final.read_bytes())
        damaged_bytes[position:position+size] = bytes(size)
        damaged = self.root / 'damaged_tail.mp4'
        damaged.write_bytes(damaged_bytes)
        strict_decode = subprocess.run(['ffmpeg', '-v', 'error', '-xerror', '-i', str(damaged),
                                        '-map', '0:a:0', '-f', 'null', '-'], capture_output=True)
        self.assertNotEqual(strict_decode.returncode, 0, 'Fixture must contain a real AAC decoder error')
        report_dir = self.root / 'damaged_report'
        result = self.cli('verify_media.py', '--video', damaged, '--voice', self.voice,
                          '--output-dir', report_dir)
        self.assertNotEqual(result.returncode, 0)
        report = json.loads((report_dir / 'verification.json').read_text())
        self.assertFalse(report['passed'])
        self.assertTrue(report['failures'])


if __name__ == '__main__':
    unittest.main()
