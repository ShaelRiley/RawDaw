# Desktop startup protection and 0.3.4 layout hotfix

## October 11 Steam Deck layout crash

The Deck's follow-up log confirms commit
`ea62b9ab62640407cd77f82f1a2de2c0c7ccc993`, Python 3.13.5 and Qt 6.8.3.
Audio-player creation and output enumeration completed. The fatal traceback
instead reaches `gui.py:728`, `QMainWindow.tabifyDockWidget`, through saved
interface-scale restoration. The earlier audio-only protection does not address
that separate native dock-layout failure.

The source hotfix removes automatic native dock tabification. At widths below
1280 pixels or 125/150% interface scale, Inspector and Browser use the existing
labeled central tabs. At wider 100% layouts they return to separate side docks.
Panel ownership transfers explicitly between these containers; resize events
cannot reenter a transfer, and responsive changes wait until widget construction
and saved geometry/layout/scale restoration are complete. Focus view and Reset
workspace retain accessible panels without exposing empty docks. Existing
preferences, projects, source packs and renderer version are retained.

Pull and use the normal launcher below; this is a 0.3.4 source hotfix and needs
no replacement renderer or compiler. Startup logs now also record workspace
restoration and `Responsive workspace ready` before the desktop event loop.

Regression coverage restores a genuine legacy tabified layout at 125% scale
while a native fault fixture makes `tabifyDockWidget` raise SIGSEGV. The original
0.3.4 editor reaches that fault; the protected editor opens the full Reach Out
project. This fixture models the reported failing API, not the physical Deck's
underlying Qt defect. Additional real-Qt tests cycle 100/125/150% scale and window
widths, check single panel ownership, access to transport and panels, Focus view,
Reset workspace, and unchanged musical state. All 81 tests pass. Evidence is in
`validation/desktop-layout-hotfix-0.3.4.log` and
`validation/desktop-layout-hotfix-0.3.4.json`. Physical Deck relaunch and listening
remain unverified until the creator reports them.

## Preserved audio-only startup protection

Shael's Steam Deck returned exit 139 immediately after Qt's FFmpeg 7.1 startup
message, with no editor window. That confirms a native startup crash; the single
message does not identify the failing driver or establish its exact cause.

An instrumented Qt 6.8.3 startup shows that constructing `QMediaPlayer` probes
video hardware before creating the audio output. PRDE1 previews prepared PCM WAV
audio, so it has no use for these video acceleration contexts. Both FFmpeg video
hardware lists are now disabled before native Qt initialization:

```
QT_FFMPEG_DECODING_HW_DEVICE_TYPES=,
QT_FFMPEG_ENCODING_HW_DEVICE_TYPES=,
```

The comma is Qt's documented empty list; an empty environment value would leave
automatic hardware selection enabled. These are private Qt settings, verified
against the pinned PySide6/Qt 6.8.3 dependency. Recheck them before a Qt upgrade.
See Qt's [Advanced FFmpeg Configuration](https://doc.qt.io/qt-6.8/advanced-ffmpeg-configuration.html).
The PCM media player, audio output selection, pause and seek remain active.
No display-platform or audio-server choice is overridden. Source packs, the
prepared renderer and musical/export behavior are unchanged.

## Pull and launch on Steam Deck

In Desktop Mode, open Konsole and run:

```sh
cd "$HOME/prde1" && git pull --ff-only origin main && ./run-prde1.sh --project packs/reach_out_full.prdeproj
```

The launcher, installed `prde1-desktop` entry point and direct
`python -m prde1.gui` all disable video hardware probes. The normal launcher also
enables a native fault traceback before importing Qt. It prints the startup-log
path and stages. Logs remain on the user's computer, with no automatic upload.
With default Linux paths, the current log is
`~/.local/state/prde1/startup.log`; the preceding run is retained as
`startup.previous.log`. An absolute `XDG_STATE_HOME` selects the corresponding
state directory instead. A Python exception or fatal native fault records its
traceback in that log. An unwritable state directory falls back to terminal
fault diagnostics.

If startup still crashes, obtain the printed log with:

```sh
cat "${XDG_STATE_HOME:-$HOME/.local/state}/prde1/startup.log"
```

## Verification and limits

The regression test injects a native library whose FFmpeg video-context creation
raises SIGSEGV. Unprotected real Qt initialization fails with that signal after
the same FFmpeg startup line. The protected actual Qt editor opens the complete
Reach Out project, displays its window offscreen, and retains 1x playback. A
separate real native-fault test verifies that the stage and traceback survive in
the local log. Existing Qt checks still exercise actual 48 kHz PCM decoding,
pause/seek and all twelve byte-identical GUI WAV exports.

This verifies prevention of the video-driver crash path, not a reproduction on
Shael's physical Deck. Its exact original failing component and successful
on-device launch remain to be confirmed. The earlier source/launcher update was
on `main` with application version 0.3.3. The previously hashed 0.3.3 distribution
archive is unchanged and does not contain this hotfix; pulling the repository
obtains it while reusing the verified renderer and installed packs.
