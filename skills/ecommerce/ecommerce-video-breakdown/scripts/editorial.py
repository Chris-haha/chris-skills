"""Check authored prose without touching source quotations or personal workbook notes.

These checks catch known production defects. Readability still needs a human read
of the saved deliverable; passing a punctuation check does not establish clarity.
"""
import re
import json
from pathlib import Path

BAD_PUNCTUATION = re.compile(r'[。；;！？!?][。；;]|[，,]{2}|[：:]{2}')
VAGUE_PHRASES = ('两版先只改这一点', '其它不变：', '其他不变：')
COMPARISON_FIELDS = (
    ('variable', '这次比较什么'), ('control', '第一条视频'), ('treatment', '第二条视频'),
    ('constants', '相同的部分'), ('metric', '记录哪些数字'),
    ('denominator', '怎么计算'), ('decision_rule', '根据结果怎么选'),
)


def paragraphs(*parts):
    """Full sentences keep their own punctuation; never add sentence separators."""
    return '\n\n'.join(str(part).strip() for part in parts if str(part).strip())


def experiment_text(experiment):
    return paragraphs(*(f'{label}：{experiment[field]}' for field, label in COMPARISON_FIELDS))


def check_analysis(analysis):
    errors = []

    def visit(value, path):
        if isinstance(value, dict):
            for key, child in value.items():
                # Quotes, IDs and evidence are source data, not generated prose.
                if key in ('evidence_ids', 'evidence_refs', 'mechanism_ids', 'id', 'quote'):
                    continue
                visit(child, f'{path}.{key}')
        elif isinstance(value, list):
            for i, child in enumerate(value):
                visit(child, f'{path}[{i}]')
        elif isinstance(value, str):
            for match in BAD_PUNCTUATION.finditer(value):
                errors.append(f'{path}: 标点连用“{match.group()}”，请重写整句')
            for phrase in VAGUE_PHRASES:
                if phrase in value:
                    errors.append(f'{path}: 表述不具体“{phrase}”，请写出两条视频各自怎么做')

    # Explicit allowlist keeps raw metadata, transcripts and workbook notes out.
    for field in ('modules', 'creation', 'elements', 'patterns'):
        visit(analysis.get(field, {}), field)
    return errors


def check_report(report):
    errors = []
    for group, identity in (('videos', 'video_key'), ('creators', 'creator_key')):
        for item in report.get(group, []):
            if item.get('report_status') not in (None, 'complete') or item.get('validation_errors'):
                continue
            key = item.get('record', {}).get(identity) or item.get(identity, group)
            errors.extend(f'{key}: {error}' for error in check_analysis(item.get('analysis', {})))
    return errors


def check_workspace(workspace):
    """Catch prose even when another validator has withheld a finished analysis."""
    root = Path(workspace) / 'analyses'
    errors = []
    for path in [*root.glob('*.json'), *(root / 'creators').glob('*.json')]:
        value = json.loads(path.read_text(encoding='utf-8'))
        if isinstance(value, dict) and value.get('status') == 'complete':
            errors.extend(f'{path.name}: {e}' for e in check_analysis(value))
    return errors
