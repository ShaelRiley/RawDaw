"""Real native preview clips, cache reuse and suppression of stale work."""
import copy
import os
import tempfile
import time
import unittest
from fractions import Fraction
from pathlib import Path

os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from PySide6.QtCore import QSettings, QProcess
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from unittest.mock import patch

from prde1.contracts import canonical_bytes
from prde1.editor import Editor,new_project
from prde1.gui import MainWindow
from prde1.note_preview import NotePreview
from prde1.pack import Pack
from prde1.sequencer import placement_preview_plan
from tools.build_fixture import make_fixture


class NativeNotePreview(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.app=QApplication.instance() or QApplication([])
    def wait(self,manager):
        deadline=time.monotonic()+10
        while (manager.job or manager.pending) and time.monotonic()<deadline:QTest.qWait(10)
        self.assertIsNone(manager.job);self.assertIsNone(manager.pending)

    def test_latest_request_wins_cache_reuses_equivalent_notes_and_stop_blocks_late_results(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);path=make_fixture(root/'fixture')
            with Pack(path) as pack:
                editor=Editor(new_project(pack),pack);instance=editor.add_pattern('bass',Fraction(0),Fraction(4))
                plans=[placement_preview_plan(editor,instance,'n_'+str(note),Fraction(0)) for note in (48,52,55)]
                notices=[];manager=NotePreview(root/'clips',lambda:None,notices.append);ready=[];manager.ready.connect(lambda key,path,hit:ready.append((key,path,hit)))
                try:
                    for plan in plans:key=manager.request(plan,pack.root,pack.manifest_hash)
                    self.wait(manager);self.assertEqual([r[0] for r in ready],[key]);self.assertTrue(Path(ready[0][1]).is_file())
                    equivalent=copy.deepcopy(plans[-1]);equivalent['events'][0]['id']='different-authored-id'
                    self.assertEqual(manager.request(equivalent,pack.root,pack.manifest_hash),key)
                    self.assertTrue(ready[-1][2]);self.assertEqual(manager.process.state(),QProcess.ProcessState.NotRunning)
                    before=len(ready);manager.request(plans[0],pack.root,pack.manifest_hash);manager.stop();self.wait(manager)
                    self.assertEqual(len(ready),before);self.assertEqual(notices,[])
                    manager.request(plans[0],pack.root,pack.manifest_hash);manager.stop()
                    replay=manager.request(plans[0],pack.root,pack.manifest_hash);self.wait(manager)
                    self.assertEqual(ready[-1][0],replay);self.assertEqual(len(ready),before+1);self.assertEqual(notices,[])
                    before=len(ready);manager.request(plans[1],pack.root,pack.manifest_hash);manager.set_device();self.wait(manager)
                    self.assertEqual(len(ready),before)
                finally:manager.close()

    def test_preview_switch_persists_as_a_preference_and_never_changes_the_project(self):
        with tempfile.TemporaryDirectory() as folder:
            settings=QSettings(folder+'/preferences.ini',QSettings.Format.IniFormat)
            with patch('prde1.gui.QSettings',return_value=settings):
                window=MainWindow(data_dir=folder,remember=True,safe_workspace=True)
                before=canonical_bytes(window.editor.project);window.sequencer.preview_click.setChecked(False)
                self.assertEqual(canonical_bytes(window.editor.project),before)
                window.editor.saved=canonical_bytes(window.editor.project);window.close();self.app.processEvents();settings.sync()
                reopened=MainWindow(data_dir=folder,remember=True,safe_workspace=True)
                self.assertFalse(reopened.sequencer.preview_click.isChecked())
                reopened.editor.saved=canonical_bytes(reopened.editor.project);reopened.close();self.app.processEvents()
