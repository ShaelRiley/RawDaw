# PRDE1 development

Read the live canonical SDD before selecting or changing product behavior:
https://docs.google.com/document/d/1qb6LWTgkk3vVJB3aFnwkXvtZ1-IxRIY0VezW0P9e_HE/edit

Read `docs/DEVELOPMENT_PLAN.md`, `docs/ARCHITECTURE.md`, and the current
`docs/CHECKPOINT.md`. Repository notes describe implementation, not a competing
product specification. Record the live revision used for each checkpoint.

* The Chord Governor selects events and existing assets. No waveform processing,
  pitch shifting, playback-rate transposition, stretching, or chord synthesis.
* Keep sample preparation, event resolution, native playback, downstream DSP,
  vocal processing, and future plug-in hosting separate.
* Never substitute sounds for missing pack coverage. Preserve authored conflicts.
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
