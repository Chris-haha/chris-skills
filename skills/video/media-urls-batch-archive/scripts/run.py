"""Portable entry point, usable from any current directory."""
from pathlib import Path
import os
import subprocess
import sys
sys.dont_write_bytecode = True
from runtime import runtime_python

if __name__ == '__main__':
    python = runtime_python()
    interpreter = str(python) if python.is_file() else sys.executable
    env = dict(os.environ, PYTHONUTF8='1', PYTHONDONTWRITEBYTECODE='1')
    raise SystemExit(subprocess.run([interpreter, str(Path(__file__).with_name('batch_archive_media_urls.py')), *sys.argv[1:]], env=env).returncode)
