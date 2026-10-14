# Clip and track loops

Drag a MIDI-library bar onto its matching timeline lane. Drag the body of a
placed clip to move it, or drag its right edge to repeat its source pattern.
The edge snaps to the timeline grid and can stop partway through a final repeat.
The source pattern remains editable in the step sequencer: extending the clip
does not duplicate or stretch its notes. The timeline marks each source cycle.

The clip context menu also exposes Move and Loop length. Shift+Left/Right moves a
selected clip; Ctrl+Left/Right shortens or extends it by one source cycle.
Placement, movement and extension protect existing clips on that instrument
lane, and every completed drag is one undoable edit. Copies retain the arranged
span. A normal copy gets its own editable pattern; a Linked Repeat shares edits,
and Make Independent detaches its pattern without losing the repeat span.

Loop track repeats the lane's entire occupied range, including its internal
rests, through the saved song ending. The inferred cycle begins with the first
clip and ends at the last clip's visible right edge. Translucent later copies
are previews of that source cycle. Selecting one selects its source clip;
editing a later cycle means disabling the track loop and placing independent
clips. While a track loop is enabled, all authored clips must stay inside its
source range. Disable it to extend that arrangement. Removing a track's final
clip disables its loop.

Loop song repeats the completed song preview until Stop. It is saved with
the project but does not add repetitions to an export. The MIDI-browser,
progression-browser and step-pattern auditions keep their own independent
single-cycle preview scope, irrespective of arrangement loops.

## Timing and persistence

An optional instance `playbackLength` stores its visible arranged length in
exact rational quarter-note beats. Omission preserves legacy one-shot behavior.
An optional project `trackLoops` maps an instrument role to `startBeat` and
`endBeat`; omission means off. `loopPlayback` is an optional saved transport
boolean and does not change the Governor's resolved plan. Old projects load
unchanged. Undo, recovery and native saves preserve these fields.

The Governor expands musical cycles into its ordinary native event plan before
audio playback. Every repeated trigger uses its actual destination harmony,
tonality, tempo, meter and rhythmic-pulse phase. Exact-pitch conflicts remain
authored and are reported at the conflicting repeat. Source-relative melodic
choices adapt to each destination chord, just as ordinary placed copies do.

Saved instance and event IDs address deterministic variation. The first cycle
retains its prior addresses; subsequent cycles append stable repeat numbers.
Extending a clip or a song retains the realization of earlier cycles. Audition,
seek and export do not consume randomness or rewrite the saved performance.

Clip-loop gates end at their source-pattern cycle boundary; track-loop gates
end at the complete track cycle boundary, preserving authored holds across
shorter source clip ends. A final partial cycle omits attacks beyond the saved
ending. The native sampler's existing smooth
attack/release envelopes prevent hard sample cuts at those gates. This is
musical clip looping over prepared PCM; it does not time-stretch source audio.
Whole-song preview repetition follows Qt's media-player transport and still
requires an on-device listening check for a particular output device's seam.

Validation rejects zero cycles, overlapping loop source clips, cycles outside
the song, placements outside an active track cycle, and expanded event/cycle
budgets above 100,000 before expansion. The native 64-voice and 30-minute bounds
remain in force. Focused loop tests cover partial repeats, exact-pitch conflicts,
meter/tempo changes, gaps, deterministic variation, copied/linked/detached clips,
undo, save/reopen, scoped previews and hostile tiny-cycle expansion.
