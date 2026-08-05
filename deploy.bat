@echo off
setlocal
cd /d "%~dp0"

REM Love Journal 生产环境部署 (Windows) —— 调用 deploy.ps1
REM 需安装 Docker Desktop for Windows
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0deploy.ps1" %*

if errorlevel 1 (
  echo.
  echo 部署失败，请查看上方错误信息。
)

echo.
echo 按任意键关闭此窗口。
pause > nul
endlocal
