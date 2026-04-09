#!/usr/bin/env sh
# Linux: dev deps + optional packaging/build_distribution.py
set -eu

ROOT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
cd "$ROOT_DIR"

USE_SYSTEM_PYTHON=0
DO_BUILD=0
while [ $# -gt 0 ]; do
  case "$1" in
    --system-python) USE_SYSTEM_PYTHON=1; shift ;;
    build) DO_BUILD=1; shift; break ;;
    *)
      echo "Unknown argument: $1" >&2
      echo "Usage: $0 [--system-python] [build [args for build_distribution.py...]]" >&2
      exit 1
      ;;
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
  echo "Installing build dependencies to user site-packages (--system-python)"
  "$PY" -m pip install --user -U pip
  "$PY" -m pip install --user -r requirements-dev.txt
  "$PY" -m pip install --user -e .
  RUN_PY="$PY"
else
  if [ ! -d .venv ]; then
    "$PY" -m venv .venv
  fi
  # shellcheck disable=SC1091
  . .venv/bin/activate
  python -m pip install -U pip
  python -m pip install -r requirements-dev.txt
  python -m pip install -e .
  RUN_PY=python
fi

if [ "$DO_BUILD" = "1" ]; then
  echo "Running packaging/build_distribution.py $*"
  exec "$RUN_PY" packaging/build_distribution.py "$@"
fi

echo "Build environment ready."
echo "Full distribution (exe + dist/readme.txt + zip):"
echo "  ./bootstrap-dist.sh build"
