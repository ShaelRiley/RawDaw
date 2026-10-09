# Architecture decisions — first core checkpoint

These are replaceable engineering selections within the live SDD's approved
scope, not claims of separate voice-session approval.

## ADR-001: control plane and native sample clock

Python 3.11+ owns untrusted archive/JSON/SMF validation, rational musical timing,
selection-only governance, deterministic realization and transactional manifests.
C++20 owns prepared float32 sample buffers and fixed-size active voice state.
It processes immutable resolved events in sample-clock order without allocation,
file I/O, locks, Python calls or UI work inside `Engine::process()`.

The native command-line runner performs JSON parsing, file loading and output
writing outside `process()`. It is an offline renderer, not a real-time device
backend. Its 256-frame blocks are not an input-to-output latency measurement.
Sample frames advance exactly once at 48 kHz. The engine exposes no harmonic
pitch/rate/stretch/reconstruction parameter. Only preparation tools may synthesize
or transform samples. The fixture generator is outside the music runtime.

The source pack is validated and materialized into a private read-only cache.
Both manifest references and every file hash are checked. Asset identity is
distinct from relative degree, source clip, normalized intent and resolved event.
Prepared absolute-note/chord samples are reused across compatible tonalities.

## ADR-002: dependency and licensing policy

MIT application code, authored for Shael Riley. The native runner uses the pinned
MIT nlohmann/json 3.12.0 header for non-real-time plan parsing; original notices
are retained. The core Python package requires only the standard library.

Qt6/PySide6 is the shortlisted native desktop surface, with LGPL obligations,
module boundaries and dynamic replacement/source distribution to be addressed
before bundling. PortAudio is the shortlisted MIT device layer; official callback
guidance informed the native/control separation. Neither is bundled or claimed
implemented in this checkpoint. The native Linux VST3 SDK's MIT licensing was
verified; the actual SDK/host and plug-in bundle are still absent. No commercial
framework or proprietary SDK obligation was imposed on the application.

## ADR-003: experimental shared contracts

Schemas use `1.0.0-dev.1`; the musical profile uses `core-v1-dev.1`. These are
development contracts, not a frozen release claim. The same pack contract is the
future builder/loader interface. Schema versions unknown to the loader fail;
future extensions require deliberate versioning and migrations.

The native `.prdeproj` JSON envelope carries current musical state, copy/link
identities, saved variation, current static mixer settings, vocal/media and
plug-in placeholders, attribution and editor context. It is deliberately not
advertised as the complete release-level project/media implementation. Parameters
and state introduced by later DSP/hosting/recording checkpoints must extend this
contract without loss. A project requesting unsupported active processing is
blocked rather than exported through an undisclosed approximation.

The offline schema validator implements the small documented vocabulary used by
the shipped standard Draft 2020-12 files, not arbitrary JSON Schema. Semantic
validation additionally checks samples, maps, pitches, roles, references, timing
and finite playback bounds. External general-validator cross-checks remain a
future contract-tooling improvement.

## ADR-004: initial musical profile and scheduler

12-TET, A4=440 Hz, all 12 tonic pitch classes. Nine named seven-note modes:
major, natural minor, Dorian, Phrygian, Lydian, Mixolydian, Locrian, harmonic minor,
ascending melodic minor. Metadata admits major/minor/diminished/augmented/power/
sus2/sus4/major7/minor7/dominant7/half-diminished7/diminished7/minor-major7,
valid inversions and degree-root alterations of ±1 semitone. Actual chord pitches
must belong to the selected mode; alteration metadata is not a passing-tone
exception. Pitched lead/bass choose strict chord tones in MIDI 48–84 and 28–60.

Six mode-derived development progression templates exist. This is not the
required extensive release catalog. Coverage rankings first admit only actual
prepared targets, then compare already-incurred preparation costs with stable
ties. Stylistic scoring/weights have not been calibrated or implemented.

Rational quarter-note positions, quarter-note BPM tempo integration, and separate
meter/grid maps. Harmonic boundaries inspect actual held sample pitches. A
5 ms (240-frame) fade ends at an incompatible boundary; no replacement event is
created. Compatible notes continue only within their prepared duration/validated
sustain. Chord samples require their complete pitch set to remain legal.

One held voice per lead/bass/rhythm lane. Open and closed hats form one mutual
choke/retrigger group. Tom 1/2 fixture identities are lower/higher; real pack
ordering must reflect source identities, not transposed drum addresses. Definitely
pitched extras are governed; uncertain classifications are reported/withheld.

Event-addressed SHA-256 randomness uses saved variation seed/revision and saved
instance/event IDs. Ordinary copies do not change the global variation state.
Disabled triggers stay silent. Play % is independent of Change %. Double hits
resolve separately at their real positions. Gates shorten; samples never stretch.

## ADR-005: resource and render bounds

| Resource | Current bound |
| --- | --- |
| Compressed pack / total uncompressed entries | 256 MiB / 512 MiB |
| Archive entries / prepared sample records | 4,096 / 1,024 |
| Decoded float sample bank | 256 MiB |
| Asset duration / file channels | 30 seconds / mono or stereo |
| Compression ratio | 200:1 maximum |
| Expanded triggers / simultaneous sample voices | 100,000 / 64 |
| Stereo render duration | 30 minutes |
| Source MIDI | PPQ SMF 0/1, ≤32 tracks, ≤4 MiB, bounded events |

The initial renderer preloads the accepted bank rather than paging in the audio
loop. Resource overflow fails before processing; voices are not silently stolen.
Actual reference-device memory/latency/loading budgets still need measurement.

Ordinary RIFF 48 kHz 24-bit mono/stereo PCM assets; runtime sample-rate conversion
is not implemented. Export is 48 kHz 24-bit stereo PCM with counter-addressed
TPDF dither, static saved gains/pans and one final peak-envelope compressor.
Default compressor: −12 dB threshold, 2:1 ratio, 10 ms attack, 150 ms release,
no makeup gain. Master reverb/delay and vocal correction retain approved Off
defaults. Unsupported effects must not be enabled in this checkpoint.

No limiter or normalization is applied. Samples exceeding −0.1 dBFS abort export
with a lower-levels instruction. The completed output is replaced only after a
successful fsync/rename. A seek reconstructs engine/compressor state from zero;
future state snapshots can improve seek speed without changing realization.
Effects and their finite tail policy remain a later DSP gate; dry rendering ends
at the saved song length, including click-free scheduled endings.
