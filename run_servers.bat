@echo off
setlocal
cd /d "%~dp0"

REM Compatibility wrapper. The unified local launcher owns dependency setup,
REM SQLite/Redis selection, health checks, and the two service windows.
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0start_local_test.ps1" %*
set "exitCode=%errorlevel%"

if not "%exitCode%"=="0" (
  echo.
  echo Local startup failed. Please check the message above.
  pause
)

endlocal & exit /b %exitCode%
