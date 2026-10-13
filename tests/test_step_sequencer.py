"""Step composition survives reuse/save and produces the intended real audio plan."""
import copy
import json
import subprocess
import tempfile
import unittest
from fractions import Fraction
from pathlib import Path

from prde1.contracts import ContractError, ROOT, canonical_bytes
from prde1.editor import Editor, new_project
from prde1.pack import Pack
from prde1.project import load_project
from prde1.sequencer import settings, audition_project
from tools.build_fixture import make_fixture


class StepComposition(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory();cls.root=Path(cls.temp.name);cls.path=make_fixture(cls.root/'fixture',extras=2)
    @classmethod
    def tearDownClass(cls):cls.temp.cleanup()
    def setUp(self):
        self.pack=Pack(self.path);self.editor=Editor(new_project(self.pack),self.pack)
        self.bass=self.editor.add_pattern('bass',Fraction(0),Fraction(4))
        self.drums=self.editor.add_pattern('drums',Fraction(0),Fraction(4))
    def tearDown(self):self.pack.close()

    def test_pitch_row_mono_replaces_and_optional_poly_really_plays_two_notes(self):
        self.editor.paint_steps(self.bass,[('n_48',Fraction(0))]);first=self.editor.plan()
        self.assertEqual(first['events'][0]['notePitches'],[48])
        self.editor.paint_steps(self.bass,[('n_52',Fraction(0))])
        self.assertEqual([e['notePitches'] for e in self.editor.plan()['events']],[[52]])
        self.editor.undo();self.assertEqual(self.editor.plan(),first)
        self.editor.set_sequencer(self.bass,entryMode='poly')
        self.editor.paint_steps(self.bass,[('n_52',Fraction(0))])
        self.assertEqual({tuple(e['notePitches']) for e in self.editor.plan()['events']},{(48,),(52,)})

    def test_row_gate_velocity_mute_and_solo_survive_save_and_reopen(self):
        self.editor.paint_steps(self.bass,[('n_48',Fraction(0)),('n_52',Fraction(1,4))])
        self.editor.set_row(self.bass,'n_48',gatePercent=50,velocityScale=.5,solo=True)
        plan=self.editor.plan();self.assertEqual(len(plan['events']),1);self.assertEqual(plan['events'][0]['endFrame'],3000)
        self.editor.set_row(self.bass,'n_48',muted=True);self.assertEqual(self.editor.plan()['events'],[])
        self.editor.undo()
        path=self.root/'rows.prdeproj';self.editor.save(path)
        self.assertEqual(Editor(load_project(path),self.pack,path).plan(),plan)

    def test_swing_offset_and_flam_are_actual_triggers_with_linked_probability(self):
        self.editor.paint_steps(self.drums,[('d_kick',Fraction(0)),('d_kick',Fraction(1,4)),('d_kick',Fraction(1,2))])
        self.editor.set_row(self.drums,'d_kick',swingPercent=75)
        self.assertEqual([e['startFrame'] for e in self.editor.plan()['events']],[0,9000,12000])
        trigger=self.editor.pattern(self.drums)['events'][0]
        self.editor.edit_step_values(self.drums,{trigger['id']},flam=True,playPercent=40)
        for revision in range(8):
            self.editor.project['variation']['revision']=revision
            plan=self.editor.plan();voices=[e for e in plan['events'] if e['id'].startswith(self.drums+':'+trigger['id']+':')]
            self.assertIn(len(voices),(0,2))
            if voices:self.assertEqual([v['startFrame'] for v in voices],[0,720])
            self.assertEqual(plan,self.editor.plan())

    def test_shifted_trigger_revalidates_at_the_new_chord_boundary(self):
        self.editor.project['harmony']=[dict(beat='0',chord=dict(degree=1,quality='major',inversion=0,alteration=0)),
                                        dict(beat='1',chord=dict(degree=2,quality='minor',inversion=0,alteration=0))]
        lead=self.editor.add_pattern('lead',Fraction(0),Fraction(4))
        self.editor.paint_steps(lead,[('n_60',Fraction(7,8))])
        self.editor.set_row(lead,'n_60',offsetPercent=50)
        event=self.editor.plan()['events'][0]
        self.assertEqual((event['startFrame'],event['notePitches']),(24000,[62]))

    def test_ties_are_one_attack_and_splitting_restores_three_attacks(self):
        self.editor.paint_steps(self.bass,[('n_48',Fraction(i,4)) for i in range(3)])
        self.editor.tie_steps(self.bass,'n_48',Fraction(0),Fraction(1,2))
        plan=self.editor.plan();self.assertEqual(len(plan['events']),1);self.assertEqual(plan['events'][0]['endFrame'],18000)
        self.editor.tie_steps(self.bass,'n_48',Fraction(0),Fraction(0),split=True)
        self.assertEqual([e['startFrame'] for e in self.editor.plan()['events']],[0,6000,12000])

    def test_grid_preserves_microtiming_and_quantization_is_explicit_and_undoable(self):
        self.editor.paint_steps(self.bass,[('n_48',Fraction(1,5))])
        plan=self.editor.plan();self.editor.set_sequencer(self.bass,stepBeat='1/3')
        self.assertEqual(self.editor.plan(),plan)
        self.editor.pattern_action(self.bass,'quantize');self.assertNotEqual(self.editor.plan(),plan)
        self.editor.undo();self.assertEqual(self.editor.plan(),plan)

    def test_row_shift_wrap_copy_and_pattern_file_keep_expression(self):
        self.editor.paint_steps(self.bass,[('n_48',Fraction(0))])
        self.editor.row_action(self.bass,'n_48','shift',step=-1)
        self.assertEqual(self.editor.pattern(self.bass)['events'][0]['beat'],'15/4')
        payload=copy.deepcopy(self.editor.pattern(self.bass)['events'])
        self.editor.row_action(self.bass,'n_52','paste',payload=payload)
        self.assertEqual({e['choice']['registerMidi'] for e in self.editor.pattern(self.bass)['events']},{48,52})
        path=self.root/'pattern.prdepattern';self.editor.save_pattern(self.bass,path)
        before=self.editor.plan();self.editor.pattern_action(self.bass,'clear');self.editor.load_pattern(self.bass,path)
        self.assertEqual(self.editor.plan(),before)

    def test_linked_edits_independence_and_audition_do_not_change_variation(self):
        self.editor.paint_steps(self.bass,[('n_48',Fraction(0))])
        linked=self.editor.copy(self.bass,Fraction(4),linked=True)
        self.editor.set_row(linked,'n_48',swingPercent=67)
        self.assertEqual(settings(self.editor.pattern(self.bass),self.pack)['rows'],settings(self.editor.pattern(linked),self.pack)['rows'])
        self.editor.detach(linked);self.editor.set_row(linked,'n_48',muted=True)
        self.assertNotEqual(settings(self.editor.pattern(self.bass),self.pack)['rows'],settings(self.editor.pattern(linked),self.pack)['rows'])
        before=canonical_bytes(self.editor.project);preview,_=audition_project(self.editor,self.bass)
        from prde1.governor import resolve
        self.assertEqual(resolve(preview,self.pack),resolve(preview,self.pack));self.assertEqual(canonical_bytes(self.editor.project),before)

    def test_bad_rows_and_truncating_pattern_edits_fail_transactionally(self):
        self.editor.paint_steps(self.bass,[('n_48',Fraction(1))]);before=canonical_bytes(self.editor.project)
        with self.assertRaises(ContractError):self.editor.set_row(self.bass,'n_48',note=127)
        with self.assertRaises(ContractError):self.editor.pattern_action(self.bass,'length',value=Fraction(1))
        with self.assertRaises(ContractError):self.editor.set_sequencer(self.bass,stepBeat='0')
        self.assertEqual(canonical_bytes(self.editor.project),before)

    def test_timing_offsets_wrap_without_losing_last_step_and_growth_protects_neighbors(self):
        self.editor.paint_steps(self.drums,[('d_kick',Fraction(15,4))]);self.editor.set_row(self.drums,'d_kick',swingPercent=99,offsetPercent=50)
        self.assertEqual(len(self.editor.plan()['events']),1)
        self.assertEqual(self.editor.plan()['events'][0]['startFrame'],2880)
        self.editor.copy(self.bass,Fraction(4));before=canonical_bytes(self.editor.project)
        with self.assertRaises(ContractError):self.editor.pattern_action(self.bass,'length',value=Fraction(8))
        self.assertEqual(canonical_bytes(self.editor.project),before)

    def test_note_midi_interchange_keeps_realized_pitch_timing_velocity_and_kit_addresses(self):
        from prde1.midi import inspect_midi
        self.editor.paint_steps(self.bass,[('n_48',Fraction(0)),('n_52',Fraction(1,4))]);path=self.root/'notes.mid'
        self.editor.export_midi(self.bass,path);midi=inspect_midi(path.read_bytes())
        self.assertEqual([(n['tick'],n['note'],n['velocity']) for n in midi['notes']],[(0,48,102),(240,52,102)])
        self.editor.import_midi(self.bass,path);self.assertEqual([v['notePitches'] for v in self.editor.plan()['events']],[[48],[52]])
        self.editor.paint_steps(self.drums,[('d_kick',Fraction(0)),('d_snare',Fraction(1,4))]);path=self.root/'kit.mid';self.editor.export_midi(self.drums,path)
        midi=inspect_midi(path.read_bytes());self.assertEqual({(n['channel'],n['note']) for n in midi['notes']},{(9,36),(9,38)})

    def test_native_audio_of_edited_pattern_and_seek_are_identical_after_reopen(self):
        self.editor.paint_steps(self.bass,[('n_48',Fraction(0)),('n_52',Fraction(1,4))]);self.editor.set_row(self.bass,'n_52',swingPercent=67)
        self.editor.paint_steps(self.drums,[('d_kick',Fraction(0))]);e=self.editor.pattern(self.drums)['events'][0]
        self.editor.edit_step_values(self.drums,{e['id']},flam=True)
        path=self.root/'edited.prdeproj';self.editor.save(path);plan=self.editor.plan()
        self.assertEqual(Editor(load_project(path),self.pack,path).plan(),plan)
        plan_path=self.root/'step-plan.json';plan_path.write_bytes(canonical_bytes(plan));full=self.root/'full.wav';seek=self.root/'seek.wav'
        for output,frame in [(full,0),(seek,12345)]:
            r=subprocess.run([str(ROOT/'build/prde1-render'),str(plan_path),str(self.pack.root),str(output),str(frame)],capture_output=True,text=True)
            self.assertEqual(r.returncode,0,r.stderr)
        import wave
        with wave.open(str(full)) as w:pcm=w.readframes(w.getnframes())
        with wave.open(str(seek)) as w:self.assertEqual(w.readframes(w.getnframes()),pcm[12345*6:])

    def test_midi_with_overlapping_pitches_retains_polyphonic_note_lengths(self):
        from prde1.midi import encode_notes
        raw=encode_notes([dict(beat=Fraction(0),duration=Fraction(1),note=48,velocity=.8,channel=0),
                          dict(beat=Fraction(1,4),duration=Fraction(3,4),note=52,velocity=.8,channel=0)])
        path=self.root/'poly.mid';path.write_bytes(raw);self.editor.import_midi(self.bass,path)
        self.assertEqual(settings(self.editor.pattern(self.bass),self.pack)['entryMode'],'poly')
        self.assertEqual([(e['startFrame'],e['endFrame']) for e in self.editor.plan()['events']],[(0,24000),(6000,24000)])

    def test_decimal_row_timing_and_gates_accept_existing_microtimed_notes(self):
        self.editor.paint_steps(self.bass,[('n_48',Fraction(1,960))])
        self.editor.set_row(self.bass,'n_48',gatePercent=66.67,offsetPercent=37.67,swingPercent=66.67)
        self.assertEqual(self.editor.plan()['conflicts'],[]);self.assertEqual(len(self.editor.plan()['events']),1)

    def test_per_note_volume_scales_actual_pcm_and_zero_stays_silent_in_midi(self):
        import math,wave
        from prde1.midi import inspect_midi
        self.editor.paint_steps(self.bass,[('n_48',Fraction(i)) for i in range(3)])
        notes=self.editor.pattern(self.bass)['events']
        self.editor.edit_step_values(self.bass,{notes[1]['id']},velocity=.4)
        self.editor.edit_step_values(self.bass,{notes[2]['id']},velocity=0)
        self.editor.apply('Bypass master for volume measurement',lambda p:p['mix']['compressor'].update(on=False))
        plan=self.editor.plan();path=self.root/'volume-plan.json';path.write_bytes(canonical_bytes(plan));output=self.root/'volume.wav'
        result=subprocess.run([str(ROOT/'build/prde1-render'),str(path),str(self.pack.root),str(output)],capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr)
        with wave.open(str(output)) as stream:raw=stream.readframes(stream.getnframes())
        levels=[]
        for e in plan['events']:
            pcm=raw[e['startFrame']*6:e['endFrame']*6]
            samples=[int.from_bytes(pcm[i:i+3],'little',signed=True) for i in range(0,len(pcm),3)]
            levels.append(math.sqrt(sum(v*v for v in samples)/len(samples)))
        self.assertGreater(levels[0],1000);self.assertAlmostEqual(levels[1]/levels[0],.5,delta=.0001);self.assertLessEqual(levels[2],1)
        midi=self.root/'volume.mid';self.editor.export_midi(self.bass,midi);decoded=inspect_midi(midi.read_bytes())
        self.assertEqual([(n['tick'],n['velocity']) for n in decoded['notes']],[(0,102),(960,51)])
