#!/usr/bin/env python3
"""Run real Whisper full JSON and bind its output to the canonical voice hash."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
import subprocess
import sys

from common import pcm_wav, run, save_json, sha256


def transcribe(audio_path, model_path, output_prefix, language='zh', timing_policy='segment', whisper_cli='whisper-cli'):
    audio_path, model_path, prefix = map(lambda path: Path(path).resolve(),
                                       (audio_path, model_path, output_prefix))
    if not model_path.is_file():
        raise ValueError('Whisper model file does not exist: ' + str(model_path))
    executable = shutil.which(str(whisper_cli))
    if not executable:
        raise ValueError('whisper-cli was not found')
    _, audio = pcm_wav(audio_path)
    asr_audio = prefix.with_name(prefix.name + '.asr16k.wav')
    asr_json = prefix.with_name(prefix.name + '.json')
    manifest_path = prefix.with_name(prefix.name + '.manifest.json')
    if audio_path in (asr_audio, asr_json, manifest_path) or model_path in (asr_audio, asr_json, manifest_path):
        raise ValueError('ASR output prefix would overwrite an input')
    prefix.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.unlink(missing_ok=True)
    asr_json.unlink(missing_ok=True)
    run(['ffmpeg', '-v', 'error', '-y', '-i', audio_path, '-map', '0:a:0', '-ac', '1',
         '-ar', '16000', '-c:a', 'pcm_s16le', asr_audio])
    command = [executable, '-m', str(model_path), '-f', str(asr_audio), '-l', language,
               '-ojf', '-of', str(prefix)]
    if timing_policy == 'token':
        command += ['-ml', '1']
    result = subprocess.run(command, capture_output=True)
    prefix.with_name(prefix.name + '.log').write_bytes(result.stdout + b'\n' + result.stderr)
    if result.returncode:
        raise ValueError(f'whisper-cli failed ({result.returncode}); inspect {prefix.name}.log')
    if not asr_json.exists():
        raise ValueError('whisper-cli did not write full JSON; inspect its log')
    parsed = json.loads(asr_json.read_text(encoding='utf-8', errors='surrogateescape'))
    if not isinstance(parsed.get('transcription'), list):
        raise ValueError('Whisper JSON contains no transcription array')
    if sha256(audio_path) != audio['sha256']:
        raise ValueError('Canonical audio changed during ASR; output cannot be bound')
    manifest = {'schemaVersion': 1, 'audioSha256': audio['sha256'], 'asrSha256': sha256(asr_json),
                'asrAudioSha256': sha256(asr_audio), 'asrAudioPath': str(asr_audio),
                'association': 'whisper_cli_run',
                'createdAt': datetime.now(timezone.utc).isoformat(),
                'audioPath': str(audio_path), 'audioSampleCount': audio['sampleCount'],
                'audioDurationMs': audio['durationMs'], 'modelPath': str(model_path),
                'modelSha256': sha256(model_path), 'command': command,
                'recognizerPath': executable, 'recognizerSha256': sha256(executable),
                'timingPolicy': timing_policy, 'language': language}
    save_json(manifest_path, manifest)
    return manifest_path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--audio', required=True, help='Canonical mono PCM16 voice WAV')
    parser.add_argument('--model', required=True)
    parser.add_argument('--output-prefix', required=True, help='Whisper output stem, without .json')
    parser.add_argument('--language', default='zh')
    parser.add_argument('--timing-policy', choices=('segment', 'token'), default='segment')
    parser.add_argument('--whisper-cli', default='whisper-cli')
    args = parser.parse_args()
    try:
        path = transcribe(args.audio, args.model, args.output_prefix, args.language,
                          args.timing_policy, args.whisper_cli)
        print('ASR complete; source hash manifest: ' + str(path))
    except (ValueError, OSError, KeyError) as error:
        print(str(error), file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
