"""Destructive operations run only against isolated synthetic installations."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
PS = str(Path(os.environ['SystemRoot'])/'System32/WindowsPowerShell/v1.0/powershell.exe')


def quote(value):
    return "'" + str(value).replace("'", "''") + "'"


class UninstallTests(unittest.TestCase):
    def run_ps(self, code):
        result = subprocess.run([PS, '-NoProfile', '-NonInteractive', '-Command',
            "$ErrorActionPreference='Stop'; . " + quote(ROOT/'scripts/uninstall-functions.ps1') + '\n' + code],
            capture_output=True, text=True, timeout=60)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def fixture(self, parent):
        root = Path(parent)/'fake app with spaces'
        (root/'frontend').mkdir(parents=True)
        (root/'frontend/package.json').write_text(json.dumps({'name': 'uvr5-ui-next'}))
        (root/'start.bat').write_text('@echo off')
        (root/'api_modern.py').write_text('# fixture')
        return root

    def test_boundary_and_root_validation(self):
        with tempfile.TemporaryDirectory() as parent:
            root = self.fixture(parent)
            self.run_ps(f"""
$root={quote(root)}
if ((Assert-ProjectRoot $root) -ne $root) {{ throw 'wrong root' }}
if (-not (Test-InProject "$root\env\python.exe" $root)) {{ throw 'child rejected' }}
if (Test-InProject "$root-other\env" $root) {{ throw 'sibling accepted' }}
if (Test-InProject "$root\..\outside" $root) {{ throw 'traversal accepted' }}
foreach ($bad in @($env:USERPROFILE, $env:SystemRoot, {quote(parent)})) {{
  $rejected=$false; try {{ Assert-ProjectRoot $bad }} catch {{ $rejected=$true }}
  if (-not $rejected) {{ throw 'unsafe root accepted' }}
}}
""")

    def test_tree_removes_hidden_readonly_but_does_not_follow_junction(self):
        with tempfile.TemporaryDirectory() as parent:
            root = self.fixture(parent)
            outside = Path(parent)/'other app'; outside.mkdir()
            canary = outside/'keep.txt'; canary.write_text('preserve')
            self.run_ps(f"""
$root=Assert-ProjectRoot {quote(root)}
New-Item -ItemType Junction -Path (Join-Path $root 'linked') -Target {quote(outside)} | Out-Null
$f=Join-Path $root '.hidden'; [IO.File]::WriteAllText($f,'test')
[IO.File]::SetAttributes($f, [IO.FileAttributes]'Hidden,ReadOnly')
Remove-ProjectTree $root $root
if (Test-Path -LiteralPath $root) {{ throw 'root remains' }}
""")
            self.assertEqual(canary.read_text(), 'preserve')

    def test_conda_registry_preserves_other_installations(self):
        with tempfile.TemporaryDirectory() as parent:
            root = self.fixture(parent)
            registry = Path(parent)/'environments.txt'
            keep = [r'C:\pinokio\bin\miniconda', str(root)+'-other\\env']
            registry.write_text('\n'.join([keep[0], str(root), str(root/'env'), keep[1]])+'\n')
            self.run_ps(f'Remove-CondaReferences {quote(registry)} {quote(root)}')
            self.assertEqual(registry.read_text().splitlines(), keep)

    def test_process_selection_preserves_unrelated_apps(self):
        self.run_ps(r'''
$root='C:\example\studio'
function P($id,$parent,$name,$exe,$cmd) {
  [pscustomobject]@{ProcessId=$id;ParentProcessId=$parent;Name=$name;ExecutablePath=$exe;CommandLine=$cmd}
}
$processes=@(
 (P 10 1 'python.exe' "$root\env\python.exe" 'api_modern.py'),
 (P 11 10 'ffmpeg.exe' 'C:\shared\ffmpeg.exe' 'convert'),
 (P 12 10 'chrome.exe' 'C:\shared\chrome.exe' 'localhost'),
 (P 13 1 'python.exe' 'C:\shared\python.exe' 'other.py'),
 (P 14 1 'node.exe' 'C:\shared\node.exe' '"C:\example\studio-other\next.js"'),
 (P 15 16 'node.exe' 'C:\shared\node.exe' '"C:\example\studio\frontend\next.js"'),
 (P 16 1 'cmd.exe' 'C:\Windows\cmd.exe' 'cmd /c npm run dev'),
 (P 17 1 'python.exe' "$root\env\python.exe" 'excluded')
)
$actual=@(Get-OwnedProcessIds $processes $root @(17) | Sort-Object)
if (($actual -join ',') -ne '10,11,15,16') { throw "wrong processes: $actual" }
''')

    def test_shortcuts_only_belonging_to_project(self):
        self.run_ps(r'''
$link=[pscustomobject]@{TargetPath='C:\Windows\System32\cmd.exe';WorkingDirectory='';Arguments='/K "C:\example\studio\env\Scripts\activate.bat"'}
if (-not (Test-ProjectShortcut $link 'C:\example\studio')) { throw 'owned shortcut missed' }
$link.Arguments='/K "C:\example\studio-other\env\activate.bat"'
if (Test-ProjectShortcut $link 'C:\example\studio') { throw 'unrelated shortcut selected' }
''')

    def test_complete_uninstall_and_cancel_on_synthetic_project(self):
        for answer in ('\n', 'SIL\n\n'):
            with self.subTest(answer=answer), tempfile.TemporaryDirectory() as parent:
                root = self.fixture(parent); (root/'scripts').mkdir()
                for name in ('uninstall.ps1', 'uninstall-functions.ps1'):
                    shutil.copyfile(ROOT/'scripts'/name, root/'scripts'/name)
                # Keep external system state untouched in this synthetic integration test.
                with (root/'scripts/uninstall-functions.ps1').open('a') as helper:
                    for name in ('Stop-ProjectProcesses', 'Remove-CondaReferences',
                                 'Remove-ProjectRegistryEntries', 'Remove-ProjectShortcuts'):
                        helper.write(f'\nfunction {name} {{ param($File,$Root) }}\n')
                (root/'models').mkdir(); (root/'models/weights.bin').write_bytes(b'model')
                result = subprocess.run([PS, '-NoProfile', '-File', str(root/'scripts/uninstall.ps1')],
                    cwd=parent, input=answer, capture_output=True, text=True, timeout=60)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertEqual(root.exists(), answer == '\n')
                if answer == '\n': self.assertFalse((root/'.runtime').exists())

    def test_runtime_caches_are_contained(self):
        from local_runtime import configure_local_runtime
        old_temp = tempfile.tempdir
        with tempfile.TemporaryDirectory() as parent:
            try:
                with patch.dict(os.environ):
                    configure_local_runtime(parent)
                    for key in ('HF_HOME','HF_HUB_CACHE','TORCH_HOME','PIP_CACHE_DIR','TEMP','npm_config_cache'):
                        path = Path(os.environ[key])
                        self.assertTrue(path.is_relative_to(parent)); self.assertTrue(path.is_dir())
            finally:
                tempfile.tempdir = old_temp


if __name__ == '__main__': unittest.main()
