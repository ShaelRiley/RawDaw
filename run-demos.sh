#!/bin/sh
set -eu
cd "$(dirname "$0")"
PRDE_VERSION=$(python3 -c 'from prde1 import __version__; print(__version__)')
if [ -f "dist/PRDE1_${PRDE_VERSION}_Linux_x86_64.parts.json" ] || [ -f BUILD_INFO.json ]; then
    python3 tools/install_renderer.py --ensure
else
    make all
fi
python3 tools/render_cc_demos.py
printf '%s\n' 'Auditions are in out/source-auditions. Ready-rendered copies are in auditions/ in the distribution.'
