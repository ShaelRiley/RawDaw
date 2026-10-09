# PRDE1 — Pop Rock Development Environment 1

Build **0.2.0** includes an offline Linux sample renderer, **three CC Song Packs**,
and six editable demo arrangements. The Governor selects prepared samples;
harmonic changes never pitch-shift or stretch audio during playback.

This is a development build. Desktop editing/device playback, recording, full
DSP and VST hosting remain to be implemented. Pack listening and complete source
analysis remain open; see [the checkpoint](docs/CHECKPOINT.md).

The [live SDD](https://docs.google.com/document/d/1qb6LWTgkk3vVJB3aFnwkXvtZ1-IxRIY0VezW0P9e_HE/edit)
is the canonical product/design authority.

## Run the three packs

The distribution in `dist/PRDE1_0.2.0_Linux_x86_64.tar.gz` contains a compiled
Linux x86_64 renderer, Python control code, three packs, six projects and six
ready-rendered WAV auditions. Extract it, enter its folder and run:

```bash
./run-demos.sh
```

Python 3.11+ is required. The supplied binary was built/tested on Ubuntu 24.04
x86_64; rebuild with `make all` on other supported Linux systems. No source
preparation packages, model downloads or network access are needed to play
these prepared packs. This is not a tested Steam Deck installer.

From a source checkout, GNU Make and a C++20 compiler are also required:

```bash
make check
make cc-demo
```

Open `out/cc-auditions/*.wav`. Each four-bar arrangement has different harmony,
tempo or variation settings. All six exports use actual source assets and need
no altered-render approval.

| Song Pack | Source sound and demonstrations |
| --- | --- |
| Reach Out (Stems) — spinningmerkaba | Acoustic whole chords, electric guitar lead, low bass; B natural minor and D major |
| Where You Are Now — Benjamin Orth / WolfFly | Credited Rhiannon vocal, synth pad and bass; C natural minor and C Dorian |
| Auld Lang Syne (Bossa) — unreal_dm | Melodic lead, piano triads/sevenths and hand percussion; F major and D natural minor |

Prepared content is **CC BY 3.0** with attribution and changes recorded in each
pack. Code is MIT. [Source credits, coverage and preparation](docs/SONG_PACKS.md)
identify every ingredient and the remaining listening checks.

## Edit, validate and render

```bash
python3 -m prde1 validate-pack packs/reach_out.prdepack
python3 -m prde1 rank packs/reach_out.prdepack --tonic 11 --mode natural_minor
python3 -m prde1 resolve packs/reach_out.prdepack packs/reach_out_a.prdeproj out/events.json
python3 -m prde1 render packs/reach_out.prdepack packs/reach_out_a.prdeproj out/edited.wav
python3 -m prde1 save-project packs/reach_out_a.prdeproj out/reopened.prdeproj
```

Project JSON preserves exact pack references, harmony, rational event timing,
quarter-note tempo maps, gates, variation seed, gain/pan and compressor state.
Explicit qualities and inversions are distinct. Governor segments do not snap
performance timing. Missing sounds block ordinary export; `resolve` reports
conflicts and natural sample-duration limits. Unsupported active effects or
vocal processing also block export. Explicit `--approve-altered-render` permits
reported missing material or unsupported VST instrument placeholders to remain
silent. It is unnecessary for the six included arrangements.

Add `--seek-frame 123457` to `render` to reconstruct state from the beginning.
For this engine, the rendered result equals the corresponding full-render slice,
including compressor and dither state. This is not a promise for future plug-ins.

`make demo` retains the two explicitly synthetic regression fixtures. They prove
core behavior and are separate from the three actual-source packs.

Application code: MIT. Dependencies/content retain their terms;
see [components](docs/COMPONENTS.md) and [remaining scope](docs/DEVELOPMENT_PLAN.md).
