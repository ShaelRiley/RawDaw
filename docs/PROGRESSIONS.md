# Choose harmony from the progression bank

Click **Choose progression** above the timeline. **Best fits** starts with twelve
choices suited to the key and mode at the edit cursor and ranked using the loaded
pack's native/prepared coverage. **All progressions** shows the complete library;
search by name, chord, musical feel or section. Style filters, favorites and
**My bank** help you return to useful choices. Each row shows ordinary chord
names, Roman numerals, cycle length and a suggested use.

The built-in bank contains **206 distinct progressions**: 136 templates whose
qualities follow the mode, and 70 progressions with authored chord qualities.
There are pop and minor loops, spacious verses, faster transitions, cadences,
blues forms, seventh chords, suspended chords, borrowed colors and inversions.
Every supported mode has a curated subset, including Dorian, Phrygian, Lydian,
Mixolydian, Locrian, harmonic minor and ascending melodic minor. Locrian's tense
tonic is labeled deliberately. Shared templates are counted once across keys and
modes. Recommendations describe musical use; preview helps you decide what fits.

**Preview** loops the whole progression using the loaded chord instrument and
current tempo, meter, mix and pulse accents. **Load into song** repeats it through
the existing song length. An empty song grows when necessary to fit one complete
cycle, so a twelve-measure preset is complete on first load. A song with placed
patterns or retained vocals keeps its length. **Bank… → Place one cycle at cursor** replaces just one
cycle, restoring the previous harmony afterwards. Both write editable chords;
**Undo** restores the previous lane. Existing patterns, vocals, mix, tempo/meter
and key changes remain in place. Pitched conflicts remain visible in
**Coverage & warnings**. After loading harmony, use **MIDI clips** to preview and
place performance patterns on empty instrument tracks.

Measure durations follow the actual meter map. One measure is four quarter-note
beats in 4/4 and three in both 3/4 and 6/8; the pulse grouping still differs.
Half-measure durations and multi-measure holds are retained. Mode-derived chords
also follow key/mode changes that occur during a held chord. Exact-quality
progressions keep their authored quality. Major-relative roots retain their
actual pitch-class offset when converted to the destination mode.

## Your reusable bank

**Custom…** remains beside the primary chooser and opens the Custom progression
dialog. Enter a sequence,
duration unit and optional duration list. **Save to My bank for future songs**
is checked initially. To save harmony you edited on the timeline, use
**Bank… → Save current harmony to My bank…**, name it, and choose the number of
measures from the cursor. That capture retains exact qualities, inversions,
quarter-note timing and credits. It can be used in another key or another song.

**Bank… → Import progressions…** accepts one or more JSON or UTF-8 text files.
The entire batch is validated before anything is saved. Duplicate musical entries
are skipped even when their names or equivalent enharmonic spellings differ. The local personal bank and favorites
survive app restarts and new projects. **Export My bank…** produces a reusable
JSON file; **Remove selected from My bank** and **Undo last bank change** manage
the collection. Removing an entry leaves songs that already loaded it intact.

For text, put one progression on each line:

```text
My spacious verse | 1 5 6 4 | 2 2 2 2
My minor answer | i bVI V i | 1 2 1 2
My soft cadence | ii7 V7 Imaj7 | 1 1 2
```

The fields are **Name | chords | durations**. Durations may be integers or
rationals such as `1/2`. Omit the last field for one measure per chord. One duration
applies to every chord. Blank lines and lines starting with `# ` or `//` are
ignored. Files use numbers for mode-derived templates or Roman numerals for exact
qualities; keep those two forms separate within a progression.

When importing text, choose **Major-relative roots** for common song charts or
**Mode-relative roots** for Raw Daw notation, and choose measures or quarter-note
beats. In A natural minor, major-relative `bVI` and mode-relative `VI` both mean F
major. An uppercase `V` is a major chord, while lowercase `v` is minor. Numbers
always derive their chord quality from the current mode. The source notation is
saved alongside the normalized entry. Text imports retain a user-supplied rights
label; JSON can carry exact license and attribution records.

## JSON bank format

Native exports use this offline versioned format. A minimal import is:

```json
{
  "format": "raw-daw-progressions",
  "version": 1,
  "entries": [
    {
      "name": "My minor answer",
      "kind": "chords",
      "basis": "major-relative",
      "sequence": "i bVI V i",
      "durations": ["1", "2", "1", "2"],
      "durationUnit": "bars"
    },
    {
      "name": "My loping verse",
      "kind": "degrees",
      "sequence": [1, 4, 5],
      "durations": ["3/2", "1/2", "1"],
      "durationUnit": "bars"
    }
  ]
}
```

For exact chords, declare `basis`. For degree templates, the basis is always
`mode-relative`. `durationUnit` is `bars` or `beats` (quarter notes). Exact
`sequence` may also be a list of objects containing `degree` (1–7), `alteration`
(−1, 0 or 1), `quality` (the existing registered quality name), and `inversion`
(zero for root position, less than the chord's tone count).

Optional metadata: `style`, `section`, `description`, `modes` (supported mode
names), `sourceNotation`, `priority` (1–5), and `credits` (records with `source`,
`license`, `attribution` and `changes`). Native exports include all normalized
fields and a stable `id` calculated from the musical content. Input IDs are
recomputed. Names, styles and transpositions do not create duplicate identities.

Bounds: 2 MiB per file and for the stored bank, 2,048 personal entries, 64 chords
per progression, 512 units per cycle, positive durations at most 128 with
denominator at most 192. Imports reject unknown fields, incompatible versions,
mixed numeric/Roman sequences, nonfinite JSON, duplicate JSON keys and impossible
inversions. File contents are never executed. An unreadable existing bank is
preserved and displayed as an error before any bank write.

The built-in templates are originally authored and dedicated under
[CC0-1.0](../prde1/data/clips/licenses/CC0-1.0.txt). Their inventory is reproducible
from `tools/build_progression_bank.py`; the app bundles `prde1/data/progressions.json`
and requires no network or account to use the bank. License/attribution records
from loaded entries follow project and export credits.
