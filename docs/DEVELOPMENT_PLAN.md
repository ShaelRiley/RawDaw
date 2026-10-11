# Development plan

Authority: the live PRDE1 SDD, sections 1–29 and the engineering selections in
28.8. Repository notes implement it; they do not supersede it.

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
4. **Variation/arrangement completion:** full independent/Linked Repeat workflow,
   Include Harmony warning, undo/redo and autosave, explicit regeneration, Freeze
   Variation, whole-song plans/locked sections, normalized MIDI adapters and
   exact rational/pulse behavior. The desktop now exposes copy/link/detach,
   Include Harmony warning, undo/recovery and regeneration. Freeze, full section
   plans and complete pattern-library workflows remain to be implemented.
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
