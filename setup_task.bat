@echo off
chcp 65001 >nul

REM ============================================
REM Dashboard Data Sync - Scheduled Task Setup
REM Run as Administrator
REM ============================================

echo.
echo === Dashboard Data Sync Task Setup ===
echo.

set PYTHON_PATH=D:\pycharm\.venv\Scripts\python.exe
set PROJECT_DIR=D:\pycharm

echo Python:  %PYTHON_PATH%
echo Project: %PROJECT_DIR%
echo Schedule: Hourly
echo.

schtasks /create /tn "DashboardDataSync" /tr "%PYTHON_PATH% %PROJECT_DIR%\sync_data.py" /sc hourly /f

if %errorlevel% equ 0 (
    echo.
    echo [OK] Task created successfully!
    echo.
    echo Task name: DashboardDataSync
    echo Flow: MySQL VIEW -^> CSV -^> GitHub -^> Streamlit auto-update
    echo.
    echo Query:  schtasks /query /tn "DashboardDataSync"
    echo Run:    schtasks /run /tn "DashboardDataSync"
    echo Delete: schtasks /delete /tn "DashboardDataSync" /f
) else (
    echo.
    echo [FAIL] Please run as Administrator.
)

echo.
pause
