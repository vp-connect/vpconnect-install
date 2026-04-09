#!/usr/bin/env sh
# Dispatch to OS-specific bootstrap-dist under scripts/.
set -eu

ROOT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
UNAME=$(uname -s 2>/dev/null || echo unknown)

case "$UNAME" in
  Linux)
    exec sh "$ROOT_DIR/scripts/linux/bootstrap-dist.sh" "$@"
    ;;
  Darwin)
    exec sh "$ROOT_DIR/scripts/macos/bootstrap-dist.sh" "$@"
    ;;
  MINGW*|MSYS_NT*|CYGWIN*)
    BAT="$ROOT_DIR/scripts/windows/cmd/bootstrap-dist.bat"
    if command -v cygpath >/dev/null 2>&1; then
      BAT_W=$(cygpath -w "$BAT")
    else
      BAT_W=$BAT
    fi
    exec cmd.exe //c "$BAT_W" "$@"
    ;;
  *)
    echo "Unsupported OS: $UNAME (use scripts/linux|macos|windows/... manually)" >&2
    exit 1
    ;;
esac
