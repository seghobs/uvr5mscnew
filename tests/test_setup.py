"""Installer logic tests; do not install packages or change the user's models."""
import importlib.util
import io
import hashlib
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('setup_runtime', Path('scripts/setup_runtime.py'))
setup = importlib.util.module_from_spec(spec)
spec.loader.exec_module(setup)


class SetupTests(unittest.TestCase):
    def test_gpu_driver_selection(self):
        self.assertEqual(setup.choose_torch_channel('577.12\n'), 'cu128')
        self.assertEqual(setup.choose_torch_channel('570.00\n577.12\n'), 'cu128')
        for value in ('', 'not supported', '555.99\n', '577.12\n555.00\n'):
            self.assertEqual(setup.choose_torch_channel(value), 'cpu')

    def test_download_commits_only_complete_files_and_reuses_existing(self):
        class Response(io.BytesIO):
            headers = {'Content-Length': '4'}
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory)/'model.bin'
            with patch.object(setup.urllib.request, 'urlopen', return_value=Response(b'no')):
                with self.assertRaises(RuntimeError):setup.download_file('https://example.com/model.bin', target)
            self.assertFalse(target.exists())
            with patch.object(setup.urllib.request, 'urlopen', return_value=Response(b'good')):
                setup.download_file('https://example.com/model.bin', target)
            self.assertEqual(target.read_bytes(), b'good')
            with patch.object(setup.urllib.request, 'urlopen') as network:
                setup.download_file('https://example.com/model.bin', target)
                network.assert_not_called()

    def test_legacy_metadata_exceptions_are_narrow(self):
        requirements = ['numpy<=1.23.5', 'librosa==0.9.2', 'transformers==4.30.2', 'chardet', 'torch>=1.13', 'progressbar', 'skipme; python_version < "3.0"']
        with patch.object(setup.metadata, 'requires', return_value=requirements), patch.object(setup, 'pip') as installer:
            setup.install_dependencies('audiosr', {'numpy', 'librosa', 'transformers'}, 'constraints.txt')
        installer.assert_called_once_with('-c', 'constraints.txt', 'chardet', 'torch>=1.13', 'progressbar')

    def test_checksum_failure_preserves_previous_download(self):
        class Response(io.BytesIO):
            headers = {'Content-Length': '4'}
        with tempfile.TemporaryDirectory() as directory:
            target=Path(directory)/'installer.exe';target.write_bytes(b'old')
            digest=hashlib.sha256(b'good').hexdigest()
            with patch.object(setup.urllib.request,'urlopen',return_value=Response(b'evil')):
                with self.assertRaises(RuntimeError):setup.download_file('https://example.com/installer.exe',target,digest)
            self.assertEqual(target.read_bytes(),b'old')

    def test_external_command_failures_propagate(self):
        with patch.object(setup.subprocess, 'run', side_effect=subprocess.CalledProcessError(1, 'pip')):
            with self.assertRaises(subprocess.CalledProcessError):setup.pip('some-package')

    def test_powershell_parser_and_checked_exit_codes(self):
        script = r'''
$tokens=$null; $errors=$null
$ast=[System.Management.Automation.Language.Parser]::ParseFile((Join-Path (Get-Location) 'scripts/setup.ps1'),[ref]$tokens,[ref]$errors)
if($errors.Count){throw ($errors | Out-String)}
$function=$ast.FindAll({param($node) $node -is [System.Management.Automation.Language.FunctionDefinitionAst] -and $node.Name -eq 'Invoke-Checked'},$true)[0]
Invoke-Expression $function.Extent.Text
Invoke-Checked 'cmd.exe' @('/c','exit 0')
Invoke-Checked 'node' @('scripts/check_frontend.cjs','--node-only')
$failed=$false
try {Invoke-Checked 'cmd.exe' @('/c','exit 17')} catch {$failed=$true}
if(-not $failed){throw 'Failed command was accepted'}
exit 0
'''
        result=subprocess.run(['powershell.exe','-NoProfile','-Command',script],capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)

    def test_setup_does_not_start_the_application(self):
        text=Path('scripts/setup.ps1').read_text()
        self.assertNotIn("@('run', 'dev')",text)
        self.assertNotIn("@('run', 'start')",text)
        self.assertIn('Get-FileHash',text)
        self.assertIn('setup.lock',text)
        bat=Path('setup.bat').read_text()
        self.assertIn('exit /b %uvr_setup_exit%',bat)
        self.assertNotIn('call start.bat',bat.lower())
