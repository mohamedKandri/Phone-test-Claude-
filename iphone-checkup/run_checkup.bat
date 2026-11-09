@echo off
setlocal
title iPhone Checkup
cd /d "%~dp0"

rem Ignore any Python virtual environment that is already active,
rem so nothing gets installed into another project.
set VIRTUAL_ENV=
set PYTHONHOME=
set PYTHONPATH=

rem The tool needs Python 3.10 or newer. Look for one.
set PY=
for %%V in (3.14 3.13 3.12 3.11 3.10) do (
  if not defined PY (
    py -%%V -c "import sys" >nul 2>nul && set "PY=py -%%V"
  )
)
if not defined PY (
  python -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>nul && set "PY=python"
)
if not defined PY (
  echo.
  echo This needs Python 3.10 or newer, and only an older Python was found.
  echo Install the latest Python from https://www.python.org/downloads/
  echo ^(choose the 64-bit "Windows installer"^), then run this file again.
  echo Your existing Python stays as it is.
  pause
  exit /b 1
)
echo Using: %PY%

rem Keep the tool in its own folder (.venv) next to this file.
if not exist ".venv\Scripts\python.exe" (
  echo Setting up a private Python folder for this tool...
  %PY% -m venv .venv
  if errorlevel 1 (
    echo Could not set it up. Take a photo of this window and send it.
    pause
    exit /b 1
  )
)
set VPY=.venv\Scripts\python.exe

echo Installing / updating the tool (pymobiledevice3). This can take a few minutes the first time...
"%VPY%" -m pip install --upgrade pip >nul 2>nul
"%VPY%" -m pip install --upgrade pymobiledevice3
if errorlevel 1 (
  echo.
  echo Installing the tool failed. Take a photo of this window and send it.
  pause
  exit /b 1
)

echo.
echo Make sure your iPhone is plugged in and UNLOCKED.
echo If it asks "Trust This Computer?", tap Trust and enter your passcode.
echo.
pause

"%VPY%" iphone_checkup.py

echo.
echo Done. Open iphone_report.txt in this folder and send it.
pause
