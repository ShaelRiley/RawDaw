# Source-derived instrument banks — Raw Daw 0.4.0

Shael's October 14 request supersedes the modeled-instrument fallback in SDD
Section 30. Native recordings are preferred. Every missing target is prepared
from a recorded waveform in the same Song Pack, without oscillator banks,
synthetic noise, MIDI synthesizers, network models or replacement instruments.
The original pack and its project references remain immutable.

## Inventory

Lead and bass each expose MIDI 0–127: 256 pitched addresses per pack. The chord
registry has 35 common qualities across all 12 roots, including sixth/add-nine,
ninth/eleventh/thirteenth, suspended and altered-dominant options. The compact
bank contains 420 root-position chords. Every valid inversion remains selectable;
the complete address space has 1,860 voicings. Inversions are prepared only when
needed rather than multiplying the normal extraction bank's storage.

Mode guides recommendations; borrowed/chromatic chords remain playable. Relative
patterns follow the actual destination chord. Incompatible exact-pitch locks
remain visible authored conflicts. Native source identities, intentional rests,
mute/solo, saved probabilities and the drum/master/sidechain graph retain their
meanings. Explicitly empty original optional kit slots stay unassigned.
The supplementary percussion bank exposes all 47 standard GM articulations at
addresses 35–81, using native source hits where compatible and explicit source
transformations otherwise. It preserves exact MIDI import/export addresses while
routing through the existing eight drum EQ families and common drum bus.

## Waveform preparation

`source_waveform.py` contains offline PCM operations. `coverage.py` chooses seeds,
tracks lineage and materializes immutable WAVs before native rendering.
The Governor selects musical events; it performs no waveform processing inside
the audio loop.

For a missing lead/bass pitch, choose the closest declared recorded pitch, then
break ties by transformation cost, accepted confidence and stable source ID.
Band-limited Fourier resampling changes pitch and duration together. Long authored
gates use a crossfaded interior of the transformed recording. Monophonic loop spans
use integral target cycles to avoid coarse low-octave loop detuning. Stereo
channels retain their relative phases. Native recordings win unchanged for ordinary
gates; longer holds get a separate source-derived sustain asset.

For chords, choose the closest useful recorded polyphonic voicing. Overlapping
short-time Fourier harmonic masks retain original complex frequency bins and phase.
Separate source voices are warped independently to the requested tones and
recombined into one complete chord waveform. The method changes chord quality
and voicing; it does not merely transpose the wrong original chord. Octave-aware
rotation gives extended chords the correct inversion bass.

Missing kit articulations use the closest recorded percussion family, followed
by rate shifts, spectral filtering, duration/envelope changes and boundary fades.
There is no generated noise or oscillator percussion. Derived sounds are
identified as approximations, never as newly extracted native recordings.

A pack without a usable pitched source for a required role, or without a usable
percussion seed, fails with an actionable source-crop instruction. A wholly absent
instrument is not filled by an unrelated replacement.

## Cost, cache and extraction

Normal playback prepares only requested targets. The curated extraction tool
also prewarms the complete compact bank. To prepare an existing archive explicitly:

```bash
python3 -m prde1 prepare-bank packs/parachute.prdepack --report out/parachute-bank.json
```

`--inversions` additionally prepares the full inversion inventory. Banks are
cached outside immutable archives by manifest hash, algorithm version, source
ID/hash and target identity. Each cached WAV has verified dimensions and SHA-256;
its metadata must match requested pitches, chord, lineage and valid loop.
Corrupt or incompatible entries are rebuilt. Writes use durable temporary
replacement. An unavailable writable cache does not prevent playback.

The persistent cache is bounded to 256 MiB per pack/version with eviction. Session
materializations have a 1 GiB disk bound and are removed on pack close. Harmonic
analysis keeps at most 32 MiB of resident voice arrays. Normal source-note analysis
uses bounded crops; generated notes use at most two seconds, generated chord
targets approximately 400 ms plus their prepared loop. Original files remain
available separately.

Only assets used in a resolved plan enter the native decoded bank. Its 256 MiB,
1,024-asset and 64-voice limits remain explicit. Audition history cannot alter the
plan's sorted asset indices or allocate the entire catalog in playback. NumPy 2.3.5
is separately installed for offline preparation; the native engine still performs
fixed sample playback and downstream DSP only.

## Fidelity and validation

These are source-derived transformations, not an assertion that sparse source
material becomes a perfect commercial instrument. Shared harmonics cannot be
perfectly demixed by masks. Residual bleed and missing fundamentals remain possible.
Rate warps change attack, decay and formants; distant MIDI pitches can sound
unnatural. Derived percussion cannot reproduce an unrecorded instrument exactly.
Original source tuning estimates also limit tuning accuracy. Listening remains
necessary to judge a bank's useful register and timbre.

`make check` validates note/chord PCM, inversion identities, all registered targets,
cache recovery, source hashes, deterministic reopen/seek, UI gestures, saved loops,
native output and DSP/security rules. Synthetic fixtures prove those invariants
and are clearly identified; they are not source listening evidence.
`make demo` renders both synthetic references.

`tools/verify_source_banks.py` prepares all 256 note addresses and 420 root chords
and all 47 standard percussion sounds in each of five shipped source packs,
verifies non-silent real PCM and no synthetic
fallback, renders all root chords and checks archive immutability.
`tools/verify_chord_coverage.py` additionally renders all 1,860 inversion voicings
per source pack. `make source-demo` verifies the fourteen arrangements,
repeat identity and exact seek slices. Reports distinguish automated coverage
from human listening and physical device testing.
