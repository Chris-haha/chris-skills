#!/usr/bin/env python3
"""Reject a stale or invalid audio-driven timeline before rendering/muxing."""
import argparse
import json
from pathlib import Path
import sys

from common import validate_timeline


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--voice', required=True)
    parser.add_argument('--timeline', required=True)
    parser.add_argument('--script', help='Also require that the source script hash is unchanged')
    args = parser.parse_args()
    try:
        timeline = json.loads(Path(args.timeline).read_text())
        audio = validate_timeline(timeline, args.voice)
        if args.script:
            from common import sha256
            if sha256(args.script) != timeline.get('provenance', {}).get('scriptSha256'):
                raise ValueError('Script hash mismatch: timeline is stale')
        print(f"Timeline valid: {timeline['durationFrames']} frames; voice hash {audio['sha256']}")
    except (ValueError, OSError, KeyError) as error:
        print(str(error), file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
