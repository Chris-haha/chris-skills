#!/usr/bin/env python3
"""Mix optional BGM and caption-anchored effects without altering the voice stem."""
import argparse
import json
import math
from pathlib import Path
import sys
import tempfile
import wave

import numpy as np

from common import decode_audio, pcm_wav, save_json, sha256, validate_timeline


def check_keys(value, allowed, label):
    if not isinstance(value, dict) or set(value) - set(allowed):
        raise ValueError(f'{label} contains unknown fields or is not an object')


def number(value, label, minimum=0, maximum=None):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f'{label} must be a finite number')
    try:
        value = float(value)
    except OverflowError as error:
        raise ValueError(f'{label} must be a finite number') from error
    if not math.isfinite(value):
        raise ValueError(f'{label} must be a finite number')
    if value < minimum or (maximum is not None and value > maximum):
        raise ValueError(f'{label} is out of range')
    return value


def same_file(first, second):
    first, second = Path(first), Path(second)
    return first.resolve() == second.resolve() or (first.exists() and second.exists() and first.samefile(second))


def reject_collisions(outputs, sources):
    for index, output in enumerate(outputs):
        for source in [*sources, *outputs[:index]]:
            if same_file(output, source):
                raise ValueError(f'Source/output collision: {output} and {source}')


def bound_source(entry, root, rate):
    path_value = entry.get('path')
    if not isinstance(path_value, str) or not path_value:
        raise ValueError('Audio source requires a nonempty path')
    path = (root/path_value).resolve()
    digest = sha256(path)
    if entry.get('sha256') != digest:
        raise ValueError(f'Audio source hash mismatch: {path}')
    samples = decode_audio(path, rate)
    if not len(samples) or not np.all(np.isfinite(samples)):
        raise ValueError(f'Audio source must contain finite samples: {path}')
    return samples.astype(np.float64), {'path': str(path), 'sha256': digest,
                                       'decodedSampleCount': len(samples), 'decodedSampleRate': rate}


def speech_ducking(voice, rate, settings):
    check_keys(settings, ('thresholdDbfs', 'gain', 'attackMs', 'releaseMs'), 'ducking')
    threshold = number(settings.get('thresholdDbfs', -35), 'thresholdDbfs', -120, 0)
    gain = number(settings.get('gain', .25), 'ducking gain', 0, 1)
    attack = number(settings.get('attackMs', 20), 'attackMs', .001, 60000)
    release = number(settings.get('releaseMs', 250), 'releaseMs', .001, 60000)
    window = max(1, round(rate*.01))
    starts = np.arange(0, len(voice), window)
    current, values = 1.0, []
    for start in starts:
        block = voice[start:start+window].astype(np.float64)
        rms = float(np.sqrt(np.mean(block*block)))
        target = gain if rms >= 10**(threshold/20) else 1.0
        smoothing_ms = attack if target < current else release
        coefficient = math.exp(-len(block)*1000/(rate*smoothing_ms))
        current = target + (current-target)*coefficient
        values.append(current)
    envelope = np.interp(np.arange(len(voice)), starts, values)
    return envelope, {'method': '10ms voice RMS threshold with exponential attack/release and linear interpolation',
        'thresholdDbfs': threshold, 'gain': gain, 'attackMs': attack, 'releaseMs': release,
        'appliedGainRange': [float(np.min(envelope)), float(np.max(envelope))]}


def quantize(samples):
    # The positive PCM16 endpoint is 32767/32768, the negative endpoint is -1.
    peak = float(np.max(np.abs(samples)))
    if not np.all(np.isfinite(samples)) or np.max(samples) > 32767/32768 or np.min(samples) < -1:
        raise ValueError(f'Mix would clip (peak {peak:.6f}); lower BGM/SFX gains; voice is never normalized')
    return np.rint(samples*32768).astype('<i2'), peak


def build_mix(voice_path, timeline_path, plan_path, omit_bgm=False):
    voice_path, timeline_path, plan_path = [Path(p).resolve() for p in (voice_path, timeline_path, plan_path)]
    voice, audio = pcm_wav(voice_path)
    timeline = json.loads(timeline_path.read_text())
    validate_timeline(timeline, voice_path)
    plan = json.loads(plan_path.read_text())
    check_keys(plan, ('schemaVersion', 'voiceSha256', 'timelineSha256', 'bgm', 'sfx'), 'audio plan')
    if type(plan.get('schemaVersion')) is not int or plan['schemaVersion'] != 1:
        raise ValueError('Audio plan requires schemaVersion 1')
    timeline_hash = sha256(timeline_path)
    if plan.get('voiceSha256') != audio['sha256'] or plan.get('timelineSha256') != timeline_hash:
        raise ValueError('Audio plan voice/timeline hash mismatch; regenerate the plan after timing changes')
    rate, count = audio['sampleRate'], audio['sampleCount']
    mix = voice.astype(np.float64).copy()
    manifest = {'schemaVersion': 1, 'association': 'caption_anchored_pcm_mix', 'omitBgm': omit_bgm,
        'voice': {**audio, 'gain': 1, 'offsetMs': 0, 'offsetSamples': 0, 'unchanged': True},
        'timeline': {'path': str(timeline_path), 'sha256': timeline_hash},
        'plan': {'path': str(plan_path), 'sha256': sha256(plan_path)}, 'bgm': None, 'sfx': []}
    sources = [voice_path, timeline_path, plan_path]
    # Also protect the provenance inputs used to validate the current timeline.
    provenance = timeline['provenance']
    binding = provenance['asrBinding']
    sources.extend([Path(provenance['asrPath']), Path(binding['manifestPath']), Path(binding['asrAudioPath'])])
    if provenance.get('scriptPath'):
        sources.append(Path(provenance['scriptPath']))
    bgm = plan.get('bgm')
    if bgm is not None:
        check_keys(bgm, ('path', 'sha256', 'volume', 'fadeInMs', 'fadeOutMs', 'ducking', 'loop'), 'bgm')
        music, source = bound_source(bgm, plan_path.parent, rate)
        sources.append(Path(source['path']))
        volume = number(bgm.get('volume', .1), 'bgm volume', 0, 100)
        fade_in = number(bgm.get('fadeInMs', 0), 'fadeInMs', 0, audio['durationMs'])
        fade_out = number(bgm.get('fadeOutMs', 0), 'fadeOutMs', 0, audio['durationMs'])
        if fade_in + fade_out > audio['durationMs']:
            raise ValueError('BGM fades must fit within the voice duration')
        loop = bgm.get('loop', True)
        if type(loop) is not bool:
            raise ValueError('BGM loop must be a boolean')
        if loop:
            music = np.resize(music, count)
        else:
            music = np.pad(music[:count], (0, max(0, count-len(music))))
        duck, settings = speech_ducking(voice, rate, bgm.get('ducking', {}))
        fades = np.ones(count, np.float64)
        for duration, reverse in ((fade_in, False), (fade_out, True)):
            length = round(duration*rate/1000)
            if length:
                ramp = np.linspace(0, 1, length) if length > 1 else np.zeros(1)
                if reverse:
                    fades[-length:] *= ramp[::-1]
                else:
                    fades[:length] *= ramp
        if not omit_bgm:
            mix += music * volume * duck * fades
        manifest['bgm'] = {**source, 'volume': volume, 'fadeInMs': fade_in, 'fadeOutMs': fade_out,
                           'loop': loop, 'included': not omit_bgm, 'ducking': settings}
    effects = plan.get('sfx', [])
    if not isinstance(effects, list):
        raise ValueError('sfx must be an array')
    captions = {caption['id']: caption for caption in timeline['captions']}
    ids = set()
    for effect in effects:
        check_keys(effect, ('id', 'path', 'sha256', 'anchorUnit', 'offsetMs', 'volume'), 'sfx event')
        identifier = effect.get('id')
        if not isinstance(identifier, str) or not identifier or identifier in ids:
            raise ValueError('SFX events require unique nonempty ids')
        ids.add(identifier)
        anchor = effect.get('anchorUnit')
        if not isinstance(anchor, str) or anchor not in captions:
            raise ValueError(f'Stale SFX caption anchor: {anchor}')
        offset = number(effect.get('offsetMs', 0), 'offsetMs', -audio['durationMs'], audio['durationMs'])
        volume = number(effect.get('volume', 1), 'sfx volume', 0, 100)
        start_ms = number(captions[anchor]['startMs'], 'caption startMs') + offset
        start = round(start_ms*rate/1000)
        samples, source = bound_source(effect, plan_path.parent, rate)
        sources.append(Path(source['path']))
        if start_ms < 0 or start < 0 or start + len(samples) > count:
            raise ValueError(f'SFX event {identifier} exceeds voice boundaries; shorten or move the effect')
        mix[start:start+len(samples)] += samples*volume
        manifest['sfx'].append({**source, 'id': identifier, 'anchorUnit': anchor,
            'anchorStartMs': captions[anchor]['startMs'], 'offsetMs': offset,
            'resolvedStartMs': start_ms, 'startSample': start, 'endSample': start+len(samples), 'volume': volume})
    pcm, peak = quantize(mix)
    manifest['peak'] = peak
    manifest['sampleRate'], manifest['sampleCount'] = rate, count
    return pcm, manifest, sources


def validate_mix(mix_path, voice_path):
    """Check hashes AND deterministically rebuild PCM; self-reported voice flags are insufficient."""
    mix_path = Path(mix_path).resolve()
    manifest_path = mix_path.with_suffix('.mix.json')
    manifest = json.loads(manifest_path.read_text())
    if not isinstance(manifest, dict) or type(manifest.get('schemaVersion')) is not int or manifest['schemaVersion'] != 1:
        raise ValueError('Mix manifest requires an object with schemaVersion 1')
    if manifest.get('association') != 'caption_anchored_pcm_mix' or type(manifest.get('omitBgm')) is not bool:
        raise ValueError('Invalid mix manifest association or omitBgm')
    for field in ('voice', 'timeline', 'plan', 'output'):
        entry = manifest.get(field)
        if not isinstance(entry, dict) or not isinstance(entry.get('path'), str) or not entry['path']:
            raise ValueError(f'Mix manifest {field} requires a source object and path')
    samples, audio = pcm_wav(mix_path)
    if manifest.get('output', {}).get('sha256') != audio['sha256']:
        raise ValueError('Mix output hash mismatch')
    expected, rebuilt, sources = build_mix(voice_path, manifest['timeline']['path'],
                                           manifest['plan']['path'], manifest['omitBgm'])
    for key, value in rebuilt.items():
        if manifest.get(key) != value:
            raise ValueError(f'Mix manifest {key} mismatch; voice must be unchanged with zero offset')
    if (audio['sampleRate'], audio['sampleCount']) != (rebuilt['sampleRate'], rebuilt['sampleCount']):
        raise ValueError('Mix sample rate/count must equal canonical voice')
    if not np.array_equal(np.rint(samples.astype(np.float64)*32768).astype('<i2'), expected):
        raise ValueError('Mix PCM differs from reproducible unchanged-voice mix')
    return {**manifest, 'manifestPath': str(manifest_path), 'manifestSha256': sha256(manifest_path),
            'voiceValidated': True, 'pcmRebuildValidated': True}, [*sources, mix_path, manifest_path]


def mix_audio(voice_path, timeline_path, plan_path, output_path, no_bgm_output=None, dry_run=False):
    output_path = Path(output_path).resolve()
    targets = [output_path]
    if no_bgm_output is not None:
        targets.append(Path(no_bgm_output).resolve())
    variants = []
    all_sources = []
    for index, target in enumerate(targets):
        pcm, manifest, sources = build_mix(voice_path, timeline_path, plan_path, omit_bgm=index == 1)
        variants.append((target, pcm, manifest))
        all_sources.extend(sources)
    outputs = [path for target in targets for path in (target, target.with_suffix('.mix.json'))]
    reject_collisions(outputs, all_sources)
    if dry_run:
        return [dict(manifest, dryRun=True, outputPath=str(target)) for target, _, manifest in variants]
    # All variants are validated, including peak limits, before any result is written.
    for target, pcm, manifest in variants:
        target.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix='.mix-', dir=target.parent) as directory:
            temporary = Path(directory)/'audio.wav'
            with wave.open(str(temporary), 'wb') as out:
                out.setnchannels(1); out.setsampwidth(2); out.setframerate(manifest['sampleRate'])
                out.writeframes(pcm.tobytes())
            manifest['output'] = {'path': str(target), 'sha256': sha256(temporary)}
            save_json(Path(directory)/'manifest.json', manifest)
            temporary.replace(target)
            (Path(directory)/'manifest.json').replace(target.with_suffix('.mix.json'))
    return [manifest for _, _, manifest in variants]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('voice', 'timeline', 'plan', 'output'):
        parser.add_argument('--'+name, required=True)
    parser.add_argument('--no-bgm-output')
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()
    try:
        result = mix_audio(args.voice, args.timeline, args.plan, args.output, args.no_bgm_output, args.dry_run)
        print(json.dumps(result, ensure_ascii=False, allow_nan=False))
        return 0
    except (ValueError, OSError, KeyError, TypeError, wave.Error) as error:
        print(str(error), file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
