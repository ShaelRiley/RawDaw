#!/bin/sh
set -eu
RAW_DAW_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
exec "$RAW_DAW_DIR/run-prde1.sh" "$@"
