"""The public PS installer reuses the complete base; it never prepares Python."""
import importlib.metadata
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from host_setup_fixtures import host_setup


def complete_base():
    try:
        for name in ('numpy','SimpleITK','scipy','pydicom','fastapi','Pillow'):
            importlib.metadata.version(name)
        return True
    except importlib.metadata.PackageNotFoundError:
        return False


class SetupPowerShellTests(unittest.TestCase):
    @unittest.skipUnless(complete_base(),'Requires the complete Local Suite Python, not a parallel test environment.')
    def test_public_setup_prepares_code_using_existing_base_python_and_prints_steps(self):
        powershell=shutil.which('powershell') or shutil.which('pwsh')
        if not powershell:self.skipTest('PowerShell unavailable')
        root=Path(__file__).resolve().parents[1]
        base=root/'runtime/test-tmp';base.mkdir(parents=True,exist_ok=True)
        with tempfile.TemporaryDirectory(dir=base) as tmp:
            work=Path(tmp);suite=work/'suite';suite.mkdir()
            for name in ('radai_panel.py','radai_ui.py'):(suite/name).write_text('synthetic')
            (suite/'entrega.txt').write_text('VERSAO=8.11\n')
            setup=host_setup(work)
            before=(Path(sys.executable).stat().st_size,Path(sys.executable).stat().st_mtime_ns)
            result=subprocess.run([powershell,'-NoProfile','-NonInteractive','-ExecutionPolicy','Bypass',
                '-File',str(root/'installer/INSTALL.ps1'),'-SuiteRoot',str(suite),
                '-PackagePath',setup['path'],'-PackageSha256',setup['sha256'],
                '-TransactionId','light-ps','-BootstrapPython',sys.executable,'-AcceptTerms'],
                cwd=work,capture_output=True,text=True,timeout=60)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
            plugin=suite/'Plugins/NEURO RT'
            state=json.loads((plugin/'installation.json').read_text())
            self.assertEqual(state['pending_execution_mode'],'host')
            self.assertIsNone(state['pending_runtime'])
            self.assertIn('Python ja instalado',result.stdout)
            self.assertIn('concluir a ativacao',result.stdout)
            self.assertFalse((plugin/'runtimes').exists())
            self.assertFalse((plugin/'models').exists())
            self.assertEqual(before,(Path(sys.executable).stat().st_size,Path(sys.executable).stat().st_mtime_ns))
