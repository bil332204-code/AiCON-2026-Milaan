@echo off
setlocal
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe (
  py -3 -m venv .venv
  if errorlevel 1 (
    echo Install Python 3.12 or 3.13 and try again, or manually follow README.md.
    exit /b 1
  )
)
if not exist .env copy .env.example .env >nul
.venv\Scripts\python.exe -m pip install -r requirements.txt
if errorlevel 1 exit /b 1
.venv\Scripts\python.exe -m alembic upgrade head
if errorlevel 1 exit /b 1
echo Open http://127.0.0.1:8000/docs
.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
