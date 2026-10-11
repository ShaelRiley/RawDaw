"""Complete songs preserve source coverage, editable form and recurring hooks."""
import hashlib
import tempfile
import unittest
from pathlib import Path

from prde1.contracts import ROOT, RATE, read_json
from prde1.governor import resolve
from prde1.music import beat, chord_identity, at, quarter_seconds
from prde1.pack import Pack
from prde1.project import load_project, save_project
from tools.build_full_demos import PROFILES, SOUNDS, compose
from tools.source_catalog import pack_for_project, projects


class FullSongCatalog(unittest.TestCase):
    def test_complete_songs_reopen_and_select_only_covered_immutable_sources(self):
        self.assertEqual(len(projects()), 12)
        for pack_id in PROFILES:
            with self.subTest(pack=pack_id):
                path = ROOT / 'packs' / (pack_id + '_full.prdeproj')
                project = load_project(path)
                authored, score = compose(pack_id)
                self.assertEqual(authored, project)
                self.assertEqual(read_json(path.with_suffix('.arrangement.json').read_bytes()), score)
                duration = quarter_seconds(beat(project['length']), project['tempoMap'])
                self.assertTrue(120 <= duration <= 180)
                pack_path = pack_for_project(path)
                digest = hashlib.sha256(pack_path.read_bytes()).hexdigest()
                with Pack(pack_path) as pack:
                    plan = resolve(project, pack)
                    self.assertEqual(plan['conflicts'], [])
                    self.assertEqual(plan['endFrame'], round(duration * RATE))
                    self.assertEqual(project['packReference']['manifestSha256'], pack.manifest_hash)
                    # Every governing chord must also be legal in the declared
                    # mode, including F major/Dorian and the relative-minor bridge.
                    for item in project['harmony']:
                        tone = at(project['tonalityMap'], beat(item['beat']))
                        self.assertTrue(chord_identity(tone['tonic'], tone['mode'], item['chord'])[2])
                    with tempfile.TemporaryDirectory() as folder:
                        saved = Path(folder) / 'song.prdeproj'
                        save_project(saved, project)
                        self.assertEqual(resolve(load_project(saved), pack), plan)
                    self.assertEqual(resolve(project, pack), plan)
                self.assertEqual(hashlib.sha256(pack_path.read_bytes()).hexdigest(), digest)

    def test_each_form_contains_music_contrast_and_the_same_refrain_hook(self):
        hooks = []
        for pack_id in PROFILES:
            with self.subTest(pack=pack_id):
                project, score = compose(pack_id)
                sections = score['sections']
                self.assertEqual(sections[0]['startBeat'], '0')
                self.assertEqual(sections[-1]['endBeat'], project['length'])
                self.assertTrue(all(a['endBeat'] == b['startBeat'] for a, b in zip(sections, sections[1:])))
                patterns = {item['id']: item for item in project['patterns']}
                occupied = set()
                for instance in project['instances']:
                    for event in patterns[instance['patternId']]['events']:
                        if event['enabled']:
                            occupied.add(int((beat(instance['beat']) + beat(event['beat'])) // 4))
                self.assertEqual(occupied, set(range(score['bars'])))
                choruses = [item for item in project['instances'] if item['id'].startswith(
                    ('chorus_1_lead_', 'chorus_2_lead_', 'final_chorus_lead_'))]
                self.assertEqual(len({item['patternId'] for item in choruses}), 1)
                self.assertTrue(all(item['linked'] for item in choruses))
                hook = patterns[choruses[0]['patternId']]['events']
                self.assertTrue(all(event['expression']['locked'] and event['expression']['playPercent'] == 100 for event in hook))
                self.assertGreater(len(hook), len(patterns['verse_lead']['events']))
                self.assertNotEqual(patterns['verse_lead']['events'], patterns['verse_2_lead']['events'])
                self.assertGreater(len(patterns['chorus_drums']['events']), len(patterns['bridge_drums']['events']))
                available = {pack_id + '_source_' + name for name in SOUNDS[pack_id].values()}
                used = {event['choice']['soundIdentity'] for pattern in patterns.values() if pattern['role'] == 'drums' for event in pattern['events']}
                self.assertEqual(used, available)
                hooks.append([(event['beat'], event['choice']['tone']) for event in hook])
        self.assertEqual(len({tuple(item) for item in hooks}), 3)


if __name__ == '__main__':
    unittest.main()
