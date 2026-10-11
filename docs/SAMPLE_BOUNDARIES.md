# Sample boundaries — 0.3.2

Shael reported an audible click at sample cutoffs in the full Parachute demo.
The existing player already ended scheduled notes with a 5 ms linear release.
However, all 28 Parachute samples start playback at a nonzero PCM value: their
onset offsets skip the fade baked into the beginning of the prepared files.
A retrigger can therefore jump from the outgoing note's zero to the incoming
sample's waveform. The linear release also changes slope abruptly.

The native sample player now applies a 1 ms safety fade at every voice start,
independent of the saved expressive Attack control. Its 5 ms release uses a
cubic smoothstep with zero slope at either end and includes the exact zero
endpoint. Very short events shorten both boundary envelopes to fit. Natural
one-shot exhaustion is capped inside the player as well as in event resolution,
so an overlong gate cannot bypass release by running off the buffer.

This is amplitude processing in the sampler. The Chord Governor still selects
only existing events/assets; no pitch, playback rate, strum, source sample,
pack hash, harmony or score changes. Notes end at their existing gate, harmonic
boundary or choke/retrigger frame, with no added pitched tail or new attack.
The first 1 ms and final 5 ms of playback receive the envelope; the intervening
frames retain their exact original playback value. A longer authored Attack
continues to apply normally.

Native synthetic DC/loop probes verify onset and release continuity, zero
endpoints, unchanged interior frames, natural exhaustion, half-open retriggers,
tiny gates and identical output across 1-, 17- and 256-frame processing blocks.
Allocation remains forbidden during processing. These probes are explicit
fixtures, not extracted music or listening evidence.

`python3 tools/verify_sample_boundaries.py` tests every real source asset through
the actual native executable, once at a shortened gate and once at its natural
end. All 194 probes across 97 assets reach zero within one 24-bit dither LSB at
both ends and preserve pack hashes. With `--previous-renderer PATH`, the audit
also compares the interior PCM bytes against the previous executable; all match.
The old isolated opening discontinuity reached −14.36 dBFS at the probe's
0.5 gain across the four packs. This diagnostic establishes boundary behavior;
it does not certify subjective source quality or remove clicks already embedded
inside a source recording.

All nine source auditions were regenerated, including the unchanged 112-bar,
2:42.91 Parachute score. Repeat renders and seek slices remain byte-identical.
The desktop uses the same native renderer for preview and export.

After pulling, `run-prde1.sh` and `run-demos.sh` verify the installed renderer
against the current build's version, byte count and SHA-256. An old executable
is replaced from the fully verified archive before playback; no compiler is
needed for that update. A matching binary can be reused offline without reading
archive parts. Extracted distributions use their `BUILD_INFO.json` identity.
Conflicting metadata or bad archive payloads leave the existing binary intact.

Current evidence is in `validation/sample-boundaries-0.3.2.json`,
`desktop-check-0.3.2.log`, `source-render-0.3.2.json` and the 0.3.2 distribution's
build-check JSON. Shael's positive 0.3.1 audition and subsequent click report are
retained; the revised demo awaits his audition.
