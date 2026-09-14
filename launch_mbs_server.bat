@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

:: =============================================================================
::  META BUSINESS SUITE INBOX AUTOMATOR - ENTERPRISE MULTI-TENANT SERVER LAUNCHER
::  Version: V4.7.0 (Production Windows 11 Server Edition)
:: =============================================================================
::  Purpose:
::  - Launches isolated, dedicated Google Chrome instances for multiple Facebook
::    Pages / Brands simultaneously on Windows 11 / Windows Server.
::  - Applies critical OS-level anti-throttling flags to prevent Windows 11 from
::    putting background or occluded tabs to sleep.
::  - Guarantees 100% Zero Cross-Talk between different Facebook accounts and pages.
:: =============================================================================

title Meta Business Suite Multi-Tenant Runner - V4.7.0

color 0B
echo.
echo  =============================================================================
echo   ⚡ META BUSINESS SUITE INBOX AUTOMATOR - 24/7 WINDOWS SERVER LAUNCHER (V4.7.0)
echo  =============================================================================
echo   • Multi-Tenant Storage Isolation ^& Profile Sandboxing
echo   • Windows 11 Anti-Throttling Engine Enabled
echo   • Dual-Layer Zero Cross-Talk Protection
echo  =============================================================================
echo.

:: -----------------------------------------------------------------------------
:: 1. LOCATE GOOGLE CHROME EXECUTABLE
:: -----------------------------------------------------------------------------
set "CHROME_EXE="

if exist "%ProgramFiles%\Google\Chrome\Application\chrome.exe" (
    set "CHROME_EXE=%ProgramFiles%\Google\Chrome\Application\chrome.exe"
) else if exist "%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe" (
    set "CHROME_EXE=%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe"
) else if exist "%LocalAppData%\Google\Chrome\Application\chrome.exe" (
    set "CHROME_EXE=%LocalAppData%\Google\Chrome\Application\chrome.exe"
)

if "%CHROME_EXE%"=="" (
    color 0C
    echo [ERROR] Google Chrome was not found in standard installation paths.
    echo Please ensure Google Chrome is installed on this server.
    echo Searched:
    echo  - %ProgramFiles%\Google\Chrome\Application\chrome.exe
    echo  - %ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe
    echo  - %LocalAppData%\Google\Chrome\Application\chrome.exe
    echo.
    pause
    exit /b 1
)

echo [OK] Located Google Chrome at:
echo      "%CHROME_EXE%"
echo.

:: -----------------------------------------------------------------------------
:: 2. SERVER STORAGE DIRECTORY CONFIGURATION
:: -----------------------------------------------------------------------------
:: Dedicated profiles directory to prevent accidental wipe by Disk Cleanup
set "BASE_PROFILES_DIR=%USERPROFILE%\MetaInboxBot_Profiles"

if not exist "%BASE_PROFILES_DIR%" (
    mkdir "%BASE_PROFILES_DIR%"
    echo [SETUP] Created master profiles root directory: "%BASE_PROFILES_DIR%"
)

:: -----------------------------------------------------------------------------
:: 3. WINDOWS 11 24/7 ANTI-THROTTLING & PERFORMANCE FLAGS
:: -----------------------------------------------------------------------------
:: CRITICAL: These flags prevent Windows 11 from suspending timer intervals,
:: DOM mutations, and WebSocket event loops when the window is minimized or behind other apps.
set "FLAGS="
set "FLAGS=%FLAGS% --disable-background-timer-throttling"
set "FLAGS=%FLAGS% --disable-backgrounding-occluded-windows"
set "FLAGS=%FLAGS% --disable-renderer-backgrounding"
set "FLAGS=%FLAGS% --disable-features=CalculateNativeWinOcclusion"
set "FLAGS=%FLAGS% --no-first-run"
set "FLAGS=%FLAGS% --no-default-browser-check"
set "FLAGS=%FLAGS% --disable-breakpad"
set "FLAGS=%FLAGS% --disable-component-update"
set "FLAGS=%FLAGS% --password-store=basic"
set "FLAGS=%FLAGS% --start-maximized"
set "FLAGS=%FLAGS% --new-window"

:: -----------------------------------------------------------------------------
:: 4. TENANT CONFIGURATION (PAGES & PROFILES)
:: -----------------------------------------------------------------------------
:: CONFIGURE YOUR PAGES BELOW:
:: Replace the asset_id or mailbox_id in the URL for each designated page.

:: --- TENANT 1: PAGE A (e.g. Primary Brand Page) ---
set "TENANT_A_NAME=Profile_PageA"
set "TENANT_A_DIR=%BASE_PROFILES_DIR%\%TENANT_A_NAME%"
set "TENANT_A_URL=https://business.facebook.com/latest/inbox/all"
:: Example with explicit asset_id:
:: set "TENANT_A_URL=https://business.facebook.com/latest/inbox/all?asset_id=10823491823901"

:: --- TENANT 2: PAGE B (e.g. Secondary Brand Page) ---
set "TENANT_B_NAME=Profile_PageB"
set "TENANT_B_DIR=%BASE_PROFILES_DIR%\%TENANT_B_NAME%"
set "TENANT_B_URL=https://business.facebook.com/latest/inbox/all"
:: Example with explicit asset_id:
:: set "TENANT_B_URL=https://business.facebook.com/latest/inbox/all?asset_id=20984712093842"

:: --- HOW TO ADD A 3RD OR 4TH TENANT: ---
:: Simply duplicate the blocks above and the start commands below:
:: set "TENANT_C_NAME=Profile_PageC"
:: set "TENANT_C_DIR=%BASE_PROFILES_DIR%\%TENANT_C_NAME%"
:: set "TENANT_C_URL=https://business.facebook.com/latest/inbox/all?asset_id=YOUR_ASSET_ID"
:: start "" "%CHROME_EXE%" --user-data-dir="%TENANT_C_DIR%" %FLAGS% "%TENANT_C_URL%"

:: -----------------------------------------------------------------------------
:: 5. LAUNCH TENANT INSTANCES
:: -----------------------------------------------------------------------------
echo =============================================================================
echo  [LAUNCHING INSTANCES]
echo =============================================================================

echo 1. Launching Tenant A [%TENANT_A_NAME%]...
echo    Profile Path: %TENANT_A_DIR%
echo    Target URL:   %TENANT_A_URL%
start "" "%CHROME_EXE%" --user-data-dir="%TENANT_A_DIR%" %FLAGS% "%TENANT_A_URL%"

timeout /t 3 /nobreak >nul

echo 2. Launching Tenant B [%TENANT_B_NAME%]...
echo    Profile Path: %TENANT_B_DIR%
echo    Target URL:   %TENANT_B_URL%
start "" "%CHROME_EXE%" --user-data-dir="%TENANT_B_DIR%" %FLAGS% "%TENANT_B_URL%"

echo.
echo =============================================================================
echo  [SUCCESS] All Tenant profiles have been dispatched in separate sandbox processes.
echo =============================================================================
echo  Important Reminders for 24/7 Server Deployment:
echo   1. Ensure Tampermonkey extension with 'meta_inbox_userscript.user.js' is
echo      installed in EACH newly created Chrome profile.
echo   2. Keep Windows Power Options set to 'High Performance' (Turn off Sleep).
echo   3. To run automatically on server reboot, add a shortcut of this batch script
echo      to the Windows Startup folder (shell:startup) or configure Task Scheduler.
echo =============================================================================
echo.
echo Press any key to exit this launcher window (browsers will remain running 24/7)...
pause >nul
exit /b 0
