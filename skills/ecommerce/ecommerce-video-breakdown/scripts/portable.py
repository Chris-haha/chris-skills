"""Local runtime discovery and first-use preparation; no repository or account state."""
import contextlib
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys

WINDOWS = os.name == 'nt'
TOOL_ENV = {
    'python': ('ECOM_VIDEO_PYTHON',),
    'ffmpeg': ('ECOM_VIDEO_FFMPEG',),
    'ffprobe': ('ECOM_VIDEO_FFPROBE',),
    'whisperCli': ('ECOM_VIDEO_WHISPER_CLI', 'VIDEO_WHISPER_CLI'),
    'whisperModel': ('ECOM_VIDEO_WHISPER_MODEL', 'VIDEO_WHISPER_MODEL'),
    'fasterWhisperModel': ('ECOM_VIDEO_FASTER_WHISPER_MODEL',),
    'node': ('ECOM_VIDEO_NODE', 'CODEX_SPREADSHEET_NODE'),
    'nodeModules': ('ECOM_VIDEO_NODE_MODULES', 'CODEX_NODE_MODULES'),
}
SETTINGS = set(TOOL_ENV) | {'language', 'packagePaths', 'transcriptionBackend', 'ffprobeLibraryPath'}


def _config_file(workspace=None, config_path=None):
    explicit = config_path or os.environ.get('ECOM_VIDEO_CONFIG')
    if explicit:
        return Path(explicit).expanduser().resolve(), True
    return (Path(workspace).resolve() / 'runtime.local.json' if workspace else None), False


def _load_settings(path, explicit=False):
    if path is None or not path.exists():
        if explicit:
            raise ValueError('运行配置不存在：' + str(path))
        return {}
    try:
        value = json.loads(path.read_text(encoding='utf-8-sig'))
    except (ValueError, OSError) as exc:
        raise ValueError('运行配置不是有效JSON：' + str(path)) from exc
    if not isinstance(value, dict):
        raise ValueError('运行配置必须是JSON对象')
    # Do not copy unknown settings or account material into setup receipts.
    return {key: value[key] for key in SETTINGS if key in value}


def _path_value(value, base, executable=False):
    if not isinstance(value, str) or not value.strip():
        return ''
    value = value.strip()
    if executable and not any(separator in value for separator in ('/', '\\')):
        found = shutil.which(value)
        if found:
            return str(Path(found).absolute())
    path = Path(value).expanduser()
    if not path.is_absolute():
        path = base / path
    # A venv's python is often a symlink. Resolving it would silently run the
    # base interpreter without the privately installed packages.
    path = Path(os.path.abspath(path))
    if executable:
        return str(path) if path.is_file() and (WINDOWS or os.access(path, os.X_OK)) else ''
    return str(path) if path.exists() else ''


def _venv_python(workspace):
    folder = Path(workspace) / 'runtime/.venv'
    return folder / ('Scripts/python.exe' if WINDOWS else 'bin/python')


def _faster_model_present(folder):
    folder = Path(folder)
    try:
        return ((folder / 'model.bin').is_file() and (folder / 'model.bin').stat().st_size > 0 and
                isinstance(json.loads((folder / 'config.json').read_text(encoding='utf-8')), dict))
    except (OSError, ValueError):
        return False


def resolve_runtime(workspace=None, config_path=None):
    """Read explicit local settings, environment and PATH; never download or read media projects."""
    path, explicit = _config_file(workspace, config_path)
    settings = _load_settings(path, explicit)
    base = path.parent if path else Path.cwd()
    runtime = {key: '' for key in TOOL_ENV}
    runtime.update(config_path=str(path) if path else '', invalid={}, packagePaths=[],
                   language=str(settings.get('language') or 'zh'))
    bundle = Path.home() / '.cache/codex-runtimes/codex-primary-runtime/dependencies'
    suffix = '.exe' if WINDOWS else ''
    candidates = {
        'python': ([str(_venv_python(workspace))] if workspace else []) + [sys.executable],
        'ffmpeg': [shutil.which('ffmpeg') or '', str(bundle / ('bin/override/ffmpeg' + suffix)),
                   str(bundle / ('bin/fallback/ffmpeg' + suffix))],
        'ffprobe': [shutil.which('ffprobe') or '', str(bundle / ('bin/override/ffprobe' + suffix)),
                    str(bundle / ('bin/fallback/ffprobe' + suffix))],
        'whisperCli': [shutil.which('whisper-cli') or ''],
        'node': [shutil.which('node') or '', str(bundle / 'node/bin/node'), str(bundle / 'node/node.exe'),
                 str(bundle / 'node/bin/node.exe')],
        'nodeModules': [str(bundle / 'node/node_modules')],
    }
    for key, names in TOOL_ENV.items():
        selected = next((os.environ[name] for name in names if os.environ.get(name)), None)
        selected_base = Path.cwd() if selected is not None else base
        if selected is None:
            selected = settings.get(key)
        executable = key in ('python', 'ffmpeg', 'ffprobe', 'whisperCli', 'node')
        if selected:
            runtime[key] = _path_value(selected, selected_base, executable)
            if not runtime[key]:
                runtime['invalid'][key] = '配置的路径不存在或不可执行'
            continue
        for candidate in candidates.get(key, []):
            resolved = _path_value(candidate, Path.cwd(), executable)
            if resolved:
                runtime[key] = resolved
                break
    if not runtime['nodeModules'] and runtime['node']:
        node = Path(runtime['node'])
        for candidate in (node.parent / 'node_modules', node.parent.parent / 'node_modules'):
            if candidate.is_dir():
                runtime['nodeModules'] = str(candidate)
                break
    for value in settings.get('packagePaths', []) if isinstance(settings.get('packagePaths', []), list) else []:
        found = _path_value(value, base)
        if found and Path(found).is_dir():
            runtime['packagePaths'].append(found)
    if settings.get('ffprobeLibraryPath'):
        runtime['ffprobeLibraryPath'] = _path_value(settings['ffprobeLibraryPath'], base)
    model = runtime['fasterWhisperModel'] or runtime['whisperModel']
    if model and Path(model).is_dir() and _faster_model_present(model):
        runtime['fasterWhisperModel'] = model
        runtime['whisperModel'] = model
        runtime['transcriptionBackend'] = 'faster-whisper'
    elif model and Path(model).is_file() and Path(model).stat().st_size > 0 and runtime['whisperCli']:
        runtime['whisperModel'] = model
        runtime['transcriptionBackend'] = 'whisper.cpp'
    else:
        if model:
            runtime['invalid']['whisperModel'] = '需要有效的whisper.cpp模型文件，或含model.bin和config.json的faster-whisper目录'
        runtime['whisperModel'] = ''
        runtime['fasterWhisperModel'] = ''
        runtime['transcriptionBackend'] = 'none'
    return runtime


@contextlib.contextmanager
def file_lock(path, message='该文件已有任务运行，请等待完成后重试'):
    """One-byte Windows lock or POSIX flock, without importing Unix modules on Windows."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('a+b') as handle:
        handle.seek(0, os.SEEK_END)
        if handle.tell() == 0:
            handle.write(b'\0')
            handle.flush()
        handle.seek(0)
        locked = False
        try:
            if WINDOWS:
                import msvcrt
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
            locked = True
        except OSError as exc:
            raise ValueError(message) from exc
        try:
            yield
        finally:
            if locked:
                handle.seek(0)
                if WINDOWS:
                    import msvcrt
                    msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(handle, fcntl.LOCK_UN)


def _stop_process_tree(process):
    if WINDOWS:
        # Windows has no killpg; taskkill /T stops descendants too.
        executable = shutil.which('taskkill')
        if not executable and os.environ.get('SystemRoot'):
            executable = str(Path(os.environ['SystemRoot']) / 'System32/taskkill.exe')
        if process.poll() is None:
            try:
                subprocess.run([executable or 'taskkill', '/PID', str(process.pid), '/T', '/F'],
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=10, check=False)
            except (OSError, subprocess.SubprocessError):
                process.kill()
    else:
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            return
        try:
            process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            pass
        # A descendant can ignore SIGTERM even if its parent has exited.
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)


def run_process(command, cwd, env, log_path, timeout=2100):
    """Run argument arrays with UTF-8 output and bounded process-tree cleanup."""
    if isinstance(command, (str, bytes)):
        raise ValueError('子进程命令必须是参数数组')
    log_path = Path(log_path); log_path.parent.mkdir(parents=True, exist_ok=True)
    child_env = {**dict(env), 'PYTHONIOENCODING': 'utf-8', 'PYTHONUTF8': '1', 'PYTHONDONTWRITEBYTECODE': '1'}
    options = {'creationflags': subprocess.CREATE_NEW_PROCESS_GROUP} if WINDOWS else {'start_new_session': True}
    with log_path.open('a', encoding='utf-8') as log:
        process = subprocess.Popen([str(arg) for arg in command], cwd=str(cwd), env=child_env, stdout=subprocess.PIPE,
                                   stderr=log, text=True, encoding='utf-8', errors='replace', **options)
        try:
            output, _ = process.communicate(timeout=timeout)
        except (subprocess.TimeoutExpired, KeyboardInterrupt) as exc:
            _stop_process_tree(process)
            try:
                process.communicate(timeout=5)
            except subprocess.TimeoutExpired:
                if process.stdout:
                    process.stdout.close()
            raise RuntimeError('解析已取消或超时，子进程已停止') from exc
        if process.returncode:
            raise RuntimeError('子进程未成功，详情见：' + str(log_path))
        return output


def _module_available(python, module):
    try:
        result = subprocess.run([python, '-c', 'import importlib.util,sys; sys.exit(0 if importlib.util.find_spec(sys.argv[1]) else 1)', module],
                                capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=15)
        return result.returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def _executable_works(executable, runtime=None):
    if not executable:
        return False
    try:
        env = os.environ.copy()
        if sys.platform == 'darwin' and (runtime or {}).get('ffprobeLibraryPath'):
            env['DYLD_LIBRARY_PATH'] = runtime['ffprobeLibraryPath']
        result = subprocess.run([executable, '-version'], capture_output=True, text=True, env=env,
                                encoding='utf-8', errors='replace', timeout=15)
        return result.returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def _faster_whisper_works(python):
    try:
        result = subprocess.run([python, '-c', 'from faster_whisper import WhisperModel'],
                                capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=30)
        return result.returncode == 0, (result.stderr or result.stdout)[-1500:]
    except (OSError, subprocess.SubprocessError) as exc:
        return False, str(exc)


def _save_config(path, settings):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + '.tmp')
    temporary.write_text(json.dumps(settings, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    os.replace(temporary, path)


def setup_runtime(workspace, with_transcription=False, config_path=None):
    """Prepare workspace-private tools. Downloads only occur in this explicit setup action."""
    workspace = Path(workspace).resolve(); workspace.mkdir(parents=True, exist_ok=True)
    config, explicit = _config_file(workspace, config_path)
    settings = _load_settings(config, explicit)
    runtime = resolve_runtime(workspace, config_path)
    for key in TOOL_ENV:
        if runtime.get(key):
            settings[key] = runtime[key]
    log = workspace / 'logs/runtime-setup.log'
    log.parent.mkdir(parents=True, exist_ok=True)
    with log.open('a', encoding='utf-8') as handle:
        handle.write('\n检查本机运行环境\n')
    steps = []
    config = config or workspace / 'runtime.local.json'
    pip_modules = not _module_available(runtime['python'], 'yt_dlp')
    media_missing = not runtime['ffmpeg'] or not runtime['ffprobe']
    model_missing = with_transcription and runtime.get('transcriptionBackend', 'none') == 'none'
    transcribe_missing = with_transcription and (model_missing or (
        runtime.get('transcriptionBackend') == 'faster-whisper' and not _module_available(runtime['python'], 'faster_whisper')))

    def step(label, command, timeout=1200):
        steps.append(label)
        log.parent.mkdir(parents=True, exist_ok=True)
        with log.open('a', encoding='utf-8') as handle:
            handle.write('\n' + label + '\n')
        output = run_process(command, workspace, os.environ.copy(), log, timeout)
        if output:
            with log.open('a', encoding='utf-8') as handle:
                handle.write(output + '\n')
        return output

    try:
        with file_lock(workspace / '.runtime-setup.lock', '运行环境正在准备，请等待完成后重试'):
            if pip_modules or media_missing or transcribe_missing:
                private = _venv_python(workspace)
                if not private.is_file():
                    step('创建工作区私有Python环境', [runtime['python'], '-m', 'venv', str(private.parent.parent)], 300)
                settings['python'] = str(private)
                python = str(private)
                packages = []
                if not _module_available(python, 'yt_dlp'):
                    packages.append('yt-dlp>=2025.1.26')
                if media_missing and not _module_available(python, 'static_ffmpeg'):
                    packages.append('static-ffmpeg>=3.0,<4')
                if transcribe_missing and not _module_available(python, 'faster_whisper'):
                    packages.append('faster-whisper>=1.1,<2')
                if packages:
                    step('安装私有运行依赖', [python, '-m', 'pip', '--isolated', 'install', '--disable-pip-version-check',
                                              '--no-input', '--cache-dir', str(workspace / 'runtime/pip-cache'),
                                              '--index-url', 'https://pypi.org/simple', *packages])
                _save_config(config, settings)
                if media_missing:
                    output = step('准备本机FFmpeg与FFprobe', [python, '-c',
                        'import json; from static_ffmpeg import run; print(json.dumps(list(run.get_or_fetch_platform_executables_else_raise())))'])
                    try:
                        paths = json.loads(output.strip().splitlines()[-1])
                        ffmpeg, ffprobe = (str(Path(value).resolve()) for value in paths)
                    except (ValueError, TypeError, IndexError) as exc:
                        raise RuntimeError('FFmpeg准备结果无法识别，详情见日志') from exc
                    if not Path(ffmpeg).is_file() or not Path(ffprobe).is_file():
                        raise RuntimeError('FFmpeg或FFprobe准备后仍不存在')
                    settings.update(ffmpeg=ffmpeg, ffprobe=ffprobe)
                    _save_config(config, settings)
                if model_missing:
                    model = workspace / 'runtime/models/faster-whisper-base'
                    # Explicit token=False and private HF cache avoid loading an account token.
                    output = step('下载公开的本地base转录模型', [python, '-c',
                        'import os,sys; os.environ["HF_HUB_DISABLE_IMPLICIT_TOKEN"]="1"; os.environ["HF_HOME"]=sys.argv[2]; '
                        'from huggingface_hub import snapshot_download; '
                        'snapshot_download(repo_id="Systran/faster-whisper-base",local_dir=sys.argv[1],token=False)',
                        str(model), str(workspace / 'runtime/huggingface')], 1800)
                    if not _faster_model_present(model):
                        raise RuntimeError('模型下载未完成，未标记转录环境可用')
                    settings.update(whisperModel=str(model), fasterWhisperModel=str(model), transcriptionBackend='faster-whisper')
            else:
                # Existing explicitly configured installations are reused without mutation.
                for key in TOOL_ENV:
                    if runtime.get(key):
                        settings[key] = runtime[key]
            _save_config(config, settings)
            runtime = resolve_runtime(workspace, config)
            checks = {'python': bool(runtime['python']), 'yt_dlp': _module_available(runtime['python'], 'yt_dlp'),
                      'ffmpeg': _executable_works(runtime['ffmpeg'], runtime), 'ffprobe': _executable_works(runtime['ffprobe'], runtime)}
            transcription_error = ''
            if with_transcription:
                if runtime['transcriptionBackend'] == 'faster-whisper':
                    checks['local_transcription'], transcription_error = _faster_whisper_works(runtime['python'])
                else:
                    checks['local_transcription'] = runtime['transcriptionBackend'] == 'whisper.cpp'
                    if not checks['local_transcription']:
                        transcription_error = '尚未取得可用的本地转录模型'
                if transcription_error and not checks['local_transcription']:
                    with log.open('a', encoding='utf-8') as handle:
                        handle.write('\n本地转录依赖检查失败\n' + transcription_error + '\n')
            return {'ok': all(checks.values()), 'runtime': runtime, 'config': str(config), 'steps': steps, 'checks': checks, 'log': str(log),
                    'transcription_error': transcription_error if not checks.get('local_transcription', True) else '',
                    'transcription_requested': bool(with_transcription), 'system_installation_changed': False}
    except (OSError, ValueError, RuntimeError) as exc:
        # Preserve successful steps in the private configuration; report incomplete state.
        return {'ok': False, 'error': str(exc), 'runtime': resolve_runtime(workspace, config) if config.exists() else runtime,
                'config': str(config), 'steps': steps, 'log': str(log), 'system_installation_changed': False}


setup = setup_runtime
