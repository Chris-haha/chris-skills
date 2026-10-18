import json
import os
from pathlib import Path
import subprocess
import shutil
import sys
import tempfile
import unittest


PIPELINE = Path(__file__).resolve().parents[1]


class VisualStoryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / 'public').mkdir()
        (self.root / 'public' / 'capture.png').write_bytes(b'actual-project-capture')
        self.timeline = {'fps': 30, 'durationFrames': 150, 'scenes': [
            {'id': 's1', 'startFrame': 0, 'endFrame': 150}], 'captions': [
            {'id': 'u1', 'startMs': 100, 'endMs': 2000}]}
        self.story = {'schemaVersion': 2, 'shots': [{'id': 'shot-1', 'sceneId': 's1',
            'goal': 'Follow an actual submitted request', 'media': 'screen',
            'recipe': 'focus', 'subjects': ['request'], 'assetIds': ['capture'],
            'holdMs': 600, 'transition': {'kind': 'cut'}, 'events': [
                {'id': 'reveal', 'unitId': 'u1', 'subjectId': 'request',
                 'action': 'focus', 'durationMs': 400, 'offsetMs': 0}]}]}
        self.assets = {'schemaVersion': 1, 'assets': [{'id': 'capture',
            'path': 'capture.png', 'kind': 'image', 'purpose': 'actual output',
            'source': {'type': 'project', 'uri': 'project-output'}}]}

    def tearDown(self):
        self.tmp.cleanup()

    def compile(self):
        for name, data in [('timeline', self.timeline), ('storyboard', self.story),
                           ('assets', self.assets)]:
            (self.root / (name + '.json')).write_text(json.dumps(data))
        entry = PIPELINE / 'compile_storyboard.py'
        self.assertTrue(entry.exists(), 'Missing visual-story compiler')
        return subprocess.run([sys.executable, str(entry), '--timeline', str(self.root / 'timeline.json'),
            '--storyboard', str(self.root / 'storyboard.json'), '--assets', str(self.root / 'assets.json'),
            '--public-dir', str(self.root / 'public'), '--output', str(self.root / 'compiled.json')],
            capture_output=True, text=True)

    def test_anchor_reflows_with_current_voice(self):
        result = self.compile()
        self.assertEqual(result.returncode, 0, result.stderr)
        before = json.loads((self.root / 'compiled.json').read_text())
        self.timeline['captions'][0]['startMs'] += 900
        result = self.compile()
        self.assertEqual(result.returncode, 0, result.stderr)
        after = json.loads((self.root / 'compiled.json').read_text())
        self.assertEqual(after['shots'][0]['events'][0]['frame'] - before['shots'][0]['events'][0]['frame'], 27)

    def test_recompiling_is_deterministic_across_python_hash_seeds(self):
        self.assertEqual(self.compile().returncode, 0)
        command = [sys.executable, str(PIPELINE / 'compile_storyboard.py'),
            '--timeline', str(self.root / 'timeline.json'),
            '--storyboard', str(self.root / 'storyboard.json'),
            '--assets', str(self.root / 'assets.json'), '--public-dir', str(self.root / 'public'),
            '--output', str(self.root / 'compiled.json')]
        outputs = []
        for seed in ('1', '2', '3', '17'):
            result = subprocess.run(command, env={**os.environ, 'PYTHONHASHSEED': seed},
                                    capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            outputs.append((self.root / 'compiled.json').read_bytes())
        for output in outputs[1:]:
            self.assertEqual(output, outputs[0], 'Unchanged visual sources must retain export approval')

    def test_missing_asset_fails_and_invalidates_compiled_output(self):
        self.assertEqual(self.compile().returncode, 0)
        (self.root / 'public' / 'capture.png').unlink()
        result = self.compile()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('missing', result.stderr.lower())
        self.assertFalse((self.root / 'compiled.json').exists())

    def test_missing_anchor_and_overflow_are_rejected(self):
        self.story['shots'][0]['events'][0]['unitId'] = 'stale-unit'
        result = self.compile()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('anchor', result.stderr.lower())
        self.story['shots'][0]['events'][0]['unitId'] = 'u1'
        self.story['shots'][0]['events'][0]['durationMs'] = 6000
        self.assertNotEqual(self.compile().returncode, 0)

    def test_path_escape_and_generated_fake_screen_are_rejected(self):
        self.assets['assets'][0]['path'] = '../timeline.json'
        self.assertNotEqual(self.compile().returncode, 0)
        self.assets['assets'][0]['path'] = 'capture.png'
        self.assets['assets'][0]['source'] = {'type': 'generated', 'uri': 'imagegen',
            'prompt': 'fake screen', 'generationAttempts': 1}
        self.assertNotEqual(self.compile().returncode, 0)

    def test_legacy_storyboard_remains_supported(self):
        self.story = [{'sceneId': 's1', 'layout': 'hero', 'items': []}]
        result = self.compile()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads((self.root / 'compiled.json').read_text())['schemaVersion'], 1)

    def test_output_collision_does_not_overwrite_source(self):
        self.compile()
        source = self.root / 'storyboard.json'
        expected = source.read_bytes()
        result = subprocess.run([sys.executable, str(PIPELINE / 'compile_storyboard.py'),
            '--timeline', str(self.root / 'timeline.json'), '--storyboard', str(source),
            '--assets', str(self.root / 'assets.json'), '--public-dir', str(self.root / 'public'),
            '--output', str(source)], capture_output=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(source.read_bytes(), expected)

    def test_huge_numeric_values_fail_without_traceback(self):
        self.story['shots'][0]['events'][0]['durationMs'] = 10**400
        result = self.compile()
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn('Traceback', result.stderr)

    def test_temporary_output_cannot_overwrite_input(self):
        self.compile()
        protected = self.root / 'compiled.tmp.json'
        protected.write_bytes((self.root / 'storyboard.json').read_bytes())
        expected = protected.read_bytes()
        result = subprocess.run([sys.executable, str(PIPELINE / 'compile_storyboard.py'),
            '--timeline', str(self.root / 'timeline.json'), '--storyboard', str(protected),
            '--assets', str(self.root / 'assets.json'), '--public-dir', str(self.root / 'public'),
            '--output', str(self.root / 'compiled.json')], capture_output=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(protected.read_bytes(), expected)

    def test_project_initializer_omits_development_artifacts(self):
        skill = self.root / 'test-skill'
        scripts = skill / 'scripts'
        scripts.mkdir(parents=True)
        shutil.copy2(PIPELINE / 'init_project.py', scripts / 'init_project.py')
        starter = skill / 'assets/starter'
        starter.mkdir(parents=True)
        (starter / 'package.json').write_text('{}')
        deps = self.root / 'local-dependencies'
        deps.mkdir()
        (deps / 'large-private-cache.txt').write_text('local only')
        (starter / 'node_modules').symlink_to(deps, target_is_directory=True)
        (starter / 'out').mkdir()
        (starter / 'out/final.mp4').write_bytes(b'old-preview')
        output = self.root / 'fresh-project'
        result = subprocess.run([sys.executable, str(scripts / 'init_project.py'), '--output', str(output)], capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue((output / 'package.json').exists())
        self.assertFalse((output / 'node_modules').exists())
        self.assertFalse((output / 'out').exists())


if __name__ == '__main__':
    unittest.main()
