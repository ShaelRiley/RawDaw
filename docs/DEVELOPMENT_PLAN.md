# Development plan

Authority: the live PRDE1 SDD, sections 1–29 and the engineering selections in
28.8. Repository notes implement it; they do not supersede it.

1. **Core checkpoint — implemented and tested:** experimental pack/project/event
   contracts, safe loader, strict selection-only Governor, rational timing,
   deterministic probabilities/variation, native sample renderer, save/reopen,
   synthetic MIDI/audio fixtures, invariant tests and reproducible source builds.
2. **Authorized source proof — prototype assembled:** user-authorized selection
   of three CC BY songs; verified artist stems, source hashes, saved crops,
   preparation-only note variants, source drum MIDI and three coverage-limited
   packs with two arrangements each. Version 0.2.1 adds Shael Riley's authorized
   Parachute stems as a fourth pack, with separate rights provenance and two
   arrangements. Keep the source-quality gate open until
   listening, stem alignment and full tonal-map checks succeed. Missing kit slots
   remain unavailable. This is not a general separator or public builder skill.
3. **Native desktop slice:** Qt prototype, pack load → custom/preset Governor →
   pattern selection/edit/copy → sample-clock playback → save/reopen → stereo
   render. Test layout/focus/keyboard/scale, context persistence and explicit
   unavailable choices. Bind the existing core; avoid duplicate rule systems.
4. **Variation/arrangement completion:** full independent/Linked Repeat workflow,
   Include Harmony warning, undo/redo and autosave, explicit regeneration, Freeze
   Variation, whole-song plans/locked sections, normalized MIDI adapters and
   exact rational/pulse behavior. Current helpers are not a complete UI workflow.
5. **Fixed DSP graph:** role/drum EQ, every channel/group's independent reverb and
   synchronized delay, static settings, master inserts/ambience, common final
   compression, no duplicate drum route, finite export tails and deliberate seek
   state. Preserve original source samples throughout.
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
   installation instructions. Curate the extensive progressions, tonal registry,
   useful authorized demo pack and substantial properly licensed one-measure
   library. Select/clear/test two to four existing instruments and a small effects
   bundle; record every notice/hash/source obligation. No invented inventory.
9. **Release gate:** full project/media state and migrations, native installers,
   privacy/local diagnostics, hardening, malicious-input and failure testing,
   30-minute declared full workload on Linux laptop/Steam Deck/interface, listening
   and manual-free first-use/accessibility pilot. Public release requires Shael's
   approval; keep the source repository private before that.

Current communication boundary: real hardware, singing, subjective listening and
source rights require the creator when they become relevant. Compilation,
fixture renders and invariant testing are performed directly.
