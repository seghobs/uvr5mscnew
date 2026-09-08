@echo off
cd /d "%~dp0frontend"
powershell -NoProfile -WindowStyle Hidden -Command "Start-Process cmd -ArgumentList '/c npm run dev' -WorkingDirectory '%~dp0frontend' -WindowStyle Hidden"
exit
