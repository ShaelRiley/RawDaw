"""Actual native clip-browser controls, drops and compact/enlarged viewport bounds."""
import os
import tempfile
import time
import unittest
from fractions import Fraction as F

os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
try:
    from PySide6.QtCore import Qt, QMimeData, QPointF
    from PySide6.QtGui import QDropEvent
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication
    from prde1.gui import MainWindow
    from prde1.library_widgets import MIME
    HAS_QT=True
except ImportError:HAS_QT=False
from prde1.contracts import canonical_bytes
from prde1 import clip_library as lib


@unittest.skipUnless(HAS_QT,'Install the desktop extra for native UI tests')
class NativeLibrary(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.app=QApplication.instance() or QApplication([])
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.w=MainWindow(data_dir=self.temp.name,remember=False,safe_workspace=True)
        self.w.editor.saved=canonical_bytes(self.w.editor.project);self.w.new_song();self.w.resize(1280,800);self.w.show();self.app.processEvents()
    def tearDown(self):
        self.w.editor.saved=canonical_bytes(self.w.editor.project);self.w.close();self.app.processEvents();self.temp.cleanup()
    def test_search_role_meter_favorites_place_and_real_preview_are_independent(self):
        w=self.w;b=w.clip_browser;w.dock_tabs.setCurrentWidget(w.browser_tabs);self.app.processEvents()
        b.role.setCurrentIndex(b.role.findData('bass'));b.search.setText('Driving');self.app.processEvents()
        self.assertGreater(b.list.count(),0);self.assertTrue(all(lib.find(b.list.item(i).data(Qt.ItemDataRole.UserRole))['role']=='bass' for i in range(b.list.count())))
        b.toggle_favorite();b.favorites_only.setChecked(True);self.assertEqual(b.list.count(),1)
        before=canonical_bytes(w.editor.project);w.preview_clip();deadline=time.monotonic()+15
        while w._job and time.monotonic()<deadline:QTest.qWait(10)
        self.assertIsNone(w._job);self.assertTrue((w.work/'preview.wav').is_file());self.assertEqual(canonical_bytes(w.editor.project),before)
        w.place_clip();self.assertEqual(len(w.editor.project['instances']),1);self.assertEqual(w.role,'bass');self.assertGreater(len(w.editor.pattern(w.selected_id)['events']),0)
        w.undo();self.assertEqual(w.editor.project['patterns'],[]);self.assertTrue('Raw Daw' in w.windowTitle());self.assertFalse(w.windowIcon().isNull())
    def test_drop_on_matching_track_places_a_bar_and_occupied_drop_is_preserved(self):
        w=self.w;clip=next(c for c in lib.catalog()['clips'] if c['role']=='lead' and c['meter']==[4,4])
        mime=QMimeData();mime.setData(MIME,clip['id'].encode())
        drop=QDropEvent(QPointF(w.timeline.header+10,30+1*w.timeline.row_height+10),Qt.DropAction.CopyAction,mime,Qt.MouseButton.LeftButton,Qt.KeyboardModifier.NoModifier)
        w.timeline.dropEvent(drop);self.assertEqual(w.role,'lead');self.assertEqual(len(w.editor.project['instances']),1)
        before=canonical_bytes(w.editor.project);w.timeline.dropEvent(drop);self.assertEqual(canonical_bytes(w.editor.project),before);self.assertIn('already',w.message.text())
    def test_modes_commit_saved_values_and_browser_buttons_fit_large_text(self):
        w=self.w;p=w.pulse_controls
        p.mode.setCurrentIndex(p.mode.findData('guide'));self.assertEqual(w.editor.project['rhythmicPulse']['mode'],'guide')
        p.mode.setCurrentIndex(p.mode.findData('on'));self.assertEqual(w.editor.project['rhythmicPulse']['mode'],'on')
        for scale in (1,1.5):
            w._apply_scale(scale);w.dock_tabs.setCurrentWidget(w.browser_tabs);self.app.processEvents()
            self.assertTrue(w.play_button.isVisible());self.assertTrue(p.mode.isVisible())
            b=w.clip_browser;self.assertTrue(b.isVisible());self.assertGreater(b.list.viewport().height(),60)
            for widget in (b.search,b.role,b.style,b.favorite):
                pos=widget.mapTo(w,widget.rect().bottomRight());self.assertLess(pos.x(),w.width());self.assertLess(pos.y(),w.height())


if __name__=='__main__':unittest.main()
