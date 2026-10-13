# Current checkpoint — per-note volume on the 0.3.4 engine

Shael's October 12 request exposes saved per-note dynamics directly. Focus a
note and adjust its 0–100% slider or percentage; default dynamics bars shape the
focused pitch/kit row. Tied-note continuations address the original attack. Edits
use existing velocity, validation, undo/recovery, pattern persistence and the
native preview/export path. Exact off-grid notes have the same volume label in
the event list/dialog. Zero-volume realized notes stay silent in MIDI export.

The focused volume controls, mute/solo and dynamics bars remain visible; More
controls reveals defaults, other expression and row timing. Timeline scrolling
and pane sizing preserve the editing viewport at 1280×800 and 150% text. The
focused note stays visible when its grid resizes. Sample banks and the compiled
renderer/DSP are unchanged.

Validation: `make check` passed all 116 Python/Qt tests without skips plus
native engine checks. The final focused Qt rerun passed 12 tests, including a
disabled intervening step beneath a continuing note. Real mouse/keyboard volume edits, single-undo slider drags,
tied notes, save/reopen/undo/redo, empty-step protection and actual viewport bounds
pass. A native synthetic PCM test verifies the expected 80%/40% amplitude ratio
and zero-level silence, including MIDI export. `make demo` passed both reference
renders; existing desktop/source exports remain identical. Evidence and the live
SDD revision are in `validation/note-volume-verification.json` and its referenced
logs. Physical Steam Deck startup and human listening remain unverified.

## Previous default step-sequencer checkpoint

Shael's October 11 request and clarification add the Cakewalk-style step
sequencer as the default bass/lead/kit pattern view. Pitch rows dispatch the
chosen notes; kit rows retain instrument identities. The interface supports
draw/erase, velocity expression, ties/flams, row mute/solo, swing/offset/gates,
mono/poly entry, row fill/copy/shift/reverse/editing, pattern files, keyboard step
entry, independent loop/row audition, note MIDI import/export and default track
selection. Grid changes preserve exact off-grid timing. Fit spacing is displayed
precisely, and pattern growth protects neighboring material. All musical controls
share the canonical save/undo/recovery and native resolver. See `STEP_SEQUENCER.md`.

Validation: full `make check` passed 107 tests plus native engine checks; the
final focused musical/UI reruns passed 22 tests including four new edge cases
(111 distinct tests verified overall). `make demo` passed both reference renders.
New tests exercise actual mouse/keyboard gestures, pitch and kit dispatch,
mono/poly voice lengths, swing/flam probability, ties, shifted harmonic boundaries,
save/reopen/reuse, loop/row preview independence, MIDI interoperability, native
audio/seek, timing wrap, truncation/overlap protection and custom Fit spacing.
All twelve legacy desktop exports still match their native auditions; complete
harmonic coverage, source integrity and responsive/startup tests remain green.
Evidence is in `validation/step-sequencer-*.log`. Qt inspection at 1280×800 and
enlarged layouts keeps the grid/actions accessible. Physical Deck startup and
subjective listening remain unverified. The existing compiled 0.3.4 renderer is
unchanged and reused by the source update.

## October 12 recovery verification

GitHub `main` at `b263d34a2a4b61f8348ef578287ef3b8be9d36a8` already
contained the complete step-sequencer implementation and final edge checks. All
102 recovered source files were verified against their remote Git blob hashes.
The live SDD revision matches the Section 31 amendment recorded above. No musical
or interface behavior changed during recovery.

Fresh `make check` passed all 111 Python/Qt tests in one run, with no skips, plus
native engine checks. `make demo` passed both synthetic reference arrangements.
`make source-demo` passed all twelve source arrangements with zero conflicts,
byte-identical repeats, exact seek slices and unchanged Song Packs; the desktop
exports matched these newly rendered auditions. Python 3.12.14 and Qt/PySide6
6.8.3 were used in the offscreen Linux environment. Physical Deck startup and
human listening remain unverified. Evidence, source hashes, environment and the
canonical SDD revision are in
`validation/step-sequencer-recovery-20261012.json` and its referenced logs.

## Previous full harmonic coverage checkpoint

Shael's October 11 request and SDD Section 30 supersede the earlier silent-gap
policy. Every pack now supports all 528 registered chord voicings, all 70 lead/
bass notes, and every tonic/mode combination. Native samples win; an offline
hybrid preparation layer supplies missing targets and sustained holds, and
explicitly modeled percussion fills missing offered slots. Borrowed chords play
as authored. Relative tone choices adapt to changing chord size. Exact pitch
conflicts, empty optional extras and intentional rests/mutes remain deliberate.

Original packs and saved pack references are unchanged, and the existing native
renderer, per-drum EQ, drum/master compression and bass sidechain are reused.
No new runtime dependencies or network access are introduced. Source fidelity
of reconstructed sounds is approximate and is labeled in the interface and
export notices. Read `HARMONIC_COVERAGE.md` for the method and measured limits.
The source-quality and physical-device gates below remain open.

Validation: `make check` passed 89 Python/Qt tests plus native engine checks;
`make demo` passed both synthetic render arrangements. The exhaustive real-pack
audit exported 2,112 chord voicings (528 per pack) with correct pitch-class and
inversion metadata and non-silent PCM in every event. All 70 role notes prepare
per pack. All twelve existing scores export without conflicts, repeat byte for
byte, and seek to exact full-render slices; GUI exports match the same auditions.
Source SHA-256 values remain unchanged. Evidence is in
`validation/full-chord-coverage.json`, `validation/full-harmonic-check.log`,
`validation/full-harmonic-demo.log`, and `validation/full-harmonic-source-demos.json`.
The sustain preparation also covers odd-length mono PCM and checks exact loop
seam continuity. No subjective listening or physical Deck success is claimed.

## Previous startup and drum-mix checkpoint

The physical Deck then pulled `058d2f2` and still crashed after `Responsive
workspace ready`, before the event loop, at the combined construction/show line.
On-device startup therefore remains failed. The follow-up source update adds
`--safe-workspace`: Inspector/Browser are central tabs from construction,
saved geometry/dock state/scale are bypassed and preserved, and the built-in
Fusion style is selected. First show and event-loop entry have separate trace
lines/stages, with display platform/style/screen diagnostics. Matching Python
3.13.5/Qt 6.8.3 headless checks open Reach Out and preserve legacy preferences.
See `validation/desktop-recovery-0.3.4.*`. Physical recovery-mode launch and
listening remain open; no native root cause is claimed.

The October 11 physical Deck trace locates a separate native crash at automatic
dock tabification during saved-scale restoration. A source hotfix replaces the
native merge with labeled central tabs for compact/enlarged layouts, guards
panel ownership transfers during startup/resize, and repairs Focus/Reset panel
visibility. The existing 0.3.4 renderer and all musical settings remain intact.
All 81 tests pass, including an injected native dock fault, legacy saved
preferences and repeated scale/size transitions; the twelve source exports
retain their original 0.3.4 hashes. See [DESKTOP_STARTUP.md](DESKTOP_STARTUP.md) and
`validation/desktop-layout-hotfix-0.3.4.*`. The subsequent physical relaunch failed
as recorded above.

This checkpoint adds native per-drum stereo EQ, combined drum bus compression
with +3 dB makeup, and kick-signal-driven bass ducking capped at 6 dB, followed
by common master compression. Mixer provides independent EQ dialogs; Dynamics
exposes the three processors' bypass, threshold, ratio, attack/release and
boost/duck controls. Settings are saved, undoable and recoverable. New songs
and all four full demos use the preset; older user projects and the eight
historical short demos retain their mix. See [MIXING.md](MIXING.md).

The 0.3.4 compiled delivery is a small hashed renderer upgrade for the repository
checkout, automatically installed by `./run-prde1.sh` after pull. It requires no
local compiler and preserves prior archives/packs. The startup hotfix remains
active; physical Steam Deck launch/playback and subjective listening remain
unverified. Validation and exact source-render evidence are in
`validation/desktop-check-0.3.4.log` and `validation/source-render-0.3.4.json`.

## Preserved 0.3.3 source/content baseline

Completed: a launchable Qt desktop editor, an offline Linux/C++20 renderer,
shared experimental contracts, four real-source Song Packs, eight editable
four-bar arrangements and four complete demos: **Reach Out 2:32.92**,
**Where You Are Now 2:33.60**, **Auld Lang Syne (Bossa) 2:42.46**, and
**Parachute 2:42.91**. All twelve projects remain editable. The source
packs contain 97 actual source-derived assets. Whole chords are selected intact;
all harmonic preparation occurs before playback. No runtime pitch shifting,
stretching or harmonic synthesis is added.

The private repository is [ShaelRiley/prde1](https://github.com/ShaelRiley/prde1).
Checkpoint 1 was verified at `71d551a27ab2b6b0b8d6e37e56f8d99fc0406328`.
The 0.3.3 build is in `dist/PRDE1_0.3.3_Linux_x86_64.tar.gz`; the accompanying
SHA-256 file and archive-internal `BUILD_INFO.json` bind the exact package inputs.
The archive is transported as hashed 8 MiB parts in git; the standard-library
`tools/assemble_build.py` restores it atomically and verifies the full hash.
This is a private development build, not a public product release.

The current source adds a startup hotfix for the reported Steam Deck exit-139
failure. Qt's unnecessary GPU video-driver probes are disabled before creating
the PCM player; native fault diagnostics and startup stages are retained locally.
An injected crashing video-driver test opens the actual Reach Out editor through
the protected path. The physical Deck's exact cause and successful launch still
need confirmation. The previously hashed archive is unchanged; pull `main` for
this source/launcher fix. See `DESKTOP_STARTUP.md` for evidence and log locations.

Run `./run-prde1.sh` after pulling. It installs the optional pinned desktop
libraries on first setup and restores the verified compiled renderer from the
build parts when necessary, including replacing an older executable after pull.
A matching binary is reused offline without reading archive parts. Parachute A opens ready
to preview; Browser → Packs → **Full-length demos** selects any of the four
complete songs. Click **Load full demo** to open the selected project.
Alternatively run `./run-prde1.sh --project packs/parachute_full.prdeproj`.
The desktop exposes the Governor, track timeline, step/event editors,
pack/progression/pattern browser, static mixer, independent or linked copies,
undo/redo, variation regeneration, project save/reopen and local recovery. Native
render preparation runs outside the UI; PCM preview, pause/seek and WAV export
reuse the saved musical realization. Cancellation and music edits reject stale
results. The launcher and extracted build both use the same project/render core.

The fourth pack is **Parachute**, created/supplied by Shael Riley using Suno.
His paid-account rights declaration and explicit authorization are retained
separately from the first three CC BY 3.0 packs. It adds 28 native source samples,
a saved estimated drum measure, and two new covered arrangements. No full stem
or original ZIP is shipped, and no new CC/MIT grant for Parachute is implied.

Version 0.3.2 addresses Shael's sample-cutoff click report: the native player
adds a 1 ms start safety fade and a smooth, zero-slope 5 ms release. Natural
one-shot exhaustion is protected in the player too. Gate, harmony, retrigger
and choke endpoints stay exact; source files and score stay unchanged. See
`SAMPLE_BOUNDARIES.md` for diagnosis, behavior and evidence.

Version 0.3.3 adds 72-bar acoustic-pop Reach Out, 64-bar synth-pop Where You
Are Now and 88-bar bossa Auld Lang Syne scores. Chorus identities return in
three refrains; verse 2, pre-chorus lifts, bridges and final accompaniments
provide contrast. Every new bar contains audible music. These are complete
authored pack demonstrations, not original source-song transcriptions. The
source packs, short scores and Parachute Full score/render are unchanged.
See `FULL_DEMOS.md` for the forms and actual coverage.

## Canonical authority

The full live SDD, including Section 28 and its initial engineering contract,
was read before this work. `SDD_REVISION.json` retains the exact revision.
Curated source-specific crop decisions and prototype quality screens live in
`recipes/cc-songs.json` and `recipes/parachute.json`; they do not replace product requirements or close the
SDD's listening/source-analysis gates. No new product-policy amendment was made.
The four full demos implement fixed authored scores against Sections 23–24,
with companion section timings; generic Song Plan generation and locks remain open.

## Verification

* The startup hotfix passes **71 Python invariant/integration tests** and the
  existing native engine checks. Its three added checks verify audio-only
  initialization, a retained traceback from a real native fault, and the actual
  Reach Out editor opening with an injected crashing video driver. The exact
  shell launcher also reaches its event loop with that driver installed and
  initializes the startup log once. PCM decode/pause/seek and all twelve GUI
  exports still pass. Evidence: `validation/desktop-startup-hotfix.log` and
  `validation/desktop-startup-hotfix.json`; physical Deck verification is open.
* `QT_QPA_PLATFORM=offscreen make check PYTHON=.venv/bin/python`: **68 Python invariant/integration tests
  passed**, including the
  four real packs, no-synthetic lineage, explicit gaps, source-MIDI tempo/semantic
  addresses, all twelve projects' save/reopen, actual mapping resolution and immutable
  assets. Native checks passed for allocation-free processing, unchanged frame
  copies, sustain-only looping, smooth endpoints/natural exhaustion, retrigger/choke,
  tiny gates, processing-block identity, release, silence and the 64-voice cap.
  Distribution assembly tests cover exact restoration plus missing, altered,
  duplicate and traversing parts and a wrong final hash, preserving prior output.
* Seven native Qt integration checks cover keyboard editing/undo, local recovery,
  cancellation without replacing prior exports, visible unavailable harmony,
  actual 48 kHz PCM decoding with pause/seek, the four full-demo selections, and
  100/125/150% layouts. All twelve
  GUI exports are byte-identical to their bundled source auditions and preserve
  pack bytes. Screens were inspected at 1366×800, 1280×800 and 1024×768; transport
  stays visible when enlarged. Renderer-install tests verify hashes, executable
  permissions, existing-executable upgrades, offline reuse without archive parts,
  conflicting identity metadata and rejection of substituted/symlink payloads.
* The real-source boundary audit checks all **97 assets / 194 probes** at
  shortened gates and natural ends. Every endpoint is zero within one 24-bit
  dither LSB. Interior PCM bytes match the 0.3.1 renderer outside the boundary
  envelopes, and all pack hashes remain unchanged. This is diagnostic evidence,
  not a human listening certification.
* `make source-demo`: **twelve ordinary source-pack exports**, no harmonic conflicts,
  48 kHz / 24-bit stereo. Repeated renders are byte-identical. The eight short
  demos seek at frame 123457; each full song seeks three quarters into its duration.
  Each seek equals the exact full-render slice, including compressor/dither state. Pack
  hashes remain unchanged. Peaks range from approximately −11.15 to −9.26 dBFS.
* The three new full songs resolve 1,594 / 1,427 / 2,200 events with no
  coverage conflicts. All 72 / 64 / 88 measures contain audible music. First
  choruses are 4.18 / 3.62 / 3.72 dB louder in RMS than their bridges; final
  silence is under 0.3 seconds. Scores rebuild identically and save/reopen
  preserves each resolved plan and exact source reference. The source-only
  hooks and MIDI dynamics vary among the songs. The eight short auditions
  and Parachute Full WAV retain their previous hashes.
* Four full-song MP3s were separately exported at 320 kbps, 48 kHz stereo,
  completely decoded, and bundled with source attributions and preparation
  changes. MP3 encoder padding is verified within 1 ms of source frame counts.
* Parachute Full exports 7,819,636 frames, 2,806 resolved events and 112 occupied
  measures, with no silent padding. Its saved chorus lead remains recognizably
  repeated and variation-locked. Verse/bridge contrasts and measured section
  levels are documented in `validation/parachute-full-verification-0.3.2.json`.
  Score rebuilding and native save/reopen retain the exact source identity/plan.
* Parachute's repeated preparation is byte-identical; a changed vocal hash and
  a false guitar-chord label fail while preserving the previous pack. Its new
  renders peak at −10.28/−10.59 dBFS. User-source rights are retained and all
  Parachute lineage is native to its own selected stems.
* Changed source hashes fail preparation and preserve prior packs. A semitone-
  shifted false whole-chord label fails the spectral screen. Preparation-only
  note variants beyond the 3.25-semitone bound are rejected.
* `make demo`: the original two explicitly synthetic regression arrangements
  still render successfully. They remain separate from real-source evidence.
* Existing failure/security checks cover archive traversal, symlinks, duplicate
  keys/entries, checksums, mappings, unsafe loops, malformed MIDI, resource budgets,
  numeric bounds, unsupported active processing and transactional export/save.

Version 0.3.3 evidence: `validation/desktop-check-0.3.3.log`,
`source-render-0.3.3.json`, `source-demo-0.3.3.log`,
`full-catalog-verification-0.3.3.json`, `mp3-full-demos-0.3.3.json`,
`synthetic-regression-0.3.3.log`, and `PRDE1-0.3.3-full-demos.png`.
Earlier version 0.3.2 evidence: `validation/desktop-check-0.3.2.log`,
`source-render-0.3.2.json`, `source-demo-0.3.2.log`,
`sample-boundaries-0.3.2.json`, `parachute-full-verification-0.3.2.json` and
`synthetic-regression-0.3.2.log`. The 0.3.2 UI layout was unchanged.
Earlier version 0.3.1 evidence: `validation/desktop-check-0.3.1.log`,
`source-render-0.3.1.json`, `source-demo-0.3.1.log`,
`parachute-full-verification-0.3.1.json`, `synthetic-regression-0.3.1.log` and
`PRDE1-0.3.1-parachute-full.png`. Earlier desktop evidence: `desktop-check-0.3.0.log`,
`synthetic-regression-0.3.0.log` and `PRDE1-0.3.0-desktop.png`.
Version 0.2.1 source evidence remains: `validation/source-check-0.2.1.log`,
`source-render-0.2.1.json`, `parachute-preparation.json` and
`synthetic-regression-0.2.1.log`. Earlier CC evidence: `cc-check.log`, `cc-render.json`,
`cc-preparation-failures.json`, `synthetic-regression.log` and the original core
validation. Archive extraction/run verification is recorded in its accompanying
build-check JSON. Tests were performed in the cloud Linux environment.

## Source-quality and product limits

All four packs say **coverage-limited**, and their release-quality gates remain
open. Artist-provided stems were used without a learned separation model. Source
notes/chords/percussion identities are saved estimates supported by diagnostics;
they are not listening-audited identities. There is no full source tonal map or
verified stem-to-master alignment. Possible baked processing/bleed remains.
Open hats and both tom slots are unavailable. Optional extras are actual source
sounds where assigned; unused extras stay empty. No stock/synthetic fills are
used. All source samples are one-shots; natural duration limits are reported.

Parachute uses the nine supplied Suno stems, selecting vocal, guitar, bass and
drum material. File lengths/rates/origins match; no original master was supplied
and acoustic alignment is not independently verified. Its source tempo, chord
labels/inversions and partial drum transcription are numerical estimates.

Shael's informal 0.3.0 and 0.3.1 auditions were positive; his 0.3.1 feedback
identified the cutoff artifact addressed here. Formal pack-wide listening,
reference laptop/Steam Deck/audio-interface benchmarks, microphone and usability
testing remain open; the 0.3.2 boundary fix awaits the creator's audition. The compiled Linux
x86_64 binary is a convenience build on Ubuntu 24.04, with system libstdc++,
libgcc, libm and glibc; source/Makefiles are included for rebuilding.

Native real-time device callbacks, full progression/pattern libraries, Freeze
Variation, section plans, durable vocal takes/comp/correction, complete fixed DSP,
Linux VST3 hosting and release installers remain unimplemented approved scope.
Desktop preview plays a prepared mix and is not a recording/monitoring engine.
Unsupported processing continues to block exports instead of being silently
omitted. No physical output-device or screen-reader pilot is claimed.

The preparation tool is a bounded curated-stem prototype, not the public pack
builder skill or a general arbitrary-song separator. See `SONG_PACKS.md` for
sources, licenses, ingredients, coverage and reproducibility, and
`DEVELOPMENT_PLAN.md` for the remaining production work.

