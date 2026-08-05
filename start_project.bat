@echo off
setlocal
cd /d "%~dp0"

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0start_local_test.ps1"
if errorlevel 1 (
  echo.
  echo Startup failed. Please check the message above.
  echo.
)

echo.
echo Press any key to close this launcher window.
echo Backend and frontend windows will stay open if startup succeeded.
pause > nul
endlocal
