# PRDE1 — Pop Rock Development Environment 1

Checkpoint 1 is an executable offline prepared-sample core. It validates song
packs, resolves editable musical events under the Chord Governor, saves/reopens
native project manifests, and renders two different harmonic arrangements.
**It is not yet the desktop DAW or a source-extraction system.**

The [live SDD](https://docs.google.com/document/d/1qb6LWTgkk3vVJB3aFnwkXvtZ1-IxRIY0VezW0P9e_HE/edit)
is the canonical product/design authority. Read [the checkpoint](docs/CHECKPOINT.md)
for precise implementation and verification limits.

## Build and hear the checkpoint

Requires Linux, Python 3.11+, GNU Make, and a C++20 compiler. No API key, Python
package installation, model, download, or network access is used by these commands.
The sole C++ source dependency is vendored with its license and hash.

```bash
cd prde1
make check
make demo
```

Open `out/demo/major.wav` and `out/demo/minor.wav` in a media player. Each is an
eight-second, 48 kHz, 24-bit stereo passage. They use the same prepared synthetic
bank under C-major I–V–vi–IV and A-natural-minor i–VI–III–VII. Every sound is
explicitly synthetic; there is no extraction-quality or human-listening claim.

The downloadable checkpoint includes ready-rendered auditions under `auditions/`.
Build from source for your machine; container-built binaries are not a tested
Steam Deck release.

## Edit, validate, and render

```bash
python3 -m prde1 validate-pack out/demo/synthetic.prdepack
python3 -m prde1 rank out/demo/synthetic.prdepack --tonic 0 --mode major
python3 -m prde1 resolve out/demo/synthetic.prdepack out/demo/major.prdeproj out/demo/events.json
python3 -m prde1 render out/demo/synthetic.prdepack out/demo/major.prdeproj out/demo/edited.wav
python3 -m prde1 save-project out/demo/major.prdeproj out/demo/reopened.prdeproj
```

Edit the project JSON to change harmony, quarter-note tempo, rational event
positions, notes, gates, gain/pan, and static compressor settings. Chord quality
is explicit: uppercase V is not a spelling variant of lowercase v. Musical
positions such as `1/3` remain rational; the Governor display grid does not snap
performance events. Project/pack references are exact and versioned.

The `resolve` command reports preserved harmonic conflicts and duration limits.
Missing prepared sounds block ordinary export. An explicit
`--approve-altered-render` permits the reported missing material to stay silent.
This is also required for unsupported VST instrument placeholders. Active
unsupported effects or vocal processing block export; their settings are not
silently dropped. Future native hosting is still required.

For a seek comparison, add `--seek-frame 123457` to `render`. This checkpoint
reconstructs state from the beginning; the output matches that slice of a full
render, including compressor state and deterministic TPDF dither.

## What is implemented

* Shared experimental JSON contracts, secure archive loading, checksums, PCM and
  marker checks, bounded SMF inspection, explicit missing/empty roles and slots.
* Strict chord-tone Governor, explicit quality/inversion, prepared asset selection,
  semantic drum identity, pitched-extra withholding and coverage-only ranking.
* Rational timing and tempo maps; deterministic Play/Change, double-trigger,
  gate and nearby-note variation; independent/linked copy helpers.
* Native sample-clock mixing, 64-voice rejection, monophonic scheduling, hat
  choke, validated sustain-only looping, natural limits and 5 ms de-click fades.
* Static gain/pan, one common final compressor, transactional 24-bit stereo WAV
  exports and native JSON manifest saves.

## Remaining production gates

Authorized real-source extraction and listening; public pack-builder skill;
desktop workspace/device playback; complete musical/pattern libraries; Freeze
Variation UI and undo history; microphone capture/retakes/comp playback and
recovery; reversible vocal correction; complete fixed effects graph; Linux VST3
hosting/state recovery and cleared starter bundle; full project/media migrations;
device stress, accessibility, usability, installer and release testing.

These capabilities remain approved v1 scope. See [the development plan](docs/DEVELOPMENT_PLAN.md).

Application code: MIT. Dependencies and content retain their own terms; see
[the component manifest](docs/COMPONENTS.md).
