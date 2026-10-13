# Raw Daw MIDI clips and rhythmic pulse

Start with a loaded bank, click New song, set a chord progression, then open
Browser → MIDI clips. Select Bass, Drums, Lead or Chords, preview a clip and Place
it at the current measure. Dragging onto its matching timeline track does the
same thing. Placement protects occupied measures and is one undoable operation.
Every placed clip remains an ordinary editable step pattern. Duplicate bars to
build a section; each copy follows its destination harmony.

The 2026.10.13 collection has 703 distinct bars: 175 bass, 247 drums, 169 lead
and 112 chord patterns. Search includes names, styles, section roles and sources.
Favorites persist with application preferences. Meter matching is on by default;
4/4, 3/4 and 6/8 bars retain their timing and are never silently squeezed into
another meter. A final partial measure must be extended before a complete bar fits.

Preview loops the loaded instrument with the actual destination harmony and
pulse. It does not alter the project, credits or variation. Lead/bass store
chord-tone relationships and register. Chords supplies one whole-chord attack
per logical source attack, rather than repeating the chord for each constituent
note. Substantial melodic reharmonization is inherent in changing the source's
chords: these are adaptable performances, not promises of identical melodies.

Drum notes retain instrument identities. The TD-11 map from the source dataset
is normalized explicitly. Core kick/snare/hat/tom voices use those kit roles.
Crash/ride only use an available matching declared MIDI address or sound identity.
If the bank has no such extra, the browser reports its omission on preview/place
and records it in pattern provenance. Simultaneous many-to-one articulations
produce one hit. Empty optional extras remain empty.

Save source MIDI exports the canonical library bar and a credits JSON beside it.
It is a source performance; the Step sequencer's Export MIDI exports the placed
pattern as heard under current harmony and pulse. Native project/pattern saves
retain editable expression, provenance and credits. MIDI is note-level interchange.

## Rhythmic Pulse Governor

| Mode | Behavior |
| --- | --- |
| Off | Existing note/row dynamics pass through unchanged. |
| Guide | Newly drawn notes and newly placed library hits receive accent-grid defaults. Existing notes and later volume edits remain free. |
| On | The accent at each actual trigger position determines its pre-mixer volume. Stored volumes are preserved for later Off playback. |

Presets include pop backbeat, four on the floor, offbeat lift, half time,
driving eighths, funk, tresillo, ballad, waltz, compound two and even volume.
Edit accents sets each subdivision to 0–100%; accent columns divide the current
measure equally. The pulse restarts at meter-map downbeats, not at every clip.
Microtiming, swing and generated doubles are evaluated at their sounding position.
Flam grace notes retain their 45% softer articulation. Mutes, rests, probability,
gates, channel levels and downstream DSP keep their established meanings.
New projects and legacy projects default to Off. Mode/custom levels are saved,
undoable and recoverable. Guide seeds notes at placement; later pulse edits do not
rewrite them. In On, zero at an accent is silence even if stored volume is nonzero;
a nonzero pulse can sound a stored zero-volume note, so use Disabled or Mute when
an intentional silence must survive On.

## Sources, licensing and reproducibility

| Source | Selected bars | License | Changes |
| --- | ---: | --- | --- |
| Google LLC, Groove MIDI Dataset v1.0.0 | 231 drums | CC BY 4.0 | Whole-bar selection, TD-11 semantic mapping, bounded one-shot gates, explicit same-address retrigger interpretation. Timing/accents retained. |
| Tozan, Piano 3 Bass With Drums (2022) | 91 melodic/chord bars | CC0 1.0 | Explicit source channels, bar slices, highest/lowest attack voice for lead/bass, collapsed simultaneous chord attacks, bounded registers/gates, inferred chord relationships. |
| Raw Daw original collection | 381 across roles | CC0 1.0 | Authored role-specific rhythms/contours, short/held chord gates, separate waltz/compound-meter grooves. |

Sources: https://magenta.tensorflow.org/datasets/groove and
https://opengameart.org/content/piano-3-bass-with-drums.
Groove attribution: Google LLC; Jon Gillick, Adam Roberts, Jesse Engel, Douglas
Eck and David Bamman, “Learning to Groove with Inverse Sequence Transformations,”
ICML 2019. License: https://creativecommons.org/licenses/by/4.0/.
CC0: https://creativecommons.org/publicdomain/zero/1.0/.
Original authored scores are explicitly dedicated to CC0; application code and
the dog SVG remain under the repository's MIT license.

The catalog is stored as size-bounded index.json.gz. Records retain source URL/file/SHA-256, source measure/tempo, license,
attribution, transformations and canonical SMF hash. Original source MIDI is
preserved in data/clips/sources. The complete canonical MIDI bank is in
data/clips/midi-clips.zip. Counts exclude exact performance/transposition
duplicates; meaningful gates and chord-tone contours distinguish patterns.
Clip credits follow native project/pattern saves and stereo export reports.
CC BY obligations still apply when distributing adaptations using those clips.

Rebuild entirely offline from bundled source data:

```bash
python3 tools/build_clip_library.py \
  --groove prde1/data/clips/sources/groove-v1.0.0-midionly.zip \
  --piano prde1/data/clips/sources/ypiano3basswithdrum.mid
```

The official drum archive SHA-256 is
651cbc524ffb891be1a3e46d89dc82a1cecb09a57c748c7b45b844c4841dcc1e.
Neither network access nor new runtime dependencies are required by the library.
