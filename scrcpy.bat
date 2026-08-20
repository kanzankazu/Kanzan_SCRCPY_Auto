@echo off
setlocal enabledelayedexpansion

:: ─── Kanzan SCRCPY Launcher — Windows Entry Point ────────────────────────────
:: Double-click this file to launch the scrcpy Python launcher on Windows.

:: Get script directory
set "SCRIPT_DIR=%~dp0"

:: Check Python
where python >nul 2>&1
if %errorlevel% neq 0 (
    echo Error: python not found.
    echo.
    echo Please install Python 3.8+ from https://www.python.org/downloads/
    echo Make sure to check "Add Python to PATH" during installation.
    echo.
    pause
    exit /b 1
)

:: Check scrcpy
where scrcpy >nul 2>&1
if %errorlevel% neq 0 (
    echo Error: scrcpy not found.
    echo.
    echo Install options:
    echo   winget : winget install Genymobile.scrcpy
    echo   choco  : choco install scrcpy
    echo   manual : https://github.com/Genymobile/scrcpy/releases
    echo.
    pause
    exit /b 1
)

:: Check adb
where adb >nul 2>&1
if %errorlevel% neq 0 (
    echo Error: adb not found.
    echo.
    echo Install options:
    echo   winget : winget install Google.PlatformTools
    echo   manual : https://developer.android.com/tools/releases/platform-tools
    echo.
    pause
    exit /b 1
)

:: Launch
python "%SCRIPT_DIR%scrcpy_launcher.py"

pause
