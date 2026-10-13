"""Native library-first selection, audition, custom saving and usable layouts."""
import copy
import os
import tempfile
import time
import unittest
from pathlib import Path

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
try:
    from PySide6.QtCore import Qt, QTimer
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication, QDialog, QDialogButtonBox, QLineEdit
    from prde1.gui import MainWindow
    HAS_QT = True
except ImportError: HAS_QT = False
from prde1.contracts import canonical_bytes
from prde1 import progression_bank as lib


@unittest.skipUnless(HAS_QT, 'Install the desktop extra for native UI tests')
class NativeProgressions(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.app = QApplication.instance() or QApplication([])
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.w = MainWindow(data_dir=self.temp.name, remember=False, safe_workspace=True)
        self.w.editor.saved = canonical_bytes(self.w.editor.project); self.w.new_song()
        self.w.resize(1280, 800); self.w.show(); self.app.processEvents()
    def tearDown(self):
        self.w.editor.saved = canonical_bytes(self.w.editor.project); self.w.close(); self.app.processEvents(); self.temp.cleanup()

    def test_default_bank_search_native_preview_load_and_undo(self):
        w = self.w; b = w.progression_browser
        self.assertIs(w.browser_tabs.currentWidget(), b); self.assertEqual(b.list.count(), 12)
        b.view.setCurrentIndex(b.view.findData('all')); self.assertEqual(b.list.count(), 206)
        b.search.setText('Open road'); self.assertEqual(b.list.count(), 2)
        identity = next(e['id'] for e in lib.catalog() if e['name'] == 'Open road'); b.select_id(identity)
        before = canonical_bytes(w.editor.project)
        QTest.mouseClick(b.preview, Qt.MouseButton.LeftButton)
        deadline = time.monotonic() + 20
        while w._job and time.monotonic() < deadline: QTest.qWait(10)
        self.assertIsNone(w._job); self.assertTrue((w.work / 'preview.wav').is_file())
        self.assertEqual(canonical_bytes(w.editor.project), before)
        QTest.mouseClick(b.load, Qt.MouseButton.LeftButton)
        self.assertEqual([v['chord']['degree'] for v in w.editor.project['harmony']], [1, 5, 6, 4])
        self.assertEqual(len(w.editor.undo_stack), 1); w.undo(); self.assertEqual(canonical_bytes(w.editor.project), before)
        b.search.setText('Twelve-bar dominant blues'); self.assertEqual(b.list.count(), 1)
        QTest.mouseClick(b.load, Qt.MouseButton.LeftButton)
        self.assertEqual(w.editor.project['length'], '48'); self.assertEqual(w.bars.value(), 12)
        self.assertEqual(len(w.editor.project['harmony']), 7)
        w.undo(); self.assertEqual(canonical_bytes(w.editor.project), before)

    def test_import_is_persistent_separate_from_song_and_bad_batch_leaves_bank_intact(self):
        w = self.w; b = w.progression_browser; before = canonical_bytes(w.editor.project)
        source = Path(self.temp.name) / 'mine.txt'; source.write_text('My turn | i bVI V i | 1 2 1 2\n', encoding='utf-8')
        self.assertEqual(b.import_files([source], text_basis='major-relative'), (1, 0))
        self.assertEqual(b.list.count(), 1); b.toggle_favorite()
        bank = lib.Bank(w.progression_bank.path)
        self.assertEqual(len(bank.entries), 1); self.assertEqual(bank.favorites, w.progression_bank.favorites)
        self.assertEqual(canonical_bytes(w.editor.project), before)
        invalid = Path(self.temp.name) / 'bad.txt'; invalid.write_text('Broken | I/3 V\n')
        self.assertIsNone(b.import_files([source, invalid])); self.assertEqual(len(bank.entries), 1)
        self.assertEqual(len(lib.Bank(w.progression_bank.path).entries), 1)
        self.assertIn('Line 1', w.message.text())

    def test_custom_authoring_saves_to_bank_and_primary_controls_fit_enlarged_text(self):
        w = self.w
        def fill_dialog():
            dialog = next(x for x in self.app.topLevelWidgets() if isinstance(x, QDialog) and x.windowTitle() == 'Custom progression')
            dialog.findChild(QLineEdit, 'progressionName').setText('My loping verse')
            dialog.findChild(QLineEdit, 'progressionNotation').setText('1 2 5 1')
            dialog.findChild(QLineEdit, 'progressionDurations').setText('3/2 1/2 1 1')
            dialog.findChild(QDialogButtonBox).button(QDialogButtonBox.StandardButton.Ok).click()
        QTimer.singleShot(50, fill_dialog); w.custom_dialog()
        self.assertEqual(len(w.progression_bank.entries), 1)
        self.assertEqual(lib.Bank(w.progression_bank.path).entries[0]['name'], 'My loping verse')
        self.assertEqual([v['beat'] for v in w.editor.project['harmony']], ['0', '6', '8', '12'])
        for scale in (1, 1.5):
            w._apply_scale(scale); w.choose_progression(); self.app.processEvents(); b = w.progression_browser
            self.assertGreaterEqual(b.list.viewport().height(), 60)
            for widget in (w.progression_button, b.search, b.view, b.style, b.preview, b.load, b.manage):
                self.assertTrue(widget.isVisible())
                point = widget.mapTo(w, widget.rect().bottomRight()); self.assertLess(point.x(), w.width()); self.assertLess(point.y(), w.height())


if __name__ == '__main__': unittest.main()
