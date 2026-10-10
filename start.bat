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
call "%~dp0env\python.exe" "%~dp0service_control.py" frontend-check
if errorlevel 11 goto launch_failed
if errorlevel 10 goto already_running
if errorlevel 1 goto launch_failed

echo Yerel servis hazirlaniyor...
call node scripts\ensure-backend.js --no-browser --quiet
if errorlevel 1 goto launch_failed

echo Uretim surumu derleniyor...
call npm run build
if errorlevel 1 goto launch_failed

cls
echo Uygulama uretim modunda aciliyor...
call npm run start
set "uvr_exit_code=%errorlevel%"
echo.
echo Uygulama durdu. Pencereyi kapatmak icin bir tusa basin.
pause >nul
exit /b %uvr_exit_code%

:already_running
call node scripts\ensure-backend.js --no-browser --quiet
if errorlevel 1 goto launch_failed
echo Uygulama zaten acik. Mevcut pencere tarayicida aciliyor...
call "%~dp0env\python.exe" "%~dp0service_control.py" frontend-focus
start "" "http://localhost:3000"
exit /b 0

:launch_failed
echo.
echo Uygulama baslatilamadi. Yukaridaki aciklamayi kontrol edin.
pause >nul
exit /b 1

:needs_setup
echo Kurulum eksik. Once setup.bat dosyasini calistirin.
pause
exit /b 1

:uninstalling
echo Kaldirma islemi baslatilmis. Uygulama acilamaz.
pause
exit /b 1
