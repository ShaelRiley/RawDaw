# Raw Daw

**Really Awesome Workflow Digital Audio Workstation**

**Build 0.4.0:** source-derived sample banks and timeline looping. Lead and bass
cover all 128 MIDI notes. Chords cover 12 roots × 35 common qualities, including
sixths, ninths, elevenths, thirteenths, suspended and altered dominants. Native
recordings win; missing targets are prepared by transforming recorded waveforms,
with no substitute synthesizer. Quality depends on source isolation and the
distance of the pitch shift. [Sample-bank method](docs/HARMONIC_COVERAGE.md).
Percussion covers all **47 standard General MIDI drum addresses (35–81)**,
with native hits preferred and missing articulations derived from recorded hits.

**Shop Vac by Jonathan Coulton** is the fifth bundled bank, extracted from his
official multitrack stems, with two editable arrangements. This bank retains
**CC BY-NC 3.0: attribution and noncommercial use**; its content is separate from
the application's MIT code license.

Drag a timeline clip to move it, or drag its **right edge** to repeat its source
pattern. Click **↻ beside a track name** to repeat that track's source cycle to
the song ending. **Loop song** repeats transport playback. Repeats follow the
actual destination harmony and pulse; edits, undo and saved sessions retain them.
[Clip and track controls](docs/CLIP_LOOPS.md).

Formerly PRDE1. **703 distinct one-bar MIDI clips** cover Bass (175), Drums (247),
Lead (169) and Chords (112). Browser → MIDI clips provides search, style/role/meter
filters, favorites, looping preview, drag/drop and a Place button. Pitched clips
follow your loaded bank and chord progression; placement never changes harmony.
Use **New song**, choose a progression, and begin placing bars on empty tracks.
The half-black, half-white dog with a spiked collar is the new app mascot.

**Choose progression** opens a bank of **206 distinct chord progressions**.
Start with twelve best fits for your key/mode, or browse all loops, cadences,
seventh-chord colors, blues and modal choices. Preview, load into the song and
edit afterwards. **Bank…** imports progression files, saves current harmony,
exports your bank and manages favorites. **Custom…** remains available and can
save a reusable preset. [Progression controls and import formats](docs/PROGRESSIONS.md)
explain the bank.

**Rhythmic Pulse Governor**, below the Chord Governor, offers **Off** (authored
volumes), **Guide** (editable defaults for new notes) and **On** (accents govern
each sounding hit). Presets and custom accent levels repeat within each measure.
Switching Off restores stored note volumes. Existing projects default to Off.
See [the clip library and pulse controls](docs/CLIP_LIBRARY.md) for sources,
kit/meter behavior and credits. Existing saves, settings and launch commands work.

**Default step sequencer:** bass/lead use labeled pitch rows; drums use named kit
rows. **Preview notes** is on by default: hear notes as you click, drag or enter
them, and switch it off for quiet editing. Each note has a visible volume
slider/percentage and dynamics bars. Draw/erase
steps, edit velocity and gates, tie notes, add flams, apply swing,
mute/solo rows, fill/copy/shift/reverse patterns, and audition a loop independently.
Keyboard step entry, full `.prdepattern` saves and note MIDI interchange are included.
See [step-sequencer controls](docs/STEP_SEQUENCER.md).

**Full harmonic coverage:** all 420 root-position chords and every valid inversion
are addressable in every shipped pack (1,860 registered voicings). Root voicings
form the compact complete bank; additional inversions are prepared on demand.
Borrowed chords play even outside the selected mode. Missing offered kit slots
derive from the closest suitable recorded percussion. Source recordings and
saved pack references remain intact. See [the methodology](docs/HARMONIC_COVERAGE.md).

The build includes **four complete song demos**: Reach Out (2:32.92),
Where You Are Now (2:33.60), Auld Lang Syne (Bossa) (2:42.46), and Parachute
(2:42.91). Each has an intro, verses, pre-choruses, a recurring chorus hook,
bridge, final chorus and outro. The native graphical editor ships five Song
Packs and fourteen editable arrangements, including two new Shop Vac demos.
Per-drum EQ now feeds a compressed drum bus with a +3 dB lift. The kick ducks
only bass, then the whole ensemble reaches the master compressor. **Mixer** and
**Dynamics** provide saved controls and bypasses; [mixing details](docs/MIXING.md)
explain the defaults. New songs and four full demos use the punch preset; older
saves have an explicit Apply punch mix button.
The Chord Governor selects prepared samples;
harmonic changes never pitch-shift or stretch audio during playback.

The 0.3.2 boundary fix remains active: a 1 ms safety fade at sample starts and
a smooth 5 ms release. Existing installations automatically receive the current
renderer after pulling. [Boundary behavior and evidence](docs/SAMPLE_BOUNDARIES.md)
explain the sampler fix.

This is a development build. Recording/comping, full DSP, VST hosting, complete
catalogs, and a real-time native device engine remain approved work. The desktop
auditions a background-rendered version of the arrangement through Qt Multimedia.
Pack listening and reference-device testing remain open; see
[the checkpoint](docs/CHECKPOINT.md).

The [live SDD](https://docs.google.com/document/d/1qb6LWTgkk3vVJB3aFnwkXvtZ1-IxRIY0VezW0P9e_HE/edit)
is the canonical product/design authority.

## Launch the desktop

From your existing repository folder:

```bash
git pull --ff-only origin main
./run-raw-daw.sh --project packs/parachute_full.prdeproj
```

For a **Raw Daw** application-menu entry with the dog icon, run
`./install-raw-daw.sh` once. The existing `run-prde1.sh` command remains compatible.

First launch installs PySide6 and NumPy into a local virtual environment if needed.
That setup needs an internet connection; the installed composer then operates
offline without an API key. The launcher restores the verified compiled renderer
from the pulled build parts, replacing an older executable when needed. Python 3.11+ is required. On Ubuntu/Linux
Lite, a missing virtual-environment or X11 cursor dependency can be installed with
`sudo apt install python3-venv libxcb-cursor0`.

Press **Play** to hear the full Parachute demo. In **Browser → Packs**, choose
any song in **Full-length demos** and click **Load full demo** to hear and edit
the complete arrangement. [The full demo scores and section timings](docs/FULL_DEMOS.md)
describe their forms. Select a pattern in the timeline and click its
steps to edit. **Choose progression** loads harmony from the bank; **Edit chord**
and **Custom…** let you author it. **Save**
writes a native project and **Export WAV** creates the stereo mix. The Browser
loads all twelve included arrangements. [Desktop controls](docs/DESKTOP.md)
explain the remaining controls and current boundaries.

![PRDE1 full-length demo selector](docs/validation/PRDE1-0.3.3-full-demos.png)

## Compiled distribution and command-line auditions

The current 0.4.0 parts contain a small verified **renderer upgrade** for the
source checkout. `./run-prde1.sh` installs it automatically; keep using the
repository's code, five packs and fourteen projects. A compiler is not
required for this upgrade. Do not extract this renderer-only update as a full app.

The older complete 0.3.3 distribution remains preserved with its original WAV
mixes. To reconstruct that historical build explicitly:

```bash
python3 tools/assemble_build.py dist/PRDE1_0.3.3_Linux_x86_64.parts.json
tar -xzf dist/PRDE1_0.3.3_Linux_x86_64.tar.gz
```

For command-line regeneration of the included auditions, run:

```bash
./run-demos.sh
```

Python 3.11+ is required. The supplied binary was built/tested on Ubuntu 24.04
x86_64; rebuild with `make all` on other supported Linux systems. No source
model downloads or network access are needed to play these packs after initial
dependency installation. NumPy prepares missing targets outside audio playback.
This is not a tested Steam Deck installer.

To rebuild and test the source, GNU Make and a C++20 compiler are required:

```bash
make check
make source-demo
```

Open `out/source-auditions/*.wav`. Each four-bar arrangement has different harmony,
tempo or variation settings; each Full arrangement adds a complete song form. All twelve
exports use actual source assets and need
no altered-render approval.

| Song Pack | Source sound and demonstrations |
| --- | --- |
| Reach Out (Stems) — spinningmerkaba | Acoustic whole chords, electric guitar lead, low bass; B natural minor and D major |
| Where You Are Now — Benjamin Orth / WolfFly | Credited Rhiannon vocal, synth pad and bass; C natural minor and C Dorian |
| Auld Lang Syne (Bossa) — unreal_dm | Melodic lead, piano triads/sevenths and hand percussion; F major and D natural minor |
| Parachute — Shael Riley | Sampled lead vocal, native whole guitar chords and bass; B-flat natural minor and B-flat harmonic minor |

The first three packs are **CC BY 3.0**. Parachute retains **Shael Riley's user
authorization and Suno paid-account rights declaration**, with no CC grant
implied. Credits and changes are recorded inside each pack. Code is MIT.
[Source credits, coverage and preparation](docs/SONG_PACKS.md)
identify every ingredient and the remaining listening checks.

## Edit, validate and render

```bash
python3 -m prde1 validate-pack packs/reach_out.prdepack
python3 -m prde1 rank packs/reach_out.prdepack --tonic 11 --mode natural_minor
python3 -m prde1 resolve packs/reach_out.prdepack packs/reach_out_a.prdeproj out/events.json
python3 -m prde1 render packs/reach_out.prdepack packs/reach_out_a.prdeproj out/edited.wav
python3 -m prde1 save-project packs/reach_out_a.prdeproj out/reopened.prdeproj
python3 -m prde1 render packs/parachute.prdepack packs/parachute_a.prdeproj out/parachute.wav
python3 -m prde1 render packs/parachute.prdepack packs/parachute_full.prdeproj out/parachute_full.wav
```

Project JSON preserves exact pack references, harmony, rational event timing,
quarter-note tempo maps, gates, variation seed, gain/pan and compressor state.
Explicit qualities and inversions are distinct. Governor segments do not snap
performance timing. Missing sounds block ordinary export; `resolve` reports
conflicts and natural sample-duration limits. Unsupported active effects or
vocal processing also block export. Explicit `--approve-altered-render` permits
reported missing material or unsupported VST instrument placeholders to remain
silent. It is unnecessary for the twelve included arrangements.

Add `--seek-frame 123457` to `render` to reconstruct state from the beginning.
For this engine, the rendered result equals the corresponding full-render slice,
including compressor and dither state. This is not a promise for future plug-ins.

`make demo` retains the two explicitly synthetic regression fixtures. They prove
core behavior and are separate from the four actual-source packs.

`make cc-demo` remains an alias for `make source-demo`.

Application code: MIT. Dependencies/content retain their terms;
see [components](docs/COMPONENTS.md) and [remaining scope](docs/DEVELOPMENT_PLAN.md).

