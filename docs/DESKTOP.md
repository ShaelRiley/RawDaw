# Desktop composition — 0.3.3

Run `./run-prde1.sh` in the checkout or extracted distribution. Parachute opens
as an editable starter. Click Play; preparation runs in a separate native process,
then the rendered mix plays through the selected audio output. Pause, Resume,
Stop, and the playback-position slider use that same realization. The blue line
is the edit cursor; the green line is playback. Selecting a clip does not change
the musical random state. Music edits stop an obsolete preview.

Version 0.3.3 adds the **Full-length demos** selector in Browser → Packs.
Choose Reach Out, Where You Are Now, Auld Lang Syne (Bossa), or Parachute and
click **Load full demo**. Each opens a complete editable song with the same
save/undo/mixer and export controls. The eight short arrangements remain in the
list below. Use `./run-prde1.sh --project packs/reach_out_full.prdeproj` to
open one directly. [Section timings and scores](FULL_DEMOS.md) describe the forms.

Version 0.3.2 adds smooth sample start/end envelopes to preview and export.
The launcher verifies the current renderer and upgrades an older executable
from the pulled build parts automatically. [Boundary details](SAMPLE_BOUNDARIES.md)
describe the click fix.

## Write and edit

* Click a timeline pattern to select it. Its Steps and Event list appear below.
  Click a step, or use arrow keys and Space, to enable/disable it. Choose a finer
  step display if useful; off-grid source events stay in the Event list.
* Double-click an event-list row, or use Edit selected step, to edit its exact
  fractional position, gate, velocity, attack, Play %, Change %, variation and
  locks. Relative notes follow the chord. An exact prepared note uses the
  separate exact-pitch lock. Rhythm triggers one whole chord; drums use fixed
  source sound identities. Unassigned/unavailable drum cells are marked ×.
* Select a timeline position and use Edit chord. Degree, quality, alteration and
  inversion are explicit. Custom progression accepts Roman chords such as
  `i IIImaj7 VI iv`, or mode-derived numbers such as `1 3 6 4`, with positive beat
  durations. It fills only the chord lane and is undoable. Authored Roman case
  is retained, including an unavailable request; there is no silent chord swap.
* Set key here changes tonality at the edit cursor. Tempo is quarter-note BPM.
  Meter/grid applies at the current measure boundary. Changing the 3/4/6/8-cell
  Governor display never quantizes performance events.
* To start from silence, use New song, choose a track in Inspector, and Add
  pattern here. Draw steps or place the active pack's source pattern from
  Browser → Patterns. Source meter mismatches require an explicit future
  conversion workflow rather than automatic squeezing.
* Duplicate offers independent copies or explicit Linked Repeat. Include Harmony
  warns before replacing destination chords. Make independent detaches one
  occurrence. Copying does not overwrite a pattern already at its destination.
* Increase Song length before placing later patterns. Shortening refuses to
  truncate existing patterns or map changes. A bar's duration follows its meter.

## Mix, retain and export

Inspector adjusts the selected role. Mixer exposes individual drum parts, the
drum group, sampled roles and master with static level, pan and mute controls.
The common final compressor remains active and editable. Neutral EQ and ambience
Off retain their existing state; their processing and VST inserts are not yet
available in this slice. A project already requesting unsupported processing
opens with its data intact and a visible export blocker.

Save writes a full native `.prdeproj` with the exact pack reference, harmony,
patterns, variation, static mix, credits and editor context. Undo/Redo have named
actions. Changes receive a local recovery copy; a later start offers Recover
unsaved session after an interrupted session. Completed manual saves remain
separate. Close/open/new-song warns about unsaved musical edits.

Export WAV uses the same native plan as audition: 48 kHz, 24-bit stereo, with a
report/credits JSON beside it. Missing prepared sounds block ordinary playback
and export. Other incompatible authored events remain flagged and withheld under
the existing Governor policy. An export over the existing peak ceiling fails with
a levels instruction. Stop or a new music edit cancels a pending render; an
existing completed export is retained. Song Packs are never overwritten.

## Layout and present limits

Inspector and Browser stay at the sides at normal scale. Smaller/enlarged layouts
use labeled tabs, and the workspace may scroll while the transport remains visible.
Interface scale offers 100%, 125% and 150%; Focus view and Reset workspace are in
View. Ctrl+O opens, Ctrl+S saves, Ctrl+Z undoes, Ctrl+Shift+Z redoes, and Ctrl+E
exports. Space controls transport except inside an editor that owns the key.

This is a working desktop composition slice, not the completed v1 DAW. The one
vocal placeholder does not capture audio. Recording/retakes/comping/correction,
full EQ/reverb/delay, real-time native audio-device callbacks, Linux VST3 hosting,
Freeze Variation, comprehensive progression/MIDI catalogs, section plans and
release installers remain in the development plan. Existing approved scope is
preserved. Preview preparation adds latency before the first audible result; it
is not a low-latency monitoring engine.

Cloud checks cover Qt controls, keyboard editing, scaling, recovery, actual PCM
decoding/pause/seek, all twelve source exports, the four full-demo selections, cancellation, exact pack identity
and unchanged pack bytes. No human listening, physical audio-interface/Steam Deck
test, screen-reader pilot or first-user usability study is claimed.
