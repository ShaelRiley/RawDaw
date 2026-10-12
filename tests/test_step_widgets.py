"""Actual Qt step gestures, keyboard entry, row controls and independent preview."""
import os
import tempfile
import time
import unittest
from fractions import Fraction
from pathlib import Path

os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from PySide6.QtCore import Qt
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
