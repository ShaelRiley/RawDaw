import copy
import hashlib
import tempfile
import unittest
from fractions import Fraction
from pathlib import Path

from prde1.contracts import ContractError,ROOT,canonical_bytes
from prde1.editor import Editor,atomic_copy,measures,parse_progression
from prde1.music import beat,diatonic
from prde1.pack import Pack
from prde1.project import load_project


class DesktopEditing(unittest.TestCase):
    def setUp(self):
        self.path=ROOT/'packs/parachute.prdepack';self.bank=Pack(self.path)
        self.project=load_project(ROOT/'packs/parachute_a.prdeproj');self.editor=Editor(self.project,self.bank)
    def tearDown(self):self.bank.close()

    def test_exact_custom_quality_conflict_is_retained_and_undo_restores_audio_plan(self):
        before=self.editor.plan();digest=hashlib.sha256(self.path.read_bytes()).digest()
        chords=parse_progression('i III VI iv',10,'natural_minor')
        self.editor.fill_progression(chords,[Fraction(4)]*4)
        self.assertEqual(self.editor.project['harmony'][1]['chord']['quality'],'major')
        self.assertTrue(any(v['code']=='missing_chord' for v in self.editor.plan()['conflicts']))
        self.editor.undo();self.assertEqual(self.editor.plan(),before)
        self.assertEqual(hashlib.sha256(self.path.read_bytes()).digest(),digest)
        self.assertEqual(parse_progression('IIImaj7',10,'natural_minor')[0]['quality'],'major7')
        self.assertEqual(parse_progression('V v',9,'natural_minor')[0]['quality'],'major')
        self.assertEqual(parse_progression('V v',9,'natural_minor')[1]['quality'],'minor')
        with self.assertRaises(ContractError):parse_progression('Iv',0,'major')

    def test_performance_only_copy_independence_and_linked_detach_survive_save(self):
        self.editor.resize(6);harmony=copy.deepcopy(self.editor.project['harmony']);source='rhythm_instance_0'
        independent=self.editor.copy(source,Fraction(16));self.assertEqual(self.editor.project['harmony'],harmony)
        event=self.editor.pattern(independent)['events'][0];updated=copy.deepcopy(event);updated['enabled']=False
        self.editor.edit_event(independent,event['id'],updated);self.assertTrue(self.editor.pattern(source)['events'][0]['enabled'])
        linked=self.editor.copy(source,Fraction(20),linked=True)
        changed=copy.deepcopy(self.editor.pattern(linked)['events'][0]);changed['expression']['playPercent']=45
        self.editor.edit_event(linked,changed['id'],changed)
        self.assertEqual(self.editor.pattern(source)['events'][0]['expression']['playPercent'],45)
        self.editor.detach(linked);changed=copy.deepcopy(self.editor.pattern(linked)['events'][0]);changed['expression']['playPercent']=20
        self.editor.edit_event(linked,changed['id'],changed)
        self.assertEqual(self.editor.pattern(source)['events'][0]['expression']['playPercent'],45)
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'session.prdeproj';self.editor.save(path);reopened=Editor(load_project(path),self.bank,path)
            self.assertEqual(self.editor.plan(),reopened.plan());self.assertFalse(reopened.dirty)

    def test_grid_changes_do_not_quantize_or_rewrite_source_steps(self):
        events=copy.deepcopy(self.editor.project['patterns']);before=self.editor.plan()
        self.editor.set_map('meterMap',Fraction(0),dict(numerator=4,denominator=4,governorSegments=6),'Grid')
        self.assertEqual(self.editor.project['patterns'],events);self.assertEqual(self.editor.plan(),before)
        self.editor.set_map('meterMap',Fraction(0),dict(numerator=6,denominator=8,governorSegments=6),'Meter')
        self.assertEqual(measures(self.editor.project)[0][1],3);self.assertEqual(self.editor.project['patterns'],events)

    def test_disabled_steps_variation_and_mute_are_saved_and_reversible(self):
        original=self.editor.plan();self.editor.toggle_step('rhythm_instance_0',Fraction(0),Fraction(1,4))
        self.assertFalse(self.editor.pattern('rhythm_instance_0')['events'][0]['enabled'])
        self.assertFalse(any(v['id'].startswith('rhythm_instance_0:strum_0:') for v in self.editor.plan()['events']))
        self.editor.set_mix('lead',muted=True);self.assertFalse(any(v['role']=='lead' for v in self.editor.plan()['events']))
        self.editor.regenerate();first=self.editor.plan();self.assertEqual(first,self.editor.plan())
        self.editor.undo();self.editor.undo();self.editor.undo();self.assertEqual(self.editor.plan(),original)

    def test_failed_edit_and_failed_export_commit_preserve_prior_state(self):
        saved=canonical_bytes(self.editor.project)
        with self.assertRaises(ContractError):self.editor.resize(2)
        self.assertEqual(canonical_bytes(self.editor.project),saved);self.assertFalse(self.editor.undo_stack)
        self.editor.project['editorContext']['selection']='bass_instance_0';self.editor.saved=canonical_bytes(self.project)
        self.assertFalse(self.editor.dirty)
        with tempfile.TemporaryDirectory() as folder:
            target=Path(folder)/'song.wav';target.write_bytes(b'prior completed export')
            with self.assertRaises(OSError):atomic_copy(Path(folder)/'missing.wav',target)
            self.assertEqual(target.read_bytes(),b'prior completed export');self.assertFalse(list(Path(folder).glob('*.partial')))


if __name__=='__main__':unittest.main()
