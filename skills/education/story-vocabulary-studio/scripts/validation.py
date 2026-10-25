"""Deterministic content checks, distinct from human editorial approval."""
import hashlib
import json
import re

MARKER = re.compile(r'\[\[([^\[\]|]+)\|([^\[\]|]+)\]\]')
SAFE_ID = re.compile(r'^[A-Za-z0-9][A-Za-z0-9_-]{0,99}$')


def content_hash(book):
    payload = {key: value for key, value in book.items() if key != 'editorial_review'} if isinstance(book, dict) else book
    return hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False,
                                     separators=(',', ':')).encode('utf-8')).hexdigest()


def contains_form(text, forms):
    return any(re.search(r'(?<![\w\x27’])' + re.escape(form) + r'(?![\w\x27’])',
                         text, re.IGNORECASE) for form in forms if isinstance(form, str) and form)


def validate_book(data):
    errors, chapters_report = [], []
    report = {'schema_version': 1, 'content_hash': content_hash(data), 'errors': errors,
              'chapters': chapters_report, 'structure_status': 'invalid',
              'semantic_status': 'pending', 'audio_status': 'unchecked', 'ready': False}
    if not isinstance(data, dict):
        errors.append('Book must be an object')
        return report
    if type(data.get('schema_version')) is not int or data.get('schema_version') != 1:
        errors.append('schema_version must be 1')
    metadata = data.get('book')
    if not isinstance(metadata, dict):
        errors.append('book metadata must be an object')
        metadata = {}
    for key in ('book_id', 'title', 'subtitle', 'audience', 'vocabulary_source'):
        if not isinstance(metadata.get(key), str) or not metadata[key].strip():
            errors.append(f'book.{key} requires nonempty text')
    if 'learning_path' in metadata and metadata['learning_path'] != ['mixed', 'meaning', 'answers']:
        errors.append('book.learning_path must be mixed, meaning, answers in that order')
    if 'chapter_narration' in metadata and type(metadata['chapter_narration']) is not bool:
        errors.append('book.chapter_narration must be a boolean')
    if not SAFE_ID.fullmatch(str(metadata.get('book_id', ''))):
        errors.append('book.book_id must be a safe stable ID')
    characters = metadata.get('characters')
    if not isinstance(characters, list) or not characters:
        errors.append('book.characters must be a nonempty array')
    elif any(not isinstance(c, dict) or any(not isinstance(c.get(k), str) or not c[k].strip()
                                           for k in ('name', 'role')) for c in characters):
        errors.append('Each character needs name and role')
    limits = {}
    for key, default in [('chapter_min_chars', 600), ('chapter_max_chars', 1000),
                         ('new_words_per_chapter', 8), ('review_words_per_chapter', 4)]:
        value = metadata.get(key, default)
        if type(value) is not int or value < (1 if key == 'new_words_per_chapter' else 0):
            errors.append(f'book.{key} must be a nonnegative integer')
            value = default
        limits[key] = value
    if limits['chapter_min_chars'] > limits['chapter_max_chars']:
        errors.append('chapter_min_chars exceeds chapter_max_chars')
    vocabulary = data.get('vocabulary')
    if not isinstance(vocabulary, list) or not vocabulary:
        errors.append('vocabulary must be a nonempty array')
        vocabulary = []
    words = {}
    for index, word in enumerate(vocabulary):
        if not isinstance(word, dict):
            errors.append(f'vocabulary[{index}] must be an object')
            continue
        word_id = word.get('word_id')
        if not isinstance(word_id, str) or not SAFE_ID.fullmatch(word_id):
            errors.append(f'vocabulary[{index}] has invalid word_id')
            continue
        if word_id in words:
            errors.append(f'Duplicate word_id: {word_id}')
        words[word_id] = word
        for field in ('lemma', 'pos', 'ipa', 'sense_zh', 'explanation', 'source', 'source_version'):
            if not isinstance(word.get(field), str) or not word[field].strip():
                errors.append(f'{word_id}.{field} requires nonempty text')
        aliases = word.get('meaning_answers', [])
        if not isinstance(aliases, list) or any(not isinstance(a, str) or not a.strip() for a in aliases):
            errors.append(f'{word_id}.meaning_answers must be an array of nonempty strings')
        forms = word.get('forms')
        if not isinstance(forms, list) or not forms or any(not isinstance(f, str) or not f.strip() for f in forms):
            errors.append(f'{word_id}.forms must explicitly list inflections')
        elif isinstance(word.get('lemma'), str) and word['lemma'].casefold() not in [f.casefold() for f in forms]:
            errors.append(f'{word_id}.forms must contain its lemma')
    chapters = data.get('chapters')
    if not isinstance(chapters, list) or not chapters:
        errors.append('chapters must be a nonempty array')
        chapters = []
    introduced, chapter_ids, paragraph_ids, question_ids = set(), set(), set(), set()

    def stable_id(item, key, seen, where):
        identifier = item.get(key)
        if not isinstance(identifier, str) or not SAFE_ID.fullmatch(identifier):
            errors.append(f'{where}.{key} must be a safe stable ID')
            return None
        if identifier in seen:
            errors.append(f'Duplicate {key}: {identifier}')
        seen.add(identifier)
        return identifier

    for number, chapter in enumerate(chapters):
        if not isinstance(chapter, dict):
            errors.append(f'chapters[{number}] must be an object')
            continue
        cid = stable_id(chapter, 'chapter_id', chapter_ids, f'chapters[{number}]') or str(number)
        for field in ('title', 'summary'):
            if not isinstance(chapter.get(field), str) or not chapter[field].strip():
                errors.append(f'{cid}.{field} requires nonempty text')
        plans = {}
        for field, count in [('new_word_ids', limits['new_words_per_chapter']),
                             ('review_word_ids', 0 if number == 0 else limits['review_words_per_chapter'])]:
            ids = chapter.get(field)
            if not isinstance(ids, list) or any(not isinstance(w, str) for w in ids):
                errors.append(f'{cid}.{field} must be an array of IDs')
                ids = []
            if len(ids) != count:
                errors.append(f'{cid}.{field} needs {count} IDs; got {len(ids)}')
            if len(ids) != len(set(ids)):
                errors.append(f'{cid}.{field} contains duplicates')
            for wid in ids:
                if wid not in words:
                    errors.append(f'{cid}.{field} references unknown word {wid}')
            plans[field] = set(ids)
        new, review = plans['new_word_ids'], plans['review_word_ids']
        if new & introduced:
            errors.append(f'{cid} introduces already introduced words: {sorted(new & introduced)}')
        if review - introduced:
            errors.append(f'{cid} reviews words not introduced earlier: {sorted(review - introduced)}')
        if new & review:
            errors.append(f'{cid} has overlapping new and review words')
        paragraphs = chapter.get('paragraphs')
        if not isinstance(paragraphs, list) or not paragraphs:
            errors.append(f'{cid}.paragraphs must be a nonempty array')
            paragraphs = []
        marked, english_text, mixed_text, local_paragraphs = set(), [], [], set()
        for paragraph in paragraphs:
            if not isinstance(paragraph, dict):
                errors.append(f'{cid} paragraph must be an object')
                continue
            pid = stable_id(paragraph, 'paragraph_id', paragraph_ids, cid)
            if pid:
                local_paragraphs.add(pid)
            mixed, english = paragraph.get('mixed'), paragraph.get('english')
            if not isinstance(mixed, str) or not mixed.strip() or not isinstance(english, str) or not english.strip():
                errors.append(f'{cid}/{pid} requires mixed and english text')
                continue
            english_text.append(english)
            clean = MARKER.sub('', mixed)
            mixed_text.append(clean)
            if '[[' in clean or ']]' in clean:
                errors.append(f'{cid}/{pid} contains malformed word markers')
            for wid, sense in MARKER.findall(mixed):
                marked.add(wid)
                if wid not in words:
                    errors.append(f'{cid}/{pid} marks unknown word {wid}')
                elif sense != words[wid].get('sense_zh'):
                    errors.append(f'{cid}/{pid}/{wid} sense does not match sense_zh')
            # Target English tokens in mixed Chinese must be explicit interactive markers.
            for wid, word in words.items():
                if contains_form(clean, word.get('forms', []) if isinstance(word.get('forms'), list) else []):
                    errors.append(f'{cid}/{pid} has unmarked vocabulary {wid}')
        targets = new | review
        combined_english = '\n'.join(english_text)
        found_english = {wid for wid, word in words.items()
                         if contains_form(combined_english, word.get('forms', []) if isinstance(word.get('forms'), list) else [])}
        missing_mixed, missing_english = sorted(targets - marked), sorted(targets - found_english)
        unexpected_mixed, unexpected_english = sorted(marked - targets), sorted(found_english - targets)
        for label, missing in [('mixed', missing_mixed), ('english', missing_english)]:
            if missing:
                errors.append(f'{cid} missing {label} targets: {missing}')
        if unexpected_mixed:
            errors.append(f'{cid} contains unplanned mixed targets: {unexpected_mixed}')
        char_count = len(re.findall(r'[\u3400-\u4dbf\u4e00-\u9fff]', ''.join(mixed_text)))
        if not limits['chapter_min_chars'] <= char_count <= limits['chapter_max_chars']:
            errors.append(f'{cid} unmarked Chinese characters {char_count} outside '
                          f"{limits['chapter_min_chars']}–{limits['chapter_max_chars']}")
        chapters_report.append({'chapter_id': cid, 'chinese_chars': char_count,
                                'missing_mixed': missing_mixed, 'missing_english': missing_english,
                                'incidental_words': unexpected_english,
                                'new_word_count': len(new), 'review_word_count': len(review)})
        questions = chapter.get('questions')
        if not isinstance(questions, list) or not questions:
            errors.append(f'{cid}.questions must be a nonempty array')
            questions = []
        for question in questions:
            if not isinstance(question, dict):
                errors.append(f'{cid} question must be an object')
                continue
            qid = stable_id(question, 'question_id', question_ids, cid)
            for field in ('prompt', 'explanation'):
                if not isinstance(question.get(field), str) or not question[field].strip():
                    errors.append(f'{cid}/{qid}.{field} requires nonempty text')
            options, answer = question.get('options'), question.get('answer_index')
            if not isinstance(options, list) or len(options) < 2 or any(not isinstance(o, str) or not o.strip() for o in options):
                errors.append(f'{cid}/{qid}.options needs at least two nonempty strings')
                options = []
            if type(answer) is not int or not 0 <= answer < len(options):
                errors.append(f'{cid}/{qid} answer_index is out of range')
            if not isinstance(question.get('evidence_paragraph_id'), str) or question['evidence_paragraph_id'] not in local_paragraphs:
                errors.append(f'{cid}/{qid} evidence_paragraph_id must reference this chapter')
        introduced |= new
    if set(words) - introduced:
        errors.append(f'Vocabulary never introduced: {sorted(set(words) - introduced)}')
    if 'review_prompts' in data:
        prompts = data['review_prompts']
        prompt_ids, sentences = set(), set()
        story_texts = []
        for c in chapters:
            if isinstance(c, dict) and isinstance(c.get('paragraphs'), list):
                story_texts.extend(p.get('english', '') for p in c['paragraphs']
                                   if isinstance(p, dict) and isinstance(p.get('english'), str))
        if not isinstance(prompts, list):
            errors.append('review_prompts must be an array')
            prompts = []
        for prompt in prompts:
            if not isinstance(prompt, dict):
                errors.append('Each review prompt must be an object')
                continue
            wid = prompt.get('word_id')
            if not isinstance(wid, str) or wid not in words:
                errors.append('Review prompt references an unknown word')
                continue
            if wid in prompt_ids:
                errors.append(f'Duplicate review prompt: {wid}')
            prompt_ids.add(wid)
            word = words[wid]
            provenance = word.get('provenance', {})
            if not isinstance(provenance, dict) or not provenance.get('sense_id') or prompt.get('sense_id') != provenance['sense_id']:
                errors.append(f'{wid} review prompt must bind its reviewed sense_id')
            sentence = prompt.get('sentence')
            if not isinstance(sentence, str) or not sentence.strip():
                errors.append(f'{wid} review prompt requires a sentence')
            else:
                forms = word.get('forms') if isinstance(word.get('forms'), list) else []
                if not contains_form(sentence, forms):
                    errors.append(f'{wid} review sentence missing allowed form')
                if sentence in sentences:
                    errors.append(f'{wid} review sentence duplicates another prompt')
                sentences.add(sentence)
                if any(sentence in text for text in story_texts):
                    errors.append(f'{wid} review sentence must use a new context')
            if not isinstance(prompt.get('explanation_zh'), str) or not prompt['explanation_zh'].strip():
                errors.append(f'{wid} review prompt requires explanation_zh')
        if set(words) != prompt_ids:
            errors.append('review_prompts must cover every vocabulary word exactly once')
    review = data.get('editorial_review')
    if isinstance(review, dict) and review.get('status') == 'approved':
        if review.get('reviewed_content_sha256') != report['content_hash']:
            report['semantic_status'] = 'stale'
        elif isinstance(review.get('reviewer'), str) and review['reviewer'].strip() and review.get('findings') == []:
            report['semantic_status'] = 'approved'
    report['structure_status'] = 'valid' if not errors else 'invalid'
    report['content_ready'] = not errors and report['semantic_status'] == 'approved'
    return report
