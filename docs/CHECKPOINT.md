# Current checkpoint — 0.1.0 prepared-sample core

Completed: an executable offline Linux/C++20 renderer plus shared experimental
pack/project/event contracts and Python control tooling. Two editable harmonic
arrangements play the same explicitly synthetic sample bank without runtime
harmonic waveform processing. `make check` and `make demo` reproduce the result.

## Canonical authority used

Live SDD: `1qb6LWTgkk3vVJB3aFnwkXvtZ1-IxRIY0VezW0P9e_HE`, tab `t.0`.
The entire current document, including consolidated decisions and Section 28,
was read before architecture/code work. Exact source and amendment revisions are
recorded in `SDD_REVISION.json`. Section 28.8 now records the engineering values;
the original document was edited in place and its content/styles were read back.
Routine commit/test history remains here rather than in the product SDD.

## Verification

* `make check`: **40 Python invariant/integration tests passed**, plus native
  checks for allocation-free block processing, unchanged frame-copy identity,
  sustain-only looping, final release, stopped silence and 64-voice rejection.
* `make demo`: major and minor **eight-second, 384,000-frame, 48 kHz, 24-bit
  stereo** renders, 88 events each, no harmonic conflicts. Approximate peak
  −13.93 dBFS. Actual PCM files differ as expected.
* Repeat renders are byte-identical for this sample engine. A seek at frame
  123,457 equals the exact full-render slice, including compressor and dither
  state. This is not a promise for arbitrary future plug-ins.
* Source archives/cache hashes stay unchanged through Governor resolution and
  rendering. Whole chords trigger once; the separate VST event adapter emits
  constituent notes without claiming a running host.
* Security/failure tests cover traversal/absolute paths, symlinks, duplicate
  archive/JSON keys, unknown versions, checksums, invalid mappings/chords/loops,
  decompression/decoded budgets, malformed MIDI and unbounded numeric values.
  Interrupted manifest replacement and clipping-aborted render preserve prior
  completed files. Explicit coverage gaps/unsupported processing are reported.

See `validation/core-check.log` and `validation/core-render.json` for evidence.
No native laptop/Steam Deck/interface, microphone, human listening, full DSP/VST
workload, or usability testing was performed. The cloud compiler/test runtime is
not a reference-device performance benchmark.

## Known limits and defects

* There is no attached authorized recording. No extraction pipeline, audited
  source-derived demonstration pack, or public builder skill exists yet. The
  generated signals/MIDI prove only the explicitly synthetic core tests.
* No desktop workspace, device backend or microphone capture. Vocal/plug-in
  state fields are experimental placeholders, not implemented media handling.
* EQ/reverb/delay/VST inserts and vocal correction/comp playback are absent.
  Active requests for them block export. Unsupported additional VST instruments
  remain silent only after explicit altered-render approval.
* Six development progression templates and one authored synthetic drum clip
  are not the extensive released preset/clip libraries. MIDI inspection is not
  the complete musical import/adaptation UI. Freeze Variation and edit history
  still require implementation.
* RIFF PCM 48 kHz assets only; other device rates, WAVE_FORMAT_EXTENSIBLE, cache
  paging, interruption journals and release installers are not implemented.
* Synthetic short drum/lead gates can hit natural duration limits. Reports
  identify those limits rather than manufacturing longer audio. Synthetic
  sustain flags are preparation fixtures, not evidence of human-audited loops.
* The application has an MIT license; no third-party plug-ins/models/content
  bundle is cleared or shipped.

## Repository/publication state

No existing PRDE1 repository was found through the connected GitHub account or
the inspected local workspace. The account is ShaelRiley. A local `main` repository
has been initialized and this tested checkpoint is committed. The downloadable
artifact contains its Git bundle and exact `CHECKPOINT_COMMIT.txt`.

**Not pushed or published.** The connected GitHub tool exposes no repository-
creation action and direct CLI/API authentication is unavailable. Creating the
requested private `ShaelRiley/prde1` through a signed-in browser requires the
browser-fallback approval specified by the browser tool. After approval: create
that private repository, push this local checkpoint through the authorized Git
transport, and verify remote `main` SHA. Do not create a public repository.

## Next concrete milestone

Finish remote checkpoint publication when browser fallback is authorized. Then
advance the real-source sound gate with one explicitly authorized short recording
and its rights declaration, while retaining the existing contract/render tests.
Preflight extraction dependencies before processing. Identify useful actual
source notes/chords/individual drum hits and reusable performance patterns;
preserve corrections and fail honestly where isolation/coverage is inadequate.
Only after useful real-source sound is demonstrated should the workflow/UI and
large inventories expand. Approved Linux VST3, four vocal lanes/simple comping,
fixed DSP, reversible correction and substantial curated libraries remain in the
bounded development plan.
