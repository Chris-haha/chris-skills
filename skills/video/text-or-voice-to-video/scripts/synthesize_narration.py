#!/usr/bin/env python3
"""Synthesize Doubao narration with complete-stream checks and resumable PCM cache."""
import argparse
import base64
import binascii
import hashlib
import http.client
import json
import os
from pathlib import Path
import socket
import sys
import time
import urllib.error
import urllib.request
import uuid
import wave

from prepare_script import save_json, split_chunks

ENDPOINT = 'https://openspeech.bytedance.com/api/v3/tts/unidirectional'
DEFAULT_CONFIG = {'provider': 'doubao', 'resourceId': 'seed-tts-2.0',
                  'speaker': 'zh_female_vv_uranus_bigtts', 'speechRate': 0,
                  'sampleRate': 24000, 'maxChunkChars': 300, 'timeoutSeconds': 60}


class SynthesisError(ValueError):
    def __init__(self, message, retryable=False):
        super().__init__(message)
        self.retryable = retryable


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as source:
        for block in iter(lambda: source.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def load_config(path):
    data = json.loads(Path(path).read_text(encoding='utf-8')) if path else {}
    if not isinstance(data, dict) or set(data) - set(DEFAULT_CONFIG):
        raise ValueError('Unknown narration config field; credentials belong only in DOUBAO_TTS_API_KEY')
    config = {**DEFAULT_CONFIG, **data}
    if config['provider'] != 'doubao' or config['resourceId'] != 'seed-tts-2.0':
        raise ValueError('This version supports doubao seed-tts-2.0 system voices only')
    speaker = config['speaker']
    if not isinstance(speaker, str) or not speaker.strip() or '\n' in speaker:
        raise ValueError('speaker must be a nonempty system voice ID')
    for key, minimum, maximum in [('speechRate', -50, 100), ('maxChunkChars', 1, 300),
                                  ('timeoutSeconds', 1, 120)]:
        value = config[key]
        if isinstance(value, bool) or not isinstance(value, int) or not minimum <= value <= maximum:
            raise ValueError(f'{key} must be an integer from {minimum} to {maximum}')
    if type(config['sampleRate']) is not int or config['sampleRate'] not in (8000, 16000, 22050, 24000, 32000, 44100, 48000):
        raise ValueError('Unsupported sampleRate')
    return config


def read_stream(response):
    """Read NDJSON records, not network chunk boundaries. Never accept EOF as success."""
    audio = bytearray()
    metadata = {'usage': None, 'completionCode': None}
    for line in response:
        if not line.strip():
            continue
        try:
            packet = json.loads(line)
        except (ValueError, UnicodeError):
            raise SynthesisError('Invalid JSON in Doubao response', retryable=True) from None
        if not isinstance(packet, dict) or type(packet.get('code')) is not int:
            raise SynthesisError('Doubao response has no integer business status')
        code = packet['code']
        if code not in (0, 20000000):
            # Examine descriptions for classification, but never persist/echo provider text.
            detail = str(packet.get('message', '')).lower()
            permanent = any(word in detail for word in (
                'auth', 'unauthorized', 'forbidden', 'quota', 'balance', 'credit',
                'speaker', 'resource', 'permission', 'invalid', 'billing',
                '额度', '余额', '音色', '鉴权', '权限', '欠费', '参数'))
            retryable = not permanent and (code >= 50000000 or any(
                word in detail for word in ('limit', 'busy', 'timeout', '限流', '繁忙')))
            raise SynthesisError(f'Doubao business error {code}; check voice, quota and console logs', retryable)
        usage = packet.get('usage')
        if isinstance(usage, dict) and type(usage.get('text_words')) is int and usage['text_words'] >= 0:
            metadata['usage'] = {'text_words': usage['text_words']}
        data = packet.get('data')
        if data is not None:
            if not isinstance(data, str):
                raise SynthesisError('Audio payload must be base64 text')
            try:
                audio.extend(base64.b64decode(data, validate=True))
            except (binascii.Error, ValueError):
                raise SynthesisError('Invalid base64 audio payload', retryable=True) from None
        if code == 20000000:
            if not audio or len(audio) % 2:
                raise SynthesisError('Completed stream contains empty or malformed PCM16 audio')
            metadata['completionCode'] = code
            return bytes(audio), metadata
    raise SynthesisError('Stream ended without synthesis completion marker; partial audio discarded', retryable=True)


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        # Never forward the API key to a redirected host.
        return None


def request_audio(text, config, api_key, transport=None, sleep=time.sleep):
    if not isinstance(api_key, str) or not api_key or any(not 33 <= ord(c) <= 126 for c in api_key):
        raise SynthesisError('DOUBAO_TTS_API_KEY contains invalid header characters; check local configuration')
    transport = transport or urllib.request.build_opener(NoRedirect).open
    payload = {'req_params': {'text': text, 'speaker': config['speaker'],
               'audio_params': {'format': 'pcm', 'sample_rate': config['sampleRate'],
                                'speech_rate': config['speechRate']}}}
    for attempt in range(3):
        request_id = str(uuid.uuid4())
        request = urllib.request.Request(ENDPOINT,
            data=json.dumps(payload, ensure_ascii=False).encode('utf-8'),
            headers={'Content-Type': 'application/json', 'X-Api-Key': api_key,
                     'X-Api-Resource-Id': config['resourceId'], 'X-Api-Request-Id': request_id,
                     'X-Control-Require-Usage-Tokens-Return': '*'}, method='POST')
        try:
            with transport(request, timeout=config['timeoutSeconds']) as response:
                pcm, metadata = read_stream(response)
            return pcm, {**metadata, 'requestId': request_id, 'attempts': attempt + 1}
        except urllib.error.HTTPError as error:
            failure = SynthesisError(f'Doubao HTTP {error.code}; check service credentials and quota',
                                     error.code in (408, 429, 500, 502, 503, 504))
            if error.fp is not None:
                error.close()
        except (urllib.error.URLError, socket.timeout, TimeoutError, ConnectionError,
                http.client.HTTPException):
            failure = SynthesisError('Doubao network/stream failure; partial audio discarded', True)
        except SynthesisError as error:
            failure = error
        except ValueError:
            # http.client may include the entire secret header value in its exception.
            failure = SynthesisError('Invalid Doubao request or header configuration')
        if not failure.retryable or attempt == 2:
            raise failure from None
        sleep(2 ** attempt)
    raise AssertionError('unreachable')


def script_chunks(script, limit):
    if not isinstance(script, dict) or not isinstance(script.get('units'), list) or not script['units']:
        raise ValueError('script.json must contain nonempty narration units')
    paragraphs, current, previous_group, ids = [], '', None, set()
    for unit in script['units']:
        if not isinstance(unit, dict) or not isinstance(unit.get('text'), str) or not unit['text'].strip():
            raise ValueError('Every unit requires nonempty text')
        unit_id = unit.get('id')
        if not isinstance(unit_id, str) or not unit_id or unit_id in ids:
            raise ValueError('Every unit requires a unique stable ID')
        ids.add(unit_id)
        group = unit.get('paragraphId', unit_id)
        if current and group != previous_group:
            paragraphs.append(current)
            current = ''
        current += unit['text']
        previous_group = group
    if current:
        paragraphs.append(current)
    return split_chunks(paragraphs, limit)


def cache_key(text, config):
    parameters = {k: config[k] for k in ('provider', 'resourceId', 'speaker', 'speechRate', 'sampleRate')}
    canonical = json.dumps({'cacheVersion': 1, 'text': text, 'format': 'pcm_s16le',
                            **parameters}, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(canonical.encode()).hexdigest()


def cached_segment(cache, key, config):
    path, metadata_path = cache / f'{key}.wav', cache / f'{key}.json'
    try:
        metadata = json.loads(metadata_path.read_text(encoding='utf-8'))
        if metadata.get('cacheKey') != key or metadata.get('audioSha256') != sha256(path):
            return None
        if metadata.get('completionCode') != 20000000:
            return None
        with wave.open(str(path), 'rb') as source:
            frames = source.getnframes()
            if (source.getnchannels(), source.getsampwidth(), source.getframerate()) != (1, 2, config['sampleRate']):
                return None
            if frames <= 0 or len(source.readframes(frames)) != frames * 2:
                return None
            if type(metadata.get('sampleCount')) is not int or metadata['sampleCount'] != frames:
                return None
            if metadata.get('sampleRate') != source.getframerate():
                return None
        return {**metadata, 'audioPath': str(path.resolve())}
    except (OSError, ValueError, TypeError, AttributeError, wave.Error, EOFError):
        return None


def write_wav(path, raw, rate):
    temporary = path.with_suffix('.wav.tmp')
    try:
        with wave.open(str(temporary), 'wb') as output:
            output.setnchannels(1)
            output.setsampwidth(2)
            output.setframerate(rate)
            output.writeframes(raw)
        with wave.open(str(temporary), 'rb') as source:
            if source.getnframes() <= 0 or len(source.readframes(source.getnframes())) != len(raw):
                raise SynthesisError('Generated WAV failed full PCM decode')
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def synthesize(script_path, config_path, output_dir, api_key=None, transport=None, sleep=time.sleep):
    script_path = Path(script_path).resolve()
    config_path = Path(config_path).resolve() if config_path else None
    output_dir = Path(output_dir).resolve()
    for source in (script_path, config_path):
        if source and (source == output_dir or output_dir in source.parents):
            raise ValueError('Output directory must not contain the script or configuration inputs')
    cache = output_dir / 'cache'
    cache.mkdir(parents=True, exist_ok=True)
    voice_path = output_dir / 'voice.wav'
    manifest_path = output_dir / 'narration.manifest.json'
    progress_path = output_dir / 'progress.json'
    # No previous success artifact may masquerade as the current failed run.
    voice_path.unlink(missing_ok=True)
    manifest_path.unlink(missing_ok=True)
    report = {'schemaVersion': 1, 'provider': 'doubao', 'aiGenerated': True,
              'status': 'running', 'segments': [],
              'cachedSegments': 0, 'newlyBilledTextWords': 0,
              'usageComplete': True, 'failedRequestsMayHaveUsage': False}
    save_json(progress_path, report)
    key_value = api_key if api_key is not None else os.environ.get('DOUBAO_TTS_API_KEY', '')
    try:
        config = load_config(config_path)
        script = json.loads(script_path.read_text(encoding='utf-8'))
        chunks = script_chunks(script, config['maxChunkChars'])
        report.update({'scriptSha256': sha256(script_path), 'config': config,
                       'requestedCharacters': sum(map(len, chunks))})
        save_json(progress_path, report)
        print(f"Narration: {report['requestedCharacters']} characters, {len(chunks)} segments; cache hits do not call the API", flush=True)
        for index, text in enumerate(chunks):
            key = cache_key(text, config)
            entry = cached_segment(cache, key, config)
            reused = entry is not None
            if reused:
                report['cachedSegments'] += 1
            else:
                if not key_value.strip():
                    raise SynthesisError('DOUBAO_TTS_API_KEY is required for uncached narration; configure it locally')
                pcm, metadata = request_audio(text, config, key_value, transport, sleep)
                target = cache / f'{key}.wav'
                write_wav(target, pcm, config['sampleRate'])
                entry = {**metadata, 'cacheKey': key, 'audioPath': str(target.resolve()),
                         'audioSha256': sha256(target), 'characterCount': len(text),
                         'sampleCount': len(pcm) // 2, 'sampleRate': config['sampleRate']}
                save_json(cache / f'{key}.json', entry)
                if metadata['usage'] is None:
                    report['usageComplete'] = False
                else:
                    report['newlyBilledTextWords'] += metadata['usage']['text_words']
                if metadata['attempts'] > 1:
                    report['failedRequestsMayHaveUsage'] = True
            report['segments'].append({**entry, 'index': index, 'cached': reused})
            save_json(progress_path, report)
        temporary = voice_path.with_suffix('.wav.tmp')
        with wave.open(str(temporary), 'wb') as output:
            output.setnchannels(1)
            output.setsampwidth(2)
            output.setframerate(config['sampleRate'])
            for entry in report['segments']:
                with wave.open(entry['audioPath'], 'rb') as source:
                    output.writeframes(source.readframes(source.getnframes()))
        if sha256(script_path) != report['scriptSha256'] or load_config(config_path) != config:
            raise SynthesisError('Script or configuration changed during synthesis; rerun before alignment')
        temporary.replace(voice_path)
        report.update({'status': 'complete', 'audioPath': str(voice_path),
                       'audioSha256': sha256(voice_path),
                       'sampleCount': sum(e['sampleCount'] for e in report['segments']),
                       'sampleRate': config['sampleRate'],
                       'durationMs': sum(e['sampleCount'] for e in report['segments']) * 1000 / config['sampleRate']})
        save_json(manifest_path, report)
        save_json(progress_path, report)
        return report
    except (ValueError, OSError, wave.Error) as error:
        voice_path.unlink(missing_ok=True)
        manifest_path.unlink(missing_ok=True)
        voice_path.with_suffix('.wav.tmp').unlink(missing_ok=True)
        report.update({'status': 'failed', 'error': str(error), 'failedRequestsMayHaveUsage': True})
        save_json(progress_path, report)
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--script', required=True)
    parser.add_argument('--config', help='narration.json; defaults used when omitted')
    parser.add_argument('--output-dir', required=True)
    parser.add_argument('--dry-run', action='store_true', help='Show characters and cache hits without credentials, writes or API calls')
    args = parser.parse_args()
    try:
        if args.dry_run:
            config = load_config(args.config)
            chunks = script_chunks(json.loads(Path(args.script).read_text(encoding='utf-8')), config['maxChunkChars'])
            hits = sum(cached_segment(Path(args.output_dir) / 'cache', cache_key(t, config), config) is not None for t in chunks)
            print(json.dumps({'characters': sum(map(len, chunks)), 'segments': len(chunks),
                              'cachedSegments': hits, 'apiRequests': len(chunks)-hits,
                              'apiKeyConfigured': bool(os.environ.get('DOUBAO_TTS_API_KEY'))}, ensure_ascii=False))
        else:
            report = synthesize(args.script, args.config, args.output_dir)
            print(f"Narration complete: {report['durationMs']:.1f} ms; newly reported billable characters: {report['newlyBilledTextWords']}")
    except (ValueError, OSError, wave.Error) as error:
        print(str(error), file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
