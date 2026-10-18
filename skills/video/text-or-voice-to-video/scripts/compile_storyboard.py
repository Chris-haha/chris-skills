#!/usr/bin/env python3
"""Validate visual assets and compile speech-anchored shots to current frames."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import sys

RECIPES = {'assemble', 'path', 'state', 'link', 'focus', 'parallax', 'compare', 'patch'}
MEDIA = {'illustration', 'screen', 'diagram', 'type'}


def number(value, name, minimum=0):
    try:
        valid = not isinstance(value, bool) and isinstance(value, (int, float)) and math.isfinite(value) and value >= minimum
    except OverflowError:
        valid = False
    if not valid:
        raise ValueError(f'{name} must be a finite number >= {minimum}')
    return value


def unique(items, key, label):
    result = {}
    for item in items:
        ident = item.get(key)
        if not isinstance(ident, str) or not ident.strip() or ident in result:
            raise ValueError(f'Missing/duplicate {label} {key}: {ident}')
        result[ident] = item
    return result


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def compile_story(story, timeline, assets, public_dir):
    fps = number(timeline['fps'], 'fps', 1)
    total = number(timeline['durationFrames'], 'durationFrames', 1)
    scenes = unique(timeline['scenes'], 'id', 'scene')
    captions = unique(timeline['captions'], 'id', 'caption')
    public_dir = Path(public_dir).resolve()
    if isinstance(story, list):
        for shot in story:
            if shot.get('sceneId') not in scenes:
                raise ValueError('Legacy storyboard references unknown scene')
            for item in shot.get('items', []):
                if item.get('visual'):
                    path = (public_dir / item['visual']).resolve()
                    if not path.is_relative_to(public_dir) or not path.is_file():
                        raise ValueError('Legacy visual asset missing or outside public directory')
        return {'schemaVersion': 1, 'legacy': True, 'shots': [], 'audit': {'legacy': True}}
    if story.get('schemaVersion') != 2:
        raise ValueError('storyboard schemaVersion must be 2')
    registry = unique(assets.get('assets', []), 'id', 'asset')
    asset_hashes = {}
    for ident, asset in registry.items():
        path = (public_dir / asset['path']).resolve()
        if not path.is_relative_to(public_dir) or not path.is_file():
            raise ValueError(f'Asset {ident} missing or outside public directory')
        if not asset.get('purpose') or not asset.get('source', {}).get('type') or not asset['source'].get('uri'):
            raise ValueError(f'Asset {ident} needs purpose and source provenance')
        if asset['source']['type'] == 'generated' and (not asset['source'].get('prompt') or
                number(asset['source'].get('generationAttempts', 0), 'generationAttempts', 1) < 1):
            raise ValueError(f'Generated asset {ident} needs prompt/attempts')
        asset_hashes[ident] = digest(path)
    shots = story.get('shots', [])
    unique(shots, 'id', 'shot')
    if not shots or len(shots) != len(scenes) or {s['sceneId'] for s in shots} != set(scenes):
        raise ValueError('Each timeline scene requires exactly one visual shot')
    # Stable bytes across Python processes keep a current visual review current.
    compiled, media_frames = [], {m: 0 for m in sorted(MEDIA)}
    event_ids = set()
    for shot in shots:
        scene = scenes[shot['sceneId']]
        start, end = scene['startFrame'], scene['endFrame']
        if not 0 <= start < end <= total:
            raise ValueError(f'Scene {scene["id"]} has invalid bounds')
        if shot.get('recipe') not in RECIPES or shot.get('media') not in MEDIA:
            raise ValueError(f'Unknown recipe/media in {shot["id"]}')
        if not shot.get('goal') or not shot.get('subjects') or len(set(shot['subjects'])) != len(shot['subjects']):
            raise ValueError(f'Shot {shot["id"]} requires goal and unique subjects')
        hold_frames = math.ceil(number(shot.get('holdMs', 0), 'holdMs') * fps / 1000)
        if hold_frames > end - start:
            raise ValueError('Reading hold exceeds shot duration')
        used = shot.get('assetIds', [])
        for ident in used:
            if ident not in registry:
                raise ValueError(f'Asset reference missing: {ident}')
        if shot['media'] in {'screen', 'illustration'} and not used:
            raise ValueError(f'{shot["media"]} shot needs a concrete asset')
        if shot['media'] == 'screen' and not any(registry[a]['source']['type'] in {'project', 'original'} for a in used):
            raise ValueError('Screen evidence needs an actual project/original capture')
        events = []
        for event in shot.get('events', []):
            if not event.get('id') or event['id'] in event_ids:
                raise ValueError('Missing/duplicate visual event id')
            event_ids.add(event['id'])
            if event.get('unitId') not in captions:
                raise ValueError(f'Unknown speech anchor: {event.get("unitId")}')
            if event.get('subjectId') not in shot['subjects'] or not event.get('action'):
                raise ValueError('Visual event requires a known subject and action')
            edge = event.get('edge', 'start')
            if edge not in {'start', 'end'}:
                raise ValueError('Anchor edge must be start or end')
            offset = number(event.get('offsetMs', 0), 'offsetMs', -10000)
            frame = round((captions[event['unitId']][edge + 'Ms'] + offset) * fps / 1000)
            duration = math.ceil(number(event.get('durationMs', 400), 'durationMs', 1) * fps / 1000)
            if frame < start or frame + duration > end - hold_frames:
                raise ValueError(f'Event {event["id"]} exceeds scene/reading-hold bounds')
            events.append({**event, 'frame': frame, 'durationFrames': duration})
        if not events:
            raise ValueError(f'Shot {shot["id"]} has no visual events')
        media_frames[shot['media']] += end - start
        compiled.append({**shot, 'startFrame': start, 'endFrame': end, 'events': events})
    compiled.sort(key=lambda s: s['startFrame'])
    if compiled[0]['startFrame'] != 0 or compiled[-1]['endFrame'] != total or any(
            a['endFrame'] != b['startFrame'] for a, b in zip(compiled, compiled[1:])):
        raise ValueError('Shots must cover timeline without gaps or overlaps')
    return {'schemaVersion': 2, 'fps': fps, 'durationFrames': total, 'shots': compiled,
            'assetHashes': asset_hashes, 'audit': {'mediaFrames': media_frames,
            'textOnlyRatio': media_frames['type'] / total,
            'mediaTypes': [m for m, n in media_frames.items() if n],
            'note': 'Declared media/subjects require rendered visual review; this is not aesthetic certification.'}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('timeline', 'storyboard', 'assets', 'public-dir', 'output'):
        parser.add_argument('--' + name, required=True)
    args = parser.parse_args()
    output = Path(args.output).resolve()
    temporary = output.with_suffix('.tmp.json').resolve()
    inputs = [Path(x).resolve() for x in (args.timeline, args.storyboard, args.assets)]
    public_dir = Path(args.public_dir).resolve()
    if output in inputs or temporary in inputs or output == temporary or output.is_relative_to(public_dir) or temporary.is_relative_to(public_dir):
        print('Output collision with inputs or public assets', file=sys.stderr)
        return 1
    try:
        story, timeline, assets = [json.loads(Path(p).read_text()) for p in (args.storyboard, args.timeline, args.assets)]
        data = compile_story(story, timeline, assets, public_dir)
        data['sourceHashes'] = {p.name: digest(p) for p in inputs}
        output.parent.mkdir(parents=True, exist_ok=True)
        temp = temporary
        temp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')
        temp.replace(output)
        print(f'Compiled {len(data["shots"])} shots; schema {data["schemaVersion"]}')
        return 0
    except (ValueError, OSError, KeyError, TypeError) as error:
        output.unlink(missing_ok=True)
        print(str(error), file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
