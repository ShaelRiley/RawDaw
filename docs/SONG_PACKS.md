# Five source-based Song Packs

The user authorized selecting the first three Creative Commons songs and pushing a build
containing their Song Packs. Artist upload pages were checked on 2026-10-09;
each audio upload lists CC BY 3.0. This differs from the site's license for its
page text. Sources were processed locally. No original complete recording or
stem is distributed in the prepared packs.

The October 14 update adds Jonathan Coulton's **Shop Vac** from the genuine
JoCo Looks Back source tracks and retains Shael Riley's authorized Parachute
as the fourth source. The immutable pack archives preserve their recorded crop
inventory and provenance. A separate, hash-bound prepared bank now supplies
all 128 lead and bass pitches, every registered chord root/quality and the
standard percussion palette through source-waveform transformations. Native
recordings remain preferred. See `HARMONIC_COVERAGE.md` for preparation limits;
these functional banks do not constitute a pack-wide listening assessment.

## Selection and credits

| Pack / source page | Artist / credited ingredients | Why it was selected |
| --- | --- | --- |
| [Reach Out (Stems)](https://ccmixter.org/files/jlbrock44/32919) | spinningmerkaba; lead from guitar-solo-extras, rhythm from acoustic guitar, bass and drum stems | Direct pop/rock reference; short strums and expressive electric guitar against low bass |
| [Where You Are Now](https://ccmixter.org/files/Benjamin_Orth/33036) | Benjamin Orth featuring WolfFly; synth-pad/bass/drum stems; [credited original vocal](https://ccmixter.org/files/ascension/27734) by Rhiannon Delpero (SizzleFly), WolfFly / Ascension | Vocal fragments plus sustained synth timbres; minor/Dorian alternatives using native different chord qualities |
| [Auld Lang Syne (Bossa)](https://ccmixter.org/files/unreal_dm/29684) | unreal_dm; Lead 1, piano, bass, drums and percussion stems | Lighter articulation; real whole dominant/major seventh chords and two distinct percussion extras |

All three: [CC BY 3.0](https://creativecommons.org/licenses/by/3.0/).
Retain the named artists, source links, license link and indication of changes
when distributing the packs or renders. Application MIT licensing does not
relicense these assets. Attribution is embedded in `ATTRIBUTION.json`,
`provenance.json`, the clip index and each project. No endorsement is implied.

The vocal is the credited upstream recording used in the selected song, with
its own matching CC BY license and hash. It is not an unrelated source fill.
Its time positions refer to that ingredient, and no stem-to-master alignment
or remix offset is claimed as verified.

## Prepared coverage

| Pack | Assets | Native whole chords (root/quality and voicing estimates) | Demonstration A / B |
| --- | ---: | --- | --- |
| Reach Out | 21 | B minor, G major, A major | B natural minor / D major; 113 / 126 BPM; 4 / 8 Governor segments |
| Where You Are Now | 25 | C minor, F major, A-flat major, B-flat major | C natural minor / C Dorian; 100 / 118 BPM; 4 / 6 segments |
| Auld Lang Syne (Bossa) | 23 | F major, C dominant seventh, D minor, B-flat major seventh | F major / D natural minor; 130 / 110 BPM; 4 / 3 segments |
| Parachute | 28 | B-flat minor, D-flat major seventh, E-flat minor, G-flat major, F major | B-flat natural minor / B-flat harmonic minor; 165 / 132 BPM; 4 / 8 segments |
| Shop Vac | 26 | C-sharp power/minor, E major, G-sharp major, A major seventh, B dominant seventh; documented source inversions | E major / C-sharp natural minor; 150 / 128 BPM; two short arrangements |

Each pack supplies real lead, rhythm, bass, kick, snare and closed-hat candidates.
Open hat, tom 1 and tom 2 are explicitly unavailable because isolated identities
have not been established. Reach Out has one source crash extra and an empty
second extra. The synth pack has a bright backbeat/clap and a longer cymbal;
the bossa pack has low/high hand percussion. Percussion labels remain estimates.
No stock content or synthetic fill was introduced into the recorded inventory.

The table records the original native crop inventory, rather than the complete
prepared playback inventory. Unrecorded pitches/chords now derive from the
nearest appropriate source waveform, and sustained gates use prepared
continuations. The original source archives remain one-shots with no sustain
loops. Source role identities, isolation, percussion labels and listening quality
remain provisional. Short vocal fragments are a lead sound bank, not complete
words or a replacement for microphone/comp/correction features.

## Fourth source — Parachute

Shael Riley supplied `Parachute Stems(1).zip` and explicitly authorized preparing
this fourth pack, stating that he created the song using Suno and holds a paid
account permitting this use. This is recorded as a **user declaration**, not
independent legal verification. Parachute is not relicensed as CC BY or MIT.
Its rights, credit and private-build scope are retained in the manifest,
`provenance.json`, clip provenance and project credits.

The supplied archive SHA-256 is:

```text
0a6202d0a6aa58f4b9a1172c146b75225d6cffd2a497c0255a27f15fbad62054
```

All nine WAV stems have 7,315,200 frames (152.4 seconds), 48 kHz, 16-bit stereo,
and a common file origin. No original master was supplied; equal dimensions
are not a claimed acoustic alignment test. The source archive and complete
stems stay outside the product tree. `recipes/parachute.json` pins every input
hash, dimensions, accepted crop, estimated identity and source timing.

The selected ensemble uses **Lead Vocals, Guitar, Bass and Drums** consistently:
12 native vocal-note fragments, five native complete guitar chords, eight
native bass notes, and a kick, snare and closed hat. These 28 assets have no
pitch variants, harmonic reconstruction, synthetic replacement or sustain
loops. Cleanup uses bounded gain calibration, DC removal and boundary fades;
drum/chord crops preserve 18 ms pre-roll with a separate onset marker.

Open hat and both toms remain unavailable. Both optional extras are empty:
short resonant Percussion-stem events have uncertain identities/pitch, and
the other supplied stems do not serve as arbitrary drum substitutes.

Drum timing supports approximately 165 quarter-note BPM, with an 82.5 BPM
half-time interpretation retained. The stored seven-hit measure is an
**estimated partial audio transcription**, not Suno-original MIDI or a verified
reconstruction of every overlapping hit. Numerical onset times and deliberate
sixteenth-grid corrections are saved. Chord/tonal candidates also remain
estimates; the pack does not claim a full-song key/modulation or chord map.

Parachute A uses B-flat natural minor at 165 BPM and B uses B-flat harmonic
minor at 132 BPM. The latter selects the already-stored F-major guitar chord
for the raised leading tone. Both are new editable four-bar arrangements.

To reproduce, place the original unchanged ZIP at
`SOURCE_ROOT/parachute/Parachute-Stems.zip`, alongside its nine original WAV
entries with the supplied names, then run:

```bash
OPENBLAS_NUM_THREADS=1 python3 tools/prepare_cc_packs.py \
  --sources SOURCE_ROOT --recipes recipes/parachute.json
make check
make source-demo
```

Changed source hashes and false whole-chord labels fail preparation and
preserve the prior pack. Repeated preparation is byte-identical with the
recorded tool versions. Both new renders pass exact repeat/seek/immutability
checks. See `docs/validation/parachute-preparation.json` and
`source-render-0.2.1.json`. Listening, percussion identity, inversion/isolation,
full source analysis and reference-device checks remain open.

## Fifth source — Shop Vac

Jonathan Coulton's [JoCo Looks Back source-track archive](https://archive.org/details/JonathanCoultonJoCoLooksBackSourceTracks)
contains the actual **Shop Vac** multitracks. The archive identifies Jonathan
Coulton as creator and preserves his source-track readme. The selected
ingredients are the lead vocal, bass, acoustic guitar and drum tracks, with
separately documented optional percussion. They are source stems from this
recording, rather than a reconstructed cover or substitute sound bank.

The archive metadata links **CC BY-NC 4.0**, while the
[artist's FAQ](https://www.jonathancoulton.com/faq/) identifies **CC BY-NC 3.0**.
Both observations remain in the recipe's license evidence; the pack does not
silently recast the noncommercial grant as CC BY or MIT. Attribution names
Jonathan Coulton, links the source and license evidence, and identifies cropping,
cleanup, estimated transcription and later waveform transformations. Use of
this pack and its rendered derivatives remains subject to that noncommercial
permission unless the artist separately grants commercial rights.

The source-track readme supplies a 150 quarter-note BPM reference and cautions
that stems may need adjustment to align to a tempo grid. The selected MP3 tracks
have matching probed durations of 210.442449 seconds and a 44.1 kHz
source sample rate, with mono/stereo differences retained in the input audit.
Matching dimensions are not a claimed acoustic alignment check. Each accepted
crop binds to its original ingredient's SHA-256 and source-local seconds.

The accepted native inventory contains eight vocal-note fragments, eight bass
notes, six complete acoustic-guitar chords and four percussion crops (kick,
snare, closed-hat candidate and the separate hand-clap track). Chord/inversion
and percussion identities remain measured estimates. These 26 source crops
feed the same complete prepared note/chord/percussion bank as the other packs;
the remaining offered targets use explicitly attributed source-derived PCM.

`recipes/shop-vac.json` supplies two new editable short arrangements, A and B,
using different harmonies. These are composition demonstrations built from the
source bank, rather than a recreation of the complete original song. The four
existing full-length demos remain available; Shop Vac does not advertise an
unwritten full-length arrangement. The archive's **The Radio** and **Vincent Solo**
tracks are excluded from pack ingredients because they contain separate
third-party material.

## Reproduce the first three CC packs

Local bank preparation requires NumPy; the native audio processing loop remains
independent of Python. Rebuilding source crops additionally requires
FFmpeg/ffprobe with the Rubber Band filter and SciPy. Recorded preparation
versions include NumPy 2.3.5 and SciPy 1.17.0; these system tools are not bundled.

```bash
python3 tools/fetch_cc_sources.py --sources ../source-work
OPENBLAS_NUM_THREADS=1 python3 tools/prepare_cc_packs.py --sources ../source-work
make check
make cc-demo
```

`recipes/cc-songs.json` pins input sizes, SHA-256s, source/license pages, archive
hashes, exact ingredient-local crops, estimated pitches/chords, normalized source
drum timing and every variant. Public downloads are artist files only; hash
changes fail instead of silently choosing a new input. Downloaded files stay
outside the product tree. Supplying the already acquired inputs avoids network
access. The fetch command's hash verification was exercised against all local
inputs; its fresh network route was not used for this checkpoint acquisition.

`tools/source_analysis.py` produces offline diagnostic candidates. It is not a
trained separator or a general song-transcription system. Author-provided stems
were chosen after dependency preflight; no separation model was available or
claimed. Candidate corrections are saved in the recipes rather than regenerated
on every pack rebuild.

The preparation profile performs DC removal, gain calibration capped at +12 dB,
and short boundary fades. All assets are ordinary 48 kHz / 24-bit stereo PCM.
One Reach Out crash candidate has a documented preparation-only 1.8 kHz high-pass
filter to reduce overlapping low drums while retaining the longer decay.
Pitched note variants are rendered offline from identified source notes:
10 total, at most 3.25 semitones including measured source-tuning compensation.
Vocal variants preserve formants through the preparation processor. Their
measured pitch checks remain in `qa/report.json`. Whole chords are native cuts;
no major-to-minor uniform transposition or runtime chord construction is used.

Single-note screens require at least three accepted pitch frames, median within
45 cents of the target and a 10th–90th percentile spread no greater than 70 cents.
Whole-chord harmonic-template screens require every expected pitch class at
least 0.18 relative strength, every outside class at most 0.25, and residual at
most 0.8. These are bounded prototype screens, not validated release-quality
thresholds or proof of separation, instrument identity, inversion or listening.
Original float crops are retained in the preparation working directory with
SHA-256s in the audit. Prepared PCM hashes are separately bound to the manifest.
FFmpeg, NumPy and SciPy versions are recorded.

Each pack has one estimated audio-derived drum measure. Its source time,
pre-normalization onset assignments and sixteenth-note timing corrections are
retained. The included SMF uses the original stated tempo and stable semantic
drum addresses. It is not artist-original MIDI. Demo extra accents are separately
identified as new authorship rather than additions to the source transcription.

## Verification and release gate

The loader checks the five `.prdepack` archives, checksums, PCM dimensions,
prepared mappings, JSON contracts and source MIDI. The catalog supplies fourteen
projects (ten short arrangements and four full-length demos) for resolution and
save/reopen verification. Native exports require no missing-material approval. Repeated exports
are byte-identical; verified seeks equal the full-render PCM slices (frame 123457
for short auditions; three quarters into each full song); source
packs remain unchanged. See `docs/validation/cc-check.log` and `cc-render.json`.

**Human listening was not performed.** Source-wide key/mode/chord timing and
stem alignment are incomplete. Artist stems may include baked processing and
individual drums may retain overlap. Percussion identity, attack integrity,
loop suitability and perceptual pitch/formant quality require listening review.
All manifests say `coverage-limited`; QA says `releaseQualityGate: open`.

This build demonstrates real-source preparation and playback. It does not close
the SDD's sound-quality, full public builder, desktop, DSP, recording, VST,
reference-device or release gates.
