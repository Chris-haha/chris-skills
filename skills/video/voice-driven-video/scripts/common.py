"""Shared media primitives. All subprocess arguments are passed without a shell."""
import hashlib
import json
import math
from pathlib import Path
import subprocess
import wave

import numpy as np


def run(command):
    result = subprocess.run(list(map(str, command)), capture_output=True)
    if result.returncode:
        raise ValueError(result.stderr.decode('utf-8', 'replace').strip())
    return result.stdout


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def save_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    temporary.replace(path)


def probe(path, count_frames=False):
    command = ['ffprobe', '-v', 'error', '-show_streams', '-show_format', '-of', 'json']
    if count_frames:
        command.append('-count_frames')
    return json.loads(run(command + [path]))


def pcm_wav(path):
    """Read canonical mono PCM16 WAV, deriving length from samples, not containers."""
    with wave.open(str(path), 'rb') as source:
        if source.getnchannels() != 1 or source.getsampwidth() != 2:
            raise ValueError('Voice must be mono PCM16 WAV; run prepare_audio.py first')
        rate = source.getframerate()
        count = source.getnframes()
        samples = np.frombuffer(source.readframes(count), dtype='<i2').astype(np.float32) / 32768
    if count == 0:
        raise ValueError('Audio contains no samples')
    return samples, {'path': str(Path(path).resolve()), 'sha256': sha256(path),
                     'sampleRate': rate, 'sampleCount': count, 'durationMs': count * 1000 / rate}


def waveform(samples, rate, fps):
    frame_count = math.ceil(len(samples) * fps / rate)
    rms = []
    for frame in range(frame_count):
        start = int(frame * rate / fps)
        end = min(len(samples), int((frame + 1) * rate / fps))
        block = samples[start:end]
        rms.append(float(np.sqrt(np.mean(block ** 2))) if block.size else 0.0)
    largest = max(rms, default=0.0)
    return [round(value / largest, 6) if largest else 0.0 for value in rms]


def low_energy_runs(samples, rate, window_ms=10, rms_threshold=0.001, min_duration_ms=350):
    """Observe sustained low PCM energy; this is not a speech/VAD classifier."""
    window_samples = max(1, round(rate * window_ms / 1000))
    runs, first_quiet_sample = [], None
    for start in range(0, len(samples) + window_samples, window_samples):
        end = min(len(samples), start + window_samples)
        block = samples[start:end]
        quiet = bool(block.size) and float(np.sqrt(np.mean(block.astype(np.float64) ** 2))) < rms_threshold
        if quiet and first_quiet_sample is None:
            first_quiet_sample = start
        elif not quiet and first_quiet_sample is not None:
            run_end = min(start, len(samples))
            if (run_end-first_quiet_sample)*1000/rate >= min_duration_ms:
                runs.append({'startMs': first_quiet_sample*1000/rate, 'endMs': run_end*1000/rate})
            first_quiet_sample = None
    return runs


def decode_audio(path, rate=16000):
    raw = run(['ffmpeg', '-v', 'error', '-xerror', '-i', path, '-map', '0:a:0', '-ac', '1',
               '-ar', rate, '-f', 'f32le', '-'])
    return np.frombuffer(raw, dtype='<f4').copy()


def bind_asr_source(voice_path, asr_path, asr_audio_path=None, manifest_path=None):
    """Check the recorded association plus full decoded source PCM equivalence."""
    audio_hash = sha256(voice_path)
    asr_hash = sha256(asr_path)
    if asr_audio_path or not manifest_path:
        raise ValueError('ASR transcription-time manifest required: rerun run_asr.py; --asr-audio cannot establish which audio produced an existing JSON')
    if manifest_path:
        manifest = json.loads(Path(manifest_path).read_text())
        if manifest.get('association') != 'whisper_cli_run':
            raise ValueError('ASR manifest must come from run_asr.py at transcription time')
        if manifest.get('audioSha256') != audio_hash or manifest.get('asrSha256') != asr_hash:
            raise ValueError('ASR manifest hash mismatch: rerun ASR for this canonical audio')
        source_path = Path(manifest['asrAudioPath'])
        if sha256(source_path) != manifest.get('asrAudioSha256'):
            raise ValueError('ASR audio hash mismatch: recorded transcription source changed')
    source = decode_audio(source_path)
    expected = decode_audio(voice_path)
    if len(source) != len(expected) or not np.allclose(source, expected, atol=0.0001, rtol=0):
        raise ValueError('ASR audio differs from canonical voice PCM; rerun ASR for the current voice')
    return {**manifest, 'verified': True, 'pcmComparisonRate': 16000,
            'pcmComparisonTolerance': 0.0001,
            'manifestPath': str(Path(manifest_path).resolve()) if manifest_path else None}


def validate_timeline(timeline, voice):
    _, audio = pcm_wav(voice)
    expected_hash = timeline.get('audio', {}).get('sha256')
    if not expected_hash or expected_hash != audio['sha256']:
        raise ValueError('Audio hash mismatch: timeline is stale; regenerate it from this voice')
    binding = timeline.get('provenance', {}).get('asrBinding', {})
    if not binding.get('verified') or binding.get('audioSha256') != audio['sha256']:
        raise ValueError('Timeline lacks a verified ASR source binding for the current audio hash')
    if binding.get('association') != 'whisper_cli_run' or not binding.get('manifestPath'):
        raise ValueError('Timeline requires a transcription-time manifest from run_asr.py')
    provenance = timeline.get('provenance', {})
    verified_binding = bind_asr_source(voice, provenance['asrPath'], manifest_path=binding['manifestPath'])
    if verified_binding['asrSha256'] != provenance.get('asrSha256'):
        raise ValueError('ASR hash mismatch: timeline is stale')
    fps = timeline.get('fps')
    if not isinstance(fps, (int, float)) or not 0 < fps <= 120:
        raise ValueError('Invalid timeline fps')
    expected_frames = math.ceil(audio['sampleCount'] * fps / audio['sampleRate'])
    if timeline.get('durationFrames') != expected_frames:
        raise ValueError('Timeline frame duration does not match voice sample count')
    duration = audio['durationMs']
    if abs(timeline.get('durationMs', -1) - duration) > 0.001:
        raise ValueError('Timeline duration does not match voice sample count')
    if len(timeline.get('waveform', [])) != expected_frames:
        raise ValueError('Timeline waveform must contain one RMS value per frame')
    for kind in ('captions', 'scenes'):
        items = timeline.get(kind, [])
        if not items:
            raise ValueError('Timeline has no ' + kind)
        previous_end = 0.0
        ids = set()
        for item in items:
            start, end = item['startMs'], item['endMs']
            if item['id'] in ids or not (previous_end <= start < end <= duration + 0.001):
                raise ValueError(kind + ' must have unique ids and monotonic nonoverlapping intervals')
            ids.add(item['id'])
            previous_end = end
        if kind == 'scenes':
            if items[0]['startMs'] != 0 or abs(items[-1]['endMs'] - duration) > 0.001:
                raise ValueError('Scenes must cover the composition from zero to voice ending')
            for before, after in zip(items, items[1:]):
                if before['endMs'] != after['startMs'] or before['endFrame'] != after['startFrame']:
                    raise ValueError('Scenes must form continuous intervals')
    return audio
