"""Real timeline gestures preserve source patterns and commit one undo step."""
import copy
import os
import tempfile
import unittest
from fractions import Fraction as F
from pathlib import Path

os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from PySide6.QtCore import Qt, QPoint, QPointF, QMimeData
from PySide6.QtGui import QDropEvent
from PySide6.QtMultimedia import QMediaPlayer
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from prde1 import clip_library
from prde1.contracts import canonical_bytes
from prde1.editor import Editor, new_project
from prde1.gui import MainWindow
from prde1.gui_widgets import ChordDialog
from prde1.library_widgets import MIME
from prde1.music import QUALITIES
from prde1.project import arrangement_spans, load_project


class LoopInterface(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.app=QApplication.instance() or QApplication([])
    def setUp(self):
        self.folder=tempfile.TemporaryDirectory()
        self.w=MainWindow(data_dir=self.folder.name,remember=False,safe_workspace=True)
        self.w.editor=Editor(new_project(self.w.pack,bars=8),self.w.pack)
        clip=next(c for c in clip_library.catalog()['clips'] if c['role']=='bass' and c['meter']==[4,4])
        self.w.place_clip(clip,F(0));self.identity=self.w.selected_id
        self.w.resize(1280,800);self.w.show();self.app.processEvents()
    def tearDown(self):
        self.w.editor.saved=canonical_bytes(self.w.editor.project);self.w.close();self.app.processEvents();self.folder.cleanup()
    def drag(self,start,end):
        t=self.w.timeline
        QTest.mousePress(t,Qt.MouseButton.LeftButton,pos=start)
        QTest.mouseMove(t,end)
        QTest.mouseRelease(t,Qt.MouseButton.LeftButton,pos=end)
        self.app.processEvents()
    def point(self,beat,y=None):
        return QPoint(round(self.w.timeline.x(beat)),y or 30+3*self.w.timeline.row_height+22)

    def test_drag_right_edge_repeats_move_snaps_and_undo_keeps_source_editable(self):
        w=self.w;pattern=copy.deepcopy(w.editor.pattern(self.identity));undo=len(w.editor.undo_stack)
        self.drag(self.point(F(4))-QPoint(7,0),self.point(F(8)))
        self.assertEqual(w.editor.instance_length(self.identity),8)
        self.assertEqual(w.editor.pattern(self.identity),pattern)
        self.assertEqual(len(w.editor.undo_stack),undo+1)
        self.assertEqual(len(w.editor.plan()['events']),2*len(pattern['events']))
        from unittest.mock import patch
        with patch.object(w.player,'playbackState',return_value=QMediaPlayer.PlaybackState.PlayingState):
            w._play_position(2500)  # Beat 5 at 120 BPM: source cycle beat 1.
            self.assertEqual(w.sequencer.grid.play_column,4)
        self.drag(self.point(F(1)),self.point(F(5))+QPoint(6,0))
        self.assertEqual(w.editor.instance(self.identity)['beat'],'4')
        self.assertEqual(len(w.editor.undo_stack),undo+2)
        self.assertEqual(w.editor.pattern(self.identity),pattern)
        w.undo();self.assertEqual(w.editor.instance(self.identity)['beat'],'0')
        w.undo();self.assertEqual(w.editor.instance_length(self.identity),4)
        self.assertNotIn('playbackLength',w.editor.instance(self.identity))

    def test_occupied_drag_is_rejected_and_keyboard_loop_controls_are_undoable(self):
        w=self.w;other=w.editor.add_pattern('bass',F(8),F(4));w.refresh()
        before=canonical_bytes(w.editor.project);undo=len(w.editor.undo_stack)
        self.drag(self.point(F(4))-QPoint(7,0),self.point(F(12)))
        self.assertEqual(w.editor.instance_length(self.identity),4)
        self.assertEqual(len(w.editor.undo_stack),undo)
        self.assertIn('overlap',w.message.text())
        # Selection/scroll context may change; musical content does not.
        saved=copy.deepcopy(w.editor.project);saved.pop('editorContext')
        import json
        original=json.loads(before);original.pop('editorContext');self.assertEqual(saved,original)
        w.timeline.setFocus();QTest.keyClick(w.timeline,Qt.Key.Key_Right,Qt.KeyboardModifier.ControlModifier)
        self.assertEqual(w.editor.instance_length(self.identity),8)
        self.assertEqual(w.editor.instance(other)['beat'],'8')
        w.undo();self.assertEqual(w.editor.instance_length(self.identity),4)
        QTest.keyClick(w.timeline,Qt.Key.Key_Right,Qt.KeyboardModifier.ShiftModifier)
        self.assertEqual(w.editor.instance(self.identity)['beat'],'1')
        w.undo();self.assertEqual(w.editor.instance(self.identity)['beat'],'0')

    def test_track_loop_has_selectable_ghosts_protects_drops_and_persists_transport_loop(self):
        w=self.w;t=w.timeline
        QTest.mouseClick(t,Qt.MouseButton.LeftButton,pos=QPoint(t.header-15,30+3*t.row_height+22))
        self.assertTrue(w.loop_track.isChecked());self.assertIn('bass',w.editor.project['trackLoops'])
        spans=list(arrangement_spans(w.editor.project));self.assertEqual(len(spans),8)
        self.assertEqual(len(w.editor.project['instances']),1)
        before=w.editor.serial
        QTest.mouseClick(t,Qt.MouseButton.LeftButton,pos=self.point(F(5)))
        self.assertEqual(w.selected_id,self.identity);self.assertEqual(w.editor.serial,before)
        # Browser auditions isolate the selected clip, even with a saved loop lane.
        clip=next(c for c in clip_library.catalog()['clips'] if c['role']=='bass' and c['meter']==[4,4])
        audition=clip_library.audition(w.editor,clip,F(4))
        self.assertNotIn('trackLoops',audition)
        self.assertEqual(len(audition['instances']),1)
        clip=next(c for c in clip_library.catalog()['clips'] if c['role']=='bass' and c['meter']==[4,4])
        mime=QMimeData();mime.setData(MIME,clip['id'].encode())
        drop=QDropEvent(QPointF(t.x(F(8))+10,30+3*t.row_height+22),Qt.DropAction.CopyAction,mime,Qt.MouseButton.LeftButton,Qt.KeyboardModifier.NoModifier)
        t.dropEvent(drop);self.assertEqual(len(w.editor.project['instances']),1)
        self.assertIn('loop',w.message.text().lower())
        QTest.mouseClick(w.loop_song,Qt.MouseButton.LeftButton)
        self.assertTrue(w.editor.project['loopPlayback']);self.assertEqual(w.player.loops(),QMediaPlayer.Loops.Infinite)
        path=Path(self.folder.name)/'loops.prdeproj';w.editor.save(path)
        reopened=load_project(path);self.assertTrue(reopened['loopPlayback']);self.assertEqual(reopened['trackLoops'],w.editor.project['trackLoops'])
        w.undo();self.assertFalse(w.loop_song.isChecked());self.assertEqual(w.player.loops(),QMediaPlayer.Loops.Once)

    def test_large_layout_and_extended_chord_inversions_remain_accessible(self):
        w=self.w
        for scale in (1,1.5):
            w._apply_scale(scale);self.app.processEvents()
            self.assertTrue(w.play_button.isVisible());self.assertTrue(w.loop_song.isVisible())
            bottom=w.loop_song.mapTo(w,w.loop_song.rect().bottomRight())
            self.assertLess(bottom.x(),w.width());self.assertLess(bottom.y(),w.height())
        dialog=ChordDialog(w.editor,F(0),w)
        try:
            quality=max(QUALITIES,key=lambda q:len(QUALITIES[q]));dialog.quality.setCurrentIndex(dialog.quality.findData(quality))
            self.assertEqual(dialog.inversion.count(),len(QUALITIES[quality]))
            dialog.inversion.setCurrentIndex(dialog.inversion.count()-1)
            self.assertTrue(dialog.buttons.button(dialog.buttons.StandardButton.Ok).isEnabled())
            dialog.quality.setCurrentIndex(dialog.quality.findData('power'))
            self.assertEqual(dialog.inversion.count(),2);self.assertLess(dialog.value()['inversion'],2)
        finally:dialog.close()


if __name__=='__main__':unittest.main()
