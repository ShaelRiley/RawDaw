"""Subprocess checks for native startup faults, with real Qt when installed."""
import importlib.util
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from prde1.contracts import ROOT
from prde1.desktop_startup import configure_audio

HW_KEYS = ('QT_FFMPEG_DECODING_HW_DEVICE_TYPES', 'QT_FFMPEG_ENCODING_HW_DEVICE_TYPES')
LINUX = sys.platform.startswith('linux')
HAS_QT = importlib.util.find_spec('PySide6') is not None


class DesktopStartup(unittest.TestCase):
    def test_pcm_startup_disables_video_drivers_and_preserves_display_selection(self):
        with patch.dict(os.environ, {HW_KEYS[0]: 'vaapi', HW_KEYS[1]: 'vulkan',
                                     'QT_QPA_PLATFORM': 'wayland', 'PULSE_SERVER': 'test-server'}):
            configure_audio()
            self.assertEqual(os.environ[HW_KEYS[0]], ',')
            self.assertEqual(os.environ[HW_KEYS[1]], ',')
            self.assertEqual(os.environ['QT_QPA_PLATFORM'], 'wayland')
            self.assertEqual(os.environ['PULSE_SERVER'], 'test-server')

    @unittest.skipUnless(LINUX, 'Linux native-fault diagnostics')
    def test_native_fault_retains_stage_and_traceback_in_local_log(self):
        with tempfile.TemporaryDirectory() as folder:
            env = dict(os.environ, XDG_STATE_HOME=folder)
            code = '''import resource, signal
resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
from prde1.desktop_startup import begin_startup_log, startup_stage
begin_startup_log()
startup_stage("Diagnostic fixture before native fault")
signal.raise_signal(signal.SIGSEGV)
'''
            result = subprocess.run([sys.executable, '-c', code], cwd=ROOT, env=env,
                                    capture_output=True, text=True, timeout=15)
            self.assertEqual(result.returncode, -signal.SIGSEGV)
            log = (Path(folder) / 'prde1/startup.log').read_text()
            self.assertIn('Diagnostic fixture before native fault', log)
            self.assertIn('Fatal Python error: Segmentation fault', log)
            self.assertIn('line 6 in <module>', log)
            self.assertIn('Startup diagnostics:', result.stderr)

    @unittest.skipUnless(LINUX and HAS_QT and shutil.which('cc'), 'Qt and a Linux C compiler')
    def test_editor_opens_when_video_device_initialization_would_segfault(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source = root / 'faulty_gpu.c'
            source.write_text('''#include <signal.h>
#include <unistd.h>
int av_hwdevice_ctx_create(void **context, int type, const char *device, void *options, int flags) {
    (void)context; (void)type; (void)device; (void)options; (void)flags;
    static const char msg[] = "Fault fixture: unexpected GPU device initialization\\n";
    write(2, msg, sizeof(msg)-1);
    raise(SIGSEGV);
    return -1;
}
''')
            library = root / 'faulty_gpu.so'
            subprocess.run([shutil.which('cc'), '-shared', '-fPIC', str(source), '-o', str(library)],
                           check=True, capture_output=True, text=True, timeout=15)
            env = dict(os.environ, QT_QPA_PLATFORM='offscreen', LD_PRELOAD=str(library),
                       XDG_STATE_HOME=str(root / 'state'), XDG_CONFIG_HOME=str(root / 'config'))
            for key in HW_KEYS:
                env.pop(key, None)
            prefix = 'import resource; resource.setrlimit(resource.RLIMIT_CORE, (0, 0))\n'
            baseline = prefix + '''from PySide6.QtWidgets import QApplication
app = QApplication([])
from PySide6.QtMultimedia import QMediaPlayer
player = QMediaPlayer()
'''
            failed = subprocess.run([sys.executable, '-c', baseline], cwd=ROOT, env=env,
                                    capture_output=True, text=True, timeout=15)
            self.assertEqual(failed.returncode, -signal.SIGSEGV, failed.stderr)
            self.assertIn('Fault fixture: unexpected GPU device initialization', failed.stderr)
            protected = prefix + '''from prde1.gui import MainWindow
from PySide6.QtWidgets import QApplication
app = QApplication([])
window = MainWindow("packs/reach_out_full.prdeproj", data_dir={folder!r}, remember=False)
window.show()
app.processEvents()
assert window.isVisible()
assert window.editor.project['projectId'] == 'reach_out_full'
assert window.player.playbackRate() == 1.0
window.close()
app.processEvents()
print("Full Reach Out editor opened")
'''.format(folder=str(root / 'session'))
            opened = subprocess.run([sys.executable, '-c', protected], cwd=ROOT, env=env,
                                    capture_output=True, text=True, timeout=20)
            self.assertEqual(opened.returncode, 0, opened.stderr)
            self.assertIn('Full Reach Out editor opened', opened.stdout)
            self.assertNotIn('unexpected GPU device initialization', opened.stderr)

    @unittest.skipUnless(LINUX and HAS_QT and shutil.which('c++'), 'Qt and a Linux C++ compiler')
    def test_saved_scale_opens_with_a_native_fault_in_dock_tabification(self):
        """Model the Deck's failing native API; this is not a physical reproduction."""
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source = root / 'faulty_dock.cpp'
            source.write_text('''#include <signal.h>
#include <unistd.h>
class QDockWidget;
class QMainWindow { public: void tabifyDockWidget(QDockWidget *, QDockWidget *); };
void QMainWindow::tabifyDockWidget(QDockWidget *, QDockWidget *) {
    static const char msg[] = "Fault fixture: native dock tabification\\n";
    write(2, msg, sizeof(msg)-1);
    raise(SIGSEGV);
}
''')
            library = root / 'faulty_dock.so'
            subprocess.run([shutil.which('c++'), '-shared', '-fPIC', str(source), '-o', str(library)],
                           check=True, capture_output=True, text=True, timeout=15)
            env = dict(os.environ, QT_QPA_PLATFORM='offscreen', XDG_STATE_HOME=str(root / 'state'),
                       XDG_CONFIG_HOME=str(root / 'config'), XDG_DATA_HOME=str(root / 'data'))
            prefix = '''import resource
resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
from PySide6.QtCore import QSettings, Qt
from PySide6.QtWidgets import QApplication, QDockWidget, QMainWindow, QWidget
app = QApplication([])
'''
            # Save a genuine legacy tabified layout before installing the fault.
            seed = prefix + '''window = QMainWindow()
first, second = QDockWidget("Inspector", window), QDockWidget("Browser", window)
first.setObjectName("inspectorDock"); second.setObjectName("browserDock")
first.setWidget(QWidget()); second.setWidget(QWidget())
window.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, first)
window.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, second)
window.tabifyDockWidget(first, second)
window.resize(1280, 800)
settings = QSettings("ShaelRiley", "PRDE1")
settings.setValue("geometry", window.saveGeometry())
settings.setValue("layout", window.saveState())
settings.setValue("scale", 1.25)
settings.sync()
'''
            seeded = subprocess.run([sys.executable, '-c', seed], cwd=ROOT, env=env,
                                    capture_output=True, text=True, timeout=15)
            self.assertEqual(seeded.returncode, 0, seeded.stderr)
            fault_env = dict(env, LD_PRELOAD=str(library))
            failed = subprocess.run([sys.executable, '-X', 'faulthandler', '-c', seed], cwd=ROOT,
                                    env=fault_env, capture_output=True, text=True, timeout=15)
            self.assertEqual(failed.returncode, -signal.SIGSEGV, failed.stderr)
            self.assertIn('Fault fixture: native dock tabification', failed.stderr)
            protected = '''import resource
resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
from prde1.desktop_startup import begin_startup_log
begin_startup_log()
from prde1.gui import MainWindow
from PySide6.QtWidgets import QApplication
app = QApplication([])
class DeckWindow(MainWindow):
    def restoreGeometry(self, geometry):
        result = super().restoreGeometry(geometry)
        # The offscreen screen is smaller than the Deck; retain its actual width.
        self.resize(1280, 800)
        return result
window = DeckWindow("packs/reach_out_full.prdeproj", data_dir={folder!r})
window.show(); app.processEvents()
assert window.isVisible()
assert window.editor.project['projectId'] == 'reach_out_full'
assert window._scale_value == 1.25
assert window.dock_tabs.indexOf(window.inspector_panel) >= 0
assert window.dock_tabs.indexOf(window.browser_tabs) >= 0
assert window._settings.value('scale', type=float) == 1.25
window.close(); app.processEvents()
print("Saved-scale Reach Out editor opened")
'''.format(folder=str(root / 'session'))
            opened = subprocess.run([sys.executable, '-X', 'faulthandler', '-c', protected], cwd=ROOT,
                                    env=fault_env, capture_output=True, text=True, timeout=25)
            log = root / 'state/prde1/startup.log'
            diagnostics = opened.stderr + (log.read_text() if log.exists() else '')
            self.assertEqual(opened.returncode, 0, diagnostics)
            self.assertIn('Saved-scale Reach Out editor opened', opened.stdout)
            self.assertNotIn('Fault fixture:', opened.stderr)


if __name__ == '__main__':
    unittest.main()
