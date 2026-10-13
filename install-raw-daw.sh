#!/bin/sh
# Optional per-user desktop launcher; no root privileges or system modifications.
set -eu
RAW_DAW_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
python3 - "$RAW_DAW_DIR" <<'PY'
import os,sys
from pathlib import Path
root=Path(sys.argv[1]).resolve()
if any(c in str(root) for c in '\r\n'):raise SystemExit('Move this checkout to a path without line breaks.')
target=Path(os.environ.get('XDG_DATA_HOME',str(Path.home()/'.local/share')))/'applications/raw-daw.desktop'
target.parent.mkdir(parents=True,exist_ok=True)
script=str(root/'run-raw-daw.sh').replace('\\','\\\\').replace('"','\\"').replace('`','\\`').replace('$','\\$')
icon=str(root/'prde1/data/raw-daw.svg').replace('\\','\\\\')
target.write_text('[Desktop Entry]\nType=Application\nName=Raw Daw\nGenericName=Music Composition\nComment=Build songs with harmony-following MIDI clips\nExec="'+script+'"\nIcon='+icon+'\nTerminal=false\nCategories=AudioVideo;Audio;Midi;\nStartupNotify=true\n')
print('Installed Raw Daw in your application menu.')
PY
