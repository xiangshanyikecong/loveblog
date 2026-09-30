@echo off
rem 恋爱记本地试用一键启动：后端(API) + 前端(Web)
rem 演示账号：admin/admin（PartnerA）、partner/partner（PartnerB）
chcp 65001 >nul
title 恋爱记本地环境

echo [1/2] 启动后端 API (http://localhost:8000) ...
start "恋爱记-后端" cmd /k "cd /d %~dp0server && .venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000"

echo [2/2] 启动前端 Web (http://localhost:5173) ...
start "恋爱记-前端" cmd /k "cd /d %~dp0web && npm run dev"

timeout /t 6 >nul
start http://localhost:5173/
echo 完成！浏览器应已打开 http://localhost:5173/  （关闭弹出的两个命令行窗口即可停止）
pause
