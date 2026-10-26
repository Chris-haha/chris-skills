"""Separate usable narration from raw recognition; heuristics never certify speech."""
import re
from collections import Counter
from archive import digest

MODE_LABELS = {'speech':'口播分析', 'visual':'画面／正文分析', 'mixed':'口播＋画面分析'}
QUALITY_LABELS = {'usable':'可用', 'pending_review':'待核听，未采用', 'unusable':'不可作为商品口播', 'missing':'无口播文字稿'}


def is_asr(source):
    return any(k in source.lower() for k in ('whisper', 'asr', 'transcri', 'speech')) and source != 'imported_transcript'


def assess(raw, source):
    risks = []
    if source in ('ai_conclusion','summary','ai_summary'):
        status='unusable'; risks.append('AI摘要不能作为口播全文')
    elif not raw.strip():
        status='missing'; risks.append('未取得口播文字稿')
    elif is_asr(source):
        status='pending_review'
        risks.append('自动转录需核听才能作为商品口播；非空不代表有效')
        lines=[re.sub(r'\s+','',s) for s in raw.splitlines() if s.strip()]
        if len(raw.strip()) < 20:
            risks.append('识别文字很短，可能为音乐、口号或识别噪声')
        if len(lines)>2 and max(Counter(lines).values())/len(lines) >= .5:
            risks.append('识别结果高度重复，需排查歌词或幻觉')
    else:
        status='usable'  # Imported full text/platform subtitles remain attributable, not independent product proof.
    return {'status':status,'reason':'；'.join(risks) or '平台字幕或导入全文；仍需阅读核对商品声称',
            'basis':'automatic_screen','raw_hash':digest(raw),'source':source,'risks':risks}


def quality(record, raw=None):
    value=record.get('narration_quality')
    if value and (raw is None or value.get('raw_hash')==digest(raw)):
        return value
    return assess(raw if raw is not None else '\n'.join(p['text'] for p in record.get('paragraphs',[])),record.get('transcript_source',''))


def mode(record):
    return record.get('analysis_mode') or ('visual' if quality(record)['status']!='usable' and record.get('frames') else 'speech')


def narration_allowed(record):
    return quality(record)['status']=='usable' and mode(record) in ('speech','mixed')
