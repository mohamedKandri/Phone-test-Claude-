@echo off
title iPhone Checkup
cd /d "%~dp0"

set PY=python
%PY% --version >nul 2>nul
if errorlevel 1 set PY=py
%PY% --version >nul 2>nul
if errorlevel 1 (
  echo Python was not found. Install it from https://www.python.org/downloads/
  echo and tick "Add Python to PATH" during setup.
  pause
  exit /b 1
)

echo Installing / updating the tool (pymobiledevice3). This can take a few minutes the first time...
%PY% -m pip install --upgrade pymobiledevice3
if errorlevel 1 (
  echo.
  echo Installing the tool failed. Take a screenshot of this window and send it.
  pause
  exit /b 1
)

echo.
echo Make sure your iPhone is plugged in and UNLOCKED.
echo If it asks "Trust This Computer?", tap Trust and enter your passcode.
echo.
pause

%PY% iphone_checkup.py

echo.
echo Done. Open iphone_report.txt in this folder and send it.
pause
