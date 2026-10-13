# Development plan

Authority: the live Raw Daw SDD, sections 1–34 and the engineering selections in
28.8. Repository notes implement it; they do not supersede it.

**Default step sequencer — implemented:** Section 31 provides melodic pitch rows
and named kit rows, gesture/keyboard entry, mono/poly scheduling, saved row and
step expression, ties/flams, swing/offsets, row/pattern reuse, independent loop
audition, native pattern files and note-level MIDI interchange. All editing uses
the shared project/Governor/native path. Wider MIDI-device integration and the
recording/VST/clip-library milestones below remain separately scoped.

**October 11 override — complete harmonic playback:** Section 30 supersedes the
old missing-coverage gate. Hybrid preparation supplies every registered note,
chord and inversion, sustained pitched holds and missing offered kit slots.
Native source banks remain immutable; modeled assets are labeled honestly.
Modes guide recommendations without withholding borrowed chords. Functional
coverage is tested separately from source-fidelity/listening quality. See
`HARMONIC_COVERAGE.md`; source separation, recording, VST3 and the wider approved
v1 scope remain in this plan.

1. **Core checkpoint — implemented and tested:** experimental pack/project/event
   contracts, safe loader, strict selection-only Governor, rational timing,
   deterministic probabilities/variation, native sample renderer, save/reopen,
   synthetic MIDI/audio fixtures, invariant tests and reproducible source builds.
   Version 0.3.2 fixes sampler boundary clicks with smooth playback envelopes and
   verified renderer upgrades; Governor selection and pack bytes stay unchanged.
2. **Authorized source proof — prototype assembled:** user-authorized selection
   of three CC BY songs; verified artist stems, source hashes, saved crops,
   preparation-only note variants, source drum MIDI and three coverage-limited
   packs with two arrangements each. Version 0.2.1 adds Shael Riley's authorized
   Parachute stems as a fourth pack, with separate rights provenance and two
   short arrangements. Version 0.3.1 adds the complete 112-bar, 2:42.91 Parachute
   demo with a recurring hook and contrasting sections. Version 0.3.3 adds
   complete 2–3 minute Reach Out, Where You Are Now and Auld Lang Syne demos,
   with distinct grooves, returning hooks and measured section contrasts.
   Keep the source-quality gate open until
   listening, stem alignment and full tonal-map checks succeed. Missing kit slots
   remain unavailable. This is not a general separator or public builder skill.
3. **Native desktop slice — 0.3.0 implemented:** Qt workspace, pack load,
   custom/preset Governor, exact-timing step/event editing, independent/linked
   copies, static mixer, undo/redo, recovery, native save/reopen and stereo export.
   Preview uses a background native render followed by Qt PCM media playback,
   with pause/seek and output selection. All twelve GUI exports match the source
   auditions. Keyboard and enlarged-layout checks passed offscreen. Real-time
   native device callbacks, physical audio/Steam Deck testing, accessibility
   and first-user pilots remain open; the UI does not duplicate Governor rules.
   A subsequent 0.3.3 source hotfix disables unnecessary Qt video-driver probes
   after Shael's Deck startup crash and adds local native-fault diagnostics.
   An injected video-driver crash is prevented in the real Qt editor; the
   physical Deck's original cause and successful startup remain unconfirmed.
   An October 11 Deck trace identifies automatic native dock tabification during
   saved-scale restoration. The subsequent source hotfix uses central tabs for
   compact/enlarged layouts and protects panel transfers, with saved-preference,
   injected native dock-fault and scale/size/Focus/Reset checks. On-device relaunch
   and listening remain open; no approved product scope is removed.
   The subsequent physical run at `058d2f2` still failed after responsive layout
   setup and before the event loop. An explicit recovery launch bypasses native
   docks and saved workspace restoration, preserves layout/scale preferences,
   and adds first-show/display diagnostics. Matching Python 3.13.5/Qt 6.8.3
   headless tests pass; native root cause and on-device recovery launch remain
   open. The diagnostic workaround does not close the physical release gate.
4. **Variation/arrangement completion:** full independent/Linked Repeat workflow,
   Include Harmony warning, undo/redo and autosave, explicit regeneration, Freeze
   Variation, whole-song plans/locked sections, normalized MIDI adapters and
   exact rational/pulse behavior. The desktop now exposes copy/link/detach,
   Include Harmony warning, undo/recovery and regeneration. Freeze, full section
   plans remain to be implemented. The 703-bar shared MIDI library and pulse
   governor now support search, previews, placement, drops and favorites.
   The four full demos are fixed authored native scores with companion section
   documentation; they do not close generic Song Plan generation or section locks.
5. **Fixed DSP graph:** role/drum EQ, every channel/group's independent reverb and
   synchronized delay, static settings, master inserts/ambience, common final
   compression, no duplicate drum route, finite export tails and deliberate seek
   state. Preserve original source samples throughout.
   Version 0.3.4 implements each drum's EQ, drum bus compression with makeup,
   real-kick-driven bass sidechain and the common master compressor, including
   saved native UI controls and reconstruction on seek. New songs/full demos
   use calibrated punch settings; older projects remain unchanged until an
   explicit preset/edit. Role/vocal EQ, ambience and complete plug-in/tail policy
   remain work within this stage. See `MIXING.md`.
6. **Recording and comping:** one visible/four possible lanes, dry durable takes,
   newest-completed selection, retained alternatives, seconds anchoring with tempo
   warnings, non-destructive comp regions, latency/monitoring measurement,
   interrupted-write and lost-input recovery. Add reversible correction starting
   Off; measure quality/latency and preserve unvoiced sounds/formants.
7. **Native Linux VST3 hosting:** isolated scan/load lifecycle, total three added
   instruments across chord/monophonic/percussion modes, three inserts per channel/
   bus, real MIDI adaptation/held-note-offs, identities/state/mode/maps/routing,
   explicit missing placeholders/effect bypass and altered-export approval,
   compensation and state-version handling. This is approved v1, not deferred.
8. **Public builder and catalogs:** read skill-creator instructions, package the
   actual `prde1-song-pack-builder` plus pipeline/locks/shared schemas/tests and
   installation instructions. The progression chooser now exposes 206 distinct
   curated entries, modal subsets, native previews, measure-aware loading,
   favorites and a persistent import/export/custom bank. Further listening and
   recommendation calibration, tonal-registry breadth and useful authorized demo
   packs remain ongoing. The initial shared one-measure library now
   contains 703 source-traceable CC BY/CC0 clips; further breadth remains curation work. Select/clear/test two to four existing instruments and a small effects
   bundle; record every notice/hash/source obligation. No invented inventory.
9. **Release gate:** full project/media state and migrations, native installers,
   privacy/local diagnostics, hardening, malicious-input and failure testing,
   30-minute declared full workload on Linux laptop/Steam Deck/interface, listening
   and manual-free first-use/accessibility pilot. Public release requires Shael's
   approval. Shael authorized publishing the tested source to the existing public
   RawDaw repository on October 13; preserve that visibility.

Current communication boundary: real hardware, singing, subjective listening and
source rights require the creator when they become relevant. Compilation,
fixture renders and invariant testing are performed directly.

