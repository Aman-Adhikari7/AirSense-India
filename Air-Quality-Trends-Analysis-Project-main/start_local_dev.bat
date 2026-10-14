@echo off
echo =======================================================
echo   AirSense India - Local Development Launcher
echo =======================================================
echo.
echo Starting Backend (FastAPI on http://localhost:8000)...
start "AirSense Backend" cmd /k "cd /d %~dp0backend && set DATABASE_URL=sqlite:///airq.db && (if exist .venv\Scripts\uvicorn.exe (.venv\Scripts\uvicorn app.main:app --reload --host 0.0.0.0 --port 8000) else (python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000))"

echo Starting Frontend (Vite on http://localhost:5173)...
start "AirSense Frontend" cmd /k "cd /d %~dp0frontend && npm run dev -- --host 0.0.0.0 --port 5173"

echo.
echo Done! Both services are launching in separate windows:
echo - API Docs: http://localhost:8000/docs
echo - Web UI:   http://localhost:5173
echo =======================================================
