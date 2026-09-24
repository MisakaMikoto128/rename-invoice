@echo off
chcp 65001 >nul
setlocal

set "SCRIPT_DIR=%~dp0"
set "PY_SCRIPT=%SCRIPT_DIR%rename_invoice.py"
set RENAME_INVOICE_PAUSE=1

if "%~1"=="" (
    python "%PY_SCRIPT%" "%CD%"
) else (
    python "%PY_SCRIPT%" %*
)

endlocal
