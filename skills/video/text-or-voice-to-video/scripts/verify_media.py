#!/usr/bin/env python3
"""Decode the complete output and measure source voice alignment in three windows."""
import argparse
from fractions import Fraction
import math
from pathlib import Path
import sys

import numpy as np

from common import decode_audio, pcm_wav, probe, run, save_json, sha256


def correlation_window(source, decoded, start, length, rate, max_lag_ms=350):
    lag = round(max_lag_ms * rate / 1000)
    block = source[start:start+length].astype(np.float64)
    block -= np.mean(block)
    energy = np.sum(block ** 2)
    if energy < 1e-9:
        return None
    padded = np.pad(decoded.astype(np.float64), (lag, lag + length))
    candidates = padded[start:start+len(block)+2*lag]
    transform_size = 1 << (len(candidates) + len(block) - 2).bit_length()
    convolution = np.fft.irfft(np.fft.rfft(candidates, transform_size) *
                               np.fft.rfft(block[::-1], transform_size), transform_size)
    dot = convolution[len(block)-1:len(candidates)]
    cumulative = np.concatenate(([0], np.cumsum(candidates)))
    squares = np.concatenate(([0], np.cumsum(candidates ** 2)))
    width = len(block)
    window_sum = cumulative[width:] - cumulative[:-width]
    variance = squares[width:] - squares[:-width] - window_sum ** 2 / width
    scores = dot / np.sqrt(energy * np.maximum(variance, 1e-15))
    best = int(np.argmax(scores))
    return {'sourceStartMs': round(start * 1000 / rate, 3),
            'sourceEndMs': round((start+length) * 1000 / rate, 3),
            'offsetMs': round((best-lag) * 1000 / rate, 3),
            'correlation': round(float(scores[best]), 6),
            'sourceRms': round(float(np.sqrt(energy / width)), 6)}


def verify(video_path, voice_path):
    samples, audio = pcm_wav(voice_path)
    video_probe = probe(video_path, count_frames=True)
    videos = [stream for stream in video_probe['streams'] if stream['codec_type'] == 'video']
    audios = [stream for stream in video_probe['streams'] if stream['codec_type'] == 'audio']
    if len(videos) != 1 or len(audios) != 1:
        raise ValueError('Expected exactly one video stream and one audio stream')
    video, output_audio = videos[0], audios[0]
    fps = float(Fraction(video['avg_frame_rate']))
    decoded_frames = int(video['nb_read_frames'])
    expected_frames = math.ceil(audio['sampleCount'] * fps / audio['sampleRate'])
    # -xerror makes an otherwise tolerated decoder error a failed verification.
    run(['ffmpeg', '-v', 'error', '-xerror', '-i', video_path, '-map', '0:v:0', '-f', 'null', '-'])
    decoded48 = decode_audio(video_path, audio['sampleRate'])
    analysis_rate = 16000
    source = decode_audio(voice_path, analysis_rate)
    decoded = decode_audio(video_path, analysis_rate)
    duration = len(source) / analysis_rate
    window_length = max(1, min(round(1.5*analysis_rate), len(source) // 3))
    maximum_start = max(0, len(source)-window_length)
    starts = [round(maximum_start*fraction) for fraction in (0.02, 0.5, 0.98)]
    windows = []
    for start in starts:
        result = correlation_window(source, decoded, start, window_length, analysis_rate)
        if result is None:
            # Try nearby windows if a chosen location is silence.
            for candidate in (max(0, start-window_length), min(maximum_start, start+window_length)):
                result = correlation_window(source, decoded, candidate, window_length, analysis_rate)
                if result is not None:
                    break
        if result is not None:
            windows.append(result)
    failures = []
    if decoded_frames != expected_frames:
        failures.append(f'video_frame_count: {decoded_frames} != {expected_frames}')
    if len(decoded48) < audio['sampleCount']:
        failures.append('decoded_audio_shorter_than_source_voice')
    # Encoding delay is handled by decoder timestamps, not guessed by the muxer.
    # Codec tail padding can still be present after decoding.
    max_tail_samples = math.ceil(audio['sampleRate'] / fps) + 1024
    if len(decoded48) - audio['sampleCount'] > max_tail_samples:
        failures.append('decoded_audio_tail_exceeds_one_video_frame_plus_AAC_codec_padding')
    if len(windows) != 3:
        failures.append('not_enough_non_silent_windows_for_audio_alignment')
    if any(window['correlation'] < 0.92 for window in windows):
        failures.append('audio_content_correlation_below_0.92')
    if any(abs(window['offsetMs']) > 8 for window in windows):
        failures.append('audio_offset_exceeds_8ms')
    offsets_ms = [window['offsetMs'] for window in windows]
    if offsets_ms and max(offsets_ms) - min(offsets_ms) > 5:
        failures.append('audio_alignment_drift_exceeds_5ms')
    peak = float(np.max(np.abs(decoded48))) if len(decoded48) else 0
    if peak > 1.01:
        failures.append('decoded_audio_peak_exceeds_full_scale')
    return {'schemaVersion': 1, 'passed': not failures, 'failures': failures,
            'voice': audio, 'videoSha256': sha256(video_path),
            'video': {'path': str(Path(video_path).resolve()), 'fps': fps,
                      'decodedFrames': decoded_frames, 'expectedFrames': expected_frames,
                      'decodedDurationMs': decoded_frames * 1000 / fps,
                      'streamDurationMs': float(video.get('duration', decoded_frames/fps)) * 1000,
                      'width': video.get('width'), 'height': video.get('height'), 'fullDecodePassed': True},
            'audio': {'codec': output_audio['codec_name'], 'decodedSamples': len(decoded48),
                      'sampleRate': audio['sampleRate'], 'decodedDurationMs': len(decoded48)*1000/audio['sampleRate'],
                      'sourceDurationMs': audio['durationMs'],
                      'tailPaddingMs': (len(decoded48)-audio['sampleCount'])*1000/audio['sampleRate'],
                      'streamDurationMs': float(output_audio.get('duration', len(decoded48)/audio['sampleRate']))*1000,
                      'sourcePeak': round(float(np.max(np.abs(samples))), 6), 'decodedPeak': round(peak, 6),
                      'decodedPeakDbfs': round(20*math.log10(peak), 3) if peak else None},
            'alignment': {'method': 'normalized PCM cross correlation in beginning/middle/end windows',
                          'analysisRate': analysis_rate, 'maxSearchedOffsetMs': 350,
                          'offsetSign': 'positive means the output voice is late', 'windows': windows,
                          'maxAllowedOffsetMs': 8, 'minCorrelation': 0.92,
                          'caveat': 'These windows establish audio stream alignment; they do not validate ASR caption boundaries'},
            'probe': video_probe}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--video', required=True)
    parser.add_argument('--voice', required=True)
    parser.add_argument('--output-dir', required=True)
    args = parser.parse_args()
    report_path = Path(args.output_dir) / 'verification.json'
    try:
        report = verify(args.video, args.voice)
        save_json(report_path, report)
        if report['passed']:
            print(f"Verified {report['video']['decodedFrames']} decoded frames; "
                  f"audio offsets {[window['offsetMs'] for window in report['alignment']['windows']]} ms")
            return 0
        print('Verification failed: ' + ', '.join(report['failures']), file=sys.stderr)
    except (ValueError, OSError, KeyError, ZeroDivisionError) as error:
        save_json(report_path, {'schemaVersion': 1, 'passed': False, 'failures': [str(error)]})
        print(str(error), file=sys.stderr)
    return 1


if __name__ == '__main__':
    raise SystemExit(main())
