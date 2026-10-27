@echo off
setlocal
where python >nul 2>&1
if %ERRORLEVEL% equ 0 (
    python -u "%~dp0dualsync_bridge.py" %*
    exit /b %ERRORLEVEL%
)
where py >nul 2>&1
if %ERRORLEVEL% equ 0 (
    py -u "%~dp0dualsync_bridge.py" %*
    exit /b %ERRORLEVEL%
)
python -u "%~dp0dualsync_bridge.py" %*
