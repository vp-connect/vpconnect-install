#!/usr/bin/env sh
# Linux: venv + requirements.txt + editable install. Repo root = два уровня выше этого файла.
set -eu

ROOT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
cd "$ROOT_DIR"

USE_SYSTEM_PYTHON=${USE_SYSTEM_PYTHON:-0}
for arg in "$@"; do
  case "$arg" in
    --system-python) USE_SYSTEM_PYTHON=1 ;;
  esac
done

if command -v python3 >/dev/null 2>&1; then
  PY=python3
elif command -v python >/dev/null 2>&1; then
  PY=python
else
  echo "python3 or python not found" >&2
  exit 1
fi

"$PY" - <<'PY' || exit 1
import sys
if sys.version_info < (3, 10):
    sys.stderr.write("Python 3.10+ required\n")
    sys.exit(1)
PY

if [ "$USE_SYSTEM_PYTHON" = "1" ]; then
  echo "Installing with user site-packages (--system-python)"
  "$PY" -m pip install --user -U pip
  "$PY" -m pip install --user -r requirements.txt
  echo "Run from project root with PYTHONPATH=src, e.g.:"
  echo "  PYTHONPATH=src $PY -m vpconnect_install --help"
  echo "  PYTHONPATH=src $PY -m vpconnect_install gui"
else
  if [ ! -d .venv ]; then
    "$PY" -m venv .venv
  fi
  # shellcheck disable=SC1091
  . .venv/bin/activate
  python -m pip install -U pip
  python -m pip install -r requirements.txt
  python -m pip install -e .
  echo "Activate and run:"
  echo "  . .venv/bin/activate"
  echo "  python -m vpconnect_install --help"
  echo "  python -m vpconnect_install gui"
fi
