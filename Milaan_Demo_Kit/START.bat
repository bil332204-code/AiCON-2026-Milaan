@echo off
setlocal
title AiCON - Milaan Reconciliation System

echo.
echo ============================================================
echo   AiCON - Milaan Payment Reconciliation System
echo ============================================================
echo.
echo  What will start:
echo    [1] Milaan Backend API  - http://localhost:8000
echo    [2] Milaan Frontend     - http://localhost:8000
echo    [3] Demo Store          - http://localhost:8090
echo.
echo  NOTE: Keep your Kaggle GPU session running for PDF parsing.
echo  Update OLLAMA_URL in milaan\backend\.env with your ngrok URL.
echo.
pause

:: ── Start Backend (FastAPI) ──────────────────────────────────────
echo [1/2] Starting Milaan backend...
cd /d "%~dp0milaan\backend"
if not exist .venv\Scripts\python.exe (
    py -3 -m venv .venv
    if errorlevel 1 ( echo Python 3.11+ required. & exit /b 1 )
)
if not exist .env copy .env.example .env >nul 2>&1
.venv\Scripts\python.exe -m pip install -r requirements.txt -q
if errorlevel 1 ( echo pip install failed. & exit /b 1 )
.venv\Scripts\python.exe -m alembic upgrade head
if errorlevel 1 ( echo Database migration failed. & exit /b 1 )

start "Milaan Backend" cmd /k ".venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload"
timeout /t 3 /nobreak >nul

:: ── Start Demo Store ─────────────────────────────────────────────
echo [2/2] Starting Demo Store...
cd /d "%~dp0demo-store"
start "Demo Store" cmd /k "python -m uvicorn server:app --host 127.0.0.1 --port 8090"
timeout /t 2 /nobreak >nul

:: ── Open browser ─────────────────────────────────────────────────
echo.
echo ============================================================
echo   Opening browser...
echo   Seller Dashboard : http://localhost:8000
echo   Demo Store       : http://localhost:8090
echo   API Docs         : http://localhost:8000/docs
echo ============================================================
echo.
start "" "http://localhost:8000"
timeout /t 2 /nobreak >nul
start "" "http://localhost:8090"

echo Both servers are running in separate windows.
echo Close those windows to stop the servers.
pause
