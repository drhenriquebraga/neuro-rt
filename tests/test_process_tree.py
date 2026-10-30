import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest

from neuro_rt.process_tree import ManagedProcess
from test_pipeline import TEMP_ROOT

ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(os.name == 'nt', 'Prova de JobObject Windows.')
class ProcessTreeTests(unittest.TestCase):
    def run_tree(self, exit_parent):
        with tempfile.TemporaryDirectory(dir=TEMP_ROOT) as tmp:
            pid_file = Path(tmp) / 'child.txt'
            script = ('import subprocess,sys,time;from pathlib import Path;'
                'p=subprocess.Popen([sys.executable,"-c","import time;time.sleep(60)"]);'
                'Path(sys.argv[1]).write_text(str(p.pid));' +
                ('' if exit_parent else 'time.sleep(60)'))
            with (Path(tmp) / 'log.txt').open('wb') as log:
                managed = ManagedProcess([sys.executable, '-c', script, str(pid_file)],
                    cwd=ROOT, env=dict(os.environ, PYTHONDONTWRITEBYTECODE='1'), stdout=log)
                try:
                    deadline = time.monotonic() + 10
                    while not pid_file.is_file() and time.monotonic() < deadline: time.sleep(.02)
                    self.assertTrue(pid_file.is_file())
                    child = int(pid_file.read_text())
                    if exit_parent: self.assertEqual(managed.wait(timeout=10), 0)
                    self.assertGreaterEqual(managed.active_count(), 1)
                    managed.terminate_tree()
                    self.assertEqual(managed.active_count(), 0)
                    import ctypes as c
                    from ctypes import wintypes as w
                    kernel = c.WinDLL('kernel32', use_last_error=True)
                    kernel.OpenProcess.argtypes = [w.DWORD, w.BOOL, w.DWORD]
                    kernel.OpenProcess.restype = w.HANDLE
                    handle = kernel.OpenProcess(0x1000, False, child)
                    if handle:
                        kernel.GetExitCodeProcess.argtypes = [w.HANDLE, c.POINTER(w.DWORD)]
                        code = w.DWORD()
                        self.assertTrue(kernel.GetExitCodeProcess(handle, c.byref(code)))
                        self.assertNotEqual(code.value, 259)
                        kernel.CloseHandle.argtypes = [w.HANDLE]; kernel.CloseHandle(handle)
                finally: managed.close()

    def test_cancel_terminates_worker_and_grandchild(self): self.run_tree(False)
    def test_orphan_is_owned_even_after_parent_finishes(self): self.run_tree(True)
