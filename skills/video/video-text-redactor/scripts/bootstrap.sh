#!/bin/bash
set -euo pipefail
skill_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
runtime_dir="${VIDEO_REDACTOR_CACHE:-$HOME/.local/share/video-text-redactor}"
if [[ "$(uname -s)" != Darwin ]]; then
  echo 'This OCR backend needs macOS, Apple Vision and the Swift command-line tools.' >&2
  exit 1
fi
if [[ ! -x "$runtime_dir/venv/bin/python" ]]; then
  python_bin="${VIDEO_REDACTOR_PYTHON:-python3}"
  "$python_bin" -m venv "$runtime_dir/venv"
fi
if ! "$runtime_dir/venv/bin/python" -c 'import cv2,numpy,PIL' >/dev/null 2>&1; then
  "$runtime_dir/venv/bin/python" -m pip install -r "$skill_dir/scripts/requirements.txt"
fi
exec "$runtime_dir/venv/bin/python" "$skill_dir/scripts/video_text_redactor.py" "$@"
