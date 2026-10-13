#!/usr/bin/env python3
"""Preserve a UTF-8 manuscript and prepare editable narration units and scene anchors."""
import argparse
from collections import Counter
import hashlib
import html
import json
from pathlib import Path
import re
import sys


def save_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    temporary.replace(path)


def clean_markdown(text):
    """Remove presentation syntax while retaining labels, headings and code content."""
    text = text.replace('\r\n', '\n').replace('\r', '\n').lstrip('\ufeff')
    code_blocks = []
    def protect_code(match):
        code_blocks.append(match.group(2))
        return f'\n\n\x00CODE{len(code_blocks)-1}\x00\n\n'
    text = re.sub(r'^\s{0,3}(`{3,}|~{3,})[^\n]*\n(.*?)^\s{0,3}\1\s*$',
                  protect_code, text, flags=re.M | re.S)
    text = re.sub(r'!\[([^\]]*)\]\([^\n]*?\)', r'\1', text)
    text = re.sub(r'\[([^\]]+)\]\([^\n]*?\)', r'\1', text)
    text = re.sub(r'^\s{0,3}#{1,6}\s+(.+?)(?:\s+#+)?\s*$', r'\1', text, flags=re.M)
    text = re.sub(r'^\s*(?:>\s*)+', '', text, flags=re.M)
    text = re.sub(r'^\s*(?:[-+*]|\d+[.)])\s+(?:\[[ xX]\]\s+)?', '', text, flags=re.M)
    text = re.sub(r'^\s*(?:[-*_]\s*){3,}$', '', text, flags=re.M)
    text = re.sub(r'^\s*\|?\s*:?-{3,}:?\s*(?:\|\s*:?-{3,}:?\s*)+\|?\s*$', '', text, flags=re.M)
    for marker in ('**', '__', '~~', '`'):
        escaped = re.escape(marker)
        text = re.sub(escaped + r'(\S(?:[^\n]*?\S)?)' + escaped, r'\1', text)
    for marker in ('*', '_'):
        escaped = re.escape(marker)
        text = re.sub(r'(?<![A-Za-z0-9])' + escaped + r'(\S(?:[^\n]*?\S)?)' +
                      escaped + r'(?![A-Za-z0-9])', r'\1', text)
    text = re.sub(r'</?[A-Za-z][^>]*>', '', text)
    text = html.unescape(text)
    for index, block in enumerate(code_blocks):
        text = text.replace(f'\x00CODE{index}\x00', block.rstrip('\n'))
    return text.strip()


CLOSING_MARKS = '”’」』）)]】》〉\"\''


def split_sentences(text):
    """Keep trailing quotation/bracket marks with the sentence they close."""
    closers = '[' + re.escape(CLOSING_MARKS) + ']*'
    pattern = r'[。！？!?；;]' + closers + r'|\.' + closers + r'(?=\s+[A-Z])'
    sentences, start = [], 0
    for match in re.finditer(pattern, text):
        sentences.append(text[start:match.end()])
        start = match.end()
    if start < len(text):
        sentences.append(text[start:])
    return sentences


def split_chunks(paragraphs, limit=300):
    """Pack complete sentences within a paragraph; never silently drop characters."""
    if isinstance(limit, bool) or not isinstance(limit, int) or limit < 1:
        raise ValueError('Chunk limit must be a positive integer')
    chunks = []
    for paragraph in paragraphs:
        current = ''
        # Use zero-width boundaries so joining chunks preserves English spaces.
        sentences = split_sentences(paragraph)
        for sentence in sentences:
            if not sentence:
                continue
            if len(current) + len(sentence) <= limit:
                current += sentence
                continue
            if current:
                chunks.append(current)
                current = ''
            while len(sentence) > limit:
                boundary = limit
                while boundary < len(sentence) and sentence[boundary] in CLOSING_MARKS:
                    boundary += 1
                chunks.append(sentence[:boundary])
                sentence = sentence[boundary:]
            current = sentence
        if current:
            chunks.append(current)
    return chunks


def prepare(raw, output_dir, title=None, markdown=False, replace=False, fps=30):
    if not isinstance(raw, str) or not raw.strip():
        raise ValueError('Manuscript is empty')
    if isinstance(fps, bool) or not isinstance(fps, int) or not 1 <= fps <= 120:
        raise ValueError('fps must be an integer from 1 to 120')
    cleaned = clean_markdown(raw) if markdown else raw.lstrip('\ufeff').strip()
    paragraphs = [re.sub(r'\s*\n\s*', ' ', p).strip()
                  for p in re.split(r'\n\s*\n', cleaned.replace('\r\n', '\n')) if p.strip()]
    if not paragraphs:
        raise ValueError('Manuscript contains no speakable text')
    units, scenes, occurrences = [], [], Counter()
    for paragraph in paragraphs:
        paragraph_id = 'p-' + hashlib.sha256(paragraph.encode()).hexdigest()[:12]
        start = len(units)
        sentences = split_sentences(paragraph)
        for sentence in split_chunks(sentences, 80):
            if not sentence.strip():
                continue
            digest = hashlib.sha256(sentence.encode()).hexdigest()[:16]
            occurrences[digest] += 1
            units.append({'id': f'u-{digest}-{occurrences[digest]}',
                          'text': sentence, 'paragraphId': f'{paragraph_id}-{len(scenes)+1}'})
        if len(units) > start:
            scenes.append({'id': 's-' + units[start]['id'][2:],
                           'anchorUnit': units[start]['id'], 'label': paragraph[:36]})
    script = {'title': title or units[0]['text'][:36], 'fps': fps,
              'units': units, 'scenes': scenes}
    root = Path(output_dir).resolve()
    script_path = root / 'script.json'
    if script_path.exists() and not replace:
        previous = json.loads(script_path.read_text(encoding='utf-8'))
        if previous != script:
            raise ValueError('script.json exists; use --replace-script to replace it explicitly')
    root.mkdir(parents=True, exist_ok=True)
    extension = 'md' if markdown else 'txt'
    original = root / f'manuscript.original.{extension}'
    if original.exists() and original.read_text(encoding='utf-8') != raw:
        digest = hashlib.sha256(original.read_bytes()).hexdigest()[:16]
        archive = root / 'manuscript-history' / f'{digest}.{extension}'
        archive.parent.mkdir(parents=True, exist_ok=True)
        archive.write_bytes(original.read_bytes())
    original.write_text(raw, encoding='utf-8')
    (root / 'manuscript.txt').write_text('\n\n'.join(paragraphs) + '\n', encoding='utf-8')
    save_json(script_path, script)
    config_path = root / 'narration.json'
    if not config_path.exists():
        from synthesize_narration import DEFAULT_CONFIG
        save_json(config_path, DEFAULT_CONFIG)
    return script


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument('--input', help='UTF-8 TXT or Markdown file')
    source.add_argument('--text', help='Literal text; for private or long scripts prefer --input')
    parser.add_argument('--markdown', action='store_true', help='Clean Markdown in --text input')
    parser.add_argument('--output-dir', required=True, help='Initialized project directory')
    parser.add_argument('--title')
    parser.add_argument('--fps', type=int, default=30)
    parser.add_argument('--replace-script', action='store_true', help='Replace script and draft scene anchors; archive previous original')
    args = parser.parse_args()
    try:
        raw = Path(args.input).read_text(encoding='utf-8') if args.input else args.text
        markdown = args.markdown or bool(args.input and Path(args.input).suffix.lower() in ('.md', '.markdown'))
        result = prepare(raw, args.output_dir, args.title, markdown, args.replace_script, args.fps)
        print(f"Prepared {len(result['units'])} units and {len(result['scenes'])} draft scenes; edit storyboard before rendering")
    except (ValueError, OSError) as error:
        print(str(error), file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
