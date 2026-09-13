@echo off
title UVR5 - Calistir
cd /d "%~dp0frontend"
call npm run dev
set "uvr_exit_code=%errorlevel%"
echo.
echo Uygulama durdu. Pencereyi kapatmak icin bir tusa basin.
pause >nul
exit /b %uvr_exit_code%
