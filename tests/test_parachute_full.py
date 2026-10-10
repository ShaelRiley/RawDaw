"""Musical and persistence checks for the real-source full-length demonstration."""
import hashlib
import tempfile
import unittest
from pathlib import Path

from prde1.contracts import ROOT, RATE, read_json
from prde1.governor import resolve
from prde1.music import beat, quarter_seconds
from prde1.pack import Pack
from prde1.project import load_project, save_project
from tools.build_parachute_demo import compose
from tools.source_catalog import pack_for_project, projects


class FullParachuteDemo(unittest.TestCase):
    def test_native_song_is_reproducible_editable_and_covered_without_changing_source(self):
        path = ROOT / 'packs/parachute_full.prdeproj'
        project = load_project(path)
        authored, score = compose()
        self.assertEqual(authored, project)
        self.assertEqual(read_json(path.with_suffix('.arrangement.json').read_bytes()), score)
        duration = quarter_seconds(beat(project['length']), project['tempoMap'])
        self.assertTrue(120 <= duration <= 180)
        self.assertIn(path, projects())
        pack_path = pack_for_project(path)
        before = hashlib.sha256(pack_path.read_bytes()).hexdigest()
        with Pack(pack_path) as pack:
            plan = resolve(project, pack)
            self.assertEqual(plan['conflicts'], [])
            self.assertEqual(plan['endFrame'], round(duration * RATE))
            self.assertTrue(all(sample['lineage']['kind'] == 'native' for sample in pack.samples.values()))
            self.assertEqual(project['packReference']['manifestSha256'], pack.manifest_hash)
            with tempfile.TemporaryDirectory() as folder:
                saved = Path(folder) / 'song.prdeproj'
                save_project(saved, project)
                self.assertEqual(resolve(load_project(saved), pack), plan)
            self.assertEqual(resolve(project, pack), plan)
        self.assertEqual(hashlib.sha256(pack_path.read_bytes()).hexdigest(), before)

    def test_form_has_continuous_music_contrasting_sections_and_a_retained_chorus_hook(self):
        project, score = compose()
        sections = score['sections']
        self.assertEqual(sections[0]['startBeat'], '0')
        self.assertEqual(sections[-1]['endBeat'], project['length'])
        self.assertTrue(all(left['endBeat'] == right['startBeat'] for left, right in zip(sections, sections[1:])))
        patterns = {pattern['id']: pattern for pattern in project['patterns']}
        uses = project['instances']
        chorus_lead = [item for item in uses if item['id'].startswith(('chorus_1_lead_', 'chorus_2_lead_', 'final_chorus_lead_'))]
        self.assertEqual(len({item['patternId'] for item in chorus_lead}), 1)
        self.assertTrue(all(item['linked'] for item in chorus_lead))
        hook = patterns[chorus_lead[0]['patternId']]
        self.assertTrue(all(event['expression']['locked'] and event['expression']['playPercent'] == 100 for event in hook['events']))
        self.assertGreater(len(hook['events']), len(patterns['verse_lead']['events']))
        self.assertGreater(len(patterns['chorus_drums']['events']), len(patterns['bridge_drums']['events']))
        self.assertNotEqual(patterns['verse_lead']['events'], patterns['verse_2_lead']['events'])
        # Check placed, enabled music in every measure; length isn't silence
        # appended to the original four-bar audition.
        occupied = set()
        for instance in uses:
            for event in patterns[instance['patternId']]['events']:
                if event['enabled']:
                    occupied.add(int((beat(instance['beat']) + beat(event['beat'])) // 4))
        self.assertEqual(occupied, set(range(112)))
        drum_sounds = {event['choice']['soundIdentity'] for pattern in patterns.values() if pattern['role'] == 'drums' for event in pattern['events']}
        self.assertEqual(drum_sounds, {'parachute_kick', 'parachute_snare', 'parachute_hatClosed'})


if __name__ == '__main__':
    unittest.main()
