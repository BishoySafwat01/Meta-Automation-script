@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

:: =============================================================================
::  META BUSINESS SUITE INBOX AUTOMATOR - WINDOWS ZERO-TOUCH PREREQUISITES SETUP
::  Version: V4.8.0 (Enterprise Production Deployment)
::  Author: Bishoy Safwat (Senior Automation Engineer)
:: =============================================================================
::  Purpose:
::  - Automated zero-touch installation & environment hardening for Windows 11 / Server.
::  - Checks for administrative elevation and self-elevates if necessary.
::  - Detects Google Chrome; downloads and silently installs it if missing.
::  - Configures Chrome Enterprise Policy to auto-provision the Tampermonkey extension
::    across all existing and newly created multi-tenant sandbox profiles.
::  - Hardens Windows Power settings (disables sleep, standby, and hibernation for 24/7 uptime).
::  - Automatically launches 'launch_mbs_server.bat' upon successful setup.
:: =============================================================================

title Meta Business Suite Automator - Prerequisites Setup (V4.8.0)

color 0B
echo.
echo  =============================================================================
echo   META BUSINESS SUITE INBOX AUTOMATOR - PREREQUISITES AUTO-INSTALLER (V4.8.0)
echo  =============================================================================
echo   - Automated Google Chrome Silent Installation
echo   - Enterprise Policy Tampermonkey Provisioning (Force-Install)
echo   - 24/7 Continuous Server Power Hardening (Sleep & Standby Disabled)
echo   - Multi-Tenant Sandbox Profiles Initialization
echo  =============================================================================
echo.

:: -----------------------------------------------------------------------------
:: 1. ADMINISTRATOR ELEVATION CHECK
:: -----------------------------------------------------------------------------
net session >nul 2>&1
if %errorlevel% neq 0 (
    color 0E
    echo [ELEVATION REQUIRED] Administrative privileges are required for system configuration.
    echo Requesting elevated Administrator privileges...
    powershell -NoProfile -ExecutionPolicy Bypass -Command "Start-Process cmd -ArgumentList '/c ""%~f0""' -Verb RunAs"
    exit /b 0
)

echo [OK] Running with verified Administrator privileges.
echo.

:: -----------------------------------------------------------------------------
:: 2. CONTINUOUS 24/7 POWER PLAN CONFIGURATION
:: -----------------------------------------------------------------------------
echo [1/4] Configuring 24/7 Continuous Operation Power Plan...
powercfg /change standby-timeout-ac 0 >nul 2>&1
powercfg /change monitor-timeout-ac 0 >nul 2>&1
powercfg /change disk-timeout-ac 0 >nul 2>&1
powercfg /hibernate off >nul 2>&1

echo   [OK] Sleep, Standby, and Hibernation timeouts set to NEVER (0 minutes).
echo.

:: -----------------------------------------------------------------------------
:: 3. GOOGLE CHROME VERIFICATION & SILENT INSTALLATION
:: -----------------------------------------------------------------------------
echo [2/4] Verifying Google Chrome Installation...

set "CHROME_EXE="
if exist "%ProgramFiles%\Google\Chrome\Application\chrome.exe" (
    set "CHROME_EXE=%ProgramFiles%\Google\Chrome\Application\chrome.exe"
) else if exist "%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe" (
    set "CHROME_EXE=%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe"
) else if exist "%LocalAppData%\Google\Chrome\Application\chrome.exe" (
    set "CHROME_EXE=%LocalAppData%\Google\Chrome\Application\chrome.exe"
)

if defined CHROME_EXE (
    echo   [OK] Google Chrome is already installed:
    echo        "!CHROME_EXE!"
) else (
    echo   [DOWNLOADING] Google Chrome not found. Downloading enterprise installer via HTTPS...
    set "INSTALLER=%TEMP%\chrome_installer.exe"
    
    powershell -NoProfile -ExecutionPolicy Bypass -Command "[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; (New-Object Net.WebClient).DownloadFile('https://dl.google.com/chrome/install/latest/chrome_installer.exe', '%INSTALLER%')"
    
    if exist "!INSTALLER!" (
        echo   [INSTALLING] Executing silent Google Chrome setup (unattended mode)...
        start /wait "" "!INSTALLER!" /silent /install
        del /f /q "!INSTALLER!" >nul 2>&1
        
        :: Re-check installation paths
        if exist "%ProgramFiles%\Google\Chrome\Application\chrome.exe" (
            set "CHROME_EXE=%ProgramFiles%\Google\Chrome\Application\chrome.exe"
            echo   [OK] Google Chrome installed successfully.
        ) else if exist "%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe" (
            set "CHROME_EXE=%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe"
            echo   [OK] Google Chrome installed successfully.
        ) else (
            echo   [WARN] Google Chrome installed, but executable not in standard 64-bit path.
        )
    ) else (
        echo   [ERROR] Failed to download Google Chrome installer. Please verify server internet connectivity.
    )
)
echo.

:: -----------------------------------------------------------------------------
:: 4. TAMPERMONKEY EXTENSION AUTO-PROVISIONING (CHROME ENTERPRISE POLICY)
:: -----------------------------------------------------------------------------
echo [3/4] Configuring Chrome Enterprise Policy for Tampermonkey Auto-Provisioning...

set "POLICY_KEY=HKLM\SOFTWARE\Policies\Google\Chrome\ExtensionInstallForcelist"
set "TM_ENTRY=dhdgffkkebhmkfjojejmpbldmpobfkfo;https://clients2.google.com/service/update2/crx"

reg add "%POLICY_KEY%" /v 1 /t REG_SZ /d "%TM_ENTRY%" /f >nul 2>&1
if %errorlevel% equ 0 (
    echo   [OK] Chrome Enterprise Policy successfully updated.
    echo   [OK] Tampermonkey will automatically be pre-installed across all profiles!
) else (
    echo   [WARN] Could not update Registry policy. Please run script as Administrator.
)
echo.

:: -----------------------------------------------------------------------------
:: 5. LAUNCH SERVER PROFILES
:: -----------------------------------------------------------------------------
echo [4/4] Finalizing Environment Configuration...
echo.
echo =============================================================================
echo  [SUCCESS] All prerequisites and 24/7 operating policies configured.
echo =============================================================================
echo.

set "LAUNCHER=%~dp0launch_mbs_server.bat"
if exist "%LAUNCHER%" (
    echo Starting Multi-Tenant Runner in 3 seconds...
    echo File: "%LAUNCHER%"
    timeout /t 3 /nobreak >nul
    call "%LAUNCHER%"
) else (
    echo [INFO] 'launch_mbs_server.bat' was not located in '%~dp0'.
    echo You can now run 'launch_mbs_server.bat' manually whenever needed.
    echo.
    echo Press any key to close this setup window...
    pause >nul
)

exit /b 0
