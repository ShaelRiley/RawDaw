"""Actual Qt step gestures, keyboard entry, row controls and independent preview."""
import os
import tempfile
import time
import unittest
from fractions import Fraction
from pathlib import Path

os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from PySide6.QtCore import Qt, QPoint
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QAbstractItemView

from prde1.gui import MainWindow
from prde1.editor import Editor,new_project
from prde1.contracts import canonical_bytes
from prde1.sequencer import settings


class StepInterface(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.app=QApplication.instance() or QApplication([])
    def setUp(self):
        self.folder=tempfile.TemporaryDirectory();self.window=MainWindow(data_dir=self.folder.name,remember=False,safe_workspace=True)
        self.window.editor=Editor(new_project(self.window.pack),self.window.pack)
        self.bass=self.window.editor.add_pattern('bass',Fraction(0),Fraction(4))
        self.drums=self.window.editor.add_pattern('drums',Fraction(0),Fraction(4))
        self.window.show();self.window.select('bass',Fraction(0),self.bass);self.app.processEvents()
    def tearDown(self):
        self.window.editor.saved=canonical_bytes(self.window.editor.project);self.window.close();self.app.processEvents();self.folder.cleanup()
    def target(self,identity,col):
        s=self.window.sequencer;row=next(i for i,r in enumerate(s.rows) if r['id']==identity)
        cell=s.grid.item(row,col);s.grid.scrollToItem(cell,QAbstractItemView.ScrollHint.PositionAtCenter);self.app.processEvents()
        return row,s.grid.visualItemRect(cell).center()
    def wait_render(self):
        deadline=time.monotonic()+20
        while self.window._job and time.monotonic()<deadline:QTest.qWait(10)
        self.assertIsNone(self.window._job)
    def wait_note_preview(self):
        manager=self.window._note_preview;deadline=time.monotonic()+10
        while (manager.job or manager.pending) and time.monotonic()<deadline:QTest.qWait(10)
        self.assertIsNone(manager.job);self.assertIsNone(manager.pending)

    def test_default_pitch_rows_select_actual_notes_and_right_click_erases(self):
        w=self.window;s=w.sequencer;self.assertEqual(s.grid.rowCount(),33);self.assertEqual(s.grid.columnCount(),16)
        self.assertIs(w.dock_tabs.currentWidget(),s)
        _,point=self.target('n_48',0);QTest.mouseClick(s.grid.viewport(),Qt.MouseButton.LeftButton,pos=point)
        self.assertEqual(w.editor.plan()['events'][0]['notePitches'],[48])
        _,point=self.target('n_52',0);QTest.mouseClick(s.grid.viewport(),Qt.MouseButton.LeftButton,pos=point)
        self.assertEqual([e['notePitches'] for e in w.editor.plan()['events']],[[52]])
        QTest.mouseClick(s.grid.viewport(),Qt.MouseButton.RightButton,pos=point);self.assertEqual(w.editor.plan()['events'],[])

    def test_drag_fills_skipped_columns_in_one_undo_and_control_drag_ties(self):
        w=self.window;s=w.sequencer;row,start=self.target('n_48',0);_,end=self.target('n_48',3)
        before=len(w.editor.undo_stack)
        QTest.mousePress(s.grid.viewport(),Qt.MouseButton.LeftButton,pos=start);QTest.mouseMove(s.grid.viewport(),end);QTest.mouseRelease(s.grid.viewport(),Qt.MouseButton.LeftButton,pos=end)
        self.assertEqual(len(w.editor.plan()['events']),4);self.assertEqual(len(w.editor.undo_stack),before+1)
        _,start=self.target('n_48',0);_,end=self.target('n_48',3)
        QTest.mousePress(s.grid.viewport(),Qt.MouseButton.LeftButton,Qt.KeyboardModifier.ControlModifier,pos=start);QTest.mouseMove(s.grid.viewport(),end);QTest.mouseRelease(s.grid.viewport(),Qt.MouseButton.LeftButton,Qt.KeyboardModifier.ControlModifier,pos=end)
        self.assertEqual(len(w.editor.plan()['events']),1);self.assertEqual(w.editor.plan()['events'][0]['endFrame'],24000)
        w.undo();self.assertEqual(len(w.editor.plan()['events']),4)

    def test_step_entry_keyboard_adds_notes_and_rests_and_drum_columns_stack(self):
        w=self.window;s=w.sequencer;row,_=self.target('n_48',0);s.grid.setCurrentCell(row,0);s.grid.setFocus();s.record.setChecked(True)
        QTest.keyClick(s.grid,Qt.Key.Key_Z);self.assertEqual(s.grid.currentColumn(),1)
        QTest.keyClick(s.grid,Qt.Key.Key_Period);self.assertEqual(s.grid.currentColumn(),2)
        QTest.keyClick(s.grid,Qt.Key.Key_C);self.assertEqual([e['notePitches'] for e in w.editor.plan()['events']],[[48],[52]])
        w.select('drums',Fraction(0),self.drums);self.assertEqual(s.grid.rowCount(),8)
        for identity in ('d_kick','d_snare'):
            _,point=self.target(identity,0);QTest.mouseClick(s.grid.viewport(),Qt.MouseButton.LeftButton,pos=point)
        self.assertEqual({e['role'] for e in w.editor.plan()['events'] if e['role'].startswith('drums.')},{'drums.kick','drums.snare'})

    def test_row_controls_and_expression_edit_are_saved_and_reversible(self):
        w=self.window;s=w.sequencer;row,point=self.target('n_48',0);QTest.mouseClick(s.grid.viewport(),Qt.MouseButton.LeftButton,pos=point)
        s.set_velocity(row,0,.35);self.assertEqual(w.editor.pattern(self.bass)['events'][0]['expression']['velocity'],.35)
        QTest.mouseClick(s.row_muted,Qt.MouseButton.LeftButton);self.assertEqual(w.editor.plan()['events'],[])
        w.undo();self.assertEqual(len(w.editor.plan()['events']),1)
        s.draw_expression({0:.6});self.assertEqual(w.editor.pattern(self.bass)['events'][0]['expression']['velocity'],.6)
        path=Path(self.folder.name)/'edited.prdeproj';w.editor.save(path)
        from prde1.project import load_project
        self.assertEqual(Editor(load_project(path),w.pack,path).plan(),w.editor.plan())

    def test_pattern_preview_and_note_audition_never_modify_authored_song(self):
        w=self.window;s=w.sequencer;row,point=self.target('n_48',0);QTest.mouseClick(s.grid.viewport(),Qt.MouseButton.LeftButton,pos=point)
        before=canonical_bytes(w.editor.project);s.play_pattern();self.wait_render()
        self.assertTrue((w.work/'preview.wav').exists());self.assertEqual(w._playback_scope['kind'],'pattern');self.assertTrue(w._playback_scope['loop'])
        s.audition_row(row);self.wait_render();self.assertEqual(w._playback_scope['kind'],'note');self.assertEqual(canonical_bytes(w.editor.project),before)
        s.playhead(Fraction(1,4));self.assertEqual(s.grid.play_column,1)

    def test_track_selection_opens_default_step_view_without_mutating_notes(self):
        w=self.window;before=w.editor.plan();w.track.setCurrentIndex(w.track.findData('drums'));self.app.processEvents()
        self.assertEqual(w.selected_id,self.drums);self.assertIs(w.dock_tabs.currentWidget(),w.sequencer);self.assertEqual(w.editor.plan(),before)

    def test_fit_to_quarters_displays_custom_spacing_and_does_not_requantize(self):
        w=self.window;s=w.sequencer;_,point=self.target('n_48',1);QTest.mouseClick(s.grid.viewport(),Qt.MouseButton.LeftButton,pos=point)
        w.change(lambda:w.editor.pattern_action(self.bass,'fit',value=Fraction(6)))
        self.assertEqual(s.resolution.currentData(),'3/8');self.assertEqual(s.grid.columnCount(),16)
        self.assertEqual(w.editor.plan()['events'][0]['startFrame'],9000)
        s.resolution.setCurrentIndex(s.resolution.findData(8))
        self.assertEqual(s.grid.columnCount(),48);self.assertEqual(w.editor.plan()['events'][0]['startFrame'],9000)

    def test_duration_expression_drag_accepts_fractional_pixel_values(self):
        w=self.window;s=w.sequencer;row,point=self.target('n_48',0);QTest.mouseClick(s.grid.viewport(),Qt.MouseButton.LeftButton,pos=point)
        s.parameter.setCurrentIndex(s.parameter.findData('duration'));s.draw_expression({0:1.032258064516129})
        self.assertGreater(w.editor.plan()['events'][0]['endFrame'],6000);self.assertEqual(w.editor.plan()['conflicts'],[])

    def test_note_volume_keyboard_edits_only_focused_note_and_survives_undo_reopen(self):
        w=self.window;s=w.sequencer
        for col in (0,1):
            _,point=self.target('n_48',col);QTest.mouseClick(s.grid.viewport(),Qt.MouseButton.LeftButton,pos=point)
        s.grid.setCurrentCell(s.grid.currentRow(),0);before=w.editor.plan();count=len(w.editor.undo_stack)
        s.note_volume.setFocus();s.note_volume.selectAll();QTest.keyClicks(s.note_volume,'35');QTest.keyClick(s.note_volume,Qt.Key.Key_Return)
        notes=w.editor.pattern(self.bass)['events']
        self.assertEqual([e['expression']['velocity'] for e in notes],[.35,.8]);self.assertEqual(len(w.editor.undo_stack),count+1)
        changed=w.editor.plan();self.assertAlmostEqual(changed['events'][0]['gain']/before['events'][0]['gain'],.35/.8)
        self.assertEqual(changed['events'][1],before['events'][1]);self.assertEqual(s.note_volume_slider.value(),35)
        w.undo();self.assertEqual(w.editor.plan(),before);w.redo();self.assertEqual(w.editor.plan(),changed)
        path=Path(self.folder.name)/'volume.prdeproj';w.editor.save(path)
        from prde1.project import load_project
        self.assertEqual(Editor(load_project(path),w.pack,path).plan(),changed)
        self.assertTrue(s.show_lane.isChecked());self.assertTrue(s.lane.isVisible())

    def test_note_volume_slider_drag_is_one_edit_and_sustain_cell_edits_original_attack(self):
        w=self.window;s=w.sequencer
        w.change(lambda:w.editor.paint_steps(self.bass,[('n_48',Fraction(i,4)) for i in range(4)]))
        w.change(lambda:w.editor.tie_steps(self.bass,'n_48',Fraction(0),Fraction(3,4)))
        # Draw and erase an intervening step: its disabled data must not steal
        # focus from the original note still sustaining through this column.
        w.change(lambda:w.editor.paint_steps(self.bass,[('n_48',Fraction(1,2))]))
        erased=w.editor.pattern(self.bass)['events'][-1]['id']
        w.change(lambda:w.editor.edit_step_values(self.bass,{erased},enabled=False))
        row,_=self.target('n_48',2);s.grid.setCurrentCell(row,2);self.assertTrue(s.note_volume.isEnabled())
        count=len(w.editor.undo_stack);slider=s.note_volume_slider
        from PySide6.QtWidgets import QStyle, QStyleOptionSlider
        option=QStyleOptionSlider();slider.initStyleOption(option)
        handle=slider.style().subControlRect(QStyle.ComplexControl.CC_Slider,option,QStyle.SubControl.SC_SliderHandle,slider).center()
        QTest.mousePress(slider,Qt.MouseButton.LeftButton,pos=handle)
        QTest.mouseMove(slider,QPoint(2,handle.y()));QTest.mouseRelease(slider,Qt.MouseButton.LeftButton,pos=QPoint(2,handle.y()))
        self.assertEqual(len(w.editor.undo_stack),count+1);self.assertEqual(s.note_volume.value(),0)
        notes=w.editor.pattern(self.bass)['events'];self.assertEqual(len(notes),2);self.assertTrue(notes[0]['enabled']);self.assertEqual(notes[0]['beat'],'0')
        self.assertFalse(notes[1]['enabled']);self.assertEqual(notes[1]['expression']['velocity'],.8)
        self.assertEqual(notes[0]['expression']['velocity'],0);self.assertEqual(w.editor.plan()['events'][0]['gain'],0)
        w.undo();self.assertEqual(s.note_volume.value(),80)

    def test_visible_dynamics_bars_change_note_levels_without_creating_other_notes(self):
        w=self.window;s=w.sequencer
        w.change(lambda:w.editor.paint_steps(self.drums,[('d_kick',Fraction(0)),('d_kick',Fraction(1,4)),('d_snare',Fraction(0))]))
        w.select('drums',Fraction(0),self.drums);row,_=self.target('d_kick',0);s.grid.setCurrentCell(row,0)
        lane=s.lane;origin=s.grid.verticalHeader().width()+s.grid.frameWidth()
        x=origin+s.grid.columnViewportPosition(0)+s.grid.columnWidth(0)//2
        before=len(w.editor.undo_stack);point=QPoint(x,lane.height()//2)
        QTest.mouseClick(lane,Qt.MouseButton.LeftButton,pos=point)
        events=w.editor.pattern(self.drums)['events'];self.assertEqual([e['expression']['velocity'] for e in events],[.5,.8,.8])
        self.assertEqual(len(w.editor.undo_stack),before+1);self.assertEqual(s.note_volume.value(),50)
        row,_=self.target('d_kick',3);s.grid.setCurrentCell(row,3);self.assertFalse(s.note_volume.isEnabled())
        x=origin+s.grid.columnViewportPosition(3)+s.grid.columnWidth(3)//2;QTest.mouseClick(lane,Qt.MouseButton.LeftButton,pos=QPoint(x,lane.height()//2))
        self.assertEqual(len(w.editor.pattern(self.drums)['events']),3);self.assertIsNone(lane.values[3])

    def test_note_volume_bars_and_focused_note_fit_the_deck_viewport_with_enlarged_text(self):
        w=self.window;s=w.sequencer
        _,point=self.target('n_48',0);QTest.mouseClick(s.grid.viewport(),Qt.MouseButton.LeftButton,pos=point)
        for scale in (1,1.5):
            w.resize(1280,800);w._apply_scale(scale);self.app.processEvents()
            view=w.body_scroll.viewport()
            for control in (s.note_volume,s.note_volume_slider,s.preview_click,s.lane):
                top=control.mapTo(view,QPoint(0,0));bottom=control.mapTo(view,QPoint(control.width()-1,control.height()-1))
                self.assertTrue(view.rect().contains(top));self.assertTrue(view.rect().contains(bottom))
            self.assertTrue(s.grid.viewport().rect().contains(s.grid.visualItemRect(s.grid.currentItem()).center()))

    def test_live_mouse_preview_precedes_commit_and_uses_an_independent_native_clip(self):
        import wave
        w=self.window;s=w.sequencer;self.assertTrue(s.preview_click.isChecked());self.assertTrue(s.preview_click.isVisible())
        row,point=self.target('n_48',0);before=canonical_bytes(w.editor.project)
        QTest.mousePress(s.grid.viewport(),Qt.MouseButton.LeftButton,pos=point)
        self.assertEqual(canonical_bytes(w.editor.project),before);self.assertIsNotNone(w._note_preview);self.assertIsNone(w._job)
        QTest.mouseRelease(s.grid.viewport(),Qt.MouseButton.LeftButton,pos=point);self.wait_note_preview()
        self.assertEqual(len(w.editor.plan()['events']),1);path=next(iter(w._note_preview.cache.values()))
        with wave.open(str(path)) as stream:
            self.assertEqual((stream.getnchannels(),stream.getsampwidth(),stream.getframerate()),(2,2,48000))
            self.assertTrue(any(stream.readframes(stream.getnframes())))
        self.assertIsNone(w._playback_scope);self.assertIsNone(w._preview_key)

    def test_live_keyboard_preview_toggle_and_stop_keep_music_and_auditions_independent(self):
        w=self.window;s=w.sequencer;row,_=self.target('n_48',0);s.grid.setCurrentCell(row,0);s.grid.setFocus()
        before=canonical_bytes(w.editor.project);s.preview_click.setChecked(False);self.assertEqual(canonical_bytes(w.editor.project),before)
        QTest.keyClick(s.grid,Qt.Key.Key_Space);self.assertIsNone(w._note_preview)
        s.preview_click.setChecked(True);s.grid.setCurrentCell(row,1);QTest.keyClick(s.grid,Qt.Key.Key_Space);self.wait_note_preview()
        self.assertEqual(len(w.editor.plan()['events']),2);self.assertTrue(w._note_preview.cache)
        before=canonical_bytes(w.editor.project);w.stop();self.assertEqual(canonical_bytes(w.editor.project),before)
        self.assertIsNone(w._note_preview.pending);self.assertIsNone(w._note_preview.play_request)

    def test_live_drag_previews_each_visited_column_but_commits_one_undo_operation(self):
        w=self.window;s=w.sequencer;requests=[];callback=s.preview_note
        s.preview_note=lambda *args:(requests.append(args),callback(*args))[-1]
        row,start=self.target('n_48',0);_,middle=self.target('n_48',1);_,end=self.target('n_48',3)
        before=len(w.editor.undo_stack)
        QTest.mousePress(s.grid.viewport(),Qt.MouseButton.LeftButton,pos=start);QTest.mouseMove(s.grid.viewport(),middle);QTest.mouseMove(s.grid.viewport(),end)
        QTest.mouseRelease(s.grid.viewport(),Qt.MouseButton.LeftButton,pos=end);self.wait_note_preview()
        self.assertEqual([r[2] for r in requests],[Fraction(0),Fraction(1,4),Fraction(3,4)])
        self.assertEqual(len(w.editor.plan()['events']),4);self.assertEqual(len(w.editor.undo_stack),before+1)
