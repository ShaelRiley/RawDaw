"""Integration checks against the shipped real-source packs, never synthetic stand-ins."""
import hashlib
import json
import tempfile
import unittest
import zipfile
from pathlib import Path

from prde1.contracts import ROOT, read_json
from prde1.governor import resolve
from prde1.midi import inspect_midi
from prde1.pack import Pack
from prde1.project import load_project, save_project
from tools.build_fixture import event, midi_drums
from tools.source_catalog import recipes


class SourcePackTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.recipes=recipes()
        cls.paths=[ROOT/'packs'/(recipe['packId']+'.prdepack') for recipe in cls.recipes]

    def test_three_cc_and_one_user_authorized_pack_with_explicit_gaps(self):
        self.assertEqual(len(self.paths),4)
        self.assertEqual(sum(recipe['license']=='CC BY 3.0' for recipe in self.recipes),3)
        for path,recipe in zip(self.paths,self.recipes):
            with self.subTest(pack=path.name),Pack(path) as pack:
                primary=recipe.get('primarySourceInput','mix')
                self.assertEqual(pack.manifest['source']['sha256'],recipe['inputs'][primary]['sha256'])
                self.assertEqual(pack.manifest['source']['kind'],'authorized_recording')
                self.assertEqual(pack.manifest['source']['license'],recipe['license'])
                self.assertEqual(pack.manifest['validation']['status'],'coverage-limited')
                self.assertTrue(pack.warnings)
                for slot in ('hatOpen','tom1','tom2'):
                    self.assertEqual(pack.manifest['instruments']['drums'][slot]['status'],'unavailable')
                    self.assertIsNone(pack.manifest['instruments']['drums'][slot]['sampleId'])

    def test_every_sample_has_real_source_lineage_and_no_loops(self):
        for path,recipe in zip(self.paths,self.recipes):
            expected={key+':'+value['sha256'] for key,value in recipe['inputs'].items()}
            with self.subTest(pack=path.name),Pack(path) as pack,zipfile.ZipFile(path) as archive:
                qa=read_json(archive.read('qa/report.json'))
                provenance=read_json(archive.read('provenance.json'))
                self.assertEqual(qa['humanListening'],'not_performed')
                self.assertEqual(qa['releaseQualityGate'],'open')
                self.assertEqual(qa['syntheticAssets'],0)
                self.assertEqual(provenance['ingredients'],recipe['inputs'])
                for sample in pack.samples.values():
                    self.assertIn(sample['lineage']['kind'],('native','pre-rendered'))
                    self.assertIsNone(sample['loop'])
                    self.assertTrue(sample['quality']['accepted'])
                    source=sample['lineage']['sourceAsset']
                    self.assertTrue(source in expected or source in pack.samples)
                for asset in qa['assets']:
                    if 'semitones' in asset:
                        self.assertLessEqual(abs(asset['semitones']),3.25)
                    if 'pitch' in asset:
                        self.assertLessEqual(abs(asset['pitch']['centsFromTarget']),45)
                self.assertFalse(any(name.endswith(('.mp3','.flac','.zip')) for name in archive.namelist()))

    def test_source_drums_keep_tempo_addresses_and_saved_timing_corrections(self):
        for path,recipe in zip(self.paths,self.recipes):
            with self.subTest(pack=path.name),zipfile.ZipFile(path) as archive:
                raw=archive.read('clips/source-midi/source_groove.mid')
                self.assertIn(b'\xff\x51\x03'+round(60000000/recipe['bpm']).to_bytes(3,'big'),raw)
                inspected=inspect_midi(raw)
                clip=read_json(archive.read('clips/normalized/source_groove.json'))
                manifest=read_json(archive.read('manifest.json'))
                addresses={r['midiAddress'] for r in manifest['instruments']['drums'].values() if r['status']=='available'}
                self.assertEqual(len(inspected['notes']),len(clip['events']))
                self.assertTrue(all(note['note'] in addresses for note in inspected['notes']))
                analysis=read_json(archive.read('analysis/harmony.json'))
                self.assertEqual(len(analysis['retainedDrumAssignments']),len(clip['events']))

    def test_eight_projects_resolve_and_reopen_without_altered_export(self):
        with tempfile.TemporaryDirectory() as folder:
            for path in self.paths:
                with Pack(path) as pack:
                    before={key:hashlib.sha256((pack.root/sample['path']).read_bytes()).hexdigest() for key,sample in pack.samples.items()}
                    for suffix in ('a','b'):
                        project=load_project(path.with_name(path.stem+'_'+suffix+'.prdeproj'))
                        plan=resolve(project,pack)
                        self.assertEqual(plan['conflicts'],[])
                        self.assertTrue(plan['events'])
                        self.assertTrue(all(plan['assets'][e['assetIndex']]['id'] in pack.samples for e in plan['events']))
                        saved=Path(folder)/(path.stem+suffix+'.prdeproj')
                        save_project(saved,project)
                        self.assertEqual(load_project(saved),project)
                    after={key:hashlib.sha256((pack.root/sample['path']).read_bytes()).hexdigest() for key,sample in pack.samples.items()}
                    self.assertEqual(before,after)

    def test_parachute_preserves_user_rights_and_only_native_supplied_ingredients(self):
        recipe=next(r for r in self.recipes if r['packId']=='parachute')
        with Pack(ROOT/'packs/parachute.prdepack') as pack,zipfile.ZipFile(ROOT/'packs/parachute.prdepack') as archive:
            provenance=read_json(archive.read('provenance.json'))
            source=pack.manifest['source']
            self.assertEqual(source['title'],'Parachute')
            self.assertEqual(source['rightsDeclaration'],recipe['rightsDeclaration'])
            self.assertNotEqual(source['license'],'CC BY 3.0')
            self.assertFalse(provenance['licenseEvidence']['creativeCommonsGrant'])
            self.assertFalse(provenance['licenseEvidence']['independentlyVerified'])
            self.assertEqual(source['sha256'],recipe['inputs']['archive']['sha256'])
            selected={'lead','rhythm','bass','drums'}
            allowed={key+':'+recipe['inputs'][key]['sha256'] for key in selected}
            self.assertTrue(all(s['lineage']['kind']=='native' and s['lineage']['sourceAsset'] in allowed
                                for s in pack.samples.values()))
            self.assertTrue(all(s['lineage']['transformationCost']==0 for s in pack.samples.values()))
            self.assertTrue(all(len(s['pitches'])>1 for s in pack.samples.values() if s['role']=='rhythm'))
            self.assertEqual(pack.manifest['instruments']['lead']['displayName'],recipe['roleLabels']['lead'])
            self.assertTrue(all(pack.manifest['instruments']['drums'][slot]['status']=='empty'
                                for slot in ('extra1','extra2')))

    def test_non_default_midi_tempo_is_preserved_and_invalid_tempo_rejected(self):
        pattern={'events':[event('hit','0','1/4','drum',sound='kick')]}
        for bpm in (100,113,130):
            raw=midi_drums(pattern,{'kick':36},bpm)
            self.assertIn(b'\xff\x51\x03'+round(60000000/bpm).to_bytes(3,'big'),raw)
            self.assertEqual(inspect_midi(raw)['notes'][0]['note'],36)
        for bpm in (0,301,float('nan')):
            with self.assertRaises(ValueError):midi_drums(pattern,{'kick':36},bpm)


if __name__=='__main__':unittest.main()
