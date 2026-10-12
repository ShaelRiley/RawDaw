# PRDE1 development

Read the live canonical SDD before selecting or changing product behavior:
https://docs.google.com/document/d/1qb6LWTgkk3vVJB3aFnwkXvtZ1-IxRIY0VezW0P9e_HE/edit

Read `docs/DEVELOPMENT_PLAN.md`, `docs/ARCHITECTURE.md`, and the current
`docs/CHECKPOINT.md`. Repository notes describe implementation, not a competing
product specification. Record the live revision used for each checkpoint.

* Follow SDD Section 30 and Shael's October 11 full-coverage amendment. Every
  registered chord, quality, inversion and note register must play in every pack.
  Mode is guidance; borrowed chords remain playable. The Governor selects musical
  events; `coverage.py` prepares native/reconstructed assets outside the audio loop.
* Keep sample preparation, event resolution, native playback, downstream DSP,
  vocal processing, and future plug-in hosting separate.
* Follow SDD Section 31 for the default step sequencer. Pitch/kit rows, saved
  expression, swing/offsets/flams, mono/poly entry, reuse, audition and MIDI
  interchange use the same validated musical resolver. Grid changes preserve
  off-grid notes. Revalidate every expanded trigger at its actual harmony position.
  Do not introduce general mixer/effect automation or confuse MIDI interchange
  with a full-fidelity save or external MIDI-device capture.
* Native samples win; source-informed reconstruction supplies unrecorded targets,
  sustained pitched gates and missing offered kit slots. Identify modeled sounds
  honestly, preserve source hashes, and never relabel them as extracted recordings.
  Preserve exact-pitch conflicts and intentionally empty optional extras.
* Never present synthetic fixtures as extracted song material or listening proof.
* Preserve all approved v1 scope, including Linux VST3 and vocal comping, in the
  development plan even when a checkpoint implements only a subset.
* Do not add network access, model downloads, or API keys to the music runtime.
* Run `make check` and `make demo` for engine/contract changes. Test cases must
  exercise musical, security, or persistence invariants, not mirror code.
* Keep coherent commits small; push and verify remote HEAD when available.
* The repository remains private until Shael authorizes public distribution.
* Do not build/publish an installable AI skill without reading the skill-creator
  instructions. Shared contracts alone do not constitute a working builder skill.

