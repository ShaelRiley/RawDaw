# Architecture decisions — first core checkpoint

## Current shared clip library and rhythmic pulse (SDD Sections 32–33)

`clip_library.py` reads a bounded offline compressed catalog and adapts whole-bar
performances into the existing native pattern contract. Placement is transactional,
protects occupied material and attaches source/license/conversion credits. The
preparation tool preserves verified source MIDI, rejects duplicates, explicitly
selects melodic source voices and emits bounded canonical SMF bars. Kit conversion
uses semantic identities or declared MIDI addresses, with visible omission reports.

`pulse.py` supplies repeating measure accents. Guide seeds only new entries;
On applies velocity at actual expanded trigger positions while retaining authored
volumes. The resolver records that effective `noteVelocity` so MIDI export uses
the same value as audio, including microtiming and flam grace levels. Scoped
auditions retain their initial partial-measure phase and reset at later meter
downbeats. Optional project fields keep old saves at Off. Sample preparation,
native rendering and downstream DSP remain separate and unchanged.

Raw Daw is the visible application identity. The scalable dog icon avoids clipping
paths so Qt's SVG renderer displays it correctly. Legacy module/format identifiers,
settings, project references and launch commands are retained for compatibility.

## Current step editor (SDD Section 31)

`sequencer.py` supplies validated pattern/row settings and pure musical edits;
`step_widgets.py` provides the default pitch/kit step grid and expression bars.
Optional project fields preserve legacy saves and source-pattern timing. Row
controls expand into ordinary events before the Governor validates each actual
trigger. Flam grace/primary events share probability addressing and distinct
resolved IDs. Melodic mono remains default; explicitly selected poly patterns
retain concurrent voices within the existing 64-voice budget. The native renderer
and DSP graph are unchanged. Scope-specific auditions get independent native
plans/cached previews while preserving authorship, saved variation and stale-job
guards. Native pattern files retain attribution; SMF is note-level interchange.
See `STEP_SEQUENCER.md` for controls, edge policies and validation.

Focused-note volume controls reuse saved `expression.velocity` and the same
native gain path. The slider commits one edit per drag; a continuation cell
addresses its held note's original event. Dynamics bars are visible by default.
Zero-volume realized events are omitted from SMF note output, preserving silence
without treating MIDI velocity zero as a new note-on. No new event schema or
sample/DSP operation is introduced.

`placement_preview_plan()` isolates and resolves a prospective or existing note
without committing it, consuming saved variation or changing credits. It shifts
the resolved primary trigger to frame zero and bounds its gate to two seconds.
`note_preview.py` uses a separate QProcess and the unchanged native renderer;
latest-request generations suppress canceled work. Acoustic keys include pack,
sound, expression and mix data rather than authored event IDs. At most 64 short
clips and eight resident QSoundEffect objects are retained. Only audition PCM is
repacked from 24 to 16 bits for portable low-latency WAV playback; its sample
clock, pitch and source/DSP path are unchanged. Stereo exports remain 24-bit.
The extra sound objects are created lazily after user input, never at startup.
See [Qt's QSoundEffect reference](https://doc.qt.io/qt-6/qsoundeffect.html).

## Current override: full harmonic coverage (SDD Section 30)

Shael's October 11 amendment supersedes the coverage-gating and strict mode
withholding rules below. The current hybrid bank prefers native targets, prepares
unrecorded notes/chords and sustain continuations through `coverage.py`, and feeds
ordinary immutable PCM assets to the unchanged native player. Every registered
chord is playable in every pack; mode guides degree interpretation and ranking.
Only referenced assets enter a resolved plan, preserving stable indices regardless
of audition history. See `HARMONIC_COVERAGE.md` for the method, fidelity limits,
complete inventory and verification. Original archives and saved pack references
remain immutable. The earlier ADRs below retain the original design history.

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

Qt6/PySide6 6.8.3 now provides the native desktop surface in 0.3.0. Widgets and
Multimedia are installed separately and dynamically imported; their libraries
and licenses are not folded into the MIT application or this archive. A bundled
Qt installer still needs its complete notices/source/replacement obligations.
PortAudio remains a shortlisted MIT native device layer; official callback
guidance informed the native/control separation. It is not implemented here.
The native Linux VST3 SDK's MIT licensing was
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

Version 0.3.2 implements the sampler's release as a cubic smoothstep with zero
endpoint/slope and adds an independent 1 ms start envelope, because onset offsets
can skip baked source fades. The player caps natural one-shot exhaustion before
applying release. Gates/boundaries remain half-open and add no pitched tail.
These amplitude envelopes belong to playback, not selection-only governance;
source PCM and its 1x frame clock remain unchanged. See `SAMPLE_BOUNDARIES.md`.

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

Version 0.3.4 adds an optional fixed drum/bass DSP graph. Each drum has independent
stereo EQ before the combined drum compressor and makeup stage; its post-processor
bus fader contributes once to the master. Actual kick PCM drives a stereo-linked,
bounded bass-only sidechain detector. The full ensemble then reaches the common
master compressor. See `MIXING.md` for editable parameters, calibrated new-song
defaults, explicit legacy-save behavior and deliberate filter/envelope seek state.
No allocations, I/O, locks or Python calls are added to block processing.

## ADR-006: desktop composition and rendered preview

The optional Qt desktop imports `editor.py` for validated project edits and the
same `resolve()` used by the CLI for its native plans. Undo uses bounded project
snapshots; autosave is a separate atomic recovery manifest with the exact pack
reference. Pack activation is transactional and never overwrites pack bytes.
Unknown media/processing remains saved and visibly blocks unsupported exports.

A `QProcess` executes the existing native renderer outside the UI thread. Each
job owns a temporary plan/output and a session fingerprint. Stop, close or a new
music edit cancels the direct child; stale completions cannot start playback or
replace an export. Successful exports alone enter the atomic file-commit step.
No Python, Qt or filesystem operations are added to `Engine::process()`.

Qt `QMediaPlayer`/`QAudioOutput` auditions the completed 48 kHz PCM render at 1×
speed, with pause/seek and an explicit output choice. The arrangement realization
is saved/deterministic and identical to export. Device conversion by Qt is audio
infrastructure, not harmonic transposition. This buffered preview has preparation
latency and does not implement the future native real-time device/recording path.
Cloud PCM decode/state tests do not establish physical-device fidelity, monitoring
latency, subjective quality or Steam Deck performance.

Launchers verify the current distribution's renderer hash/length/version even
when an executable already exists. Verified archive installation replaces an old
binary atomically; matching binaries need no archive reads. Extracted builds use
their bound `BUILD_INFO.json`. This ensures a pulled engine fix reaches playback.

