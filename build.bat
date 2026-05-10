@echo off
REM Build AccountManager.exe via PyInstaller (flet pack)
REM Output: release\v<version>\AccountManager.exe
cd /d "%~dp0"
python build.py
if errorlevel 1 (
    echo.
    echo [ERROR] Build failed - see output above.
    pause
    exit /b 1
)
echo.
echo [OK] Build complete. See release\ for the exe.
pause
