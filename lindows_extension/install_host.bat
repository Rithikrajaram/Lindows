@echo off
setlocal enabledelayedexpansion

echo ===================================================
echo     DualSync Native Host Installer for Windows
echo ===================================================
echo.
echo Please find your DualSync Extension ID:
echo 1. Open chrome://extensions (or brave://extensions)
echo 2. Find DualSync and copy its ID (e.g. obkmhhkdmmbpjaiadpikanbjnfcoehah)
echo.

set /p EXT_ID="Enter Extension ID [default: obkmhhkdmmbpjaiadpikanbjnfcoehah]: "
if "%EXT_ID%"=="" set EXT_ID=obkmhhkdmmbpjaiadpikanbjnfcoehah

set SCRIPT_DIR=%~dp0
set HOST_BAT=%SCRIPT_DIR%native_host\dualsync_bridge.bat
set JSON_FILE=%SCRIPT_DIR%native_host\com.dualsync.bridge.json

REM Escape backslashes for JSON
set ESCAPED_BAT=%HOST_BAT:\=\\%

echo {> "%JSON_FILE%"
echo   "name": "com.dualsync.bridge",>> "%JSON_FILE%"
echo   "description": "DualSync Native Messaging Host",>> "%JSON_FILE%"
echo   "path": "%ESCAPED_BAT%",>> "%JSON_FILE%"
echo   "type": "stdio",>> "%JSON_FILE%"
echo   "allowed_origins": [>> "%JSON_FILE%"
echo     "chrome-extension://%EXT_ID%/">> "%JSON_FILE%"
echo   ]>> "%JSON_FILE%"
echo }>> "%JSON_FILE%"

echo Generated manifest: %JSON_FILE%

REM Register for Brave Browser
reg add "HKCU\Software\BraveSoftware\Brave-Browser\NativeMessagingHosts\com.dualsync.bridge" /ve /t REG_SZ /d "%JSON_FILE%" /f >nul 2>&1
if %ERRORLEVEL% equ 0 echo [OK] Registered for Brave Browser

REM Register for Google Chrome
reg add "HKCU\Software\Google\Chrome\NativeMessagingHosts\com.dualsync.bridge" /ve /t REG_SZ /d "%JSON_FILE%" /f >nul 2>&1
if %ERRORLEVEL% equ 0 echo [OK] Registered for Google Chrome

REM Register for Microsoft Edge
reg add "HKCU\Software\Microsoft\Edge\NativeMessagingHosts\com.dualsync.bridge" /ve /t REG_SZ /d "%JSON_FILE%" /f >nul 2>&1
if %ERRORLEVEL% equ 0 echo [OK] Registered for Microsoft Edge

echo.
echo ===================================================
echo  Registration complete!
echo  Re-open the DualSync extension popup and click 'Test Bridge'.
echo ===================================================
pause
