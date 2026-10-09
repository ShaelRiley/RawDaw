# Current checkpoint — 0.3.0 native desktop with four source Song Packs

Completed: a launchable Qt desktop editor, an offline Linux/C++20 renderer,
shared experimental contracts, four real-source Song Packs and eight editable
four-bar arrangements. The source
packs contain 97 actual source-derived assets. Whole chords are selected intact;
all harmonic preparation occurs before playback. No runtime pitch shifting,
stretching or harmonic synthesis is added.

The private repository is [ShaelRiley/prde1](https://github.com/ShaelRiley/prde1).
Checkpoint 1 was verified at `71d551a27ab2b6b0b8d6e37e56f8d99fc0406328`.
The 0.3.0 build is in `dist/PRDE1_0.3.0_Linux_x86_64.tar.gz`; the accompanying
SHA-256 file and archive-internal `BUILD_INFO.json` bind the exact package inputs.
The archive is transported as hashed 8 MiB parts in git; the standard-library
`tools/assemble_build.py` restores it atomically and verifies the full hash.
This is a private development build, not a public product release.

Run `./run-prde1.sh` after pulling. It installs the optional pinned desktop
libraries on first setup and restores the verified compiled renderer from the
build parts when necessary. Later launches work offline. Parachute A opens ready
to preview. The desktop exposes the Governor, track timeline, step/event editors,
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

## Canonical authority

The full live SDD, including Section 28 and its initial engineering contract,
was read before this work. `SDD_REVISION.json` retains the exact revision.
Curated source-specific crop decisions and prototype quality screens live in
`recipes/cc-songs.json` and `recipes/parachute.json`; they do not replace product requirements or close the
SDD's listening/source-analysis gates. No new product-policy amendment was made.

## Verification

* `QT_QPA_PLATFORM=offscreen make check`: **62 Python invariant/integration tests
  passed**, including the
  four real packs, no-synthetic lineage, explicit gaps, source-MIDI tempo/semantic
  addresses, eight-project save/reopen, actual mapping resolution and immutable
  assets. Native checks passed for allocation-free processing, unchanged frame
  copies, sustain-only looping, release, silence and the 64-voice cap.
  Distribution assembly tests cover exact restoration plus missing, altered,
  duplicate and traversing parts and a wrong final hash, preserving prior output.
* Seven native Qt integration checks cover keyboard editing/undo, local recovery,
  cancellation without replacing prior exports, visible unavailable harmony,
  actual 48 kHz PCM decoding with pause/seek, and 100/125/150% layouts. All eight
  GUI exports are byte-identical to their bundled source auditions and preserve
  pack bytes. Screens were inspected at 1366×800, 1280×800 and 1024×768; transport
  stays visible when enlarged. Renderer-install tests verify hashes, executable
  permissions and rejection of substituted/symlink payloads.
* `make source-demo`: **eight ordinary source-pack exports**, no harmonic conflicts,
  48 kHz / 24-bit stereo. Repeated renders are byte-identical. Seek frame 123457
  equals the exact full-render slice including compressor/dither state. Pack
  hashes remain unchanged. Peaks range from approximately −10.72 to −9.80 dBFS.
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

Version 0.3.0 evidence: `validation/desktop-check-0.3.0.log`,
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

No human listening, reference laptop/Steam Deck/audio-interface testing,
microphone testing or usability testing was performed. The compiled Linux
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
