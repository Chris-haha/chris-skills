"""Local caption format reader (shared repository implementation)."""
import html
import json
from pathlib import Path
import re
import xml.etree.ElementTree as ET


def plain_text(value: str) -> str:
    return html.unescape(re.sub(r'<[^>]*>', '', value)).strip()


def xml_caption(node) -> str:
    parts = [node.text or '']
    for child in node:
        parts.append('\n' if child.tag.rsplit('}', 1)[-1] == 'br' else xml_caption(child))
        parts.append(child.tail or '')
    return ''.join(parts)


def read_subtitle(path: Path) -> str:
    content = path.read_text(encoding='utf-8-sig')
    if path.suffix.lower() == '.json3':
        data = json.loads(content)
        lines = [''.join(segment.get('utf8', '') for segment in event.get('segs', []))
                 for event in data.get('events', [])]
    elif path.suffix.lower() in ('.srv3', '.ttml', '.xml'):
        tree = ET.fromstring(content)
        lines = [xml_caption(node) for node in tree.iter()
                 if node.tag.rsplit('}', 1)[-1] in ('p', 'text')]
    else:
        lines = []
        for block in re.split(r'\n\s*\n', content.replace('\r\n', '\n')):
            block_lines = block.strip().splitlines()
            if not block_lines or block_lines[0].startswith(('WEBVTT', 'NOTE', 'STYLE', 'REGION')):
                continue
            timing = next((i for i, line in enumerate(block_lines) if '-->' in line), None)
            if timing is not None:
                lines.extend(line for line in block_lines[timing + 1:] if '-->' not in line)
    # Repeated sentences in separate cues are real content; keep them.
    return '\n'.join(text for line in lines if (text := plain_text(line)))
