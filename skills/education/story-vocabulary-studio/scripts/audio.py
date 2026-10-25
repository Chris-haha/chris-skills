"""Independent Doubao NDJSON speech client and verified, resumable WAV artifacts."""
import base64
import binascii
import hashlib
import http.client
import json
import os
from pathlib import Path
import socket
import tempfile
import time
import urllib.error
import urllib.request
import uuid
import wave

from validation import content_hash, validate_book

ENDPOINT = 'https://openspeech.bytedance.com/api/v3/tts/unidirectional'
DEFAULT_CONFIG = {'provider': 'doubao', 'resourceId': 'seed-tts-2.0',
                  'speaker': 'en_female_dacey_uranus_bigtts', 'sampleRate': 24000,
                  'speechRate': 0, 'timeoutSeconds': 60}


class SynthesisError(ValueError):
    def __init__(self, message, retryable=False):
        super().__init__(message)
        self.retryable = retryable


def digest_bytes(raw):
    return hashlib.sha256(raw).hexdigest()


def file_hash(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as source:
        for block in iter(lambda: source.read(1048576), b''):
            digest.update(block)
    return digest.hexdigest()


def save_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, name = tempfile.mkstemp(prefix='.' + path.name, suffix='.tmp', dir=path.parent)
    try:
        with os.fdopen(descriptor, 'w', encoding='utf-8') as target:
            json.dump(data, target, ensure_ascii=False, indent=2)
            target.write('\n')
        os.replace(name, path)
    finally:
        Path(name).unlink(missing_ok=True)


def load_config(config=None):
    if isinstance(config, (str, Path)):
        config = json.loads(Path(config).read_text(encoding='utf-8'))
    if config is None:
        config = {}
    if not isinstance(config, dict) or set(config) - set(DEFAULT_CONFIG):
        raise ValueError('Unknown audio configuration field; credentials belong in the environment only')
    result = {**DEFAULT_CONFIG, **config}
    if result['provider'] != 'doubao' or result['resourceId'] != 'seed-tts-2.0':
        raise ValueError('Only doubao seed-tts-2.0 is supported')
    if not isinstance(result['speaker'], str) or not result['speaker'].strip() or any(c in result['speaker'] for c in '\r\n'):
        raise ValueError('speaker must be a system voice ID')
    if type(result['sampleRate']) is not int or result['sampleRate'] not in (8000, 16000, 22050, 24000, 32000, 44100, 48000):
        raise ValueError('Unsupported sampleRate')
    for field, minimum, maximum in [('speechRate', -50, 100), ('timeoutSeconds', 1, 120)]:
        if type(result[field]) is not int or not minimum <= result[field] <= maximum:
            raise ValueError(f'{field} outside supported integer range')
    return result


def voice_hash(config):
    return digest_bytes(json.dumps({key: config[key] for key in DEFAULT_CONFIG if key != 'timeoutSeconds'},
                                  sort_keys=True, separators=(',', ':')).encode())


def segment_key(text, config):
    return digest_bytes((voice_hash(config) + '\n' + text).encode('utf-8'))


def read_stream(response):
    pcm = bytearray()
    for raw in response:
        if not raw.strip():
            continue
        try:
            packet = json.loads(raw)
        except (ValueError, UnicodeError):
            raise SynthesisError('Invalid JSON speech response', True) from None
        if not isinstance(packet, dict) or type(packet.get('code')) is not int:
            raise SynthesisError('Speech response lacks integer status')
        code = packet['code']
        if code not in (0, 20000000):
            detail = str(packet.get('message', '')).lower()
            permanent = any(token in detail for token in ('auth', 'quota', 'balance', 'credit', 'permission',
                'speaker', 'resource', 'invalid', 'billing', 'forbidden', '余额', '额度', '鉴权', '音色', '参数', '欠费'))
            retryable = not permanent and (code >= 50000000 or any(
                token in detail for token in ('busy', 'timeout', 'limit', '限流', '繁忙')))
            raise SynthesisError(f'Doubao business error {code}; check console credentials and quota', retryable)
        if packet.get('data') is not None:
            try:
                if not isinstance(packet['data'], str):
                    raise ValueError()
                pcm.extend(base64.b64decode(packet['data'], validate=True))
            except (ValueError, binascii.Error):
                raise SynthesisError('Invalid base64 speech payload', True) from None
        if code == 20000000:
            if not pcm or len(pcm) % 2:
                raise SynthesisError('Completed speech is empty or malformed PCM16')
            return bytes(pcm)
    raise SynthesisError('Speech stream ended without completion marker; discarded partial audio', True)


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def request_audio(text, config, api_key, transport=None, sleep=time.sleep):
    if not isinstance(api_key, str) or not api_key or any(not 33 <= ord(c) <= 126 for c in api_key):
        raise SynthesisError('DOUBAO_TTS_API_KEY is missing or contains invalid header characters')
    transport = transport or urllib.request.build_opener(NoRedirect).open
    payload = {'req_params': {'text': text, 'speaker': config['speaker'], 'audio_params': {
        'format': 'pcm', 'sample_rate': config['sampleRate'], 'speech_rate': config['speechRate']}}}
    for attempt in range(3):
        request = urllib.request.Request(ENDPOINT, data=json.dumps(payload, ensure_ascii=False).encode(),
            headers={'Content-Type': 'application/json', 'X-Api-Key': api_key,
                     'X-Api-Resource-Id': config['resourceId'], 'X-Api-Request-Id': str(uuid.uuid4())}, method='POST')
        try:
            with transport(request, timeout=config['timeoutSeconds']) as response:
                return read_stream(response)
        except urllib.error.HTTPError as error:
            failure = SynthesisError(f'Doubao HTTP {error.code}; check credentials and quota',
                                     error.code in (408, 429, 500, 502, 503, 504))
            error.close()
        except (urllib.error.URLError, socket.timeout, TimeoutError, ConnectionError, http.client.HTTPException):
            failure = SynthesisError('Speech network failure; discarded partial audio', True)
        except SynthesisError as error:
            failure = error
        except ValueError:
            failure = SynthesisError('Invalid speech request configuration')
        if not failure.retryable or attempt == 2:
            raise failure from None
        sleep(2 ** attempt)


def read_wav(path, sample_rate=None):
    with wave.open(str(path), 'rb') as source:
        frames, rate = source.getnframes(), source.getframerate()
        if source.getnchannels() != 1 or source.getsampwidth() != 2 or source.getcomptype() != 'NONE':
            raise ValueError('Audio must be uncompressed mono PCM16 WAV')
        if sample_rate is not None and rate != sample_rate:
            raise ValueError('Audio sample rate differs from configured voice')
        pcm = source.readframes(frames)
        if frames <= 0 or len(pcm) != frames * 2:
            raise ValueError('Audio WAV is empty or truncated')
        return pcm, rate


def write_wav(path, pcm, rate):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix='.' + path.name, suffix='.wav', dir=path.parent)
    os.close(descriptor)
    try:
        with wave.open(temporary, 'wb') as target:
            target.setnchannels(1)
            target.setsampwidth(2)
            target.setframerate(rate)
            target.writeframes(pcm)
        read_wav(temporary, rate)
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


def verified_file(root, entry, config):
    try:
        if not isinstance(entry, dict) or not isinstance(entry.get('file'), str):
            return False
        relative = Path(entry['file'])
        if relative.is_absolute() or '..' in relative.parts or relative.parts[0] != 'audio':
            return False
        path = root / relative
        if path.is_symlink() or root.resolve() not in path.resolve().parents:
            return False
        pcm, rate = read_wav(path, config['sampleRate'])
        return (entry.get('sha256') == file_hash(path) and entry.get('sample_count') == len(pcm) // 2
                and entry.get('duration') == len(pcm) / 2 / rate and entry.get('voice_hash') == voice_hash(config))
    except (OSError, ValueError, TypeError, wave.Error, EOFError, IndexError):
        return False


def cache_entry(cache, text, config):
    key = segment_key(text, config)
    target = cache / (key + '.wav')
    try:
        metadata = json.loads((cache / (key + '.json')).read_text(encoding='utf-8'))
        pcm, rate = read_wav(target, config['sampleRate'])
        if (target.is_symlink() or metadata.get('completion_code') != 20000000
                or metadata.get('source_text') != text or metadata.get('voice_hash') != voice_hash(config)
                or metadata.get('sha256') != file_hash(target)):
            return None
        return pcm
    except (OSError, ValueError, TypeError, AttributeError, wave.Error, EOFError):
        return None


def narrated_chapters(book):
    return book['chapters'] if book['book'].get('chapter_narration', True) else []


def expected_segments(book):
    return [(word['word_id'], word['lemma']) for word in book['vocabulary']] + [
        (paragraph['paragraph_id'], paragraph['english'])
        for chapter in narrated_chapters(book) for paragraph in chapter['paragraphs']]


def inspect_audio(book, output_dir, config=None):
    config = load_config(config)
    root = Path(output_dir)
    empty = {'schema_version': 1, 'content_hash': content_hash(book), 'status': 'missing',
             'voice': config, 'voice_hash': voice_hash(config), 'words': {}, 'chapters': {}, 'errors': []}
    try:
        manifest = json.loads((root / 'audio-manifest.json').read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return empty
    if not isinstance(manifest, dict):
        return empty
    if (manifest.get('status') == 'missing' and manifest.get('content_hash') == content_hash(book)
            and manifest.get('voice_hash') == voice_hash(config)):
        return empty
    empty['status'] = 'stale'
    if (manifest.get('status') != 'ready' or manifest.get('content_hash') != content_hash(book)
            or manifest.get('voice_hash') != voice_hash(config)):
        empty['errors'].append('Audio manifest is incomplete or bound to different content/voice')
        return empty
    errors = empty['errors']
    words, chapters = manifest.get('words'), manifest.get('chapters')
    if not isinstance(words, dict) or not isinstance(chapters, dict):
        return empty
    if (set(words) != {word['word_id'] for word in book['vocabulary']}
            or set(chapters) != {chapter['chapter_id'] for chapter in narrated_chapters(book)}):
        errors.append('Audio manifest IDs must exactly match book vocabulary and chapters')
        return empty
    for word in book['vocabulary']:
        entry = words.get(word['word_id'], {})
        if not isinstance(entry, dict):
            errors.append(f"Malformed word audio entry: {word['word_id']}")
            continue
        if (not verified_file(root, entry, config) or entry.get('source_text') != word['lemma']
                or entry.get('text_hash') != digest_bytes(word['lemma'].encode())):
            errors.append(f"Missing or stale word audio: {word['word_id']}")
    for chapter in narrated_chapters(book):
        entry = chapters.get(chapter['chapter_id'], {})
        if not isinstance(entry, dict):
            errors.append(f"Malformed chapter audio entry: {chapter['chapter_id']}")
            continue
        text = '\n'.join(p['english'] for p in chapter['paragraphs'])
        valid = (verified_file(root, entry, config) and entry.get('source_text') == text
                 and entry.get('text_hash') == digest_bytes(text.encode()))
        cues = entry.get('cues', [])
        valid = valid and isinstance(cues, list) and len(cues) == len(chapter['paragraphs'])
        previous_end = 0
        if valid:
            for paragraph, cue in zip(chapter['paragraphs'], cues):
                if (not isinstance(cue, dict) or cue.get('paragraph_id') != paragraph['paragraph_id']
                        or cue.get('source_text') != paragraph['english'] or cue.get('start') != previous_end
                        or type(cue.get('end')) not in (int, float) or cue['end'] <= previous_end
                        or cue['end'] > entry['duration']):
                    valid = False
                    break
                previous_end = cue['end']
            valid = valid and previous_end == entry['duration']
        if not valid:
            errors.append(f"Missing or stale chapter audio: {chapter['chapter_id']}")
    if errors:
        # Never expose unchecked file references to the reader.
        return empty
    return {**manifest, 'errors': []}


def generate_audio(book, output_dir, config=None, dry_run=False, api_key=None,
                   transport=None, sleep=time.sleep):
    report = validate_book(book)
    if report['errors']:
        raise ValueError('Content validation failed: ' + '; '.join(report['errors']))
    config = load_config(config)
    root = Path(output_dir)
    cache = root / '.cache' / 'paragraph-audio'
    segments = expected_segments(book)
    pending = [(identifier, text) for identifier, text in segments if cache_entry(cache, text, config) is None]
    if dry_run:
        return {'status': 'dry-run', 'content_hash': content_hash(book), 'voice': config,
                'segments': len(segments), 'pending_segments': len(pending),
                'cached_segments': len(segments) - len(pending),
                'pending_characters': sum(len(text) for _, text in pending),
                'credential_available': bool(os.environ.get('DOUBAO_TTS_API_KEY') or api_key)}
    root.mkdir(parents=True, exist_ok=True)
    manifest_path = root / 'audio-manifest.json'
    manifest = {'schema_version': 1, 'content_hash': content_hash(book), 'status': 'running',
                'provider': 'doubao', 'ai_generated': True, 'voice': config,
                'voice_hash': voice_hash(config), 'words': {}, 'chapters': {}}
    save_json(manifest_path, manifest)
    key = api_key if api_key is not None else os.environ.get('DOUBAO_TTS_API_KEY', '')

    def segment(text):
        pcm = cache_entry(cache, text, config)
        if pcm is None:
            pcm = request_audio(text, config, key, transport, sleep)
            cache.mkdir(parents=True, exist_ok=True)
            identity = segment_key(text, config)
            target = cache / (identity + '.wav')
            write_wav(target, pcm, config['sampleRate'])
            save_json(cache / (identity + '.json'), {'completion_code': 20000000,
                'source_text': text, 'voice_hash': voice_hash(config), 'sha256': file_hash(target)})
        return pcm

    def public_entry(relative, pcm, text):
        target = root / relative
        write_wav(target, pcm, config['sampleRate'])
        return {'file': relative, 'sha256': file_hash(target), 'source_text': text,
                'text_hash': digest_bytes(text.encode()), 'voice_hash': voice_hash(config),
                'sample_count': len(pcm) // 2, 'sample_rate': config['sampleRate'],
                'duration': len(pcm) / 2 / config['sampleRate']}

    try:
        for word in book['vocabulary']:
            text = word['lemma']
            manifest['words'][word['word_id']] = public_entry('audio/words/' + word['word_id'] + '.wav', segment(text), text)
        for chapter in narrated_chapters(book):
            pieces, cues, frame_count = [], [], 0
            for paragraph in chapter['paragraphs']:
                text = paragraph['english']
                pcm = segment(text)
                start = frame_count / config['sampleRate']
                frame_count += len(pcm) // 2
                cues.append({'paragraph_id': paragraph['paragraph_id'], 'source_text': text,
                             'start': start, 'end': frame_count / config['sampleRate']})
                pieces.append(pcm)
            text = '\n'.join(p['english'] for p in chapter['paragraphs'])
            entry = public_entry('audio/chapters/' + chapter['chapter_id'] + '.wav', b''.join(pieces), text)
            entry['cues'] = cues
            manifest['chapters'][chapter['chapter_id']] = entry
        manifest['status'] = 'ready'
        save_json(manifest_path, manifest)
        checked = inspect_audio(book, root, config)
        if checked['status'] != 'ready':
            raise SynthesisError('Generated audio failed final integrity checks')
        return checked
    except Exception:
        manifest['status'] = 'failed'
        save_json(manifest_path, manifest)
        raise
