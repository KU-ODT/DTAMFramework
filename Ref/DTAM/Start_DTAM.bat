@echo off
setlocal

cd /d "%~dp0"
python "%~dp0Start_DTAM.py" %*

if errorlevel 1 (
    echo.
    echo Start_DTAM failed. Press any key to close this window.
    pause >nul
)
