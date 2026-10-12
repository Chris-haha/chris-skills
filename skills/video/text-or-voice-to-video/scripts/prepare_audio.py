#!/usr/bin/env python3
"""Create untrimmed canonical voice, ASR copy, waveform and sample-derived metadata."""
import argparse
from pathlib import Path
import sys

from common import pcm_wav, probe, run, save_json, sha256, waveform


def prepare(input_path, output_dir):
    source = Path(input_path).resolve()
    output_dir = Path(output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    canonical = output_dir / 'canonical.wav'
    asr_copy = output_dir / 'asr16k.wav'
    if source in (canonical, asr_copy):
        raise ValueError('Input must differ from prepared output files')
    run(['ffmpeg', '-v', 'error', '-y', '-i', source, '-map', '0:a:0',
         '-ac', '1', '-ar', '48000', '-c:a', 'pcm_s16le', canonical])
    run(['ffmpeg', '-v', 'error', '-y', '-i', canonical, '-map', '0:a:0',
         '-ac', '1', '-ar', '16000', '-c:a', 'pcm_s16le', asr_copy])
    samples, info = pcm_wav(canonical)
    _, asr_info = pcm_wav(asr_copy)
    source_probe = probe(source)
    metadata = {'schemaVersion': 1, 'source': {'path': str(source), 'sha256': sha256(source),
                'probe': source_probe}, 'canonical': info, 'asr': asr_info,
                'processing': {'trimmed': False, 'speedChanged': False, 'normalized': False,
                               'channelPolicy': 'ffmpeg mono downmix', 'canonicalPcm': 's16le'}}
    save_json(output_dir / 'metadata.json', metadata)
    save_json(output_dir / 'waveform.json', {'fps': 30, 'durationMs': info['durationMs'],
                                           'audioSha256': info['sha256'],
                                           'normalization': 'RMS divided by largest frame RMS',
                                           'peaks': waveform(samples, info['sampleRate'], 30)})
    return metadata


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', required=True)
    parser.add_argument('--output-dir', required=True)
    args = parser.parse_args()
    try:
        result = prepare(args.input, args.output_dir)
        print(f"Prepared {result['canonical']['sampleCount']} samples at 48000 Hz; "
              f"{result['canonical']['durationMs']:.3f} ms")
    except (ValueError, OSError) as error:
        print(str(error), file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
