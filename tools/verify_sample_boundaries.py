"""Probe real prepared assets through the native player; no listening claim."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import subprocess
import sys
import tempfile
import wave
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from prde1 import __version__
from prde1.contracts import VERSION, canonical_bytes
from prde1.pack import Pack
from tools.source_catalog import recipes


def pcm(path):
    with wave.open(str(path), 'rb') as stream:
        assert (stream.getframerate(), stream.getsampwidth(), stream.getnchannels()) == (48000, 3, 2)
        return stream.readframes(stream.getnframes())


def frame(data, index):
    raw = data[index * 6:(index + 1) * 6]
    return [int.from_bytes(raw[i:i + 3], 'little', signed=True) for i in (0, 3)]


def verify(output, previous_renderer=None):
    records = []
    packs = []
    with tempfile.TemporaryDirectory(prefix='prde1-boundaries-') as folder:
        folder = Path(folder)
        for recipe in recipes():
            source = ROOT / 'packs' / (recipe['packId'] + '.prdepack')
            before = hashlib.sha256(source.read_bytes()).hexdigest()
            with Pack(source) as pack:
                for asset in pack.manifest['samples']:
                    assert asset['loop'] is None, 'This real-source audit covers one-shot assets'
                    available = asset['frames'] - asset['onsetFrame']
                    for kind, duration in [('shortened_gate', min(4800, available)), ('natural_end', available)]:
                        start, end = 256, 256 + duration
                        plan = dict(formatVersion=VERSION, sampleRate=48000, endFrame=end + 256,
                                    assets=[dict(id=asset['id'], path=asset['path'], channels=asset['channels'],
                                                 frames=asset['frames'], onsetFrame=asset['onsetFrame'],
                                                 loopStart=0, loopEnd=0)],
                                    events=[dict(assetIndex=0, startFrame=start, endFrame=end,
                                                 attackFrames=0, releaseFrames=min(240, duration), gain=0.5, pan=0)],
                                    compressor=dict(on=False, thresholdDb=-12, ratio=2, attackMs=10, releaseMs=150),
                                    masterGain=1, peakCeilingDb=-0.1)
                        manifest = folder / 'probe.json'
                        manifest.write_bytes(canonical_bytes(plan))
                        result = subprocess.run([str(ROOT / 'build/prde1-render'), str(manifest), str(pack.root),
                                                 str(folder / 'new.wav')], check=True, capture_output=True, text=True)
                        data = pcm(folder / 'new.wav')
                        first, last = frame(data, start), frame(data, end - 1)
                        # Counter-addressed TPDF dither may leave one 24-bit LSB.
                        assert max(abs(value) for value in first + last) <= 1, (source.name, asset['id'], kind)
                        assert json.loads(result.stdout)['frames'] == end + 256
                        record = dict(pack=source.name, asset=asset['id'], boundary=kind, durationFrames=duration,
                                      firstFrameLsb=first, lastFrameLsb=last)
                        if previous_renderer:
                            subprocess.run([str(previous_renderer), str(manifest), str(pack.root),
                                            str(folder / 'old.wav')], check=True, capture_output=True, text=True)
                            old = pcm(folder / 'old.wav')
                            record['previousFirstFrameLsb'] = frame(old, start)
                            interior_start, interior_end = start + 48, end - min(240, duration)
                            assert data[interior_start * 6:interior_end * 6] == old[interior_start * 6:interior_end * 6]
                            record['interiorComparedFrames'] = max(0, interior_end - interior_start)
                            record['interiorByteIdenticalToPrevious'] = True
                        records.append(record)
            assert hashlib.sha256(source.read_bytes()).hexdigest() == before
            packs.append(dict(pack=source.name, sha256=before, unchanged=True))
            print(source.name, 'start/end boundaries and immutable pack passed', flush=True)
    previous_peak = max((abs(value) for record in records for value in record.get('previousFirstFrameLsb', [0])), default=0)
    report = dict(version=__version__, sampleRate=48000, attackSafetyMs=1, releaseMs=5,
                  curve='cubic smoothstep with zero slope at both endpoints',
                  assetCount=len(records) // 2, probes=len(records), packs=packs,
                  maxEndpointLsb=max(abs(v) for r in records for v in r['firstFrameLsb'] + r['lastFrameLsb']),
                  previousMaxOpeningStepDbFS=20 * math.log10(previous_peak / (1 << 23)) if previous_peak else None,
                  interiorComparisonPerformed=bool(previous_renderer),
                  humanListening='not_performed; automated boundaries do not certify source quality', probesByAsset=records)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({key: value for key, value in report.items() if key not in ('packs', 'probesByAsset')}, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT / 'out/sample-boundaries/validation.json')
    parser.add_argument('--previous-renderer', type=Path)
    arguments = parser.parse_args()
    verify(arguments.output, arguments.previous_renderer)
