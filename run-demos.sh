#!/bin/sh
set -eu
cd "$(dirname "$0")"
if [ ! -x build/prde1-render ]; then
    make all
fi
python3 tools/render_cc_demos.py
printf '%s\n' 'Auditions are in out/cc-auditions. Ready-rendered copies are in auditions/ in the distribution.'
