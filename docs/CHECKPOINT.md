# Current checkpoint — 0.2.0 with three CC Song Packs

Completed: an offline Linux/C++20 renderer, shared experimental contracts,
three real-source Song Packs and six editable four-bar arrangements. The source
packs contain 69 actual source-derived assets. Whole chords are selected intact;
all harmonic preparation occurs before playback. No runtime pitch shifting,
stretching or harmonic synthesis is added.

The private repository is [ShaelRiley/prde1](https://github.com/ShaelRiley/prde1).
Checkpoint 1 was verified at `71d551a27ab2b6b0b8d6e37e56f8d99fc0406328`.
The 0.2.0 build is in `dist/PRDE1_0.2.0_Linux_x86_64.tar.gz`; the accompanying
SHA-256 file and archive-internal `BUILD_INFO.json` bind the exact package inputs.
This is a private development build, not a public product release.

## Canonical authority

The full live SDD, including Section 28 and its initial engineering contract,
was read before this work. `SDD_REVISION.json` retains the exact revision.
Curated source-specific crop decisions and prototype quality screens live in
`recipes/cc-songs.json`; they do not replace product requirements or close the
SDD's listening/source-analysis gates. No new product-policy amendment was made.

## Verification

* `make check`: **45 Python invariant/integration tests passed**, including the
  three real packs, no-synthetic lineage, explicit gaps, source-MIDI tempo/semantic
  addresses, six-project save/reopen, actual mapping resolution and immutable
  assets. Native checks passed for allocation-free processing, unchanged frame
  copies, sustain-only looping, release, silence and the 64-voice cap.
* `make cc-demo`: **six ordinary source-pack exports**, no harmonic conflicts,
  48 kHz / 24-bit stereo. Repeated renders are byte-identical. Seek frame 123457
  equals the exact full-render slice including compressor/dither state. Pack
  hashes remain unchanged. Peaks range from approximately −10.72 to −9.80 dBFS.
* Changed source hashes fail preparation and preserve prior packs. A semitone-
  shifted false whole-chord label fails the spectral screen. Preparation-only
  note variants beyond the 3.25-semitone bound are rejected.
* `make demo`: the original two explicitly synthetic regression arrangements
  still render successfully. They remain separate from real-source evidence.
* Existing failure/security checks cover archive traversal, symlinks, duplicate
  keys/entries, checksums, mappings, unsafe loops, malformed MIDI, resource budgets,
  numeric bounds, unsupported active processing and transactional export/save.

Evidence: `validation/cc-check.log`, `cc-render.json`,
`cc-preparation-failures.json`, `synthetic-regression.log` and the original core
validation. Archive extraction/run verification is recorded in its accompanying
build-check JSON. Tests were performed in the cloud Linux environment.

## Source-quality and product limits

All three packs say **coverage-limited**, and their release-quality gates remain
open. Artist-provided stems were used without a learned separation model. Source
notes/chords/percussion identities are saved estimates supported by diagnostics;
they are not listening-audited identities. There is no full source tonal map or
verified stem-to-master alignment. Possible baked processing/bleed remains.
Open hats and both tom slots are unavailable. Optional extras are actual source
sounds where assigned; unused extras stay empty. No stock/synthetic fills are
used. All source samples are one-shots; natural duration limits are reported.

No human listening, reference laptop/Steam Deck/audio-interface testing,
microphone testing or usability testing was performed. The compiled Linux
x86_64 binary is a convenience build on Ubuntu 24.04, with system libstdc++,
libgcc, libm and glibc; source/Makefiles are included for rebuilding.

Desktop workspace/device I/O, full progression/pattern libraries, variation UI
and undo, durable vocal takes/comp/correction, complete fixed DSP, Linux VST3
hosting and release installers remain unimplemented approved scope. Unsupported
processing continues to block exports instead of being silently omitted.

The preparation tool is a bounded curated-stem prototype, not the public pack
builder skill or a general arbitrary-song separator. See `SONG_PACKS.md` for
sources, licenses, ingredients, coverage and reproducibility, and
`DEVELOPMENT_PLAN.md` for the remaining production work.
