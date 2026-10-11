# Drum punch and kick-to-bass sidechain — 0.3.4

Shael's October 10 request extends the fixed downstream graph: give each drum
its own EQ, compress and gently boost their combined bus, then compress the
whole ensemble at the master. A kick-triggered bass compressor creates room for
the kick. These are sample-clock audio processors outside Chord Governor
selection; original sample buffers and all four pack files remain immutable.

## Controls and defaults

New songs and the four bundled full demos use the punch preset. Existing user
projects and the eight historical short demos retain their saved sound. Use
**Mixer → Apply punch mix** to enable it in an older project; this explicitly
replaces the drum EQ and the three dynamics presets, preserving faders/pans.
The operation is undoable. Save retains every static setting and recovery does
the same. There are no parameter-automation curves.

**Mixer → individual drum's EQ…** opens its independent On/Off, high-pass,
bell frequency/gain/Q, and high-shelf frequency/gain controls. Reset restores
that slot's curve; it does not affect another slot. Open/closed hats have separate
EQ state despite sharing their established choke behavior. Missing kit slots
remain unavailable; EQ does not synthesize or substitute a missing sound.

| Drum slot | Low cut Hz | Bell Hz | Bell dB | Q | Air shelf Hz | Shelf dB |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Kick | 30 | 65 | +3 | 0.8 | 3000 | +2 |
| Snare | 110 | 190 | +2.5 | 0.9 | 4500 | +2 |
| Closed hat | 450 | 6500 | −1.5 | 1 | 9000 | +1.5 |
| Open hat | 350 | 5000 | −1 | 1 | 10500 | +1 |
| Low tom | 45 | 110 | +2.5 | 0.8 | 3500 | +1 |
| High tom | 65 | 180 | +2.5 | 0.8 | 4500 | +1.5 |
| Extra 1 | 100 | 2200 | +1.5 | 0.9 | 8000 | +1 |
| Extra 2 | 180 | 3200 | −1 | 0.9 | 10000 | +2 |

These are adjustable starting curves, especially for pack-specific extras,
not source-classification or subjective listening certification. Independent
stereo high-pass/bell/shelf biquads use the RBJ coefficient equations documented
in the [W3C Audio EQ Cookbook](https://www.w3.org/TR/audio-eq-cookbook/).

**Dynamics** provides separate On/Off, threshold, ratio, attack and release
controls for the drum bus, kick → bass, and master. Drum/master compressors also
have makeup gain; sidechain has maximum duck instead of makeup.

| Processor | Threshold | Ratio | Attack | Release | Boost / cap |
| --- | ---: | ---: | ---: | ---: | ---: |
| Drum bus | −26 dB | 3:1 | 25 ms | 100 ms | +3 dB makeup |
| Kick → bass | −30 dB | 4:1 | 1 ms | 140 ms | 6 dB maximum duck |
| Master | −18 dB | 2:1 | 10 ms | 150 ms | 0 dB makeup |

Thresholds were calibrated against the shipped sample levels; the earlier
−18 dB drum / −12 dB master thresholds scarcely engaged in these demos.
The slower drum attack lets transients through. Bypass includes bypassing a
compressor's boost. All detectors/gain changes are stereo linked.

## Exact routing and state

Each drum's source playback → its EQ → drum sum → drum compressor/makeup →
drum bus fader/balance → master sum. Fixed channel level and pan commute with
these linear, time-invariant EQs and are applied when the channel samples are
accumulated. The bus fader is downstream of compression in this graph, rather
than multiplying every drum voice before detection as in the old dry renderer.
There is exactly one drum contribution to the master, with no duplicate dry
route or audible detector contribution.

The kick detector taps the actual post-EQ/post-channel-level kick signal before
drum bus compression/fader. A smoothed peak envelope governs gain only on the
bass stereo pair. Snare/hat hits cannot trigger it; absent/disabled/muted kicks
and a muted drum bus cannot duck the bass. The group fader does not change the
sidechain threshold sensitivity. No scheduled substitute pulse is created.

Lead + rhythm + ducked bass + compressed drum bus → saved master level → master
compressor/makeup → output. The existing ceiling check still rejects clipping
without overwriting a completed export. There is no normalization or limiter.

Persistent filter/envelope state crosses steps and rests. A render starts with
fresh state; native seeking reconstructs it from sample zero. Repeat renders
and seek slices are byte-identical with the same dither. EQ filter residuals
close with a 5 ms smooth end fade inside the saved song length. No additional
reverb/delay tail or song-duration extension is introduced by this checkpoint.

The backward-compatible optional project fields are per-drum `channel.eq`,
`mix.drumBusCompressor`, `mix.bassSidechain`, and compressor `makeupDb`.
Resolved plans declare `processing.version = drum-mix-v1`; unknown graph versions,
unsupported EQ or invalid/nonfinite filter settings fail before export.
Absent new fields retain the exact legacy dry accumulation/compressor behavior.

## Validation and delivery

Native tests check actual EQ response, combined drum compression, makeup/bypass,
single routing, bass-only ducking, its cap/recovery/stereo link, block partition
identity, and allocation-free processing. Python/Qt checks cover old-save
behavior, source identities, settings/undo/reopen/recovery, invalid-state export
protection, muted triggers, and processed seek/repeat identity. All twelve real
source arrangements are rendered and checked without changing the packs.

The hashed 0.3.4 archive parts contain a small **renderer upgrade for a source
checkout**, not another full-content distribution. The normal launcher restores
it automatically after `git pull`; a local compiler is not required. The older
0.3.3 all-content distribution remains intact. The Qt startup protection is
retained. Physical Steam Deck playback and subjective listening remain open.
Role/vocal EQ, reverb/delay, VST hosting and recording/comping remain approved
work in the development plan.
