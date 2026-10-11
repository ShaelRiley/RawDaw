# Four full-length demo scores

Build 0.3.3 gives every included Song Pack a complete editable 2–3 minute
demonstration. The eight short A/B auditions remain available. These scores
are newly authored performances of the prepared source material, not exact
transcriptions of the original recordings. Every measure contains music.

| Full project | Duration | Bars | Quarter BPM | Resolved events |
| --- | --- | --- | --- | --- |
| `reach_out_full.prdeproj` | 2:32.92 | 72 | 113 | 1,594 |
| `where_you_are_now_full.prdeproj` | 2:33.60 | 64 | 100 | 1,427 |
| `auld_lang_syne_bossa_full.prdeproj` | 2:42.46 | 88 | 130 | 2,200 |
| `parachute_full.prdeproj` | 2:42.91 | 112 | 165 | 2,806 |

Open **Browser → Packs → Full-length demos**, choose a song and click
**Load full demo**. Or launch with:

```bash
./run-prde1.sh --project packs/reach_out_full.prdeproj
```

The source-only native renderer, 1 ms onset safety envelope and 5 ms smooth
release are unchanged from 0.3.2. No new source assets, real-time transposition,
stretching, normalization, stock percussion or invented sustain are used.

Reach Out uses acoustic Bm/G/A chords and electric-guitar calls, with a
syncopated chorus and half-time bridge. Where You Are Now uses chopped vocal
calls and a four-on-the-floor chorus; C natural minor verses (Cm/Ab/Bb) change
to C Dorian refrains (Cm/F/Bb), making the prepared F major legal. Auld Lang
Syne uses piano anticipations, F/C7/Bbmaj7/Dm, hand percussion and a D minor
bridge. The short C7 asset remains a deliberate piano stab. Available source
extras supply crash/cymbal/hand-percussion accents; open hats/toms remain absent.

Each score retains one linked, variation-locked chorus lead pattern through
three refrains. Verse 2 phrasing, later pre-chorus lifts, quieter bridges and
final accompaniment fills provide contrast. Saved seeded variations remain
stable when reopened. Companion `.arrangement.json` files describe section
timings; they do not implement generic Song Plan state or section locks.

Regenerate the three new scores with `python3 tools/build_full_demos.py`.
Parachute retains its approved score and separate authoring script
`python3 tools/build_parachute_demo.py`. Neither authoring script processes PCM.
Run `make source-demo` for all twelve verified WAV auditions.

## Form and section times

### Reach Out

| Section | Bars | Start → end | Chord cycle |
| --- | --- | --- | --- |
| Intro | 1–4 | 0:00.00 → 0:08.50 | Bm / Bm / G / A |
| Verse 1 | 5–12 | 0:08.50 → 0:25.49 | Bm / G / A / Bm |
| Pre-chorus 1 | 13–16 | 0:25.49 → 0:33.98 | G / G / A / A |
| Chorus 1 | 17–28 | 0:33.98 → 0:59.47 | G / A / Bm / Bm |
| Verse 2 | 29–36 | 0:59.47 → 1:16.46 | Bm / G / A / Bm |
| Pre-chorus 2 | 37–40 | 1:16.46 → 1:24.96 | G / G / A / A |
| Chorus 2 | 41–52 | 1:24.96 → 1:50.44 | G / A / Bm / Bm |
| Bridge | 53–60 | 1:50.44 → 2:07.43 | G / G / Bm / A |
| Final chorus | 61–68 | 2:07.43 → 2:24.42 | G / A / Bm / Bm |
| Outro | 69–72 | 2:24.42 → 2:32.92 | G / A / A / Bm |

### Where You Are Now

| Section | Bars | Start → end | Chord cycle |
| --- | --- | --- | --- |
| Intro | 1–4 | 0:00.00 → 0:09.60 | Cm / Cm / Ab / Bb |
| Verse 1 | 5–12 | 0:09.60 → 0:28.80 | Cm / Ab / Bb / Cm |
| Pre-chorus 1 | 13–16 | 0:28.80 → 0:38.40 | Ab / Bb / Ab / Bb |
| Chorus 1 | 17–24 | 0:38.40 → 0:57.60 | Cm / F / Bb / Cm |
| Verse 2 | 25–32 | 0:57.60 → 1:16.80 | Cm / Ab / Bb / Cm |
| Pre-chorus 2 | 33–36 | 1:16.80 → 1:26.40 | Ab / Bb / Ab / Bb |
| Chorus 2 | 37–44 | 1:26.40 → 1:45.60 | Cm / F / Bb / Cm |
| Bridge | 45–52 | 1:45.60 → 2:04.80 | Ab / Ab / Bb / Cm |
| Final chorus | 53–60 | 2:04.80 → 2:24.00 | Cm / F / Bb / Cm |
| Outro | 61–64 | 2:24.00 → 2:33.60 | Bb / Ab / Bb / Cm |

### Auld Lang Syne (Bossa)

| Section | Bars | Start → end | Chord cycle |
| --- | --- | --- | --- |
| Intro | 1–4 | 0:00.00 → 0:07.38 | F / F / Bbmaj7 / C7 |
| Verse 1 | 5–16 | 0:07.38 → 0:29.54 | F / Dm / Bbmaj7 / C7 |
| Pre-chorus 1 | 17–20 | 0:29.54 → 0:36.92 | Dm / Bbmaj7 / C7 / C7 |
| Chorus 1 | 21–36 | 0:36.92 → 1:06.46 | F / C7 / Bbmaj7 / F |
| Verse 2 | 37–48 | 1:06.46 → 1:28.62 | F / Dm / Bbmaj7 / C7 |
| Pre-chorus 2 | 49–52 | 1:28.62 → 1:36.00 | Dm / Bbmaj7 / C7 / C7 |
| Chorus 2 | 53–68 | 1:36.00 → 2:05.54 | F / C7 / Bbmaj7 / F |
| Bridge | 69–76 | 2:05.54 → 2:20.31 | Dm / Bbmaj7 / F / C7 |
| Final chorus | 77–84 | 2:20.31 → 2:35.08 | F / C7 / Bbmaj7 / F |
| Outro | 85–88 | 2:35.08 → 2:42.46 | Bbmaj7 / C7 / C7 / F |

### Parachute

| Section | Bars | Start → end | Chord cycle |
| --- | --- | --- | --- |
| Intro | 1–4 | 0:00.00 → 0:05.82 | i / i / VI / iv |
| Verse 1 | 5–20 | 0:05.82 → 0:29.09 | i / IIImaj7 / VI / iv |
| Pre-chorus 1 | 21–28 | 0:29.09 → 0:40.73 | iv / iv / VI / VI / iv / VI / V / V |
| Chorus 1 | 29–44 | 0:40.73 → 1:04.00 | i / VI / IIImaj7 / iv |
| Verse 2 | 45–60 | 1:04.00 → 1:27.27 | i / IIImaj7 / VI / iv |
| Pre-chorus 2 | 61–68 | 1:27.27 → 1:38.91 | iv / iv / VI / VI / iv / VI / V / V |
| Chorus 2 | 69–84 | 1:38.91 → 2:02.18 | i / VI / IIImaj7 / iv |
| Bridge | 85–92 | 2:02.18 → 2:13.82 | VI / VI / iv / iv / i / iv / VI / V |
| Final chorus | 93–108 | 2:13.82 → 2:37.09 | i / VI / IIImaj7 / iv |
| Outro | 109–112 | 2:37.09 → 2:42.91 | VI / iv / V / i |

## Evidence and source rights

`validation/full-catalog-verification-0.3.3.json` records actual per-bar and
per-section RMS, peak, duration and source hashes. The native project tests
also check return-hook identity, complete form, coverage and save/reopen. The three new choruses exceed bridge RMS by
4.18 / 3.62 / 3.72 dB. All source WAV renders are repeatable; late seeks
match full-render slices. Existing short auditions and Parachute Full retain
their exact 0.3.2 hashes. No human listening or device test is claimed.

Separate 320 kbps MP3 listening exports preserve source credits in tags and
include the four packs’ original attribution/change notices in their ZIP.
The first three sources retain CC BY 3.0; Parachute retains Shael Riley’s
supplied-source authorization and Suno paid-account declaration. MIT applies
to the arrangement metadata/code, not a new license for the source recordings.
See [source credits](SONG_PACKS.md) and [Parachute score](PARACHUTE_DEMO.md).
