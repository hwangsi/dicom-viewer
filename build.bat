@echo off
setlocal

cd /d "%~dp0"
chcp 65001 >nul
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8

set "PY=.venv\Scripts\python.exe"

echo.
echo ============================================================
echo   Hwang Viewer v4.1 EXE Build - Start
echo ============================================================
echo.

if not exist "%PY%" (
    echo [0/4] Virtual environment not found. Creating .venv...
    py -3 -m venv .venv
    if errorlevel 1 (
        python -m venv .venv
    )
    if not exist "%PY%" (
        echo.
        echo ============================================================
        echo   Build failed: could not create .venv
        echo ============================================================
        pause
        exit /b 1
    )
)

echo [1/4] Installing/updating dependencies...
"%PY%" -m pip --disable-pip-version-check install -r requirements.txt
if errorlevel 1 goto :fail
"%PY%" -m pip --disable-pip-version-check install pyinstaller
if errorlevel 1 goto :fail

echo.
echo [2/4] Cleaning previous build folders...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist

echo.
echo [3/4] Running PyInstaller (this takes 2-3 minutes)...
"%PY%" -m PyInstaller HwangViewer.spec --noconfirm
if errorlevel 1 goto :fail

echo.
echo [4/4] Checking output...
if exist dist\HwangViewer.exe (
    echo ============================================================
    echo   Build complete!
    echo   Run: dist\HwangViewer.exe
    echo ============================================================
    pause
    exit /b 0
)

:fail
echo.
echo ============================================================
echo   Build failed. Check the log above.
echo ============================================================
pause
exit /b 1
