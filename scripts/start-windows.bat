@echo off
title APEX AI Trading Lab — Auto-Updating Windows Launcher
cd /d "%~dp0.."

echo [APEX] Checking GitHub for latest updates...
where git >nul 2>nul
if %errorlevel%==0 (
  git fetch origin main >nul 2>nul
  git pull --ff-only origin main
)

echo [APEX] Ensuring backend dependencies and database migrations...
if exist "backend\.venv\Scripts\python.exe" (
  cd backend
  ".venv\Scripts\alembic.exe" upgrade head
  start "APEX Backend" ".venv\Scripts\uvicorn.exe" app.main:app --host 127.0.0.1 --port 8000
  cd ..
) else (
  python -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000
)

timeout /t 2 >nul
if exist "frontend\dist\index.html" (
  start "APEX UI" /D frontend npx vite preview --host 127.0.0.1 --port 5173
) else (
  start "APEX UI" /D frontend npm run dev
)
timeout /t 2 >nul
start "" "http://127.0.0.1:5173"
