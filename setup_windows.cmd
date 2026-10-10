@echo off
setlocal
cd /d "%~dp0"
echo.
echo === AARON-1 Windows setup ===
echo Python 3.11 or 3.12 (64-bit) is required.
echo No admin privileges or Ollama are needed for planner/calendar features.
echo.

if exist ".venv-win\Scripts\python.exe" goto install

where py >nul 2>&1
if not errorlevel 1 (
    py -3.12 -c "import sys; assert sys.version_info[:2] == (3, 12) and sys.maxsize > 2**32" >nul 2>&1
    if not errorlevel 1 (
        set "PY=py -3.12"
        goto create
    )
    py -3.11 -c "import sys; assert sys.version_info[:2] == (3, 11) and sys.maxsize > 2**32" >nul 2>&1
    if not errorlevel 1 (
        set "PY=py -3.11"
        goto create
    )
)
where python >nul 2>&1
if errorlevel 1 goto missing
python -c "import sys; assert sys.version_info >= (3, 11) and sys.version_info < (3, 13) and sys.maxsize > 2**32" >nul 2>&1
if errorlevel 1 goto missing
set "PY=python"

:create
echo Creating .venv-win with %PY% ...
%PY% -m venv ".venv-win"
if errorlevel 1 goto fail

:install
echo Installing/updating Windows app dependencies ...
".venv-win\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 goto fail
echo.
echo Setup completed. Double-click start_windows.cmd to run AARON-1.
exit /b 0

:missing
echo ERROR: No supported 64-bit Python 3.11 or 3.12 found.
echo Install Python 3.12 from https://www.python.org/downloads/windows/
echo Select "Add python.exe to PATH" during installation.
echo Then run setup_windows.cmd again.
exit /b 1

:fail
echo.
echo Setup failed. Nothing in your saved data folder was deleted.
echo Check the error shown above; then run setup_windows.cmd again.
exit /b 1
