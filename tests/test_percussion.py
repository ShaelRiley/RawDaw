"""The full GM kit retains MIDI identities, source lineage and native mixing."""
import copy
import hashlib
import subprocess
import tempfile
import unittest
import wave
from fractions import Fraction as F
from pathlib import Path

from prde1.contracts import ROOT, SLOTS, canonical_bytes
from prde1.editor import Editor, new_project
from prde1.midi import encode_notes, inspect_midi
from prde1.pack import Pack
from prde1.percussion import GM, prepare_bank, record, records, sample
from prde1.project import load_project
from prde1.sequencer import row_defaults, settings
from tools.build_fixture import make_fixture


class CompletePercussion(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.root = Path(cls.temp.name)
        cls.path = make_fixture(cls.root/'fixture', extras=0)
    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_all_47_addresses_import_export_save_and_render_through_original_mixer_families(self):
        with Pack(self.path) as pack:
            editor = Editor(new_project(pack, bars=12), pack)
            instance = editor.add_pattern('drums', F(0), F(48))
            incoming = self.root/'all-gm.mid'
            incoming.write_bytes(encode_notes([dict(beat=F(i), duration=F(1,8), note=address,
                                  velocity=.5, channel=9) for i, address in enumerate(GM)]))
            editor.import_midi(instance, incoming)
            plan = editor.plan()
            self.assertFalse(plan['conflicts'])
            self.assertEqual([event['drumMidiAddress'] for event in plan['events']], list(GM))
            self.assertEqual({event['role'] for event in plan['events']}, {'drums.'+slot for slot in SLOTS})
            self.assertEqual(len(plan['events']), 47)
            self.assertEqual({row['sound'] for row in settings(editor.pattern(instance),pack)['rows']},
                             {*SLOTS, *['gm_'+str(address) for address in GM]})
            path = self.root/'all-gm.prdeproj'; editor.save(path)
            self.assertEqual(Editor(load_project(path), pack, path).plan(), plan)
            exported = self.root/'roundtrip.mid'; editor.export_midi(instance, exported)
            notes = inspect_midi(exported.read_bytes())['notes']
            self.assertEqual([note['note'] for note in notes], list(GM))
            self.assertEqual([note['tick'] for note in notes], [i*960 for i in range(47)])
            self.assertTrue(all(note['channel']==9 and note['velocity']==64 for note in notes))
            plan_path = self.root/'gm-plan.json'; plan_path.write_bytes(canonical_bytes(plan))
            output = self.root/'all-gm.wav'
            process = subprocess.run([str(ROOT/'build/prde1-render'),str(plan_path),str(pack.root),str(output)], capture_output=True,text=True)
            self.assertEqual(process.returncode,0,process.stderr)
            with wave.open(str(output)) as audio:
                self.assertEqual((audio.getframerate(),audio.getsampwidth(),audio.getnchannels()), (48000,3,2))
                for event in plan['events']:
                    audio.setpos(event['startFrame'])
                    raw = audio.readframes(event['endFrame']-event['startFrame'])
                    self.assertGreater(max(abs(int.from_bytes(raw[i:i+3],'little',signed=True)) for i in range(0,len(raw),3)),10)

    def test_real_pack_bank_is_source_only_lazy_deterministic_and_preserves_empty_extras(self):
        path = ROOT/'packs/parachute.prdepack'; before = hashlib.sha256(path.read_bytes()).hexdigest()
        with Pack(path) as pack:
            original = copy.deepcopy(pack.manifest)
            count = len(pack.samples)
            mapped = records(pack)
            self.assertEqual(len(mapped),55)
            self.assertEqual(len(pack.samples),count)
            result = prepare_bank(pack)
            self.assertEqual([row['midiAddress'] for row in result],list(range(35,82)))
            signatures = {}
            for address in GM:
                slot = 'gm_'+str(address); row = record(pack,slot); sound = sample(pack,slot)
                self.assertEqual(row['pitchClass'],'unpitched')
                self.assertIn(row['mixSlot'],SLOTS)
                self.assertNotEqual(sound['lineage']['kind'],'synthetic')
                if row['derived']:
                    self.assertEqual(sound['lineage']['kind'],'pre-rendered')
                    self.assertEqual(sound['lineage']['sourceAsset'],row['sourceAsset'])
                    self.assertIn('approximate articulation',sound['lineage']['recipe'])
                signatures[address] = (row['soundIdentity'],sound['sha256'])
            self.assertEqual(pack.manifest,original)
        with Pack(path) as pack:
            for address in GM:
                slot = 'gm_'+str(address)
                self.assertEqual((record(pack,slot)['soundIdentity'],sample(pack,slot)['sha256']),signatures[address])
        with Pack(self.path) as pack:
            self.assertEqual(pack.instruments['drums']['extra1']['status'],'empty')
            self.assertEqual(pack.instruments['drums']['extra2']['status'],'empty')
            prepare_bank(pack)
            self.assertEqual(pack.instruments['drums']['extra1']['status'],'empty')
            self.assertEqual(pack.instruments['drums']['extra2']['status'],'empty')
        self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(),before)

    def test_legacy_kit_rows_expand_without_mutating_saved_controls(self):
        with Pack(self.path) as pack:
            pattern = dict(role='drums',length='4')
            config = settings(pattern,pack)
            config.pop('bankProfile')
            config['rows'] = [row for row in config['rows'] if row['sound'] in SLOTS]
            config['rows'][0].update(velocityScale=.3, muted=True)
            pattern['sequencer'] = config; before = copy.deepcopy(pattern)
            expanded = settings(pattern,pack)
            self.assertEqual(len(expanded['rows']),55)
            self.assertEqual(expanded['rows'][0],config['rows'][0])
            self.assertEqual(pattern,before)

    def test_named_gm_hits_work_in_event_editor_and_row_paste(self):
        with Pack(self.path) as pack:
            editor = Editor(new_project(pack), pack)
            instance = editor.add_pattern('drums',F(0),F(4))
            editor.toggle_step(instance,F(0),F(1,8),record(pack,'gm_54')['soundIdentity'])
            copied = copy.deepcopy(editor.pattern(instance)['events'])
            editor.row_action(instance,'d_gm_56','paste',payload=copied)
            self.assertEqual({event['drumMidiAddress'] for event in editor.plan()['events']},{54,56})

    def test_deleted_row_stays_hidden_after_reopen_and_can_be_reinserted(self):
        with Pack(self.path) as pack:
            editor = Editor(new_project(pack),pack)
            instance = editor.add_pattern('drums',F(0),F(4))
            editor.paint_steps(instance,[('d_gm_56',F(0))])
            editor.row_action(instance,'d_gm_56','delete')
            self.assertNotIn('gm_56',{row['sound'] for row in settings(editor.pattern(instance),pack)['rows']})
            path = self.root/'hidden-gm.prdeproj'; editor.save(path)
            reopened = Editor(load_project(path),pack,path)
            config = settings(reopened.pattern(instance),pack)
            self.assertNotIn('gm_56',{row['sound'] for row in config['rows']})
            self.assertEqual(sample(pack,'gm_56')['role'],'drums')
            config['rows'].append(row_defaults('drums','gm_56'))
            reopened.set_sequencer(instance,rows=config['rows'])
            reopened.paint_steps(instance,[('d_gm_56',F(0))])
            self.assertEqual(reopened.plan()['events'][0]['drumMidiAddress'],56)


if __name__ == '__main__':
    unittest.main()
