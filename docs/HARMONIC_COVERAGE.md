# Complete harmonic playback

Shael's October 11, 2026 instruction and canonical SDD Section 30 supersede the
earlier policy that missing prepared targets must silence a part. This is a
source update using the existing 0.3.4 native renderer; a normal pull activates
it for old packs and saved projects without rewriting their source identities.

Every pack is now a hybrid instrument bank: native source samples remain the
first choice for recorded targets. `prde1/coverage.py` prepares unrecorded
targets in the pack's private session cache. The native engine receives ordinary
48 kHz 24-bit WAV assets and keeps its fixed playback clock, drum/channel/mix
routing and kick-to-bass sidechain. No extra dependencies or network access are
added to the music runtime.

## Complete inventory

All 12 roots; major, minor, diminished, augmented, power, sus2, sus4, major7,
minor7, dominant7, half-diminished7, diminished7 and minor-major7; every valid
inversion. This makes 528 rhythm voicings per pack. Bass covers MIDI 28–60 and
lead 48–84 (70 notes). All 108 registered tonic/mode combinations and the six
development progression templates remain playable. These are the entire current
registry, not a claim to enumerate every possible extended musical chord.

The selected chord supplies the actual permitted tones. Mode supplies degree
interpretation and recommendation context; it no longer withholds a borrowed
chord. Relative tone indices wrap inside the selected chord's tone count, so a
fourth-tone motif can continue when its seventh chord becomes a triad. Exact
pitch locks outside the chord or role register remain explicit authored conflicts.
Deliberate rests, probability skips, mutes and harmonic-boundary fades remain.

## Sound preparation and fidelity

An eight-partial harmonic model estimates instrument color from a stable source
seed where available, with a deterministic modeled profile when an instrument
has no clean seed. It renders each requested note and the constituent tones of
each chord. Inversions move the correct tones up an octave; qualities are not
approximated by transposing a different-quality chord. Absolute chord identities
are checked by the existing pack validator. Reconstructed sounds are identified
in the interface and export notices; they are synthesized, not extracted source
recordings. Source fidelity and articulation remain approximate.

Generated single-note loops contain 64 complete cycles, tuned within 0.3 cents
over the defined registers. Whole chords use one-second integral-cycle periods:
each constituent pitch is quantized to the nearest Hz, within 6.7 cents for the
current rhythm voicings. Two periods separate the initial amplitude attack from
the steady sustain. The highest modeled partial remains below Nyquist. Smooth
native-to-model crossfades and phase-continuous loop seams let a short recorded
sample sustain to its authored gate. Long continuations downmix native stereo
attacks into mono; the original recording remains intact for shorter events.

Missing required kit slots receive deterministic modeled percussion. Intentionally
empty extras remain unassigned. Existing semantic identities and recorded hits
remain; a genuinely unknown imported sound is still reported for repair rather
than silently remapped to another extra. Pitched-extra conflicts retain the
established explicit behavior.

## Persistence, cost and verification

Only requested reconstructions are prepared. Rankings and chord previews do not
render the whole inventory. Prepared targets are reused throughout the loaded
session; subsequent loads regenerate the same PCM from the same source hash and
versioned algorithm. Resolution includes only used assets, so audition history
cannot change a plan's asset indices or inflate its native decoded bank. Pack
archives, manifest hashes, saved pack references and original credits are unchanged.

`make check` exercises PCM fundamentals, borrowed chords, relative tone adaptation,
all registered roots/qualities/inversions, native export, sustain loop seams,
source immutability, saves, seek, desktop controls and existing DSP/security rules.
`make demo` checks both synthetic reference arrangements.
`python3 tools/verify_chord_coverage.py` exports all 528 chord voicings in each of
the four actual shipped packs, checks exact pitch-class and inversion metadata,
and inspects PCM in every event. It also prepares all 70 role notes and verifies
every registered key/mode ranking. Evidence goes to
`docs/validation/full-chord-coverage.json`. `make source-demo` checks all twelve
original projects for conflict-free repeatable audio, exact seek slices and
unchanged pack bytes. Automated checks do not replace subjective listening or
physical Steam Deck validation.
