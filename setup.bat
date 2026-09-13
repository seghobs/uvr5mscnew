@echo off
setlocal
cd /d "%~dp0"
title UVR5 Next Studio - Kurulum
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\setup.ps1"
set "uvr_setup_exit=%errorlevel%"
echo.
if "%uvr_setup_exit%"=="0" (
    echo Kurulum tamamlandi. Uygulamayi acmak icin start.bat dosyasini kullanin.
) else (
    echo Kurulum tamamlanamadi. Yukaridaki aciklamayi ve logs\setup.log dosyasini kontrol edin.
    echo Sorunu giderdikten sonra setup.bat dosyasini yeniden calistirabilirsiniz.
)
pause
exit /b %uvr_setup_exit%
