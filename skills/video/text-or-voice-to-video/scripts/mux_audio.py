#!/usr/bin/env python3
"""Mux the complete canonical voice using the system FFmpeg with no timing offset."""
import argparse
from fractions import Fraction
import json
import math
from pathlib import Path
import shutil
import sys

from common import pcm_wav, probe, run, save_json, sha256, validate_timeline
from mix_audio import reject_collisions, validate_mix


def mux(video_path, voice_path, output_path, timeline_path=None, mix_path=None):
    video_path, voice_path, output_path = map(lambda path: Path(path).resolve(),
                                              (video_path, voice_path, output_path))
    if output_path in (video_path, voice_path):
        raise ValueError('Mux output must differ from both input files')
    _, audio = pcm_wav(voice_path)
    mix_manifest = None
    sources = [video_path, voice_path]
    audio_input = voice_path
    if mix_path is not None:
        audio_input = Path(mix_path).resolve()
        mix_manifest, mix_sources = validate_mix(audio_input, voice_path)
        sources.extend(mix_sources)
    if timeline_path:
        sources.append(Path(timeline_path).resolve())
        if mix_manifest is not None and sha256(timeline_path) != mix_manifest['timeline']['sha256']:
            raise ValueError('Supplied timeline hash differs from the mix timeline; regenerate the audio plan and mix for current timing')
    reject_collisions([output_path, output_path.with_suffix('.mux.json'),
                       output_path.with_suffix('.mux.json.tmp'),
                       output_path.with_name(output_path.stem + '.mux.tmp' + output_path.suffix)], sources)
    video_probe = probe(video_path, count_frames=True)
    streams = [stream for stream in video_probe['streams'] if stream['codec_type'] == 'video']
    if len(streams) != 1:
        raise ValueError('Input requires one silent video stream')
    stream = streams[0]
    fps = float(Fraction(stream['avg_frame_rate']))
    frames = int(stream['nb_read_frames'])
    if timeline_path:
        timeline = json.loads(Path(timeline_path).read_text())
        validate_timeline(timeline, voice_path)
        if abs(timeline['fps'] - fps) > 0.00001:
            raise ValueError('Video frame rate differs from timeline fps')
    expected_frames = math.ceil(audio['sampleCount'] * fps / audio['sampleRate'])
    if frames != expected_frames:
        raise ValueError(f'Video frame count {frames} differs from audio-driven {expected_frames}; rerender video')
    composition_seconds = frames / fps
    padded_samples = math.ceil(composition_seconds * audio['sampleRate'] - 1e-7)
    pad_samples = padded_samples - audio['sampleCount']
    if pad_samples < 0 or pad_samples > math.ceil(audio['sampleRate'] / fps):
        raise ValueError('Audio padding would exceed one frame')
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = output_path.with_name(output_path.stem + '.mux.tmp' + output_path.suffix)
    ffmpeg = shutil.which('ffmpeg')
    if not ffmpeg:
        raise ValueError('System ffmpeg was not found')
    command = [ffmpeg, '-v', 'error', '-y', '-i', video_path, '-i', audio_input,
               '-map', '0:v:0', '-map', '1:a:0', '-c:v', 'copy', '-c:a', 'aac',
               '-b:a', '192k', '-af', f'apad=whole_len={padded_samples}',
               '-movflags', '+faststart', temporary]
    try:
        run(command)
        temporary.replace(output_path)
    finally:
        temporary.unlink(missing_ok=True)
    metadata = {'schemaVersion': 1, 'voiceSha256': audio['sha256'], 'videoSha256': sha256(video_path),
                'outputSha256': sha256(output_path), 'frames': frames, 'fps': fps,
                'sourceSamples': audio['sampleCount'], 'padSamples': pad_samples,
                'padMs': pad_samples * 1000 / audio['sampleRate'], 'offsetMs': 0,
                'command': list(map(str, command)),
                'ffmpegVersion': run([ffmpeg, '-version']).decode().splitlines()[0],
                'tailCaveat': 'AAC may decode extra codec padding; verify_media.py measures decoded duration and content offsets'}
    if mix_manifest is not None:
        metadata['mix'] = {'path': str(audio_input), 'sha256': sha256(audio_input),
            'manifestPath': mix_manifest['manifestPath'], 'manifestSha256': mix_manifest['manifestSha256'],
            'voiceValidated': True, 'pcmRebuildValidated': True}
    save_json(output_path.with_suffix('.mux.json'), metadata)
    return metadata


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--video', required=True)
    parser.add_argument('--voice', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--timeline')
    parser.add_argument('--mix', help='Optional mix WAV with adjacent .mix.json manifest; voice drives timing')
    args = parser.parse_args()
    try:
        result = mux(args.video, args.voice, args.output, args.timeline, args.mix)
        print(f"Muxed {result['frames']} frames; voice retained; {result['padMs']:.3f} ms silence padding")
    except (ValueError, OSError, KeyError, ZeroDivisionError) as error:
        print(str(error), file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
