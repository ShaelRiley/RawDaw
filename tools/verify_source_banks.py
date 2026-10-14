"""Audit complete source-derived banks and render all root-position chords.

This verifies functional coverage and provenance, not indistinguishable timbre
or subjective listening quality. Original source archives must remain intact.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
import time
import wave
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from prde1.contracts import RATE, atomic_json, canonical_bytes
from prde1.coverage import VERSION as BANK_VERSION
from prde1.governor import resolve
from prde1.music import QUALITIES, REGISTERS
from prde1.pack import Pack
from prde1.percussion import GM, record as percussion_record
from prde1.project import load_project
from tools.build_fixture import event


def pcm(raw):
    octets = np.frombuffer(raw, dtype=np.uint8).reshape(-1, 3).astype(np.int32)
    words = octets[:, 0] | octets[:, 1] << 8 | octets[:, 2] << 16
    return np.where(words & 0x800000, words - 0x1000000, words) / 8388608.0


def verify():
    reports = []
    for path in sorted((ROOT / 'packs').glob('*.prdepack')):
        archive_hash = hashlib.sha256(path.read_bytes()).hexdigest()
        started = time.monotonic()
        with Pack(path) as pack, tempfile.TemporaryDirectory(prefix='raw-daw-bank-audit-') as folder:
            inventory = pack.coverage.prepare_bank()
            assert inventory['percussionAddresses'] == list(range(35, 82))
            for role, (low, high) in REGISTERS.items():
                for note in range(low, high + 1):
                    sample = pack.sample_for((role, note))
                    assert sample['pitches'] == [note]
                    assert sample['lineage']['kind'] != 'synthetic'
                    with wave.open(str(pack.root / sample['path'])) as stream:
                        values = pcm(stream.readframes(stream.getnframes()))
                    assert np.isfinite(values).all() and np.max(np.abs(values)) > 1e-5, (role, note)
            base = load_project(path.with_name(path.stem + '_a.prdeproj'))
            all_chords = [(root, quality) for quality in QUALITIES for root in range(12)]
            count = len(all_chords)
            base.update(length=str(count), tempoMap=[dict(beat='0', quarterBpm=120)],
                        meterMap=[dict(beat='0', numerator=4, denominator=4, governorSegments=4)],
                        tonalityMap=[dict(beat=str(i), tonic=root, mode='major')
                                     for i, (root, _) in enumerate(all_chords)],
                        harmony=[dict(beat=str(i), chord=dict(degree=1, alteration=0,
                                                            quality=quality, inversion=0))
                                 for i, (_, quality) in enumerate(all_chords)],
                        patterns=[dict(id='bank_audit', role='rhythm', length=str(count),
                                       events=[event('chord_' + str(i), i, '1', 'chord') for i in range(count)],
                                       provenance=dict(sourceClip='source bank audit', license='MIT', changes='none'))],
                        instances=[dict(id='bank_audit_instance', patternId='bank_audit', beat='0', linked=False)])
            plan = resolve(base, pack)
            assert not plan['conflicts'] and len(plan['events']) == count
            for voice, (root, quality) in zip(plan['events'], all_chords):
                assert {n % 12 for n in voice['notePitches']} == {(root + i) % 12 for i in QUALITIES[quality]}
                sample = pack.samples[plan['assets'][voice['assetIndex']]['id']]
                assert sample['lineage']['kind'] != 'synthetic'
            work = Path(folder)
            (work / 'plan.json').write_bytes(canonical_bytes(plan))
            run = subprocess.run([str(ROOT / 'build/prde1-render'), str(work / 'plan.json'),
                                  str(pack.root), str(work / 'all-chords.wav')], capture_output=True, text=True)
            if run.returncode:
                raise RuntimeError(run.stderr)
            with wave.open(str(work / 'all-chords.wav')) as stream:
                for i in range(count):
                    stream.setpos(i * RATE // 2 + 2400)
                    assert np.max(np.abs(pcm(stream.readframes(2048)))) > 1e-5, all_chords[i]
            chord_digest = hashlib.sha256((work/'all-chords.wav').read_bytes()).hexdigest()
            drum_count = len(GM)
            base.update(length=str(drum_count),
                        tonalityMap=[dict(beat='0', tonic=0, mode='major')],
                        harmony=[dict(beat='0', chord=dict(degree=1, alteration=0, quality='major', inversion=0))],
                        patterns=[dict(id='percussion_audit', role='drums', length=str(drum_count),
                                       events=[event('drum_'+str(address), i, '1/4', 'drum',
                                                     sound=percussion_record(pack,'gm_'+str(address))['soundIdentity'])
                                               for i,address in enumerate(GM)],
                                       provenance=dict(sourceClip='source percussion audit', license='MIT', changes='none'))],
                        instances=[dict(id='percussion_audit_instance', patternId='percussion_audit', beat='0', linked=False)])
            drum_plan = resolve(base, pack)
            assert not drum_plan['conflicts'] and len(drum_plan['events']) == drum_count
            assert [voice['drumMidiAddress'] for voice in drum_plan['events']] == list(GM)
            (work/'plan.json').write_bytes(canonical_bytes(drum_plan))
            drums = subprocess.run([str(ROOT/'build/prde1-render'),str(work/'plan.json'),
                                    str(pack.root),str(work/'all-percussion.wav')],capture_output=True,text=True)
            if drums.returncode:raise RuntimeError(drums.stderr)
            with wave.open(str(work/'all-percussion.wav')) as stream:
                for i,address in enumerate(GM):
                    stream.setpos(i*RATE//2+240)
                    assert np.max(np.abs(pcm(stream.readframes(2048)))) > 1e-5, address
            report = dict(pack=path.name, archiveSha256=archive_hash, bankVersion=BANK_VERSION,
                          inventory=inventory, noteAddressesAudited=sum(high-low+1 for low, high in REGISTERS.values()),
                          rootChordsRendered=count, renderedSha256=chord_digest,
                          percussionAddressesRendered=drum_count,
                          percussionRenderedSha256=hashlib.sha256((work/'all-percussion.wav').read_bytes()).hexdigest(),
                          render=json.loads(run.stdout), elapsedSeconds=round(time.monotonic()-started, 3),
                          syntheticFallbackAssets=0, sourceArchiveUnchanged=True,
                          humanListeningPerformed=False, physicalDeviceTestingPerformed=False)
        assert hashlib.sha256(path.read_bytes()).hexdigest() == archive_hash
        reports.append(report)
        print(path.name, report['noteAddressesAudited'], 'notes;', count, 'chords rendered', flush=True)
    assert len(reports) == len(list((ROOT/'packs').glob('*.prdepack')))
    atomic_json(ROOT / 'docs/validation/source-banks-0.4.0.json', reports)
    return reports


if __name__ == '__main__':
    verify()
