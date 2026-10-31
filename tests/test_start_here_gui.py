"""Windows PowerShell 5.1 GUI contract; no download or live Suite installation."""
from pathlib import Path
import os
import subprocess
import unittest

ROOT=Path(__file__).resolve().parents[1]
SCRIPT=ROOT/'installer/START_HERE.ps1'
POWERSHELL=Path(os.environ.get('SystemRoot','C:/Windows'))/'System32/WindowsPowerShell/v1.0/powershell.exe'


@unittest.skipUnless(os.name=='nt' and POWERSHELL.is_file(),'Windows PowerShell 5.1 required')
class StartHereGuiTests(unittest.TestCase):
    def test_gui_is_utf8_bom_and_supports_library_loading(self):
        raw=SCRIPT.read_bytes()
        self.assertTrue(raw.startswith(b'\xef\xbb\xbf'),'Windows PowerShell requires an explicit UTF-8 BOM')
        source=raw.decode('utf-8-sig')
        self.assertIn('function New-NeuroWizard',source)
        self.assertIn('ReadToEndAsync()',source)
        self.assertNotIn('.ReadLine(',source)
        self.assertNotIn('.Peek(',source)
        self.assertNotIn('.Kill(',source)

    def test_windows_powershell_parser_accepts_the_script(self):
        command="$errors=$null;$tokens=$null;[void][System.Management.Automation.Language.Parser]::ParseFile('"+str(SCRIPT).replace("'","''")+"',[ref]$tokens,[ref]$errors);if($errors.Count){$errors|ForEach-Object {$_.Message};exit 1}"
        result=subprocess.run([str(POWERSHELL),'-NoProfile','-Command',command],
            capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=30)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)

    def test_real_winforms_controls_consent_progress_cancel_and_quoting(self):
        self.assertIn('function New-NeuroWizard',SCRIPT.read_text(encoding='utf-8-sig'))
        result=subprocess.run([str(POWERSHELL),'-NoProfile','-STA','-ExecutionPolicy','Bypass','-File',
            str(ROOT/'tests/start_here_gui_smoke.ps1'),'-ScriptPath',str(SCRIPT)],
            capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=75)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        self.assertIn('NEURO_GUI_SMOKE=OK',result.stdout)


if __name__=='__main__':unittest.main()
