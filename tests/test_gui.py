"""Real Qt event-loop tests; optional desktop libraries do not burden core-only users."""
import copy
import os
import tempfile
import time
import unittest
from fractions import Fraction
from pathlib import Path

os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
try:
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication
    from PySide6.QtCore import QUrl
    from PySide6.QtMultimedia import QAudioBufferOutput,QMediaPlayer
    from prde1.gui import MainWindow
    from prde1.gui_widgets import EventDialog
    HAS_QT=True
except ImportError:HAS_QT=False
from prde1.contracts import ROOT,canonical_bytes
from prde1.project import load_project
from prde1.mixing import DRUM_COMPRESSOR, BASS_SIDECHAIN, apply_punch_mix


@unittest.skipUnless(HAS_QT,'Install the desktop extra for native UI tests')
class NativeDesktop(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.app=QApplication.instance() or QApplication([])
    def setUp(self):
        self.folder=tempfile.TemporaryDirectory();self.window=MainWindow(data_dir=self.folder.name,remember=False)
        self.window.show();self.app.processEvents()
    def tearDown(self):
        self.window.editor.saved=canonical_bytes(self.window.editor.project);self.window.close();self.app.processEvents();self.folder.cleanup()
    def wait_render(self):
        deadline=time.monotonic()+15
        while self.window._job and time.monotonic()<deadline:QTest.qWait(10)
        self.assertIsNone(self.window._job,'Background native render timed out')

    def test_keyboard_step_edit_and_undo_resolve_the_actual_source_bank(self):
        w=self.window;before=w.editor.plan();w.steps.setCurrentCell(0,0);w.steps.setFocus();QTest.keyClick(w.steps,Qt.Key.Key_Space)
        self.assertFalse(w.editor.pattern(w.selected_id)['events'][0]['enabled'])
        self.assertEqual(len(w.editor.plan()['events']),len(before['events'])-1)
        QTest.keyClick(w,Qt.Key.Key_Z,Qt.KeyboardModifier.ControlModifier);self.app.processEvents()
        self.assertEqual(w.editor.plan(),before)
        self.assertEqual(w.player.playbackRate(),1.0)

    def test_all_catalog_gui_exports_equal_bundled_auditions_and_keep_packs_intact(self):
        import hashlib
        w=self.window
        for path in sorted((ROOT/'packs').glob('*.prdeproj')):
            with self.subTest(project=path.name):
                if path.stem.endswith('_full'):
                    index=w.full_demos.findData(path.stem.removesuffix('_full'));self.assertGreaterEqual(index,0)
                    w.full_demos.setCurrentIndex(index);QTest.mouseClick(w.full_demo_button,Qt.MouseButton.LeftButton)
                    self.assertEqual(w.editor.project['projectId'],path.stem)
                else:self.assertTrue(w.load_session(path))
                digest=hashlib.sha256(w.pack.path.read_bytes()).digest()
                output=Path(self.folder.name)/(path.stem+'.wav');self.assertTrue(w.request_render(destination=output));self.wait_render()
                self.assertTrue(output.exists(),w.message.text())
                audition=ROOT/'out/source-auditions'/(path.stem+'.wav')
                if not audition.exists():audition=ROOT/'auditions'/(path.stem+'.wav')
                self.assertEqual(output.read_bytes(),audition.read_bytes())
                self.assertEqual(hashlib.sha256(w.pack.path.read_bytes()).digest(),digest)
                self.assertTrue(output.with_suffix('.report.json').exists())

    def test_cancel_preserves_existing_export_and_cannot_publish_stale_audio(self):
        w=self.window;target=Path(self.folder.name)/'prior.wav';target.write_bytes(b'completed earlier export')
        self.assertTrue(w.request_render(destination=target));w.stop();QTest.qWait(30)
        self.assertEqual(target.read_bytes(),b'completed earlier export');self.assertIsNone(w._job)
        self.assertTrue(w.request_render());w.change(lambda:w.editor.set_mix('bass',muted=True));QTest.qWait(30)
        self.assertIsNone(w._preview_key);self.assertIsNone(w._job)

    def test_rendered_preview_decodes_at_48khz_and_pause_seek_reuse_saved_realization(self):
        w=self.window;plan=w.editor.plan();fingerprint=w.editor.fingerprint
        self.assertTrue(w.request_render());self.wait_render();self.assertEqual(w._preview_key,fingerprint)
        buffers=[];tap=QAudioBufferOutput(w);tap.audioBufferReceived.connect(lambda b:buffers.append((b.frameCount(),b.format().sampleRate())))
        w.player.setAudioBufferOutput(tap);w.player.setSource(QUrl.fromLocalFile(str(w.work/'preview.wav')));w.player.play()
        QTest.qWait(350);self.assertTrue(buffers);self.assertTrue(all(rate==48000 for frames,rate in buffers if frames))
        self.assertEqual(w.player.playbackState(),QMediaPlayer.PlaybackState.PlayingState)
        w.player.pause();QTest.qWait(40);self.assertEqual(w.player.playbackState(),QMediaPlayer.PlaybackState.PausedState)
        w.player.setPosition(1000);w.player.play();QTest.qWait(80)
        self.assertGreaterEqual(w.player.position(),1000);self.assertEqual(w.editor.plan(),plan);self.assertEqual(w.editor.fingerprint,fingerprint)

    def test_unrecorded_chord_is_reconstructed_and_keeps_playback_and_export_enabled(self):
        w=self.window
        w.change(lambda:w.editor.set_chord(Fraction(4),dict(degree=3,quality='major',inversion=0,alteration=0)))
        self.assertIn('reconstructed',w.issues.toPlainText());self.assertTrue(w.play_button.isEnabled());self.assertTrue(w.export_button.isEnabled())
        target=Path(self.folder.name)/'reconstructed.wav';self.assertTrue(w.request_render(destination=target));self.wait_render();self.assertTrue(target.exists())
        w.undo();self.assertTrue(w.play_button.isEnabled())

    def test_recovery_restores_mix_timing_selection_and_variation(self):
        w=self.window;w.change(lambda:w.editor.set_mix('bass',gainDb=-14));w.select('bass',Fraction(4),'bass_instance_1')
        w.change(w.editor.regenerate);w.autosave();self.assertTrue(w.recovery_file.exists())
        original=copy.deepcopy(w.editor.project)
        other=MainWindow(data_dir=self.folder.name,remember=False);other.show();self.app.processEvents()
        try:
            self.assertTrue(other.recover_button.isVisible());other.recover();self.assertEqual(other.editor.project,original)
            self.assertEqual(other.editor.plan(),w.editor.plan());self.assertEqual(other.selected_id,'bass_instance_1')
        finally:other.editor.saved=canonical_bytes(other.editor.project);other.close();self.app.processEvents()

    def test_scale_and_small_window_keep_primary_actions_accessible(self):
        w=self.window
        for width,height,scale in [(1366,800,1),(1280,800,1.25),(1024,768,1.5)]:
            w._apply_scale(scale);w.resize(width,height);self.app.processEvents()
            self.assertLessEqual(w.width(),width);self.assertLessEqual(w.height(),height)
            self.assertTrue(w.play_button.isVisible());self.assertTrue(w.export_button.isVisible());self.assertTrue(w.dock_tabs.isVisible())
            self.assertGreaterEqual(w.tempo.font().pointSizeF(),10*scale-.1)
        w._apply_scale(1)

    def test_saved_dynamics_controls_apply_to_the_same_native_preview_and_recover(self):
        w=self.window;before=w.editor.plan()
        w.change(lambda:w.editor.apply('Punch drums',apply_punch_mix))
        self.assertTrue(w.dynamics_controls['drumBusCompressor']['on'].isChecked())
        self.assertTrue(w.dynamics_controls['bassSidechain']['on'].isChecked())
        widget=w.dynamics_controls['bassSidechain']['maxDuckDb'];widget.setValue(3.5)
        w.set_dynamics('bassSidechain')
        self.assertEqual(w.editor.plan()['processing']['bassSidechain']['maxDuckDb'],3.5)
        w.autosave();saved=w.editor.project.copy()
        other=MainWindow(data_dir=self.folder.name,remember=False);other.show();self.app.processEvents()
        try:
            other.recover();self.assertEqual(other.editor.project,saved)
            self.assertEqual(other.editor.plan(),w.editor.plan())
        finally:other.editor.saved=canonical_bytes(other.editor.project);other.close();self.app.processEvents()
        w.undo();w.undo();self.assertEqual(w.editor.plan(),before)


if __name__=='__main__':unittest.main()

