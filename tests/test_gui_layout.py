"""Real Qt ownership/accessibility checks across responsive workspace changes."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
try:
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QApplication
    from prde1.gui import MainWindow
    HAS_QT = True
except ImportError:
    HAS_QT = False

from prde1.contracts import canonical_bytes


@unittest.skipUnless(HAS_QT, 'Install the desktop extra for native UI tests')
class ResponsiveWorkspace(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.window = MainWindow(data_dir=self.folder.name, remember=False)
        self.window.show()
        self.app.processEvents()

    def tearDown(self):
        self.window.editor.saved = canonical_bytes(self.window.editor.project)
        self.window.close()
        self.app.processEvents()
        self.folder.cleanup()

    def assert_panels_accessible(self, compact):
        w = self.window
        self.assertTrue(w.play_button.isVisible())
        self.assertTrue(w.export_button.isVisible())
        for panel, dock, title, area in (
            (w.inspector_panel, w.inspector_dock, 'Inspector', Qt.DockWidgetArea.LeftDockWidgetArea),
            (w.browser_tabs, w.browser_dock, 'Browser', Qt.DockWidgetArea.RightDockWidgetArea),
        ):
            index = w.dock_tabs.indexOf(panel)
            if compact:
                self.assertGreaterEqual(index, 0)
                self.assertEqual(w.dock_tabs.tabText(index), title)
                self.assertEqual(sum(w.dock_tabs.widget(i) is panel for i in range(w.dock_tabs.count())), 1)
                self.assertIsNone(dock.widget())
                self.assertFalse(dock.isVisible())
                w.dock_tabs.setCurrentWidget(panel)
            else:
                self.assertEqual(index, -1)
                self.assertIs(dock.widget(), panel)
                self.assertEqual(w.dockWidgetArea(dock), area)
                self.assertTrue(dock.isVisible())
            self.app.processEvents()
            self.assertTrue(panel.isVisible())

    def test_scale_resize_cycles_keep_one_accessible_copy_and_the_same_music(self):
        w = self.window
        fingerprint = w.editor.fingerprint
        tabs = w.dock_tabs.count()
        states = [(1280, 1.25, True), (1024, 1.5, True), (1366, 1, False),
                  (1200, 1, True), (1366, 1.5, True), (1280, 1, False)]
        for _ in range(3):
            for width, scale, compact in states:
                with self.subTest(width=width, scale=scale):
                    w.resize(width, 800)
                    w._apply_scale(scale)
                    self.app.processEvents()
                    self.assert_panels_accessible(compact)
                    self.assertEqual(w.dock_tabs.count(), tabs + (2 if compact else 0))
                    self.assertEqual(w.editor.fingerprint, fingerprint)

    def test_focus_and_reset_do_not_expose_empty_docks_or_lose_panels(self):
        w = self.window
        fingerprint = w.editor.fingerprint
        for width, scale, compact in [(1280, 1.25, True), (1366, 1, False)]:
            w.resize(width, 800)
            w._apply_scale(scale)
            self.app.processEvents()
            w.focus_action.setChecked(True)
            w.focus_view()
            self.assertFalse(w.inspector_dock.isVisible())
            self.assertFalse(w.browser_dock.isVisible())
            w.focus_action.setChecked(False)
            w.focus_view()
            self.app.processEvents()
            self.assert_panels_accessible(compact)
            w.reset_layout()
            self.app.processEvents()
            self.assert_panels_accessible(compact)
            self.assertEqual(w.editor.fingerprint, fingerprint)


if __name__ == '__main__':
    unittest.main()
