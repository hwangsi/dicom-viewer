@echo off
echo ============================================
echo  Hwang Viewer - EXE Build Script
echo ============================================

pip install pyinstaller pydicom pyqt6 numpy pylibjpeg

pyinstaller ^
  --onefile ^
  --windowed ^
  --name "HwangViewer" ^
  --icon=icon.ico ^
  dicom_viewer.py

echo.
echo Build complete! Check dist\HwangViewer.exe
pause
