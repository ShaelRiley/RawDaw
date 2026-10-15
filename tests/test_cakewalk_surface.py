"""Row-strip actions and scrolled expression keep their musical targets."""
import os
import tempfile
import unittest
from fractions import Fraction
from pathlib import Path

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from PySide6.QtCore import Qt, QPoint
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QAbstractItemView

from prde1.contracts import canonical_bytes
from prde1.editor import Editor, new_project
from prde1.gui import MainWindow
from prde1.project import load_project
from prde1.sequencer import settings


class CakewalkSurface(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.window = MainWindow(data_dir=self.folder.name, remember=False, safe_workspace=True)
        self.window.editor = Editor(new_project(self.window.pack), self.window.pack)
        self.drums = self.window.editor.add_pattern('drums', Fraction(0), Fraction(16))
        self.window.show()
        self.window.select('drums', Fraction(0), self.drums)
        self.window.sequencer.preview_click.setChecked(False)
        self.app.processEvents()

    def tearDown(self):
        self.window.editor.saved = canonical_bytes(self.window.editor.project)
        self.window.close()
        self.app.processEvents()
        self.folder.cleanup()

    def target(self, identity, column=0):
        grid = self.window.sequencer.grid
        row = next(i for i, record in enumerate(self.window.sequencer.rows) if record['id'] == identity)
        grid.setCurrentCell(row, column)
        grid.scrollToItem(grid.item(row, column), QAbstractItemView.ScrollHint.PositionAtCenter)
        self.app.processEvents()
        return row

    def row_click(self, row, action):
        header = self.window.sequencer.grid.row_header
        area = header.button_rect(row, action)
        self.assertTrue(header.viewport().rect().contains(area.center()))
        QTest.mouseClick(header.viewport(), Qt.MouseButton.LeftButton, pos=area.center())
        self.app.processEvents()

    def test_row_mute_and_solo_edit_clicked_identity_and_survive_undo_and_reopen(self):
        w = self.window
        w.change(lambda: w.editor.paint_steps(self.drums, [
            ('d_kick', Fraction(0)), ('d_snare', Fraction(1, 4))]))
        authored = canonical_bytes(w.editor.pattern(self.drums)['events'])
        before = w.editor.plan()
        snare = self.target('d_snare')
        self.target('d_kick', 7)
        undo_count = len(w.editor.undo_stack)
        self.row_click(snare, 'mute')
        self.assertEqual(w.sequencer.grid.currentColumn(), 7)
        self.assertEqual(len(w.sequencer.grid.selectedIndexes()), 1)
        self.assertEqual([e['role'] for e in w.editor.plan()['events']], ['drums.kick'])
        self.assertEqual(canonical_bytes(w.editor.pattern(self.drums)['events']), authored)
        rows = settings(w.editor.pattern(self.drums), w.pack)['rows']
        self.assertTrue(next(r for r in rows if r['id'] == 'd_snare')['muted'])
        self.assertFalse(next(r for r in rows if r['id'] == 'd_kick')['muted'])
        self.assertEqual(len(w.editor.undo_stack), undo_count + 1)
        w.undo()
        self.assertEqual(w.editor.plan(), before)
        self.row_click(snare, 'solo')
        self.assertEqual([e['role'] for e in w.editor.plan()['events']], ['drums.snare'])
        self.assertEqual(canonical_bytes(w.editor.pattern(self.drums)['events']), authored)
        path = Path(self.folder.name) / 'row-solo.prdeproj'
        w.editor.save(path)
        reopened = Editor(load_project(path), w.pack, path)
        self.assertEqual(reopened.plan(), w.editor.plan())
        self.assertTrue(next(r for r in settings(reopened.pattern(self.drums), w.pack)['rows']
                             if r['id'] == 'd_snare')['solo'])

    def test_scrolled_dynamics_edits_visible_column_and_sidebar_cannot_edit_hidden_notes(self):
        w = self.window
        w.change(lambda: w.editor.paint_steps(self.drums, [
            ('d_kick', Fraction(column, 4)) for column in range(64)]))
        self.target('d_kick', 45)
        s = w.sequencer
        self.assertGreater(s.grid.horizontalScrollBar().value(), 0)
        origin = s.lane.origin()
        x = origin + s.grid.columnViewportPosition(45) + s.grid.columnWidth(45) // 2
        self.assertTrue(s.lane.rect().contains(QPoint(x, s.lane.height() // 2)))
        undo_count = len(w.editor.undo_stack)
        QTest.mouseClick(s.lane, Qt.MouseButton.LeftButton,
                         pos=QPoint(x, s.lane.height() // 2))
        events = w.editor.pattern(self.drums)['events']
        self.assertEqual([e['expression']['velocity'] for e in events],
                         [.5 if column == 45 else .8 for column in range(64)])
        self.assertEqual(len(w.editor.undo_stack), undo_count + 1)
        unchanged = canonical_bytes(w.editor.project)
        QTest.mouseClick(s.inspector, Qt.MouseButton.LeftButton,
                         pos=QPoint(s.inspector.width() - 2, s.inspector.height() - 2))
        self.assertEqual(canonical_bytes(w.editor.project), unchanged)
        self.assertEqual(len(w.editor.undo_stack), undo_count + 1)

    def test_scrolled_row_buttons_remain_usable_with_enlarged_text(self):
        w = self.window
        identity = 'd_gm_80'
        w.change(lambda: w.editor.paint_steps(self.drums, [(identity, Fraction(0))]))
        before = w.editor.plan()
        authored = canonical_bytes(w.editor.pattern(self.drums)['events'])
        for scale in (1, 1.5):
            w.resize(1280, 800)
            w._apply_scale(scale)
            row = self.target(identity)
            s = w.sequencer
            header = s.grid.row_header
            self.assertGreater(s.grid.verticalScrollBar().value(), 0)
            self.assertGreaterEqual(s.grid.viewport().height(), header.sectionSize(row))
            self.assertTrue(s.grid.viewport().rect().contains(s.grid.visualItemRect(s.grid.currentItem())))
            for action in ('mute', 'solo', 'audition', 'details'):
                self.assertTrue(header.viewport().rect().contains(header.button_rect(row, action)))
            view = w.body_scroll.viewport()
            note_controls = (s.note_volume, s.note_volume_slider, s.preview_click)
            for control in (*note_controls, s.grid, s.lane):
                top = control.mapTo(view, QPoint(0, 0))
                bottom = control.mapTo(view, QPoint(control.width() - 1, control.height() - 1))
                self.assertTrue(view.rect().contains(top))
                self.assertTrue(view.rect().contains(bottom))
            grid_bottom = s.grid.mapTo(s, QPoint(0, s.grid.height())).y()
            self.assertLessEqual(grid_bottom, min(control.mapTo(s, QPoint(0, 0)).y()
                                                 for control in note_controls))
            self.assertIs(s.lane.parentWidget(), s.grid.viewport())
            self.assertTrue(s.grid.viewport().rect().contains(s.lane.geometry()))
            self.assertTrue(header.viewport().rect().contains(s.inspector.geometry()))
            self.assertEqual(s.lane.y(), s.grid.rowViewportPosition(row) + s.grid.button_height)
            self.row_click(row, 'mute')
            self.assertEqual(w.editor.plan()['events'], [])
            self.assertEqual(canonical_bytes(w.editor.pattern(self.drums)['events']), authored)
            w.undo()
            self.assertEqual(w.editor.plan(), before)

    def test_expanded_row_controls_remain_reachable_without_overlap_at_enlarged_text(self):
        w = self.window
        before = canonical_bytes(w.editor.project)
        w.resize(1280, 800)
        w._apply_scale(1.5)
        s = w.sequencer
        s.details.setChecked(True)
        self.app.processEvents()
        self.app.processEvents()
        self.assertTrue(s.parentWidget().rect().contains(s.geometry()))
        self.assertLessEqual(s.grid.geometry().bottom(), s.note_volume.geometry().top())
        self.assertLessEqual(s.note_volume.geometry().bottom(), s.advanced_panel.geometry().top())
        self.assertLessEqual(s.advanced_panel.geometry().bottom(), s.row_panel.geometry().top())
        self.assertTrue(s.grid.viewport().rect().contains(s.lane.geometry()))
        self.assertTrue(s.grid.row_header.viewport().rect().contains(s.inspector.geometry()))
        for control in (s.row_panel, s.grid):
            w.body_scroll.ensureWidgetVisible(control)
            self.app.processEvents()
            view = w.body_scroll.viewport()
            self.assertTrue(view.rect().contains(control.mapTo(view, QPoint(0, 0))))
            self.assertTrue(view.rect().contains(control.mapTo(
                view, QPoint(control.width() - 1, control.height() - 1))))
        self.assertEqual(canonical_bytes(w.editor.project), before)

    def test_row_dials_change_audible_gate_and_swing_and_preserve_notes_across_undo_reopen(self):
        w = self.window
        bass = w.editor.add_pattern('bass', Fraction(0), Fraction(4))
        w.change(lambda: w.editor.paint_steps(bass, [('n_48', Fraction(1, 4))]))
        w.select('bass', Fraction(0), bass)
        self.target('n_48', 1)
        s = w.sequencer
        s.details.setChecked(True)
        self.app.processEvents()
        before = w.editor.plan()
        original = next(e for e in before['events'] if e['role'] == 'bass')
        authored = canonical_bytes(w.editor.pattern(bass)['events'])
        undo_count = len(w.editor.undo_stack)
        gate = s.row_dials['gatePercent']
        gate.setFocus()
        QTest.keyClick(gate, Qt.Key.Key_End)
        gated = next(e for e in w.editor.plan()['events'] if e['role'] == 'bass')
        self.assertEqual(gated['endFrame'] - gated['startFrame'],
                         2 * (original['endFrame'] - original['startFrame']))
        self.assertEqual(s.row_controls['gatePercent'].value(), 200)
        swing = s.row_dials['swingPercent']
        swing.setFocus()
        QTest.keyClick(swing, Qt.Key.Key_End)
        changed = w.editor.plan()
        swung = next(e for e in changed['events'] if e['role'] == 'bass')
        self.assertGreater(swung['startFrame'], gated['startFrame'])
        self.assertEqual(s.row_controls['swingPercent'].value(), 99)
        self.assertEqual(len(w.editor.undo_stack), undo_count + 2)
        self.assertEqual(canonical_bytes(w.editor.pattern(bass)['events']), authored)
        path = Path(self.folder.name) / 'row-dials.prdeproj'
        w.editor.save(path)
        self.assertEqual(Editor(load_project(path), w.pack, path).plan(), changed)
        w.undo()
        w.undo()
        self.assertEqual(w.editor.plan(), before)


if __name__ == '__main__':
    unittest.main()
