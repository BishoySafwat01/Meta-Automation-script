@echo off
REM ==============================================================================
REM Meta Automation Hub (Apple Prismatic Glass Edition V6.5.3)
REM Windows Desktop Launcher
REM ==============================================================================

chcp 65001 >nul
cd /d "%~dp0"

echo ==============================================================================
echo   ⚡ Meta Business Suite Automation - Desktop Control Center V6.5.3
echo   Apple Prismatic Glass Edition (Windows Launcher)
echo ==============================================================================

where python >nul 2>nul
if %errorlevel% neq 0 (
    echo [ERROR] Python is not installed or not in PATH!
    pause
    exit /b 1
)

python -c "import webview" >nul 2>nul
if %errorlevel% neq 0 (
    echo [INFO] Installing pywebview dependency...
    pip install pywebview
)

echo [INFO] Launching Desktop Control Center...
python desktop_app.py %*
if %errorlevel% neq 0 (
    pause
)
