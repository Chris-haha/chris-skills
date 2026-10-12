#!/usr/bin/env python3
"""Map script units to observed Whisper tokens, retaining timing uncertainty."""
import argparse
from difflib import SequenceMatcher
import json
import math
from pathlib import Path
import sys
import unicodedata

from common import bind_asr_source, low_energy_runs, pcm_wav, save_json, sha256, validate_timeline, waveform


class AlignmentBlocked(ValueError):
    def __init__(self, message, report):
        super().__init__(message)
        self.report = report


def paths_alias(first, second):
    first, second = Path(first), Path(second)
    if first.resolve() == second.resolve():
        return True
    return first.exists() and second.exists() and first.samefile(second)


def guard_alignment_outputs(output, report_path, inputs):
    # save_json writes a temporary sibling before replacing the destination.
    # Protect those paths too, as they can otherwise alias a supplied input.
    writes = [output, report_path, output.with_suffix(output.suffix+'.tmp'),
              report_path.with_suffix(report_path.suffix+'.tmp')]
    for index, target in enumerate(writes):
        for source in inputs:
            if paths_alias(target, source):
                raise ValueError(f'Output collision: {target} aliases protected input {source}')
        for other in writes[:index]:
            if paths_alias(target, other):
                raise ValueError(f'Output collision: {target} aliases another output {other}')


def preflight_outputs(args, output, report_path):
    default_manifest = Path(args.asr).with_suffix('.manifest.json')
    manifest_path = args.asr_manifest
    if not manifest_path and not args.asr_audio and default_manifest.exists():
        manifest_path = default_manifest
    protected = [Path(args.audio), Path(args.asr), Path(args.script), default_manifest]
    if args.asr_manifest:
        protected.append(Path(args.asr_manifest))
    if args.asr_audio:
        protected.append(Path(args.asr_audio))
    guard_alignment_outputs(output, report_path, protected)
    if manifest_path:
        manifest = json.loads(Path(manifest_path).read_text(encoding='utf-8'))
        if not isinstance(manifest, dict):
            raise ValueError('ASR manifest must be a JSON object')
        for field in ('asrAudioPath', 'audioPath'):
            if field in manifest:
                if not isinstance(manifest[field], str) or not manifest[field].strip():
                    raise ValueError('ASR manifest ' + field + ' must be a nonempty path string')
                protected.append(Path(manifest[field]))
        guard_alignment_outputs(output, report_path, protected)
    return manifest_path


def validate_script_schema(script):
    if not isinstance(script, dict):
        raise ValueError('Script must be a JSON object')
    if not isinstance(script.get('title', ''), str):
        raise ValueError('Script title must be a string')
    for collection, fields in (('units', ('id', 'text')),
                               ('scenes', ('id', 'anchorUnit', 'label'))):
        items = script.get(collection)
        if not isinstance(items, list) or not items:
            raise ValueError('Script ' + collection + ' must be a nonempty list')
        ids = set()
        for index, item in enumerate(items):
            if not isinstance(item, dict):
                raise ValueError(f'Script {collection}[{index}] must be an object')
            for field in fields:
                if not isinstance(item.get(field), str) or not item[field].strip():
                    raise ValueError(f'Script {collection}[{index}].{field} must be a nonempty string')
            if item['id'] in ids:
                raise ValueError('Script ' + collection + ' ids must be unique')
            ids.add(item['id'])
    reviewed = script.get('reviewedUnits', {})
    if not isinstance(reviewed, dict):
        raise ValueError('Script reviewedUnits must be an object')
    for unit_id, override in reviewed.items():
        if not isinstance(unit_id, str) or not unit_id.strip() or not isinstance(override, dict):
            raise ValueError('Script reviewedUnits must map unit id strings to objects')
        if not isinstance(override.get('reason'), str) or not override['reason'].strip():
            raise ValueError('Reviewed override requires a documented reason')
        for field in ('startMs', 'endMs'):
            value = override.get(field)
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
                raise ValueError('Reviewed override ' + field + ' must be a finite number')


def normalizer():
    try:
        from opencc import OpenCC
    except ImportError:
        raise ValueError('OpenCC missing: install pipeline/requirements.txt in pipeline/.venv')
    converter = OpenCC('t2s')
    return lambda text: ''.join(char for char in converter.convert(
        unicodedata.normalize('NFKC', text)).casefold() if char.isalnum())


def offsets(item):
    value = item.get('offsets', {})
    start, end = value.get('from'), value.get('to')
    if isinstance(start, (int, float)) and isinstance(end, (int, float)) and 0 <= start <= end:
        return float(start), float(end)
    return None


def merge_utf8_tokens(tokens):
    """Repair old full-json token strings that split a UTF-8 character's bytes."""
    merged, pending, data = [], b'', []
    for token in tokens:
        text = token.get('text', '')
        if is_control_token(text):
            continue
        pending += text.encode('utf-8', 'surrogateescape')
        data.append(token)
        try:
            text = pending.decode('utf-8')
        except UnicodeDecodeError as error:
            if error.reason == 'unexpected end of data':
                continue
            raise ValueError('Malformed UTF-8 in ASR token bytes') from error
        timings = [offsets(part) for part in data]
        timings = [timing for timing in timings if timing is not None]
        merged.append({'text': text, 'offsets': {'from': timings[0][0], 'to': timings[-1][1]}
                       if timings else {}, 'p': min(float(part.get('p', 0)) for part in data),
                       't_dtw': data[0].get('t_dtw', -1), 'mergedByteFragments': len(data) > 1})
        pending, data = b'', []
    if pending:
        raise ValueError('ASR ends with an incomplete UTF-8 token')
    return merged


def is_control_token(text):
    return ((text.startswith('<|') and text.endswith('|>')) or
            (text.startswith('[_') and text.endswith(']')) or
            text in ('[BLANK_AUDIO]', '[MUSIC]', '[SILENCE]'))


def observed_characters(asr, normalize, duration_ms, timing_policy):
    observed = []
    sources = set()
    review_flags, discarded_segments = [], []
    for segment_index, segment in enumerate(asr.get('transcription', [])):
        segment_times = offsets(segment)
        if segment_times is None:
            raise ValueError('ASR segments require offsets.from/to in milliseconds')
        if segment_times[1] > duration_ms:
            if 'asr_spans_outside_audio' not in review_flags:
                review_flags.append('asr_spans_outside_audio')
        span = segment_times[1] - segment_times[0]
        inside_span = max(0, min(duration_ms, segment_times[1]) - max(0, segment_times[0]))
        if segment_times[0] >= duration_ms or (span > 0 and inside_span / span < 0.5):
            discarded_segments.append({'segmentIndex': segment_index, 'text': segment.get('text', ''),
                                       'startMs': segment_times[0], 'endMs': segment_times[1],
                                       'reason': 'majority_of_segment_outside_audio'})
            continue
        segment_times = (max(0, segment_times[0]), min(duration_ms, segment_times[1]))
        tokens = merge_utf8_tokens(segment.get('tokens', []))
        if not tokens and segment.get('tokens'):
            continue
        if not tokens and not is_control_token(segment.get('text', '')):
            tokens = [{'text': segment.get('text', ''), 'p': 0, 't_dtw': -1, 'offsets': {}}]
        lengths = [len(normalize(token['text'])) for token in tokens]
        total = max(1, sum(lengths))
        char_offset = 0
        for index, token in enumerate(tokens):
            text = normalize(token['text'])
            if not text:
                continue
            timing = offsets(token)
            if timing_policy == 'segment':
                start = segment_times[0] + (segment_times[1] - segment_times[0]) * char_offset / total
                end = segment_times[0] + (segment_times[1] - segment_times[0]) * (char_offset+len(text)) / total
                source = 'segment_character_interpolation'
            elif timing is not None and timing[1] > timing[0]:
                start, end = timing
                source = 'whisper_token_offsets'
            elif isinstance(token.get('t_dtw'), (int, float)) and token['t_dtw'] >= 0:
                # t_dtw is in Whisper's 10-ms ticks and describes an output moment.
                # The next moment bounds an estimated interval, not a phonetic boundary.
                start = float(token['t_dtw']) * 10
                following = [float(next_token['t_dtw']) * 10 for next_token in tokens[index+1:]
                             if isinstance(next_token.get('t_dtw'), (int, float))
                             and next_token['t_dtw'] >= 0 and next_token['t_dtw'] * 10 > start]
                end = following[0] if following else max(start, segment_times[1])
                source = 'whisper_dtw_output_moment_interpolation'
            else:
                start = segment_times[0] + (segment_times[1] - segment_times[0]) * char_offset / total
                end = segment_times[0] + (segment_times[1] - segment_times[0]) * (char_offset+len(text)) / total
                source = 'segment_character_interpolation'
            if end > duration_ms:
                if 'asr_spans_outside_audio' not in review_flags:
                    review_flags.append('asr_spans_outside_audio')
            if start >= duration_ms:
                continue
            start, end = max(0, start), min(duration_ms, end)
            sources.add(source)
            for char_index, char in enumerate(text):
                observed.append({'char': char, 'startMs': start+(end-start)*char_index/len(text),
                                 'endMs': start+(end-start)*(char_index+1)/len(text),
                                 'p': token['p'], 'timingSource': source,
                                 'interpolatedWithinToken': len(text) > 1,
                                 'segmentIndex': segment_index, 'segmentStartMs': segment_times[0],
                                 'segmentEndMs': segment_times[1]})
            char_offset += len(text)
    if not observed:
        raise ValueError('ASR contains no usable speech characters')
    return observed, sorted(sources), review_flags, discarded_segments


def align(audio_path, asr_path, script_path, timing_policy='segment', asr_audio_path=None, manifest_path=None):
    samples, audio = pcm_wav(audio_path)
    binding = bind_asr_source(audio_path, asr_path, asr_audio_path, manifest_path)
    quiet_runs = low_energy_runs(samples, audio['sampleRate'])
    quiet_policy = {'method': 'leading_low_energy_run', 'windowMs': 10,
                    'rmsThreshold': 0.001, 'minQuietDurationMs': 350,
                    'caveat': 'Observed low PCM energy is not phonetic boundary detection or VAD'}
    script = json.loads(Path(script_path).read_text(encoding='utf-8'))
    validate_script_schema(script)
    # surrogateescape preserves invalid bytes in old Whisper token strings until merge.
    asr = json.loads(Path(asr_path).read_text(encoding='utf-8', errors='surrogateescape'))
    normalize = normalizer()
    fps = script.get('fps', 30)
    if not isinstance(fps, (int, float)) or not 0 < fps <= 120:
        raise ValueError('Script fps must be positive and at most 120')
    units = script.get('units', [])
    if not units or len({unit['id'] for unit in units}) != len(units):
        raise ValueError('Script requires nonempty units with unique ids')
    normalized_units = [normalize(unit['text']) for unit in units]
    if any(not text for text in normalized_units):
        raise ValueError('Every script unit must contain speech characters')
    script_text = ''.join(normalized_units)
    observed, sources, review_flags, discarded_segments = observed_characters(asr, normalize, audio['durationMs'], timing_policy)
    asr_text = ''.join(character['char'] for character in observed)
    matcher = SequenceMatcher(None, script_text, asr_text, autojunk=False)
    mapping = {}
    for block in matcher.get_matching_blocks():
        for offset in range(block.size):
            mapping[block.a+offset] = block.b+offset
    script_coverage = len(mapping) / len(script_text)
    asr_coverage = len(mapping) / len(asr_text)
    report = {'schemaVersion': 1, 'matchedCharacterRatio': round(script_coverage, 6),
              'asrCharacterCoverage': round(asr_coverage, 6), 'normalizedScript': script_text,
              'normalizedAsr': asr_text, 'timingSources': sources,
              'timingPolicy': timing_policy, 'reviewFlags': review_flags,
              'discardedSegments': discarded_segments,
              'leadingSilenceRefinement': quiet_policy, 'refinedUnits': [],
              'unmatchedScriptRanges': [{'operation': tag, 'script': script_text[a:b],
                                         'asr': asr_text[c:d], 'scriptRange': [a,b], 'asrRange': [c,d]}
                                        for tag,a,b,c,d in matcher.get_opcodes() if tag != 'equal'],
              'confidenceMeaning': 'Text match fraction multiplied by mean ASR token probability; not calibrated timing confidence'}
    if script_coverage < 0.68 or asr_coverage < 0.55:
        report['status'] = 'blocked_script_mismatch'
        raise AlignmentBlocked(f'Script/ASR significant mismatch ({script_coverage:.1%} script coverage); review required', report)

    # Missing script characters are estimated only between adjacent matched evidence.
    char_times = [None] * len(script_text)
    for script_index, asr_index in mapping.items():
        char_times[script_index] = dict(observed[asr_index], matched=True)
    unit_ranges = []
    unit_start = 0
    for text in normalized_units:
        unit_ranges.append((unit_start, unit_start+len(text)))
        unit_start += len(text)
    index = 0
    while index < len(char_times):
        if char_times[index] is not None:
            index += 1
            continue
        stop = index
        while stop < len(char_times) and char_times[stop] is None:
            stop += 1
        start_time = char_times[index-1]['endMs'] if index else 0
        end_time = char_times[stop]['startMs'] if stop < len(char_times) else audio['durationMs']
        bounded = False
        if timing_policy == 'segment':
            # A substitution at the edge of a script phrase should not borrow
            # the next phrase's filler pause merely because that filler is ASR-only.
            for unit_start, unit_stop in unit_ranges:
                if unit_start <= index < stop <= unit_stop:
                    if index > unit_start and 'segmentEndMs' in char_times[index-1]:
                        phrase_end = char_times[index-1]['segmentEndMs']
                        if stop == unit_stop and phrase_end < end_time:
                            end_time, bounded = phrase_end, True
                    if stop < unit_stop and 'segmentStartMs' in char_times[stop]:
                        phrase_start = char_times[stop]['segmentStartMs']
                        if index == unit_start and phrase_start > start_time:
                            start_time, bounded = phrase_start, True
                    break
        end_time = max(start_time, end_time)
        for position in range(index, stop):
            char_times[position] = {'startMs': start_time+(end_time-start_time)*(position-index)/(stop-index),
                                    'endMs': start_time+(end_time-start_time)*(position-index+1)/(stop-index),
                                    'matched': False, 'p': 0, 'timingSource': 'asr_gap_interpolation',
                                    'interpolatedWithinToken': False, 'boundedToPhrase': bounded}
        index = stop

    captions = []
    cursor, previous_end = 0, 0
    reviewed = script.get('reviewedUnits', {})
    if set(reviewed) - {unit['id'] for unit in units}:
        raise ValueError('reviewedUnits contains an unknown unit id')
    for unit, text in zip(units, normalized_units):
        characters = char_times[cursor:cursor+len(text)]
        cursor += len(text)
        matched = [character for character in characters if character['matched']]
        match_ratio = len(matched) / len(text)
        flags = ['token_times_are_estimates' if timing_policy == 'token' else 'segment_character_interpolation'] + review_flags
        if any(character['interpolatedWithinToken'] for character in characters):
            flags.append('intra_token_character_interpolation')
        if match_ratio < 1:
            flags.append('asr_text_mismatch_or_gap')
        if any(character.get('boundedToPhrase') for character in characters):
            flags.append('asr_gap_bounded_to_phrase')
        raw_start = max(0, min(audio['durationMs'], characters[0]['startMs']))
        raw_end = max(raw_start, min(audio['durationMs'], characters[-1]['endMs']))
        start, end = max(previous_end, raw_start), raw_end
        if start != raw_start:
            flags.append('monotonic_boundary_clamp')
        timing_source = '+'.join(sorted({character['timingSource'] for character in characters}))
        caption = {'id': unit['id'], 'text': unit['text'], 'startMs': round(start, 3),
                   'endMs': round(end, 3), 'confidence': round(match_ratio * (
                       sum(character['p'] for character in matched) / len(matched) if matched else 0), 4),
                   'matchedCharacterRatio': round(match_ratio, 6), 'needsReview': True,
                   'reviewFlags': flags, 'timingSource': timing_source}
        if unit['id'] not in reviewed:
            for quiet in quiet_runs:
                if quiet['startMs'] <= caption['startMs'] < quiet['endMs']:
                    if quiet['endMs'] >= caption['endMs']:
                        blocked = {**report, 'status': 'blocked_silent_unit_interval',
                                   'unitId': unit['id'], 'estimatedStartMs': caption['startMs'],
                                   'estimatedEndMs': caption['endMs'], 'quietRun': quiet,
                                   'reason': 'Entire estimated unit interval lies in sustained low-energy PCM; review narration/ASR or supply an inspected override'}
                        raise AlignmentBlocked('Unit ' + unit['id'] + ' interval is entirely inside a long quiet run; review required', blocked)
                    caption['boundaryRefinement'] = {**quiet_policy,
                        'priorStartMs': caption['startMs'], 'quietRunStartMs': quiet['startMs'],
                        'quietRunEndMs': quiet['endMs'], 'refinedStartMs': quiet['endMs']}
                    caption['startMs'] = quiet['endMs']
                    caption['reviewFlags'].append('leading_silence_boundary_refined')
                    caption['timingSource'] += '+leading_silence_boundary_refined'
                    report['refinedUnits'].append(unit['id'])
                    break
        if unit['id'] in reviewed:
            override = reviewed[unit['id']]
            if not isinstance(override.get('reason'), str) or not override['reason'].strip():
                raise ValueError('Reviewed override requires a documented reason')
            start, end = override.get('startMs'), override.get('endMs')
            if not isinstance(start, (int, float)) or not isinstance(end, (int, float)):
                raise ValueError('Reviewed override requires numeric startMs/endMs')
            if start < previous_end:
                raise ValueError('Reviewed override overlaps previous caption')
            if not 0 <= start < end <= audio['durationMs']:
                raise ValueError('Reviewed override must lie inside audio duration')
            caption.update({'startMs': start, 'endMs': end, 'autoTiming': {
                            'startMs': caption['startMs'], 'endMs': caption['endMs'],
                            'timingSource': caption['timingSource']}, 'reviewReason': override['reason'],
                            'timingSource': 'reviewed_override', 'needsReview': False})
        if caption['endMs'] <= caption['startMs']:
            raise ValueError('Unit ' + unit['id'] + ' has no usable time span; provide a reviewedUnits override')
        caption['startFrame'] = int(math.ceil(caption['startMs'] * fps / 1000))
        caption['endFrame'] = int(math.ceil(caption['endMs'] * fps / 1000))
        captions.append(caption)
        previous_end = caption['endMs']

    duration_frames = math.ceil(audio['sampleCount'] * fps / audio['sampleRate'])
    by_id = {caption['id']: caption for caption in captions}
    scene_specs = script.get('scenes', [])
    if not scene_specs or len({scene['id'] for scene in scene_specs}) != len(scene_specs):
        raise ValueError('Script requires nonempty scenes with unique ids')
    scenes = []
    for index, spec in enumerate(scene_specs):
        if spec.get('anchorUnit') not in by_id:
            raise ValueError('Scene anchorUnit is missing from script units')
        anchor = by_id[spec['anchorUnit']]
        start = anchor['startMs'] if index else 0
        if scenes and start <= scenes[-1]['startMs']:
            raise ValueError('Scenes must be ordered by distinct increasing anchor units')
        scenes.append({**spec, 'startMs': start, 'startFrame': int(math.floor(start*fps/1000)),
                       'anchorMs': anchor['startMs'], 'needsReview': anchor['needsReview']})
    for index, scene in enumerate(scenes):
        scene['endMs'] = scenes[index+1]['startMs'] if index+1 < len(scenes) else audio['durationMs']
        scene['endFrame'] = scenes[index+1]['startFrame'] if index+1 < len(scenes) else duration_frames
    report['status'] = 'ready_with_review' if any(caption['needsReview'] for caption in captions) else 'reviewed'
    report['unitsNeedingReview'] = [caption['id'] for caption in captions if caption['needsReview']]
    timeline = {'schemaVersion': 1, 'title': script.get('title', ''), 'fps': fps,
                'durationMs': audio['durationMs'], 'durationFrames': duration_frames,
                'compositionDurationMs': duration_frames * 1000 / fps,
                'audio': audio, 'captions': captions, 'scenes': scenes,
                'waveform': waveform(samples, audio['sampleRate'], fps), 'alignment': report,
                'provenance': {'audioSha256': audio['sha256'], 'asrSha256': sha256(asr_path),
                               'scriptSha256': sha256(script_path), 'asrPath': str(Path(asr_path).resolve()),
                               'scriptPath': str(Path(script_path).resolve()),
                               'asrModel': asr.get('model', {}).get('type'),
                               'method': 'normalized_character_sequence_match', 'normalization': 'NFKC+OpenCC t2s+casefold+alphanumeric',
                               'asrBinding': binding, 'timingPolicy': timing_policy,
                               'leadingSilenceRefinement': quiet_policy,
                               'tokenOffsetUnit': 'milliseconds', 'dtwUnit': '10 millisecond ticks',
                               'timingCaveat': 'Whisper token estimates and character interpolation are not measured acoustic boundaries'}}
    validate_timeline(timeline, audio_path)
    return timeline


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--audio', required=True)
    parser.add_argument('--asr', required=True)
    parser.add_argument('--script', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--timing-policy', choices=('token', 'segment'), default='segment',
                        help='segment uses phrase offsets and marks character interpolation; token uses optional token offsets/DTW')
    binding = parser.add_mutually_exclusive_group()
    binding.add_argument('--asr-audio', help='Deprecated association shortcut; rejected. Rerun run_asr.py to record a transcription-time manifest')
    binding.add_argument('--asr-manifest', help='Source hash manifest generated at ASR time by run_asr.py')
    args = parser.parse_args()
    try:
        output = Path(args.output)
        report_path = output.with_suffix('.review.json')
        manifest_path = preflight_outputs(args, output, report_path)
    except (ValueError, OSError, KeyError, RuntimeError) as error:
        # No alignment, writes or cleanup may run until both output destinations
        # and their temporary files have been checked against every source.
        print(str(error), file=sys.stderr)
        return 1
    try:
        timeline = align(args.audio, args.asr, args.script, args.timing_policy, args.asr_audio, manifest_path)
        save_json(output, timeline)
        save_json(report_path, timeline['alignment'])
        print(f"Aligned {len(timeline['captions'])} units; {timeline['durationFrames']} frames; "
              f"{timeline['alignment']['matchedCharacterRatio']:.1%} text coverage; "
              f"{len(timeline['alignment']['unitsNeedingReview'])} review flags")
    except AlignmentBlocked as error:
        # A failed regeneration must never leave an apparently usable previous timeline.
        output.unlink(missing_ok=True)
        save_json(report_path, error.report)
        print(str(error), file=sys.stderr)
        return 2
    except (ValueError, OSError, KeyError) as error:
        output.unlink(missing_ok=True)
        save_json(report_path, {'status': 'blocked_invalid_input', 'reason': str(error)})
        print(str(error), file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
