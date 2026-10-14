"""Real PCM and ffmpeg coverage for anchored, provenance-bound audio mixes."""
import json
import math
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import wave

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from align_narration import align
from common import pcm_wav, save_json, sha256
from test_recording_pipeline import asr_fixture, script_fixture, write_wav


class MixAudioTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.voice = self.root/'voice.wav'
        write_wav(self.voice, 4.21)
        self.asr = self.root/'asr.json'
        self.script = self.root/'script.json'
        save_json(self.asr, asr_fixture())
        save_json(self.script, script_fixture())
        self.asr_manifest = self.root/'asr.manifest.json'
        save_json(self.asr_manifest, {'audioSha256': sha256(self.voice), 'asrSha256': sha256(self.asr),
            'asrAudioSha256': sha256(self.voice), 'asrAudioPath': str(self.voice), 'association': 'whisper_cli_run'})
        self.timeline = self.root/'timeline.json'
        save_json(self.timeline, align(self.voice, self.asr, self.script, manifest_path=self.asr_manifest))
        self.bgm = self.root/'bgm.wav'
        self.sfx = self.root/'sfx.wav'
        write_wav(self.bgm, 5.0, 24000)
        write_wav(self.sfx, .12, 32000)
        self.plan_path = self.root/'audio-plan.json'
        self.plan = {'schemaVersion': 1, 'voiceSha256': sha256(self.voice),
            'timelineSha256': sha256(self.timeline),
            'bgm': {'path': self.bgm.name, 'sha256': sha256(self.bgm), 'volume': .15,
                    'fadeInMs': 100, 'fadeOutMs': 200,
                    'ducking': {'thresholdDbfs': -40, 'gain': .25, 'attackMs': 20, 'releaseMs': 150}},
            'sfx': [{'id': 'accent', 'path': self.sfx.name, 'sha256': sha256(self.sfx),
                     'anchorUnit': 'late', 'offsetMs': 20, 'volume': .3}]}
        self.output = self.root/'mix.wav'
        self.save_plan()

    def save_plan(self):
        save_json(self.plan_path, self.plan)

    def cli(self, script, *args):
        return subprocess.run([sys.executable, str(Path(__file__).resolve().parents[1]/script),
                               *map(str, args)], capture_output=True, text=True)

    def mix_cli(self, *extra):
        return self.cli('mix_audio.py', '--voice', self.voice, '--timeline', self.timeline,
                        '--plan', self.plan_path, '--output', self.output, *extra)

    def require_mix(self, *extra):
        result = self.mix_cli(*extra)
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(self.output.with_suffix('.mix.json').read_text())

    def test_voice_only_is_bit_exact_and_dry_run_writes_nothing(self):
        self.plan.pop('bgm'); self.plan['sfx'] = []; self.save_plan()
        result = self.mix_cli('--dry-run')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(self.output.exists())
        self.assertFalse(self.output.with_suffix('.mix.json').exists())
        original = self.voice.read_bytes()
        manifest = self.require_mix()
        self.assertTrue(np.array_equal(pcm_wav(self.voice)[0], pcm_wav(self.output)[0]))
        self.assertEqual(self.voice.read_bytes(), original)
        self.assertEqual(manifest['voice']['gain'], 1)
        self.assertEqual(manifest['voice']['offsetSamples'], 0)
        self.assertTrue(manifest['voice']['unchanged'])

    def test_sfx_uses_current_caption_anchor_and_no_bgm_retains_effect(self):
        no_bgm = self.root/'no-bgm.wav'
        manifest = self.require_mix('--no-bgm-output', no_bgm)
        voice, audio = pcm_wav(self.voice)
        mixed, info = pcm_wav(self.output)
        effect_only, _ = pcm_wav(no_bgm)
        self.assertEqual((audio['sampleCount'], audio['sampleRate']), (info['sampleCount'], info['sampleRate']))
        caption = next(c for c in json.loads(self.timeline.read_text())['captions'] if c['id'] == 'late')
        start = round((caption['startMs'] + 20)*audio['sampleRate']/1000)
        self.assertEqual(manifest['sfx'][0]['startSample'], start)
        self.assertEqual(manifest['sfx'][0]['anchorStartMs'], caption['startMs'])
        self.assertTrue(np.array_equal(effect_only[:start], voice[:start]))
        self.assertGreater(float(np.max(np.abs(effect_only[start:start+4000]-voice[start:start+4000]))), .01)
        self.assertFalse(np.array_equal(mixed, effect_only))
        self.assertTrue(json.loads(no_bgm.with_suffix('.mix.json').read_text())['omitBgm'])

    def test_ducking_reduces_music_during_speech_and_fades_music(self):
        # A quiet/speech/quiet envelope exposes the BGM attenuation independently.
        with wave.open(str(self.voice), 'rb') as source:
            pcm = np.frombuffer(source.readframes(source.getnframes()), '<i2').copy()
        pcm[:48000] = 0; pcm[-48000:] = 0
        with wave.open(str(self.voice), 'wb') as out:
            out.setnchannels(1); out.setsampwidth(2); out.setframerate(48000); out.writeframes(pcm.tobytes())
        save_json(self.asr_manifest, {'audioSha256': sha256(self.voice), 'asrSha256': sha256(self.asr),
            'asrAudioSha256': sha256(self.voice), 'asrAudioPath': str(self.voice), 'association': 'whisper_cli_run'})
        timeline = json.loads(self.timeline.read_text())
        timeline['audio']['sha256'] = sha256(self.voice)
        timeline['provenance']['asrBinding']['audioSha256'] = sha256(self.voice)
        timeline['provenance']['asrBinding']['asrAudioSha256'] = sha256(self.voice)
        save_json(self.timeline, timeline)
        self.plan['voiceSha256'] = sha256(self.voice); self.plan['timelineSha256'] = sha256(self.timeline)
        self.plan['sfx'] = []; self.save_plan()
        manifest = self.require_mix()
        gains = manifest['bgm']['ducking']['appliedGainRange']
        self.assertLessEqual(gains[0], .251)
        self.assertGreater(gains[1], .99)
        mixed, _ = pcm_wav(self.output)
        self.assertEqual(mixed[0], 0)
        self.assertEqual(mixed[-1], 0)

    def test_invalid_plans_fail_without_output(self):
        original = json.loads(json.dumps(self.plan))
        cases = [('stale anchor', lambda p: p['sfx'][0].update(anchorUnit='gone')),
            ('stale source', lambda p: p['sfx'][0].update(sha256='0'*64)),
            ('stale timeline', lambda p: p.update(timelineSha256='0'*64)),
            ('stale voice', lambda p: p.update(voiceSha256='0'*64)),
            ('NaN', lambda p: p['sfx'][0].update(volume=float('nan'))),
            ('negative gain', lambda p: p['bgm'].update(volume=-1)),
            ('absolute timing', lambda p: p['sfx'][0].update(startMs=200)),
            ('overlong', lambda p: p['sfx'][0].update(offsetMs=4000)),
            ('before zero', lambda p: p['sfx'][0].update(offsetMs=-5000)),
            ('oversized integer', lambda p: p['sfx'][0].update(volume=10**400)),
            ('clipping', lambda p: p['sfx'][0].update(volume=100)),
            ('invalid fade', lambda p: p['bgm'].update(fadeInMs=float('inf')))]
        for label, mutate in cases:
            with self.subTest(label=label):
                self.plan = json.loads(json.dumps(original)); mutate(self.plan); self.save_plan()
                result = self.mix_cli()
                self.assertNotEqual(result.returncode, 0, result.stderr)
                self.assertNotIn('Traceback', result.stderr)
                self.assertFalse(self.output.exists())

    def test_output_and_sidecar_collisions_preserve_inputs(self):
        targets = [self.voice, self.timeline, self.plan_path, self.sfx]
        # Existing hard links and an adjacent manifest used as an input are protected too.
        hardlink = self.root/'linked.wav'
        hardlink.hardlink_to(self.voice)
        targets.append(hardlink)
        sidecar_source = self.root/'target.mix.json'
        sidecar_source.write_bytes(self.sfx.read_bytes())
        self.plan['sfx'].append({**self.plan['sfx'][0], 'id': 'sidecar',
                                 'path': sidecar_source.name, 'sha256': sha256(sidecar_source)})
        self.save_plan()
        targets.append(self.root/'target.wav')
        for target in targets:
            with self.subTest(target=target):
                self.output = target
                inputs = (self.voice, self.timeline, self.plan_path, self.sfx, sidecar_source)
                originals = {p: p.read_bytes() for p in inputs}
                result = self.mix_cli()
                self.assertNotEqual(result.returncode, 0)
                self.assertIn('collision', result.stderr.lower())
                for path, data in originals.items():
                    self.assertEqual(path.read_bytes(), data)

    def test_mix_validation_detects_changed_sources_pcm_and_shape(self):
        from mix_audio import validate_mix
        self.require_mix()
        original_output = self.output.read_bytes()
        original_manifest = self.output.with_suffix('.mix.json').read_bytes()
        original_source = self.sfx.read_bytes()
        for failure in ('source', 'PCM', 'rate', 'count', 'manifest gain', 'manifest hash'):
            with self.subTest(failure=failure):
                self.output.write_bytes(original_output)
                self.sfx.write_bytes(original_source)
                self.output.with_suffix('.mix.json').write_bytes(original_manifest)
                manifest = json.loads(original_manifest)
                if failure == 'source':
                    write_wav(self.sfx, .13)
                elif failure in ('PCM', 'rate', 'count'):
                    samples, audio = pcm_wav(self.output)
                    pcm = np.rint(samples*32768).astype('<i2')
                    if failure == 'PCM':
                        pcm[1000] += 100
                    if failure == 'count':
                        pcm = pcm[:-10]
                    with wave.open(str(self.output), 'wb') as out:
                        out.setnchannels(1); out.setsampwidth(2)
                        out.setframerate(audio['sampleRate']//2 if failure == 'rate' else audio['sampleRate'])
                        out.writeframes(pcm.tobytes())
                    # Updating the hash cannot bless a voice-modifying or mistimed mix.
                    manifest['output']['sha256'] = sha256(self.output)
                elif failure == 'manifest gain':
                    manifest['voice']['gain'] = .9
                else:
                    manifest['output']['sha256'] = '0'*64
                save_json(self.output.with_suffix('.mix.json'), manifest)
                with self.assertRaises(ValueError):
                    validate_mix(self.output, self.voice)

    def test_malformed_mix_manifest_fails_cleanly(self):
        from mix_audio import validate_mix
        self.require_mix()
        sidecar = self.output.with_suffix('.mix.json')
        original = json.loads(sidecar.read_text())
        for malformed in ([], {**original, 'timeline': None}, {**original, 'plan': []},
                          {**original, 'output': None}, {**original, 'schemaVersion': True}):
            with self.subTest(manifest=malformed):
                save_json(sidecar, malformed)
                with self.assertRaises(ValueError):
                    validate_mix(self.output, self.voice)

    def test_sfx_anchor_retiming_requires_plan_refresh_and_resolves_new_start(self):
        before = self.require_mix()
        timeline = json.loads(self.timeline.read_text())
        timeline['captions'][1]['startMs'] += 50
        save_json(self.timeline, timeline)
        self.output.unlink(); self.output.with_suffix('.mix.json').unlink()
        result = self.mix_cli()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('hash', result.stderr)
        self.plan['timelineSha256'] = sha256(self.timeline); self.save_plan()
        after = self.require_mix()
        self.assertEqual(after['sfx'][0]['startSample']-before['sfx'][0]['startSample'], 2400)

    def test_real_mux_rejects_a_different_valid_current_timeline(self):
        from common import validate_timeline
        self.require_mix()
        silent = self.root/'silent.mp4'
        subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 'lavfi', '-i',
            'color=c=black:s=96x96:r=30', '-frames:v', str(math.ceil(4.21*30)),
            '-c:v', 'libx264', '-pix_fmt', 'yuv420p', str(silent)], check=True)
        current = self.root/'current-timeline.json'
        timeline = json.loads(self.timeline.read_text())
        timeline['captions'][1]['startMs'] += 50
        validate_timeline(timeline, self.voice)
        save_json(current, timeline)
        rejected = self.root/'stale.mp4'
        result = self.cli('mux_audio.py', '--video', silent, '--voice', self.voice,
            '--mix', self.output, '--timeline', current, '--output', rejected)
        self.assertNotEqual(result.returncode, 0, result.stderr)
        self.assertIn('timeline', result.stderr.lower())
        self.assertFalse(rejected.exists())
        # Omitting a caller timeline intentionally uses the pinned manifest timeline.
        result = self.cli('mux_audio.py', '--video', silent, '--voice', self.voice,
            '--mix', self.output, '--output', self.root/'manifest-timeline.mp4')
        self.assertEqual(result.returncode, 0, result.stderr)
        # Matching hashes work even when the caller uses a different path.
        current.write_bytes(self.timeline.read_bytes())
        result = self.cli('mux_audio.py', '--video', silent, '--voice', self.voice,
            '--mix', self.output, '--timeline', current, '--output', self.root/'same-timeline.mp4')
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_real_mux_and_verify_compare_mix_and_reject_stale_provenance(self):
        self.require_mix()
        silent = self.root/'silent.mp4'
        frames = math.ceil(4.21*30)
        subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 'lavfi', '-i',
            'color=c=black:s=96x96:r=30', '-frames:v', str(frames), '-c:v', 'libx264',
            '-pix_fmt', 'yuv420p', str(silent)], check=True)
        final = self.root/'final.mp4'
        result = self.cli('mux_audio.py', '--video', silent, '--voice', self.voice,
                          '--mix', self.output, '--output', final, '--timeline', self.timeline)
        self.assertEqual(result.returncode, 0, result.stderr)
        result = self.cli('verify_media.py', '--video', final, '--voice', self.voice,
                          '--mix', self.output, '--output-dir', self.root/'verify')
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads((self.root/'verify/verification.json').read_text())
        self.assertTrue(report['passed'], report)
        self.assertTrue(report['mix']['voiceValidated'])
        self.assertEqual(report['alignment']['reference'], 'mix')
        previous_sfx = self.sfx.read_bytes()
        modified_sfx = bytearray(previous_sfx)
        modified_sfx[44] ^= 1
        self.sfx.write_bytes(modified_sfx)
        self.assertNotEqual(sha256(self.sfx), self.plan['sfx'][0]['sha256'])
        result = self.cli('verify_media.py', '--video', final, '--voice', self.voice,
                          '--mix', self.output, '--output-dir', self.root/'verify')
        self.assertNotEqual(result.returncode, 0)
        failed_report = json.loads((self.root/'verify/verification.json').read_text())
        self.assertFalse(failed_report['passed'], failed_report)
        self.assertTrue(failed_report['failures'])
        self.sfx.write_bytes(previous_sfx)
        collision_dir = self.root/'verify-current-plan-collision'
        collision_dir.mkdir()
        collision_source = collision_dir/'verification.json'
        collision_source.write_bytes(previous_sfx)
        original_plan = self.plan_path.read_bytes()
        self.plan['sfx'][0]['path'] = str(collision_source)
        self.plan['sfx'][0]['sha256'] = sha256(collision_source)
        self.save_plan()
        result = self.cli('verify_media.py', '--video', final, '--voice', self.voice,
                          '--mix', self.output, '--output-dir', collision_dir)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(collision_source.read_bytes(), previous_sfx)
        self.plan_path.write_bytes(original_plan)

        timeline = json.loads(self.timeline.read_text())
        asr_manifest_path = Path(timeline['provenance']['asrBinding']['manifestPath'])
        original_asr_manifest = asr_manifest_path.read_bytes()
        asr_collision_dir = self.root/'verify-current-asr-collision'
        asr_collision_dir.mkdir()
        asr_collision_source = asr_collision_dir/'verification.json'
        asr_collision_source.write_bytes(previous_sfx)
        asr_manifest = json.loads(original_asr_manifest)
        asr_manifest['asrAudioPath'] = str(asr_collision_source)
        asr_manifest['asrAudioSha256'] = sha256(asr_collision_source)
        save_json(asr_manifest_path, asr_manifest)
        result = self.cli('verify_media.py', '--video', final, '--voice', self.voice,
                          '--mix', self.output, '--output-dir', asr_collision_dir)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(asr_collision_source.read_bytes(), previous_sfx)
        asr_manifest_path.write_bytes(original_asr_manifest)
        manifest_path = self.output.with_suffix('.mix.json')
        manifest = json.loads(manifest_path.read_text()); manifest['voice']['offsetSamples'] = 1
        save_json(manifest_path, manifest)
        result = self.cli('mux_audio.py', '--video', silent, '--voice', self.voice,
                          '--mix', self.output, '--output', self.root/'bad.mp4')
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse((self.root/'bad.mp4').exists())
        result = self.cli('verify_media.py', '--video', final, '--voice', self.voice,
                          '--mix', self.output, '--output-dir', self.root/'badverify')
        self.assertNotEqual(result.returncode, 0)


if __name__ == '__main__':
    unittest.main()
