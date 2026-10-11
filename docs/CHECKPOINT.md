# Current checkpoint — 0.3.3 with four full-length demos and startup hotfix

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
