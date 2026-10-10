@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv-win\Scripts\python.exe" (
    echo First run: setting up Python and app dependencies...
    call "%~dp0setup_windows.cmd"
    if errorlevel 1 (
        echo.
        echo Setup failed. Review errors above.
        pause
        exit /b 1
    )
)

echo.
echo Starting AARON-1 for Windows ...
echo Browser URL: http://localhost:8501
echo Close the program with Ctrl+C in this window.
echo Data remains on this computer, in the data directory.
echo.
".venv-win\Scripts\python.exe" -m streamlit run app.py --server.address 127.0.0.1 --server.port 8501
if errorlevel 1 (
    echo.
    echo AARON-1 exited with an error. If the address is already in use,
    echo close the other Streamlit process before restarting.
    pause
    exit /b 1
)
exit /b 0
