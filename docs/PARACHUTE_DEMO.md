# Parachute — full-length demonstration, 0.3.2

The full demo lasts **2:42.91**: 112 bars of 4/4 at 165 quarter-note BPM. It uses
only the existing 28-asset Parachute Song Pack and is saved as the ordinary
editable `packs/parachute_full.prdeproj`. Open it with:

```bash
./run-prde1.sh --project packs/parachute_full.prdeproj
```

The Browser → Packs button **Full Parachute demo · 2:43** also opens it. Press Play.
Save As retains your changes separately from the bundled example. The extracted
distribution includes the exact ready-rendered `auditions/parachute_full.wav`.

| Section | First bar | Bars | Starts | Arrangement |
| --- | ---: | ---: | --- | --- |
| Intro | 1 | 4 | 0:00.00 | Guitar first; bass, drums and a vocal-sample pickup enter |
| Verse 1 | 5 | 16 | 0:05.82 | Sparse lead phrases and a restrained pulse |
| Pre-chorus 1 | 21 | 8 | 0:29.09 | Added motion; F-major dominant leads into the chorus |
| Chorus 1 | 29 | 16 | 0:40.73 | Repeating four-bar lead hook and a fuller groove |
| Verse 2 | 45 | 16 | 1:04.00 | Extra pickup notes, syncopation and bounded saved variation |
| Pre-chorus 2 | 61 | 8 | 1:27.27 | The recognizable rise returns |
| Chorus 2 | 69 | 16 | 1:38.91 | The same lead hook returns |
| Bridge | 85 | 8 | 2:02.18 | Half-time drum phrasing and longer vocal-sample notes |
| Final chorus | 93 | 16 | 2:13.82 | Original lead hook, stronger phrase-ending snare fills |
| Outro | 109 | 4 | 2:37.09 | Thinning MIDI dynamics and a deliberate B-flat-minor ending |

Harmony uses the prepared B-flat minor, D-flat major seventh, E-flat minor,
G-flat major and F major whole-guitar samples. The F-major dominant cadences
explicitly select B-flat harmonic minor at their actual positions; the other
sections use B-flat natural minor. Lead/bass remain strict covered chord-tone
selections. The recurring lead hook is explicitly Linked Repeat and locked
against variation; Make independent creates an editable occurrence. Verse 2's
small probability/gate/neighbor changes use the saved deterministic seed.

These are new authored performance patterns, not a transcription of the original
Suno song or newly recorded complete lyrics. Drum fills use the actual kick,
snare and closed hat; no unavailable drum sound is invented. Event gates and
velocities supply the phrasing and dynamics. No source waveform, playback rate, sample
pitch or Song Pack is altered.

Version 0.3.2 keeps this score and applies the sampler boundary fix: a 1 ms
start safety fade and smooth 5 ms release at each voice cutoff, including
retriggers. The ready-rendered full demo includes the fix; Song Pack bytes stay
identical. See [sample boundaries](SAMPLE_BOUNDARIES.md).

Rebuild the score with `python3 tools/build_parachute_demo.py`, then use
`make source-demo` to render/verify all nine included arrangements. The full demo
re-renders byte-identically; seeking three quarters into the song produces the
exact corresponding PCM slice. All 112 measures have authored music and measured
signal. The export is 48 kHz, 24-bit stereo, peaks at approximately −9.26 dBFS,
and has no unresolved sample/harmony requests. Automated section measurements
show the chorus above the verse and final chorus above the bridge; subjective
judgment belongs to the creator's next audition.

`packs/parachute_full.arrangement.json` describes this score's section timings.
It is companion documentation, not implemented generic Song Plan or section-lock
state. The full Song Plan, recording/comping, effects and VST scope stays in the
development plan. Source rights/credits and the original eight short arrangements
are preserved.
