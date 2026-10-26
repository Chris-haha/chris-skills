"""Create/check a user-local runtime; importing this file has no side effects."""
from __future__ import annotations
import argparse
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import venv

SKILL_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = {
    'whisper_mode': 'local', 'whisper_model': 'base', 'language': 'zh',
    'extract_frames': False, 'frames_per_video': 6, 'cache_ttl_days': 7,
    'ffmpeg': '', 'ffprobe': '', 'cookies_file': '',
}


def runtime_root() -> Path:
    return Path(os.environ.get('MEDIA_URLS_RUNTIME', str(Path.home() / '.cache' / 'media-urls-batch-archive'))).expanduser().absolute()


def runtime_python() -> Path:
    return runtime_root() / 'venv' / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')


def config_path() -> Path:
    return Path(os.environ.get('MEDIA_URLS_CONFIG', str(runtime_root() / 'config.json'))).expanduser().absolute()


def load_config(path: Path | None = None) -> dict:
    location = path or config_path()
    config = dict(DEFAULT_CONFIG)
    if location.is_file():
        data = json.loads(location.read_text(encoding='utf-8-sig'))
        if not isinstance(data, dict):
            raise ValueError('配置文件必须是 JSON 对象')
        config.update(data)
    elif path is not None or 'MEDIA_URLS_CONFIG' in os.environ:
        raise ValueError(f'找不到配置文件: {location}')
    if config['whisper_mode'] not in ('local', 'disabled'):
        raise ValueError('whisper_mode 只支持 local 或 disabled')
    # Explicit relative file paths are relative to their config, not the caller cwd.
    for key in ('ffmpeg', 'ffprobe', 'cookies_file'):
        value = str(config.get(key) or '')
        if value:
            config[key] = str((location.parent / Path(value).expanduser()).absolute())
    model = str(config.get('whisper_model') or 'base')
    if model.startswith(('.', '~', '/')) or '/' in model or '\\' in model:
        config['whisper_model'] = str((location.parent / Path(model).expanduser()).absolute())
    config['model_download_root'] = str(runtime_root() / 'models')
    return config


def command_exists(config: dict, name: str) -> str | None:
    explicit = config.get(name)
    if explicit:
        return explicit if Path(explicit).is_file() else None
    return shutil.which(name)


def doctor() -> dict:
    try:
        config = load_config()
    except (ValueError, OSError) as exc:
        return {'ready': False, 'error': str(exc), 'next_step': '修复配置后运行 runtime.py setup'}
    checks = {'python_3_11': sys.version_info >= (3, 11)}
    errors = {}
    for name in ('yt_dlp', 'youtube_transcript_api'):
        checks[name] = importlib.util.find_spec(name) is not None
    for name in ('ffmpeg', 'ffprobe'):
        tool = command_exists(config, name)
        try:
            checks[name] = bool(tool) and subprocess.run([tool, '-version'], capture_output=True, timeout=15).returncode == 0
        except (OSError, subprocess.SubprocessError):
            checks[name] = False
    if config['whisper_mode'] == 'local':
        checks['faster_whisper'] = importlib.util.find_spec('faster_whisper') is not None
        if checks['faster_whisper']:
            # Importability alone misses binary/API incompatibilities (e.g. PyAV).
            probe = subprocess.run([sys.executable, '-c',
                'import io,wave;from faster_whisper.audio import decode_audio;'
                'b=io.BytesIO();w=wave.open(b,"wb");w.setnchannels(1);w.setsampwidth(2);'
                'w.setframerate(16000);w.writeframes(bytes(3200));w.close();b.seek(0);'
                'assert len(decode_audio(b))==1600'], capture_output=True, text=True, encoding='utf8', timeout=60)
            checks['audio_decode'] = probe.returncode == 0
            if probe.returncode:
                errors['audio_decode'] = probe.stderr[-1500:]
        else:
            checks['audio_decode'] = False
        model = Path(config['whisper_model'])
        checks['local_model'] = model.is_dir() and (model / 'model.bin').is_file()
    if config.get('cookies_file'):
        checks['cookies_file'] = Path(config['cookies_file']).is_file()
    return {'ready': all(checks.values()), 'checks': checks, 'errors': errors, 'runtime': str(runtime_root()),
            'python': sys.executable, 'config': str(config_path()), 'mode': config['whisper_mode'],
            'next_step': '可以执行 scripts/run.py' if all(checks.values()) else '运行 python scripts/runtime.py setup；只提字幕可加 --subtitles-only'}


def setup(subtitles_only: bool) -> int:
    if sys.version_info < (3, 11):
        raise ValueError('请使用 Python 3.11 或更新版本运行 setup，推荐 Python 3.12')
    root = runtime_root()
    root.mkdir(parents=True, exist_ok=True)
    python = runtime_python()
    if not python.is_file():
        venv.EnvBuilder(with_pip=True).create(root / 'venv')
    subprocess.run([str(python), '-m', 'pip', 'install', '-r', str(SKILL_ROOT / 'requirements.txt')], check=True)
    if not subtitles_only:
        subprocess.run([str(python), '-m', 'pip', 'install', '-r', str(SKILL_ROOT / 'requirements-transcription.txt')], check=True)
    config = load_config()
    config['whisper_mode'] = 'disabled' if subtitles_only else 'local'
    if not all(command_exists(config, name) for name in ('ffmpeg', 'ffprobe')):
        # Fetch native binaries for this OS; never carry another machine's binaries.
        completed = subprocess.run([str(python), '-c',
            'import json;from static_ffmpeg import run;print(json.dumps(list(run.get_or_fetch_platform_executables_else_raise())))'],
            check=True, capture_output=True, text=True, encoding='utf8')
        paths = json.loads(completed.stdout.strip().splitlines()[-1])
        config['ffmpeg'], config['ffprobe'] = paths
    if not subtitles_only:
        model = Path(str(config['whisper_model'])).expanduser()
        if not (model.is_dir() and (model / 'model.bin').is_file()):
            name = str(config['whisper_model'])
            if '/' in name or '\\' in name:
                raise ValueError(f'指定的本地模型不存在或缺少 model.bin: {name}')
            model = root / 'models' / name
            subprocess.run([str(python), '-c',
                'import sys;from faster_whisper.utils import download_model;download_model(sys.argv[1],output_dir=sys.argv[2])',
                name, str(model)], check=True)
        config['whisper_model'] = str(model.absolute())
    location = config_path()
    location.parent.mkdir(parents=True, exist_ok=True)
    location.write_text(json.dumps(config, ensure_ascii=False, indent=2) + '\n', encoding='utf8')
    return subprocess.run([str(python), str(Path(__file__).resolve()), 'doctor']).returncode


def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, 'reconfigure'):
            stream.reconfigure(encoding='utf8')
    parser = argparse.ArgumentParser(description='初始化或检查独立视频归档运行环境')
    parser.add_argument('command', choices=['setup', 'doctor'])
    parser.add_argument('--subtitles-only', action='store_true', help='仅安装字幕能力，跳过语音识别包和模型')
    args = parser.parse_args()
    try:
        if args.command == 'setup':
            return setup(args.subtitles_only)
        python = runtime_python()
        if python.is_file() and os.path.abspath(sys.executable) != str(python):
            return subprocess.run([str(python), str(Path(__file__).resolve()), 'doctor']).returncode
        report = doctor()
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0 if report['ready'] else 1
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        print(f'环境初始化失败: {exc}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
