@echo off
setlocal
title UVR5 Next Studio - Kaldirma
rem A separate PowerShell window can remove this batch file after cmd exits.
start "UVR5 Next Studio - Kaldirma" /D "%SystemRoot%" "%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe" -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\uninstall.ps1"
exit /b
