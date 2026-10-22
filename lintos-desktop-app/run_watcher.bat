@echo off
TITLE DualSync Windows Watcher
echo ====================================================
echo        DualSync Windows - Reverse Sync Service
echo ====================================================
echo.

REM Optional: Change the target folder below to your mounted Linux/Shared partition
REM Example: D:\SharedPartition or \\wsl$\Ubuntu\home\username\Downloads
SET TARGET_DIR=D:\DualSyncShared

REM Check if Python is installed
python --version >nul 2>&1
IF %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Python is not installed or not in system PATH.
    echo Please install Python 3 from python.org
    pause
    exit /b 1
)

REM Install dependencies if needed
pip install -r requirements.txt >nul 2>&1

echo Starting DualSync Watcher...
echo Monitoring: %USERPROFILE%\Downloads
echo Syncing to: %TARGET_DIR%
echo.
echo (Press Ctrl+C to stop)
python windows_watcher.py "%USERPROFILE%\Downloads" "%TARGET_DIR%"
pause
