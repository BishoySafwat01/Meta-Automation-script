@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

:: =============================================================================
::  META BUSINESS SUITE INBOX AUTOMATOR - ENTERPRISE SERVER LAUNCHER
::  Version: V4.9.4 (Pure Python Zero-Extension Edition)
::  Author: Bishoy Safwat (Senior Automation Engineer)
:: =============================================================================
::  Purpose:
::  - Launches the Pure Python Zero-Extension Playwright Engine on Windows 11 / Server.
::  - Native script injection eliminating Tampermonkey requirement completely.
::  - Manages isolated tenant profiles with 100% Zero Cross-Talk.
::  - Automatically cleans stale Chrome SingletonLocks before launch.
:: =============================================================================

title Meta Business Suite Multi-Tenant Runner - V4.9.4

color 0B
echo.
echo  =============================================================================
echo   META BUSINESS SUITE INBOX AUTOMATOR - WINDOWS SERVER LAUNCHER (V4.9.4)
echo  =============================================================================
echo   - Pure Python Zero-Extension Playwright Engine
echo   - Multi-Tenant Storage Isolation ^& Sandbox Persistence
echo   - Windows Background Anti-Throttling Architecture
echo   - 100%% Zero Cross-Talk Guarantee (Tampermonkey Not Required)
echo  =============================================================================
echo.

:: -----------------------------------------------------------------------------
:: 1. VERIFY PYTHON ENVIRONMENT
:: -----------------------------------------------------------------------------
set "PY_CMD="
python --version >nul 2>&1
if %errorlevel% equ 0 (
    set "PY_CMD=python"
) else (
    py --version >nul 2>&1
    if %errorlevel% equ 0 (
        set "PY_CMD=py"
    )
)

if "%PY_CMD%"=="" (
    color 0C
    echo [ERROR] Python 3 was not found in system PATH.
    echo Please install Python 3.10+ from https://www.python.org/downloads/
    echo Make sure to check "Add python.exe to PATH" during installation.
    echo.
    pause
    exit /b 1
)

:: -----------------------------------------------------------------------------
:: 2. VERIFY PLAYWRIGHT PACKAGE
:: -----------------------------------------------------------------------------
%PY_CMD% -c "import playwright" >nul 2>&1
if %errorlevel% neq 0 (
    echo [SETUP] Playwright package is missing. Installing now...
    %PY_CMD% -m pip install playwright
    if %errorlevel% neq 0 (
        color 0C
        echo [ERROR] Failed to install Playwright package.
        echo Please check your internet connection and run: pip install playwright
        pause
        exit /b 1
    )
)

:: -----------------------------------------------------------------------------
:: 3. DISPATCH PYTHON ENGINE
:: -----------------------------------------------------------------------------
echo [OK] Python environment verified.
echo.

if "%~1"=="" (
    echo [LAUNCH] Starting Multi-Tenant Sandboxes (--all)...
    echo.
    %PY_CMD% "%~dp0main.py" --all
) else (
    echo [LAUNCH] Starting with arguments: %*
    echo.
    %PY_CMD% "%~dp0main.py" %*
)

if %errorlevel% neq 0 (
    echo.
    echo [NOTICE] Process exited with code %errorlevel%.
    pause
)
exit /b %errorlevel%
