@echo off
REM Buildly Forge Controller - Windows Installer
REM Installs the cross-platform Forge Controller application

setlocal enabledelayedexpansion

echo.
echo ╔════════════════════════════════════════════════════════════╗
echo ║          Buildly Forge Controller Installer               ║
echo ║          Cross-Platform Service Manager                    ║
echo ╚════════════════════════════════════════════════════════════╝
echo.

set "SCRIPT_DIR=%~dp0"

REM Check Python
echo [*] Checking Python installation...
python --version >nul 2>&1
if errorlevel 1 (
    python3 --version >nul 2>&1
    if errorlevel 1 (
        echo [X] Python 3 is required but not found.
        echo     Please install Python 3 from https://python.org
        pause
        exit /b 1
    )
    set "PYTHON_CMD=python3"
) else (
    set "PYTHON_CMD=python"
)

for /f "tokens=*" %%i in ('%PYTHON_CMD% --version 2^>^&1') do set "PYTHON_VERSION=%%i"
echo [✓] Found %PYTHON_VERSION%

REM Install dependencies
echo.
echo [*] Installing Python dependencies...
%PYTHON_CMD% -m pip install --user requests PyQt5 --quiet
if errorlevel 1 (
    echo [!] Warning: Some dependencies may have failed to install
) else (
    echo [✓] Dependencies installed
)

REM Copy icon if exists
echo.
echo [*] Setting up icons...
if exist "%SCRIPT_DIR%macos\forge-logo.png" (
    copy "%SCRIPT_DIR%macos\forge-logo.png" "%SCRIPT_DIR%forge_controller\forge-logo.png" >nul 2>&1
    echo [✓] Icon copied
) else if exist "%SCRIPT_DIR%macos\buildly_icon.png" (
    copy "%SCRIPT_DIR%macos\buildly_icon.png" "%SCRIPT_DIR%forge_controller\forge-logo.png" >nul 2>&1
    echo [✓] Icon copied
) else (
    echo [!] No icon found. App will use default icon.
)

REM Create batch launcher
echo.
echo [*] Creating launcher scripts...

(
echo @echo off
echo cd /d "%%~dp0"
echo %PYTHON_CMD% forge_controller_app.py
) > "%SCRIPT_DIR%ForgeController.bat"

(
echo @echo off
echo cd /d "%%~dp0"
echo start /b "" pythonw forge_controller_app.py
) > "%SCRIPT_DIR%ForgeController-Background.bat"

echo [✓] Launcher scripts created

echo.
echo ╔════════════════════════════════════════════════════════════╗
echo ║              Installation Complete!                        ║
echo ╚════════════════════════════════════════════════════════════╝
echo.
echo To run the Forge Controller:
echo.
echo   %SCRIPT_DIR%ForgeController.bat
echo.
echo Or run in background (no console):
echo.
echo   %SCRIPT_DIR%ForgeController-Background.bat
echo.
echo To add to Windows Startup:
echo   1. Press Win+R
echo   2. Type: shell:startup
echo   3. Copy ForgeController-Background.bat to that folder
echo.
echo The controller will scan ports 8000-9000 for running Forge services.
echo.
pause
