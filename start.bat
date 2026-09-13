@echo off
setlocal
title UVR5 - Calistir
set "PATH=%~dp0tools\setup-runtime\ffmpeg\bin;%~dp0env;%~dp0env\Scripts;%~dp0env\Library\bin;%~dp0env\Lib\site-packages\torch\lib;%PATH%"
set "PYTHONUTF8=1"
set "PYTHONNOUSERSITE=1"
set "npm_config_cache=%~dp0cache\npm"
set "TEMP=%~dp0cache\tmp"
set "TMP=%TEMP%"
if not exist "%TEMP%" mkdir "%TEMP%"
if exist "%~dp0.runtime\uninstalling" goto uninstalling
if not exist "%~dp0env\python.exe" goto needs_setup
if not exist "%~dp0frontend\node_modules\next\package.json" goto needs_setup
where node >nul 2>nul
if errorlevel 1 goto needs_setup
cd /d "%~dp0frontend"
call npm run dev
set "uvr_exit_code=%errorlevel%"
echo.
echo Uygulama durdu. Pencereyi kapatmak icin bir tusa basin.
pause >nul
exit /b %uvr_exit_code%

:needs_setup
echo Kurulum eksik. Once setup.bat dosyasini calistirin.
pause
exit /b 1

:uninstalling
echo Kaldirma islemi baslatilmis. Uygulama acilamaz.
pause
exit /b 1
