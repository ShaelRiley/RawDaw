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


if __name__ == '__main__':
    unittest.main()
