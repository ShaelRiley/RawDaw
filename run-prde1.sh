#!/bin/sh
set -eu
cd "$(dirname "$0")"

if ! command -v python3 >/dev/null 2>&1; then
    printf '%s\n' 'PRDE1 needs Python 3.11 or newer. Install Python, then run this launcher again.' >&2
    exit 1
fi
python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 11) else "PRDE1 needs Python 3.11 or newer")'

PRDE_PYTHON=python3
if [ -x .venv/bin/python ] && .venv/bin/python -c 'from PySide6.QtWidgets import QApplication; from PySide6.QtMultimedia import QMediaPlayer' >/dev/null 2>&1; then
    PRDE_PYTHON=.venv/bin/python
elif ! python3 -c 'from PySide6.QtWidgets import QApplication; from PySide6.QtMultimedia import QMediaPlayer' >/dev/null 2>&1; then
    printf '%s\n' 'First launch: installing the native desktop libraries in a local virtual environment.'
    python3 -m venv .venv || {
        printf '%s\n' 'Could not create a virtual environment. On Ubuntu/Linux Lite install python3-venv, then retry.' >&2
        exit 1
    }
    .venv/bin/python -m pip install -r requirements-desktop.txt || {
        printf '%s\n' 'Desktop setup did not finish. Check your connection and run this launcher again.' >&2
        exit 1
    }
    PRDE_PYTHON=.venv/bin/python
fi

PRDE_VERSION=$(python3 -c 'from prde1 import __version__; print(__version__)')
if [ -f "dist/PRDE1_${PRDE_VERSION}_Linux_x86_64.parts.json" ] || [ -f BUILD_INFO.json ]; then
    python3 tools/install_renderer.py --ensure || {
        printf '%s\n' 'Compiled renderer installation failed. Check the pulled build parts, or rebuild with make all.' >&2
        exit 1
    }
else
    if ! command -v make >/dev/null 2>&1 || ! command -v g++ >/dev/null 2>&1; then
        printf '%s\n' 'This source checkout needs GNU Make and a C++20 compiler. Install them, or use the compiled distribution.' >&2
        exit 1
    fi
    make all
fi

exec "$PRDE_PYTHON" -m prde1.gui "$@"
