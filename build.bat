@echo off
REM ============================================================
REM   Hwang Viewer for Radiologic Presentation v2.1
REM   Windows EXE Build Script
REM ============================================================

setlocal

echo.
echo ============================================================
echo   Hwang Viewer v2.1 EXE Build - Start
echo ============================================================
echo.

REM [1/3] Install dependencies and PyInstaller (skip if already installed)
echo [1/3] Checking dependencies...
pip install -q -r requirements.txt
pip install -q pyinstaller

REM [2/3] Clean previous build
echo.
echo [2/3] Cleaning previous build folders...
if exist build rmdir /s /q build
if exist dist  rmdir /s /q dist

REM [3/3] Run PyInstaller
echo.
echo [3/3] Running PyInstaller (this takes 2-3 minutes)...
pyinstaller HwangViewer.spec --noconfirm

echo.
if exist dist\HwangViewer.exe (
    echo ============================================================
    echo   Build complete!
    echo   Run: dist\HwangViewer.exe
    echo ============================================================
) else (
    echo ============================================================
    echo   Build failed. Check the log above.
    echo ============================================================
)
echo.
pause
