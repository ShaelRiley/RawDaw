"""Render every registered chord in all four shipped packs and inspect PCM."""
from __future__ import annotations
import copy
import hashlib
import json
import subprocess
import sys
import tempfile
import wave
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from prde1.contracts import RATE, canonical_bytes
from prde1.governor import resolve, rank_progressions
from prde1.music import QUALITIES, REGISTERS, MODES
from prde1.pack import Pack
from prde1.project import load_project
from tools.build_fixture import event


def main():
    reports = []
    for path in sorted((ROOT / 'packs').glob('*.prdepack')):
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        base = load_project(path.with_name(path.stem + '_a.prdeproj'))
        report = dict(pack=path.name, originalSha256=digest, chordsRendered=0, notesPrepared=0, silentEvents=0, conflicts=0)
        with Pack(path) as pack, tempfile.TemporaryDirectory() as folder:
            work = Path(folder)
            for tonic in range(12):
                for mode in MODES:
                    assert all(row['playable'] and not row['missing'] for row in rank_progressions(pack, tonic, mode))
            for role, (low, high) in REGISTERS.items():
                for note in range(low, high + 1):
                    sample = pack.sample_for((role, note))
                    assert sample['pitches'] == [note]
                    report['notesPrepared'] += 1
            for quality, intervals in QUALITIES.items():
                project = copy.deepcopy(base)
                count = 12 * len(intervals)
                project['length'] = str(count)
                project['tempoMap'] = [dict(beat='0', quarterBpm=120)]
                project['meterMap'] = [dict(beat='0', numerator=4, denominator=4, governorSegments=4)]
                project['tonalityMap'] = [dict(beat=str(i), tonic=i // len(intervals), mode='major') for i in range(count)]
                project['harmony'] = [dict(beat=str(i), chord=dict(degree=1, alteration=0, quality=quality, inversion=i % len(intervals))) for i in range(count)]
                project['patterns'] = [dict(id='audit', role='rhythm', length=str(count),
                    events=[event('audit_' + str(i), i, '1', 'chord') for i in range(count)],
                    provenance=dict(sourceClip='musical coverage audit', license='MIT', changes='none'))]
                project['instances'] = [dict(id='audit_instance', patternId='audit', beat='0', linked=False)]
                plan = resolve(project, pack)
                assert plan['conflicts'] == [] and len(plan['events']) == count
                for i, voice in enumerate(plan['events']):
                    root = i // len(intervals); inversion = i % len(intervals)
                    assert {n % 12 for n in voice['notePitches']} == {(root + interval) % 12 for interval in intervals}
                    assert min(voice['notePitches']) % 12 == (root + intervals[inversion]) % 12
                (work / 'plan.json').write_bytes(canonical_bytes(plan))
                result = subprocess.run([str(ROOT / 'build/prde1-render'), str(work / 'plan.json'), str(pack.root), str(work / 'render.wav')], capture_output=True, text=True)
                if result.returncode: raise RuntimeError(result.stderr)
                with wave.open(str(work / 'render.wav')) as audio:
                    for i in range(count):
                        audio.setpos(i * RATE // 2 + 2400)
                        raw = audio.readframes(2048)
                        assert max(abs(int.from_bytes(raw[j:j + 3], 'little', signed=True)) for j in range(0, len(raw), 3)) > 1000
                report['chordsRendered'] += count
            report['reconstructedAssetCount'] = sum(s['id'].startswith('hybrid_') for s in pack.samples.values())
            report['kitSlotsPlayable'] = [slot for slot, row in pack.instruments['drums'].items() if row['status'] == 'available']
        assert hashlib.sha256(path.read_bytes()).hexdigest() == digest
        report.update(packUnchanged=True, humanListening='not_performed', pcmAudited=True)
        reports.append(report)
        print(path.name, report['chordsRendered'], 'chords rendered without gaps', flush=True)
    assert len(reports) == 4
    target = ROOT / 'docs/validation/full-chord-coverage.json'
    target.parent.mkdir(exist_ok=True)
    target.write_text(json.dumps(reports, indent=2) + '\n')


if __name__ == '__main__':
    main()
