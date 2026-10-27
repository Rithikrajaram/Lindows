@echo off
setlocal enabledelayedexpansion

echo ===================================================
echo     DualSync Native Host Installer for Windows
echo ===================================================
echo.

set FIXED_ID=dlgiaeggibjmhegpeakmgjckgpildjdb
set LEGACY_ID=obkmhhkdmmbpjaiadpikanbjnfcoehah
set EXT_ID=%FIXED_ID%

if not "%~1"=="" (
    set EXT_ID=%~1
    echo Custom Extension ID provided: !EXT_ID!
) else (
    echo Using automated DualSync Extension ID: !EXT_ID!
)

echo.
REM Check for Python availability
where python >nul 2>&1
if !ERRORLEVEL! equ 0 (
    echo [OK] Python detected.
) else (
    where py >nul 2>&1
    if !ERRORLEVEL! equ 0 (
        echo [OK] Python py-launcher detected.
    ) else (
        echo [WARNING] Python was not detected in your PATH.
        echo Please ensure Python 3 is installed from https://www.python.org/
    )
)

set SCRIPT_DIR=%~dp0
set HOST_BAT=%SCRIPT_DIR%native_host\dualsync_bridge.bat
set JSON_FILE=%SCRIPT_DIR%native_host\com.dualsync.bridge.json

REM Escape backslashes for JSON
set ESCAPED_BAT=%HOST_BAT:\=\\%

echo.
echo Generating Native Host manifest...
(
    echo {
    echo   "name": "com.dualsync.bridge",
    echo   "description": "DualSync Native Messaging Host",
    echo   "path": "!ESCAPED_BAT!",
    echo   "type": "stdio",
    echo   "allowed_origins": [
    if not "!EXT_ID!"=="%FIXED_ID%" (
        echo     "chrome-extension://!EXT_ID!/",
    )
    echo     "chrome-extension://%FIXED_ID%/",
    echo     "chrome-extension://%LEGACY_ID%/"
    echo   ]
    echo }
) > "%JSON_FILE%"

echo Manifest created at: %JSON_FILE%
echo.

REM Register for Brave Browser
reg add "HKCU\Software\BraveSoftware\Brave-Browser\NativeMessagingHosts\com.dualsync.bridge" /ve /t REG_SZ /d "%JSON_FILE%" /f >nul 2>&1
if %ERRORLEVEL% equ 0 echo [OK] Registered for Brave Browser

REM Register for Google Chrome
reg add "HKCU\Software\Google\Chrome\NativeMessagingHosts\com.dualsync.bridge" /ve /t REG_SZ /d "%JSON_FILE%" /f >nul 2>&1
if %ERRORLEVEL% equ 0 echo [OK] Registered for Google Chrome

REM Register for Microsoft Edge
reg add "HKCU\Software\Microsoft\Edge\NativeMessagingHosts\com.dualsync.bridge" /ve /t REG_SZ /d "%JSON_FILE%" /f >nul 2>&1
if %ERRORLEVEL% equ 0 echo [OK] Registered for Microsoft Edge

REM Register for Chromium
reg add "HKCU\Software\Chromium\NativeMessagingHosts\com.dualsync.bridge" /ve /t REG_SZ /d "%JSON_FILE%" /f >nul 2>&1
if %ERRORLEVEL% equ 0 echo [OK] Registered for Chromium

REM Register for Vivaldi
reg add "HKCU\Software\Vivaldi\NativeMessagingHosts\com.dualsync.bridge" /ve /t REG_SZ /d "%JSON_FILE%" /f >nul 2>&1
if %ERRORLEVEL% equ 0 echo [OK] Registered for Vivaldi

echo.
echo ===================================================
echo  Registration complete!
echo  Extension ID: !EXT_ID!
echo  Now open the DualSync popup in Chrome and click 'Test Bridge'.
echo ===================================================
if "%~1"=="" if "%NO_PAUSE%"=="" pause
