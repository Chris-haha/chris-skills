"""Extract one video through this skill's local pipeline and emit JSON."""
from __future__ import annotations
import argparse
import json
import sys
sys.dont_write_bytecode = True
from runtime import load_config, runtime_root
from media_pipeline import MediaPipeline


def main() -> int:
    cli = argparse.ArgumentParser(description='提取视频字幕或本地语音转录')
    cli.add_argument('url')
    args = cli.parse_args()
    try:
        pipeline = MediaPipeline(load_config(), runtime_root() / 'parser-state')
        result = pipeline.extract(args.url)
    except Exception as exc:
        result = {'url': args.url, 'error': str(exc)}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 1 if result.get('error') else 0


if __name__ == '__main__':
    raise SystemExit(main())
