"""Join synthesis to the existing pipeline; both speech engines are explicit fixtures."""
import base64
import io
import json
import math
from pathlib import Path
import struct
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from align_narration import align
from common import sha256, validate_timeline
from prepare_audio import prepare as prepare_audio
from prepare_script import prepare, save_json
from run_asr import transcribe
from synthesize_narration import synthesize


class TextPipelineIntegration(unittest.TestCase):
    def test_pcm_synthesis_normalization_asr_binding_and_timeline_join(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            script = prepare('学习研究。逻辑记录。', root)
            samples = [int(6000 * math.sin(2 * math.pi * (211 * i / 24000 + 7 * (i / 24000)**2)))
                       for i in range(24000 * 4)]
            raw = struct.pack('<' + 'h' * len(samples), *samples)
            def fixture_service(request, timeout):
                return io.BytesIO((json.dumps({'code': 0, 'data': base64.b64encode(raw).decode()}) +
                    '\n' + json.dumps({'code': 20000000, 'usage': {'text_words': 10}})).encode())
            narration = synthesize(root/'script.json', root/'narration.json', root/'out/narration',
                                   api_key='fixture-only', transport=fixture_service)
            metadata = prepare_audio(root/'out/narration/voice.wav', root/'out/audio')
            self.assertEqual(metadata['source']['sha256'], narration['audioSha256'])
            self.assertEqual(metadata['canonical']['sampleCount'], 4 * 48000)
            asr_fixture = {'transcription': [
                {'text': '学习研究。', 'offsets': {'from': 100, 'to': 1800},
                 'tokens': [{'text': '学习研究', 'offsets': {'from': 100, 'to': 1800}, 'p': 0.99}]},
                {'text': '逻辑记录。', 'offsets': {'from': 2000, 'to': 3800},
                 'tokens': [{'text': '逻辑记录', 'offsets': {'from': 2000, 'to': 3800}, 'p': 0.99}]}]}
            recognizer = root/'fixture_recognizer'
            recognizer.write_text('#!' + sys.executable + '\nimport json,pathlib,sys\n' +
                'out=sys.argv[sys.argv.index("-of")+1]+".json"\n' +
                'pathlib.Path(out).write_text(' + repr(json.dumps(asr_fixture, ensure_ascii=False)) + ')\n')
            recognizer.chmod(0o755)
            model = root/'fixture_model.bin'
            model.write_bytes(b'explicit-test-fixture')
            manifest = transcribe(root/'out/audio/canonical.wav', model, root/'out/audio/asr',
                                  whisper_cli=recognizer)
            timeline = align(root/'out/audio/canonical.wav', root/'out/audio/asr.json',
                             root/'script.json', manifest_path=manifest)
            self.assertEqual(timeline['durationFrames'], 120)
            self.assertEqual([c['text'] for c in timeline['captions']], [u['text'] for u in script['units']])
            self.assertEqual(timeline['provenance']['scriptSha256'], sha256(root/'script.json'))
            self.assertTrue(timeline['provenance']['asrBinding']['verified'])
            validate_timeline(timeline, root/'out/audio/canonical.wav')
            save_json(root/'timeline.json', timeline)


if __name__ == '__main__':
    unittest.main()
