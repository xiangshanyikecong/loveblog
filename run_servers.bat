@echo off
cd /d "%~dp0"

echo Starting Love Journal servers...
echo.

REM Start backend
echo Starting backend on port 8000...
start "Love Backend" cmd /k "cd /d "%~dp0server" && set APP_ENV=development && set PYTHONUTF8=1 && set DATABASE_URL=sqlite:///local_demo.db && .venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000"

REM Wait a bit
timeout /t 3 /nobreak >nul

REM Start frontend
echo Starting frontend on port 5173...
start "Love Frontend" cmd /k "cd /d "%~dp0web" && set VITE_API_BASE_URL=/api && set BACKEND_PROXY_TARGET=http://127.0.0.1:8000 && npm run dev -- --host 0.0.0.0 --port 5173"

echo.
echo ========================================
echo Servers started!
echo ========================================
echo Backend:  http://localhost:8000
echo Frontend: http://localhost:5173
echo API Docs: http://localhost:8000/docs
echo.
echo Login: admin/admin or partner/partner
echo.
pause
