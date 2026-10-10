#!/usr/bin/env python3
import argparse, json, re, sys
from pathlib import Path

HIRAGANA = re.compile(r'[\u3040-\u309F]')
KATAKANA = re.compile(r'[\u30A0-\u30FF]')
CJK = re.compile(r'[\u4e00-\u9fff]')
BAD = re.compile(r'[�□◻◼☐]')

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--annotations', required=True)
    args = ap.parse_args()

    data = json.loads(Path(args.annotations).read_text(encoding='utf-8'))
    items = data.get('annotations', [])
    translate = [x for x in items if x.get('category') == 'translate']
    errors = []

    for i, x in enumerate(translate, 1):
        src = (x.get('source_text') or '').strip()
        text = (x.get('text') or '').strip()
        if not text:
            errors.append(f'{i}: empty translation')
            continue
        if text == src:
            errors.append(f'{i}: translation equals source text: {src}')
        if BAD.search(text):
            errors.append(f'{i}: garbled character found: {text}')
        if HIRAGANA.search(text) or KATAKANA.search(text):
            errors.append(f'{i}: Japanese kana remains: {text}')
        if not CJK.search(text):
            errors.append(f'{i}: no Chinese characters found: {text}')

    print(f'translate_count={len(translate)}')
    print(f'validated_count={len(translate)-len(errors)}')

    if errors:
        print('FAIL')
        for e in errors:
            print(e)
        sys.exit(1)

    print('PASS')

if __name__ == '__main__':
    main()
