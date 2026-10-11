"""Native mix routing, immutable sources and durable/undoable DSP settings."""
import copy
import json
import subprocess
import tempfile
import unittest
import wave
from pathlib import Path

from prde1.contracts import ROOT, SLOTS, ContractError, canonical_bytes
from prde1.editor import Editor, new_project
from prde1.governor import resolve
from prde1.mixing import apply_punch_mix, drum_eq
from prde1.pack import Pack
from prde1.project import load_project, save_project, validate_project
from tools.build_fixture import make_fixture


class MixRouting(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory(prefix='prde1-mix-');cls.root=Path(cls.temp.name)
        cls.source=make_fixture(cls.root/'fixture',extras=2)
        cls.original=load_project(cls.root/'fixture/major.prdeproj')
    @classmethod
    def tearDownClass(cls):cls.temp.cleanup()
    def setUp(self):self.project=copy.deepcopy(self.original)
    def render(self,pack,plan,name,seek=0):
        path=self.root/(name+'.json');output=self.root/(name+'.wav');path.write_bytes(canonical_bytes(plan))
        result=subprocess.run([str(ROOT/'build/prde1-render'),str(path),str(pack.root),str(output),str(seek)],capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr)
        return output,json.loads(result.stdout)

    def test_legacy_save_is_not_silently_remixed_and_new_projects_have_unique_drum_curves(self):
        with Pack(self.source) as pack:
            before=copy.deepcopy(self.project);self.assertNotIn('processing',resolve(self.project,pack));self.assertEqual(before,self.project)
            new=new_project(pack);validate_project(new)
            curves=[new['mix']['channels']['drums.'+slot]['eq'] for slot in SLOTS]
            self.assertEqual(len({canonical_bytes(v) for v in curves}),8)
            self.assertTrue(all(v['on'] for v in curves))
            self.assertFalse(new['mix']['master']['reverbOn']);self.assertFalse(new['mix']['master']['delayOn'])

    def test_dsp_changes_save_reopen_undo_and_leave_sample_choices_and_source_bytes_intact(self):
        source_bytes=self.source.read_bytes()
        with Pack(self.source) as pack:
            editor=Editor(self.project,pack);dry=editor.plan();editor.apply('Punch mix',apply_punch_mix)
            wet=editor.plan();self.assertEqual(wet['assets'],dry['assets'])
            self.assertEqual([(v['assetIndex'],v['startFrame'],v['endFrame'],v['notePitches']) for v in wet['events']],
                             [(v['assetIndex'],v['startFrame'],v['endFrame'],v['notePitches']) for v in dry['events']])
            custom=drum_eq('kick');custom.update(bellDb=1.7,bellHz=72)
            editor.set_mix('drums.kick',eqPreset='custom',eq=custom)
            path=self.root/'custom.prdeproj';editor.save(path);self.assertEqual(resolve(load_project(path),pack),editor.plan())
            editor.undo();self.assertEqual(editor.plan(),wet);editor.undo();self.assertEqual(editor.plan(),dry)
        self.assertEqual(source_bytes,self.source.read_bytes())

    def test_full_render_repeat_and_seek_reconstruct_eq_both_compressors_and_detector(self):
        apply_punch_mix(self.project)
        with Pack(self.source) as pack:
            plan=resolve(self.project,pack);full,stats=self.render(pack,plan,'processed')
            repeated,_=self.render(pack,plan,'processed-repeat');seek,_=self.render(pack,plan,'processed-seek',123457)
            self.assertEqual(full.read_bytes(),repeated.read_bytes())
            self.assertGreater(stats['bassMaxDuckDb'],0);self.assertLessEqual(stats['bassMaxDuckDb'],6.000001)
            with wave.open(str(full),'rb') as a,wave.open(str(seek),'rb') as b:
                a.setpos(123457);self.assertEqual(a.readframes(a.getnframes()-123457),b.readframes(b.getnframes()))
                a.setpos(a.getnframes()-1)
                # Last-frame silence is dithered by at most a single PCM LSB.
                data=a.readframes(1);self.assertTrue(all(abs(int.from_bytes(data[i:i+3],'little',signed=True))<=1 for i in (0,3)))

    def test_muted_kick_or_muted_drum_bus_cannot_trigger_bass_ducking(self):
        apply_punch_mix(self.project)
        for name in ('drums.kick','drums'):
            with self.subTest(mute=name),Pack(self.source) as pack:
                project=copy.deepcopy(self.project);project['mix']['channels'][name]['muted']=True
                _,stats=self.render(pack,resolve(project,pack),'mute-'+name)
                self.assertEqual(stats['bassMaxDuckDb'],0)

    def test_drum_bus_fader_is_after_compression_and_does_not_change_the_kick_detector(self):
        apply_punch_mix(self.project)
        for slot in SLOTS:self.project['mix']['channels']['drums.'+slot]['eq']['on']=False
        with Pack(self.source) as pack:
            plan=resolve(self.project,pack);_,loud=self.render(pack,plan,'bus-loud')
            self.project['mix']['channels']['drums']['gainDb']-=12
            quieter=resolve(self.project,pack);_,quiet=self.render(pack,quieter,'bus-quiet')
            self.assertEqual(plan['events'],quieter['events'])
            self.assertEqual(loud['bassMaxDuckDb'],quiet['bassMaxDuckDb'])
            self.assertEqual(loud['drumBusMaxReductionDb'],quiet['drumBusMaxReductionDb'])

    def test_invalid_active_dsp_and_unknown_eq_fail_without_overwriting_export(self):
        apply_punch_mix(self.project)
        with Pack(self.source) as pack:
            plan=resolve(self.project,pack);plan['processing']['drumEq']['kick']['bellQ']=0
            manifest=self.root/'bad-dsp.json';manifest.write_bytes(canonical_bytes(plan))
            target=self.root/'protected.wav';target.write_bytes(b'previous completed audio')
            result=subprocess.run([str(ROOT/'build/prde1-render'),str(manifest),str(pack.root),str(target)],capture_output=True,text=True)
            self.assertNotEqual(result.returncode,0);self.assertEqual(target.read_bytes(),b'previous completed audio')
            self.project['mix']['channels']['drums.kick']['eqPreset']='unknown'
            with self.assertRaisesRegex(ContractError,'Unsupported EQ'):resolve(self.project,pack)
        self.project=copy.deepcopy(self.original);apply_punch_mix(self.project)
        self.project['mix']['bassSidechain']['maxDuckDb']=float('nan')
        with self.assertRaises(ContractError):validate_project(self.project)


if __name__=='__main__':unittest.main()
