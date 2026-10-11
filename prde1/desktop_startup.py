"""Audio-only Qt startup and local diagnostics, before native Qt initialization."""
from __future__ import annotations

import faulthandler
import os
import platform
import sys
import traceback
from pathlib import Path

_log = None


def configure_audio():
    # QMediaPlayer probes video hardware even when we only play PCM WAV files.
    # Qt requires a comma (an empty list), rather than an empty environment value.
    # Neither the prepared renderer nor PCM decoding needs a GPU video driver.
    os.environ['QT_FFMPEG_DECODING_HW_DEVICE_TYPES'] = ','
    os.environ['QT_FFMPEG_ENCODING_HW_DEVICE_TYPES'] = ','


def startup_stage(message):
    if _log is not None:
        print('PRDE1: ' + message, file=_log, flush=True)
        print('PRDE1: ' + message, file=sys.stderr, flush=True)


def begin_startup_log():
    """Retain the startup stage and a native fault traceback; never upload it."""
    global _log
    if _log is not None:
        return
    state = Path(os.environ.get('XDG_STATE_HOME', ''))
    if not state.is_absolute():
        state = Path.home() / '.local/state'
    path = state / 'prde1/startup.log'
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists():
            path.replace(path.with_name('startup.previous.log'))
        _log = path.open('w', encoding='utf-8', buffering=1)
    except OSError as error:
        print('PRDE1: Startup log unavailable: ' + str(error), file=sys.stderr, flush=True)
        faulthandler.enable(all_threads=True)
        return
    faulthandler.enable(file=_log, all_threads=True)

    def report_exception(kind, value, trace):
        traceback.print_exception(kind, value, trace, file=_log)
        _log.flush()
        sys.__excepthook__(kind, value, trace)

    sys.excepthook = report_exception
    print('PRDE1: Startup diagnostics: ' + str(path), file=sys.stderr, flush=True)
    startup_stage('Python ' + platform.python_version() + ' on ' + platform.system())


def main(argv=None):
    configure_audio()
    begin_startup_log()
    startup_stage('Loading Qt; GPU video probes disabled for PCM audio')
    from .gui import main as desktop_main
    return desktop_main(argv)


if __name__ == '__main__':
    # Share the same log with gui.py when run as a module (not a second __main__).
    from .desktop_startup import main as entry_point
    raise SystemExit(entry_point())
