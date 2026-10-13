"""Verify the complete harmony inventory on real packs and render varied examples."""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
import wave
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from prde1 import progression_bank as lib
from prde1.contracts import ROOT, atomic_json, canonical_bytes
from prde1.editor import Editor, new_project
from prde1.governor import resolve
from prde1.music import MODES, at, chord_identity
from prde1.pack import Pack
from prde1.project import load_project

EXAMPLES = ('Open road', 'Nightfall circle', 'Soft landing seven', 'Twelve-bar dominant blues',
            'Suspended return', 'Dorian light', 'Lydian window', 'Locrian half-diminished field')


def verify():
    entries = lib.catalog(); results = []
    prototypes = {}
    for p in sorted((ROOT / 'packs').glob('*.prdeproj')):
        project = load_project(p); prototypes.setdefault(project['packReference']['packId'], project)
    for path in sorted((ROOT / 'packs').glob('*.prdepack')):
        before = hashlib.sha256(path.read_bytes()).hexdigest()
        with Pack(path) as pack:
            prototype = prototypes[pack.manifest['packId']]
            tone = prototype['tonalityMap'][0]
            editor = Editor(new_project(pack, tone['tonic'], tone['mode']), pack)
            original = canonical_bytes(editor.project)
            samples_before_ranking = len(pack.samples)
            for tonic in range(12):
                for mode in MODES:
                    rows = lib.ranked(pack, tonic, mode)
                    assert len(rows) == len(entries) and all(r['playable'] for r in rows)
                    assert sum(r['recommended'] for r in rows) >= 20
            assert len(pack.samples) == samples_before_ranking
            events = 0
            for entry in entries:
                loaded = Editor(editor.project, pack); lib.load_into(loaded, entry, grow_empty=True)
                assert lib.beat(loaded.project['length']) >= lib.cycle_end(editor.project, entry)
                assert len(loaded.project['harmony']) >= len(entry['sequence'])
                preview = lib.audition_project(editor, entry)
                plan = resolve(preview, pack)
                assert not plan['conflicts'] and len(plan['events']) == len(entry['sequence'])
                for event, governing in zip(plan['events'], preview['harmony']):
                    tonality = at(preview['tonalityMap'], 0)
                    _, pitches, _ = chord_identity(tonality['tonic'], tonality['mode'], governing['chord'])
                    assert {p % 12 for p in event['notePitches']} == set(pitches)
                events += len(plan['events'])
                assert canonical_bytes(editor.project) == original
            rendered = []
            with tempfile.TemporaryDirectory(prefix='raw-daw-progression-qa-') as temp:
                root = Path(temp)
                for name in EXAMPLES:
                    entry = next(e for e in entries if e['name'] == name)
                    audition_editor = Editor(new_project(pack, tone['tonic'], entry['modes'][0]), pack)
                    plan = resolve(lib.audition_project(audition_editor, entry), pack)
                    plan_path = root / 'plan.json'; plan_path.write_bytes(canonical_bytes(plan))
                    audio = root / 'audition.wav'
                    run = subprocess.run([str(ROOT / 'build/prde1-render'), str(plan_path), str(pack.root), str(audio), '0'],
                                         check=True, capture_output=True, text=True)
                    report = json.loads(run.stdout)
                    with wave.open(str(audio)) as pcm:
                        assert pcm.getnchannels() == 2 and pcm.getframerate() == 48000 and pcm.getnframes() > 0
                        frames = pcm.getnframes()
                        assert any(pcm.readframes(min(frames, 48000)))
                    rendered.append(dict(name=name, mode=entry['modes'][0], frames=frames,
                                         sha256=hashlib.sha256(audio.read_bytes()).hexdigest(), report=report))
            results.append(dict(packId=pack.manifest['packId'], catalogAuditions=len(entries),
                                loadedEmptySongs=len(entries),
                                resolvedChordEvents=events, rankedCandidates=12 * len(MODES) * len(entries),
                                renderExamples=rendered, packSha256=before, packUnchanged=True))
        assert hashlib.sha256(path.read_bytes()).hexdigest() == before
        print(f'{path.name}: {len(entries)} auditions resolved, {len(EXAMPLES)} native WAVs rendered, pack unchanged', flush=True)
    return dict(inventory=len(entries), kinds=dict(Counter(e['kind'] for e in entries)),
                styles=dict(Counter(e['style'] for e in entries)),
                curatedPerMode={m: sum(m in e['modes'] for e in entries) for m in MODES},
                catalogSha256=hashlib.sha256(lib.DATA.read_bytes()).hexdigest(), packs=results,
                automaticPreviewCount=len(results) * len(entries), nativeRenderedExamples=len(results) * len(EXAMPLES),
                humanListeningPerformed=False, physicalDeviceTestingPerformed=False)


if __name__ == '__main__':
    result = verify()
    atomic_json(ROOT / 'docs/validation/progression-bank-verification.json', result)
    print('Saved progression bank verification.')
