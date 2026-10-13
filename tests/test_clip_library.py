"""Real catalog, placement, pulse persistence and matching MIDI/audio dynamics."""
import copy
import hashlib
import json
import subprocess
import wave
import tempfile
import unittest
from fractions import Fraction as F
from pathlib import Path

from prde1 import clip_library as lib
from prde1.contracts import ContractError, canonical_bytes
from prde1.editor import Editor, new_project
from prde1.governor import context
from prde1.midi import inspect_midi
from prde1.pack import Pack
from prde1.project import load_project
from prde1.pulse import set_pulse, settings, level
from prde1.sequencer import audition_project, placement_preview_plan
from tools.build_fixture import make_fixture


class ClipComposition(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory();cls.root=Path(cls.temp.name);cls.path=make_fixture(cls.root/'fixture',extras=2)
    @classmethod
    def tearDownClass(cls):cls.temp.cleanup()
    def setUp(self):
        self.pack=Pack(self.path);self.editor=Editor(new_project(self.pack),self.pack)
    def tearDown(self):self.pack.close()
    def clip(self,role,meter=(4,4)):
        choices=[c for c in lib.catalog()['clips'] if c['role']==role and c['meter']==list(meter)]
        return next((c for c in choices if c['origin']=='Raw Daw original'),choices[0])

    def test_every_bundled_midi_is_valid_one_bar_and_hash_matches(self):
        counts=lib.catalog()['curation']['counts']
        self.assertTrue(all(counts[r]>=100 for r in ('bass','lead','drums','rhythm')))
        ids=set()
        for clip in lib.catalog()['clips']:
            self.assertNotIn(clip['id'],ids);ids.add(clip['id'])
            raw=lib.midi_bytes(clip);data=inspect_midi(raw);length=F(4*clip['meter'][0],clip['meter'][1])
            self.assertTrue(data['notes']);self.assertEqual(hashlib.sha256(raw).hexdigest(),clip['midiSha256'])
            self.assertTrue(all(F(n['tick']+n['durationTicks'],data['ticksPerQuarter'])<=length for n in data['notes']))
            self.assertIn(clip['license'],('CC-BY-4.0','CC0-1.0'));self.assertEqual(len(clip['sourceSha256']),64)

    def test_placement_adapts_all_roles_without_overwriting_harmony_and_is_undoable(self):
        self.editor.fill_progression([dict(degree=1,alteration=0,quality='major',inversion=0),dict(degree=2,alteration=0,quality='minor',inversion=0)],[F(1),F(1)])
        harmony=copy.deepcopy(self.editor.project['harmony']);ids=[]
        for role in ('bass','lead','rhythm','drums'):
            iid,_=lib.place(self.editor,self.clip(role),F(0));ids.append(iid)
        plan=self.editor.plan();self.assertFalse(plan['conflicts']);self.assertEqual(self.editor.project['harmony'],harmony)
        for e in plan['events']:
            if not e['role'].startswith('drums.'):
                pitches=context(self.editor.project,F(e['startFrame'],24000))[2]
                self.assertTrue({n%12 for n in e['notePitches']}.issubset(pitches))
        before=canonical_bytes(self.editor.project);self.editor.undo();self.assertEqual(len(self.editor.project['instances']),3)
        self.editor.redo();self.assertEqual(canonical_bytes(self.editor.project),before)
        with self.assertRaises(ContractError):lib.place(self.editor,self.clip('bass'),F(0))
        self.assertEqual(canonical_bytes(self.editor.project),before)

    def test_meter_and_downbeat_mismatches_fail_without_mutation(self):
        before=canonical_bytes(self.editor.project)
        with self.assertRaises(ContractError):lib.place(self.editor,self.clip('bass',(3,4)),F(0))
        with self.assertRaises(ContractError):lib.place(self.editor,self.clip('bass'),F(1))
        self.assertEqual(canonical_bytes(self.editor.project),before)
        self.editor.project['meterMap'][0].update(numerator=6,denominator=8)
        iid,_=lib.place(self.editor,self.clip('bass',(6,8)),F(0));self.assertEqual(self.editor.pattern(iid)['length'],'3')

    def test_kit_extra_omissions_are_explicit_not_silent_extra_reassignment(self):
        clip=next(c for c in lib.catalog()['clips'] if c['role']=='drums' and any(e['choice']['soundIdentity'] in ('crash','ride') for e in c['pattern']['events']))
        pattern,report=lib.native_pattern(self.editor,clip,F(0))
        self.assertTrue(report)
        known={r['soundIdentity'] for r in self.pack.instruments['drums'].values() if r['status']=='available'}
        self.assertTrue(all(e['choice']['soundIdentity'] in known for e in pattern['events']))
        self.assertTrue(all(e['choice']['soundIdentity'] not in ('fixture_extra1','fixture_extra2') for e in pattern['events']))
        self.assertIn('omitted',pattern['provenance']['changes'])

    def test_guide_only_seeds_new_entries_and_leaves_existing_edits_free(self):
        iid=self.editor.add_pattern('bass',F(0),F(4));self.editor.paint_steps(iid,[('n_48',F(0))])
        first=self.editor.pattern(iid)['events'][0]['expression']['velocity']
        set_pulse(self.editor,mode='guide',levels=[.25,.9],preset='Custom')
        self.editor.paint_steps(iid,[('n_48',F(1))]);events=self.editor.pattern(iid)['events']
        self.assertEqual(events[0]['expression']['velocity'],first);self.assertEqual(events[1]['expression']['velocity'],.25)
        self.editor.edit_step_values(iid,{events[1]['id']},velocity=.73)
        self.assertAlmostEqual(self.editor.plan()['events'][1]['noteVelocity'],.73)
        clip=self.clip('lead');pid,_=lib.place(self.editor,clip,F(4))
        self.assertTrue(all(e['expression']['velocity']==level(self.editor.project,F(4)+F(e['beat'])) for e in self.editor.pattern(pid)['events']))

    def test_on_uses_actual_shifted_repeat_positions_and_off_restores_authorship(self):
        iid=self.editor.add_pattern('bass',F(0),F(4));self.editor.paint_steps(iid,[('n_48',F(0))])
        e=self.editor.pattern(iid)['events'][0];self.editor.edit_step_values(iid,{e['id']},velocity=.31,duration='2',changePercent=100,variation='double',offsetBeat='1')
        stored=copy.deepcopy(self.editor.pattern(iid));before=self.editor.plan()
        set_pulse(self.editor,mode='on',levels=[.2,.9],preset='Custom')
        voices=self.editor.plan()['events'];self.assertEqual([v['startFrame'] for v in voices],[24000,48000]);self.assertEqual([v['noteVelocity'] for v in voices],[.2,.9])
        self.assertEqual(self.editor.pattern(iid),stored)
        set_pulse(self.editor,mode='off');self.assertEqual(self.editor.plan(),before)

    def test_pulse_audition_phase_save_reopen_and_midi_match_native_events(self):
        iid=self.editor.add_pattern('drums',F(1),F(4));self.editor.paint_steps(iid,[('d_kick',F(0)),('d_kick',F(1))])
        set_pulse(self.editor,mode='on',levels=[.1,.4,.7,1],preset='Custom')
        full=self.editor.plan();project,_=audition_project(self.editor,iid)
        from prde1.governor import resolve
        preview=resolve(project,self.pack);self.assertEqual([e['noteVelocity'] for e in full['events']],[e['noteVelocity'] for e in preview['events']])
        path=self.root/'pulse.prdeproj';self.editor.save(path);self.assertEqual(Editor(load_project(path),self.pack,path).plan(),full)
        midi=self.root/'pulse.mid';self.editor.export_midi(iid,midi);notes=inspect_midi(midi.read_bytes())['notes']
        self.assertEqual([n['velocity'] for n in notes],[round(e['noteVelocity']*127) for e in preview['events']])
        before=canonical_bytes(self.editor.project);clip=self.clip('bass');lib.audition(self.editor,clip,F(4));self.assertEqual(canonical_bytes(self.editor.project),before)

    def test_entry_preview_keeps_pulse_at_original_song_position(self):
        iid=self.editor.add_pattern('bass',F(1),F(4));set_pulse(self.editor,mode='on',levels=[.1,.4,.7,1],preset='Custom')
        before=canonical_bytes(self.editor.project);plan=placement_preview_plan(self.editor,iid,'n_48',F(1))
        self.assertEqual(plan['events'][0]['noteVelocity'],.7);self.assertEqual(canonical_bytes(self.editor.project),before)

    def test_native_pcm_pulse_level_and_reopen_seek_are_exact(self):
        from prde1.contracts import ROOT
        iid=self.editor.add_pattern('bass',F(0),F(4));self.editor.paint_steps(iid,[('n_48',F(0))])
        self.editor.project['mix']['compressor']['on']=False
        set_pulse(self.editor,mode='on',levels=[.8,.8],preset='Custom')
        def render(name,plan,seek=0):
            p=self.root/(name+'.json');w=self.root/(name+'.wav');p.write_bytes(canonical_bytes(plan))
            subprocess.run([str(ROOT/'build/prde1-render'),str(p),str(self.pack.root),str(w),str(seek)],check=True,capture_output=True)
            with wave.open(str(w),'rb') as f:return f.readframes(f.getnframes())
        loud=render('pulse-loud',self.editor.plan());set_pulse(self.editor,levels=[.4,.4]);plan=self.editor.plan();soft=render('pulse-soft',plan)
        def peak(raw):return max(abs(int.from_bytes(raw[i:i+3],'little',signed=True)) for i in range(0,len(raw),3))
        self.assertGreater(peak(soft),0);self.assertAlmostEqual(peak(loud)/peak(soft),2,places=3)
        path=self.root/'native-pulse.prdeproj';self.editor.save(path);reopened=Editor(load_project(path),self.pack,path)
        self.assertEqual(render('pulse-reopened',reopened.plan()),soft)
        self.assertEqual(render('pulse-seek',plan,3000),soft[3000*6:])

    def test_scoped_audition_preserves_first_phase_and_resets_at_later_meter_change(self):
        iid=self.editor.add_pattern('drums',F(1),F(6));self.editor.paint_steps(iid,[('d_kick',F(0)),('d_kick',F(3))])
        self.editor.project['meterMap'].append(dict(beat='4',numerator=3,denominator=4,governorSegments=3))
        set_pulse(self.editor,mode='on',levels=[.2,.5,1],preset='Custom')
        from prde1.governor import resolve
        full=self.editor.plan();project,_=audition_project(self.editor,iid);preview=resolve(project,self.pack)
        self.assertEqual([e['noteVelocity'] for e in full['events']],[e['noteVelocity'] for e in preview['events']])
        self.assertEqual(full['events'][1]['noteVelocity'],.2)


if __name__=='__main__':unittest.main()
