"""Musical loop boundaries, deterministic reuse and durable editing semantics."""
import copy
import tempfile
import unittest
from fractions import Fraction
from pathlib import Path

from prde1.contracts import ContractError, RATE, canonical_bytes
from prde1.editor import Editor, new_event, new_project
from prde1.music import beat, quarter_seconds
from prde1.pack import Pack
from prde1.project import arrangement_spans, load_project, validate_project
from prde1.sequencer import audition_project
from tools.build_fixture import make_fixture


class ArrangementLoops(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory()
        cls.root=Path(cls.temp.name)
        cls.path=make_fixture(cls.root/'fixture',extras=2)

    @classmethod
    def tearDownClass(cls):cls.temp.cleanup()

    def setUp(self):
        self.pack=Pack(self.path)
        self.editor=Editor(new_project(self.pack,bars=6),self.pack)

    def tearDown(self):self.pack.close()

    def clip(self,role='bass',start=0,length=4,events=None):
        pattern=dict(id='test_source',role=role,length=str(length),events=events or [],
                     provenance=dict(sourceClip='Synthetic loop invariant fixture',license='MIT',changes='test score'))
        return self.editor.add_pattern(role,Fraction(start),Fraction(length),source=pattern)

    def frames(self,position):
        return round(quarter_seconds(Fraction(position),self.editor.project['tempoMap'])*RATE)

    def test_edge_extension_repeats_source_and_trims_partial_final_cycle(self):
        events=[new_event('bass',0,2),new_event('bass',3,2)]
        clip=self.clip(events=events);source=copy.deepcopy(self.editor.pattern(clip))
        self.editor.resize_instance(clip,Fraction(10))
        plan=self.editor.plan()
        self.assertEqual(self.editor.pattern(clip),source)
        self.assertEqual(self.editor.instance_length(clip),10)
        self.assertEqual([e['startFrame'] for e in plan['events']],[self.frames(n) for n in (0,3,4,7,8)])
        self.assertEqual([e['endFrame'] for e in plan['events']],[self.frames(n) for n in (2,4,6,8,10)])
        self.assertEqual([e['endReason'] for e in plan['events'] if e['startFrame'] in (self.frames(3),self.frames(7))],['loop_boundary']*2)
        self.assertEqual(len({e['id'] for e in plan['events']}),len(plan['events']))
        self.editor.undo();self.assertEqual(self.editor.instance_length(clip),4)
        self.editor.redo();self.assertEqual(self.editor.plan(),plan)

    def test_every_repeat_revalidates_exact_pitch_against_destination_harmony(self):
        note=new_event('lead',0,1,register=60)
        note['choice']['exactMidi']=60;note['expression']['lockExactPitch']=True
        clip=self.clip('lead',events=[note]);self.editor.resize_instance(clip,Fraction(12))
        self.editor.set_chord(Fraction(4),dict(degree=2,alteration=0,quality='major',inversion=0))
        self.editor.set_chord(Fraction(8),dict(degree=1,alteration=0,quality='major',inversion=0))
        plan=self.editor.plan()
        self.assertEqual([e['startFrame'] for e in plan['events']],[self.frames(0),self.frames(8)])
        self.assertEqual([c['code'] for c in plan['conflicts']],['exact_pitch_conflict'])
        self.assertIn(':loop_1:',plan['conflicts'][0]['eventId'])
        self.assertEqual(self.editor.pattern(clip)['events'][0]['choice']['exactMidi'],60)

    def test_track_cycle_preserves_gaps_and_exact_clock_through_meter_and_tempo(self):
        sound=self.pack.instruments['drums']['kick']['soundIdentity']
        first=self.clip('drums',1,1,[new_event('drums',0,Fraction(1,4),sound)])
        second=self.clip('drums',3,1,[new_event('drums',0,Fraction(1,4),sound)])
        self.editor.set_map('meterMap',Fraction(4),dict(numerator=3,denominator=4,governorSegments=3),'Meter')
        self.editor.set_map('tempoMap',Fraction(4),dict(quarterBpm=90),'Tempo')
        self.editor.set_track_loop('drums',True)
        self.assertEqual(self.editor.project['trackLoops']['drums'],dict(startBeat='1',endBeat='4'))
        starts=sorted([1+3*n for n in range(8)]+[3+3*n for n in range(7)])
        self.assertEqual([e['startFrame'] for e in self.editor.plan()['events']],[self.frames(n) for n in starts])
        spans=list(arrangement_spans(self.editor.project))
        self.assertEqual(len(self.editor.project['instances']),2)
        self.assertEqual({source['id'] for source,_,_,_,_ in spans},{first,second})
        self.assertTrue(any(cycle>0 for _,_,_,_,cycle in spans))
        self.editor.set_track_loop('drums',False)
        self.assertEqual(len(self.editor.plan()['events']),2)

    def test_track_loop_preserves_authored_holds_within_its_complete_cycle(self):
        self.clip('bass',0,2,[new_event('bass',1,5)])
        self.clip('bass',4,2)
        before=self.editor.plan()['events'][0]
        self.editor.set_track_loop('bass',True)
        events=self.editor.plan()['events']
        self.assertEqual(events[0],before)
        self.assertEqual([e['startFrame'] for e in events],[self.frames(n) for n in (1,7,13,19)])
        self.assertEqual([e['endFrame'] for e in events],[self.frames(n) for n in (6,12,18,24)])

    def test_copy_detach_repeats_and_transport_survive_save_without_changing_source(self):
        clip=self.clip(events=[new_event('bass',0,1)])
        self.editor.resize_instance(clip,Fraction(8))
        linked=self.editor.copy(clip,Fraction(12),linked=True)
        self.assertEqual(self.editor.instance_length(linked),8)
        changed=copy.deepcopy(self.editor.pattern(linked)['events'][0]);changed['expression']['velocity']=.3
        self.editor.edit_event(linked,changed['id'],changed)
        self.assertEqual(self.editor.pattern(clip)['events'][0]['expression']['velocity'],.3)
        self.editor.detach(linked)
        changed['expression']['velocity']=.7;self.editor.edit_event(linked,changed['id'],changed)
        self.assertEqual(self.editor.pattern(clip)['events'][0]['expression']['velocity'],.3)
        self.assertEqual(self.editor.instance_length(linked),8)
        prior=self.editor.plan();self.editor.set_playback_loop(True)
        self.assertEqual(self.editor.plan(),prior)
        path=self.root/'loop-save.prdeproj';self.editor.save(path)
        reopened=Editor(load_project(path),self.pack,path)
        self.assertFalse(reopened.dirty);self.assertTrue(reopened.project['loopPlayback'])
        self.assertEqual(reopened.plan(),prior)
        reopened.set_playback_loop(False);self.assertTrue(reopened.dirty)
        reopened.undo();self.assertFalse(reopened.dirty)

    def test_invalid_moves_expansions_and_loop_cycles_are_transactional(self):
        clip=self.clip(events=[new_event('bass',0,1)])
        self.clip(start=12,length=4)
        before=canonical_bytes(self.editor.project);undo=len(self.editor.undo_stack)
        for action in (lambda:self.editor.resize_instance(clip,Fraction(16)),
                       lambda:self.editor.move_instance(clip,Fraction(12)),
                       lambda:self.editor.resize_instance(clip,Fraction(0)),
                       lambda:self.editor.move_instance(clip,Fraction(-1)),
                       lambda:self.editor.set_track_loop('bass',True,start=0,end=4)):
            with self.assertRaises(ContractError):action()
            self.assertEqual(canonical_bytes(self.editor.project),before)
            self.assertEqual(len(self.editor.undo_stack),undo)
        self.editor.set_track_loop('bass',True)
        with self.assertRaises(ContractError):self.clip(start=20,length=4)
        self.editor.set_track_loop('bass',False);self.clip(start=20,length=4)

    def test_loop_extension_preserves_existing_probability_and_audition_is_one_cycle(self):
        events=[new_event('bass',Fraction(n,4),Fraction(1,4)) for n in range(16)]
        for note in events:note['expression'].update(playPercent=53,changePercent=71,variation='double')
        clip=self.clip(events=events);self.editor.resize_instance(clip,Fraction(8))
        first=self.editor.plan();self.editor.resize_instance(clip,Fraction(12));second=self.editor.plan()
        cutoff=self.frames(8)
        self.assertEqual([e for e in first['events'] if e['endFrame']<cutoff],[e for e in second['events'] if e['endFrame']<cutoff])
        self.editor.set_track_loop('bass',True);before=canonical_bytes(self.editor.project)
        audition,_=audition_project(self.editor,clip)
        self.assertEqual(audition['length'],'4');self.assertNotIn('trackLoops',audition)
        self.assertNotIn('playbackLength',audition['instances'][0]);validate_project(audition)
        self.assertEqual(canonical_bytes(self.editor.project),before)

    def test_empty_short_cycle_and_expanded_trigger_budgets_fail_before_iteration(self):
        clip=self.clip(length=Fraction(1,1000000))
        before=canonical_bytes(self.editor.project)
        with self.assertRaisesRegex(ContractError,'budget'):self.editor.set_track_loop('bass',True)
        self.assertEqual(canonical_bytes(self.editor.project),before)
        with self.assertRaisesRegex(ContractError,'budget'):self.editor.resize_instance(clip,Fraction(1))
        with self.assertRaises(ContractError):self.editor.set_track_loop('lead',True)

    def test_browser_auditions_ignore_saved_track_cycles_and_do_not_mutate_them(self):
        from prde1 import clip_library,progression_bank
        bass=self.clip(events=[new_event('bass',0,1)])
        self.clip('rhythm',events=[new_event('rhythm',0,1)])
        self.editor.resize_instance(bass,Fraction(8))
        self.editor.set_track_loop('bass',True);self.editor.set_track_loop('rhythm',True)
        self.editor.set_playback_loop(True);before=canonical_bytes(self.editor.project)
        clip=next(c for c in clip_library.catalog()['clips'] if c['role']=='bass' and c['meter']==[4,4] and c['origin']=='Raw Daw original')
        preview=clip_library.audition(self.editor,clip,Fraction(8))
        validate_project(preview);self.assertNotIn('trackLoops',preview)
        self.assertNotIn('loopPlayback',preview)
        harmony=progression_bank.audition_project(self.editor,progression_bank.catalog()[0])
        validate_project(harmony);self.assertNotIn('trackLoops',harmony)
        self.assertNotIn('loopPlayback',harmony)
        self.assertEqual(canonical_bytes(self.editor.project),before)


if __name__=='__main__':unittest.main()
