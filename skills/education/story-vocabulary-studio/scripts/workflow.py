#!/usr/bin/env python3
"""Validate, voice, render and export a portable story vocabulary reader."""
import argparse
import csv
import html
import json
import os
from pathlib import Path
import re
import sys
import tempfile
import zipfile

from audio import generate_audio, inspect_audio, load_config, save_json, narrated_chapters
from validation import validate_book

SKILL_ROOT = Path(__file__).resolve().parents[1]
GENERATED = ('index.html', 'book.json', 'vocabulary.csv', 'quality-report.json', 'audio-manifest.json')


def load_book(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def quality_report(book, output_dir, config=None):
    report = validate_book(book)
    if report['errors']:
        return report
    audio = inspect_audio(book, output_dir, config)
    report['audio_status'] = audio['status']
    report['audio_errors'] = audio.get('errors', [])
    report['ready'] = report['content_ready'] and audio['status'] == 'ready'
    return report


def inline_json(data):
    return json.dumps(data, ensure_ascii=False, separators=(',', ':')).replace('<', '\\u003c').replace('>', '\\u003e').replace('&', '\\u0026').replace('\u2028', '\\u2028').replace('\u2029', '\\u2029')


def render(book_path, output_dir, skill_root=None, config=None):
    book_path, root = Path(book_path).resolve(), Path(output_dir).resolve()
    if root == book_path or root in book_path.parents:
        raise ValueError('Output directory must not contain the source book')
    book = load_book(book_path)
    report = quality_report(book, root, config)
    if report['errors']:
        raise ValueError('Content validation failed: ' + '; '.join(report['errors']))
    assets = Path(skill_root or SKILL_ROOT) / 'assets'
    template = (assets / 'reader.html').read_text(encoding='utf-8')
    if not book['book'].get('chapter_narration', True):
        template = re.sub(r'<section class="audio-panel"[^>]*>.*?</section>', '', template, flags=re.DOTALL)
    css = (assets / 'reader.css').read_text(encoding='utf-8')
    script = (assets / 'reader.js').read_text(encoding='utf-8')
    for token in ('<!--STYLE-->', '<!--BOOK-->', '<!--AUDIO-->', '<!--SCRIPT-->'):
        if template.count(token) != 1:
            raise ValueError(f'Reader template requires exactly one {token} placeholder')
    audio = inspect_audio(book, root, config)
    payload = {**book, 'content_hash': report['content_hash'], 'quality_report': report}
    def inject(document, token, text, tag):
        # Templates normally supply the wrapping style/script element. Also support
        # bare placeholders to keep standalone minimal templates usable.
        prefix = document[:document.index(token)].lower()
        inside = prefix.rfind('<' + tag) > prefix.rfind('</' + tag)
        return document.replace(token, text if inside else '<' + tag + '>' + text + '</' + tag + '>')

    document = inject(template, '<!--STYLE-->', css, 'style')
    document = inject(document, '<!--BOOK-->', 'window.STORY_BOOK=' + inline_json(payload) + ';', 'script')
    document = inject(document, '<!--AUDIO-->', 'window.STORY_AUDIO=' + inline_json(audio) + ';', 'script')
    document = inject(document, '<!--SCRIPT-->', script.replace('</script', '<\\/script'), 'script')
    document = re.sub(r'<title>.*?</title>', lambda _: '<title>' + html.escape(book['book']['title']) + '</title>',
                      document, count=1, flags=re.DOTALL | re.IGNORECASE)
    if not report['ready']:
        banner = '<aside id="delivery-draft-banner" role="status">'
        if report['content_ready']:
            banner += ('学习样包 · 内容已审校 · 单词点读配音待做。' if not book['book'].get('chapter_narration', True)
                       else '学习样包 · 内容已审校 · 配音待做，当前版本不含可播放音频。')
        else:
            banner += '内容草稿 · 语义审校尚未通过；配音按实际状态提供。'
        banner += '</aside>'
        body = re.search(r'<body\b[^>]*>', document, re.IGNORECASE)
        if body:
            document = document[:body.end()] + banner + document[body.end():]
        else:
            document += banner
    root.mkdir(parents=True, exist_ok=True)
    (root / 'index.html').write_text(document, encoding='utf-8')
    save_json(root / 'book.json', book)
    save_json(root / 'quality-report.json', report)
    # An absent or stale manifest is replaced with nonplayable metadata when rendering drafts.
    # Existing verified audio metadata remains byte-for-byte intact.
    if audio['status'] != 'ready':
        save_json(root / 'audio-manifest.json', audio)
    fields = ('word_id', 'lemma', 'pos', 'ipa', 'sense_zh', 'forms', 'explanation', 'source', 'source_version')
    with (root / 'vocabulary.csv').open('w', encoding='utf-8-sig', newline='') as target:
        writer = csv.DictWriter(target, fieldnames=fields)
        writer.writeheader()
        for word in book['vocabulary']:
            writer.writerow({field: '|'.join(word[field]) if field == 'forms' else word[field] for field in fields})
    return report


def safe_artifact(path, base):
    relative = path.relative_to(base)
    if path.is_symlink() or any((base / Path(*relative.parts[:n])).is_symlink() for n in range(1, len(relative.parts))):
        raise ValueError('Symlinks are forbidden in delivery artifacts')
    if not path.is_file() or base.resolve() not in path.resolve().parents or '..' in relative.parts:
        raise ValueError('Delivery artifact escapes its source directory')
    return path


def package(book_path, output_dir, output_path, skill_root=None, config=None, allow_draft=False):
    if Path(book_path).is_symlink():
        raise ValueError('Symlink sources are forbidden in delivery artifacts')
    root, skill = Path(output_dir).resolve(), Path(skill_root or SKILL_ROOT).resolve()
    target = Path(output_path).resolve()
    book = load_book(book_path)
    report = quality_report(book, root, config)
    if not report.get('content_ready'):
        raise ValueError('Package requires valid content and current approved editorial review')
    if not report['ready'] and not allow_draft:
        raise ValueError('Final package requires valid content, current approved editorial review and verified ready audio')
    render(book_path, root, skill, config)
    audio = inspect_audio(book, root, config)
    if audio['status'] != 'ready' and not allow_draft:
        raise ValueError('Audio became invalid while preparing delivery')
    files = [(safe_artifact(root / name, root), 'reader/' + name) for name in GENERATED]
    if audio['status'] == 'ready':
        from audio import verified_file
        entries = [audio['words'][word['word_id']] for word in book['vocabulary']]
        entries += [audio['chapters'][chapter['chapter_id']] for chapter in narrated_chapters(book)]
        for entry in entries:
            if not verified_file(root, entry, load_config(config)):
                raise ValueError('Audio failed integrity checks while collecting package files')
            files.append((safe_artifact(root / entry['file'], root), 'reader/' + entry['file']))
    required_skill_files = ['SKILL.md', 'scripts/workflow.py', 'scripts/audio.py', 'scripts/validation.py',
                            'assets/reader.html', 'assets/reader.css', 'assets/reader.js']
    for name in required_skill_files:
        files.append((safe_artifact(skill / name, skill), 'skill/story-vocabulary-studio/' + name))
    metadata = skill / 'agents/openai.yaml'
    if metadata.exists():
        files.append((safe_artifact(metadata, skill), 'skill/story-vocabulary-studio/agents/openai.yaml'))
    reference_root = skill / 'references'
    if reference_root.exists():
        for source in sorted(reference_root.rglob('*')):
            if source.is_symlink():
                raise ValueError('Symlinks are forbidden in skill references')
            if source.is_file() and source.suffix in ('.md', '.json', '.csv', '.txt') and not any(p.startswith('.') for p in source.relative_to(skill).parts):
                files.append((safe_artifact(source, skill), 'skill/story-vocabulary-studio/' + source.relative_to(skill).as_posix()))
    # Source material is explicitly selected; no recursive project/raw/cache copy occurs.
    files.append((Path(book_path).resolve(), 'sample/book.json'))
    if target in [source for source, _ in files]:
        raise ValueError('ZIP destination would overwrite an input artifact')
    target.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix='.' + target.name, suffix='.zip', dir=target.parent)
    os.close(descriptor)
    try:
        with zipfile.ZipFile(temporary, 'w', zipfile.ZIP_DEFLATED) as archive:
            for source, name in files:
                archive.write(source, name)
            pending = audio['status'] != 'ready'
            status = {'status': 'audio_pending' if pending else 'ready', 'content_hash': report['content_hash'],
                      'missing_audio': {'word_ids': [w['word_id'] for w in book['vocabulary'] if w['word_id'] not in audio['words']],
                                        'chapter_ids': [c['chapter_id'] for c in narrated_chapters(book) if c['chapter_id'] not in audio['chapters']]}}
            archive.writestr('PACKAGE-STATUS.json', json.dumps(status, ensure_ascii=False, indent=2) + '\n')
            archive.writestr('README.txt', ('AUDIO PENDING: 配音待做。No playable audio is included; no substitute or fake audio was generated.\n' if pending else '')
                + 'Open reader/index.html in a modern browser.\n'
                'The sample/book.json source and standalone skill are included.\n'
                + ('Generate real audio later using the included workflow audio command and DOUBAO_TTS_API_KEY environment variable.\n' if pending
                   else 'Audio is AI generated by Doubao; all playback files are local.\n'))
        os.replace(temporary, target)
    finally:
        Path(temporary).unlink(missing_ok=True)
    return target


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    for name in ('validate', 'audio', 'render', 'package'):
        command = commands.add_parser(name)
        command.add_argument('book', help='Path to book.json')
        command.add_argument('--output-dir', default='output', help='Reader/audio output directory')
        command.add_argument('--config', help='JSON file containing voice settings only')
        if name == 'validate':
            command.add_argument('--require-ready', action='store_true')
        if name == 'audio':
            command.add_argument('--dry-run', action='store_true')
        if name in ('render', 'package'):
            command.add_argument('--skill-root', help='Standalone skill source folder')
        if name == 'package':
            command.add_argument('--output', required=True, help='Destination ZIP path')
            command.add_argument('--allow-draft', action='store_true', help='Explicitly export an editorially approved package with audio marked pending')
    args = parser.parse_args(argv)
    try:
        config = load_config(args.config)
        if args.command == 'validate':
            report = quality_report(load_book(args.book), args.output_dir, config)
            print(json.dumps(report, ensure_ascii=False, indent=2))
            return 1 if report['errors'] or (args.require_ready and not report['ready']) else 0
        if args.command == 'audio':
            report = generate_audio(load_book(args.book), args.output_dir, config, args.dry_run)
        elif args.command == 'render':
            report = render(args.book, args.output_dir, args.skill_root, config)
        else:
            report = {'package': str(package(args.book, args.output_dir, args.output, args.skill_root, config, args.allow_draft))}
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0
    except (OSError, ValueError, KeyError, TypeError) as error:
        print(f'Workflow failed: {error}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
