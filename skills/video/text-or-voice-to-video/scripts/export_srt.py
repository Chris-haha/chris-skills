#!/usr/bin/env python3
"""Export machine-aligned captions without altering their timing."""
import argparse
import json
from pathlib import Path

def stamp(ms):
    total = round(ms)
    return f'{total//3600000:02d}:{total//60000%60:02d}:{total//1000%60:02d},{total%1000:03d}'

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--timeline', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    source = Path(args.timeline).resolve()
    output = Path(args.output).resolve()
    if source == output or (output.exists() and source.samefile(output)):
        parser.error('SRT output must differ from input timeline')
    timeline = json.loads(source.read_text(encoding='utf-8'))
    blocks = [f'{i}\n{stamp(c["startMs"])} --> {stamp(c["endMs"])}\n{c["text"]}' for i,c in enumerate(timeline['captions'],1)]
    output = Path(args.output)
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text('\n\n'.join(blocks)+'\n',encoding='utf-8')
    print(output.resolve())

if __name__ == '__main__':
    main()
