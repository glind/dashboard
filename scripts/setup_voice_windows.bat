@echo off
REM Voice system setup for Windows

echo.
echo ======================================
echo   Rogr Voice System Setup (Windows)
echo ======================================
echo.

REM Check for ffmpeg
where ffmpeg >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] ffmpeg not found!
    echo.
    echo Please install ffmpeg first:
    echo   1. Download from: https://ffmpeg.org/download.html
    echo   2. Or use chocolatey: choco install ffmpeg
    echo   3. Or use scoop: scoop install ffmpeg
    echo.
    pause
    exit /b 1
)
echo [OK] ffmpeg installed

REM Create directories
if not exist "data\voice_models\piper" mkdir data\voice_models\piper
if not exist "data\voice_cache" mkdir data\voice_cache
echo [OK] Directories created

REM Download Piper for Windows
set PIPER_VERSION=2023.11.14-2
set PIPER_DIR=data\voice_models\piper
set PIPER_BIN=%PIPER_DIR%\piper.exe

if not exist "%PIPER_BIN%" (
    echo [DOWNLOAD] Downloading Piper TTS for Windows...
    powershell -Command "& {Invoke-WebRequest -Uri 'https://github.com/rhasspy/piper/releases/download/%PIPER_VERSION%/piper_windows_amd64.zip' -OutFile 'piper_temp.zip'}"
    powershell -Command "& {Expand-Archive -Path 'piper_temp.zip' -DestinationPath '%PIPER_DIR%' -Force}"
    del piper_temp.zip
    echo [OK] Piper installed
) else (
    echo [OK] Piper already installed
)

REM Download voice model (Ryan - deep male voice)
set MODEL_NAME=en_US-ryan-high
set MODEL_FILE=%PIPER_DIR%\%MODEL_NAME%.onnx

if not exist "%MODEL_FILE%" (
    echo [DOWNLOAD] Downloading voice model: %MODEL_NAME%...
    powershell -Command "& {Invoke-WebRequest -Uri 'https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/en/en_US/ryan/high/en_US-ryan-high.onnx' -OutFile '%MODEL_FILE%'}"
    powershell -Command "& {Invoke-WebRequest -Uri 'https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/en/en_US/ryan/high/en_US-ryan-high.onnx.json' -OutFile '%MODEL_FILE%.json'}"
    echo [OK] Voice model installed
) else (
    echo [OK] Voice model already installed
)

REM Test installation
echo.
echo [TEST] Testing voice system...
"%PIPER_BIN%" -m "%MODEL_FILE%" -f "test_voice_temp.wav" < NUL
echo Roger roger. Voice system online.
if exist "test_voice_temp.wav" (
    ffplay -nodisp -autoexit -loglevel quiet "test_voice_temp.wav" 2>NUL
    del test_voice_temp.wav
    echo [OK] Voice synthesis successful
) else (
    echo [ERROR] Voice synthesis failed
    pause
    exit /b 1
)

echo.
echo ======================================
echo   Installation Complete!
echo ======================================
echo.
echo Voice system ready at: %PIPER_BIN%
echo Model: %MODEL_FILE%
echo.
echo To use in Python:
echo   from src.voice import announce
echo   announce('Dashboard online')
echo.
echo NOTE: Voice INPUT (microphone) is optional.
echo To enable voice commands:
echo   1. Install PortAudio
echo   2. pip install -r requirements-voice.txt
echo.
pause
