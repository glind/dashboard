@echo off
REM Install Windows Dashboard Control App

echo Installing Dashboard Controller for Windows...
echo ====================================

REM Install PyQt5 and requests
echo Installing Python dependencies...
pip install PyQt5 requests

echo.
echo Installation complete!
echo.
echo To run:
echo   python dashboard_control.py
echo.
echo To run in background (no console window):
echo   pythonw dashboard_control.py
echo.
echo To add to startup:
echo   1. Press Win+R
echo   2. Type: shell:startup
echo   3. Create shortcut to dashboard_control.py in that folder
echo.
pause
