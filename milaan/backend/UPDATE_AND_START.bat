@echo off
setlocal
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe (
  echo Copy this update into your EXISTING milaan-backend folder first.
  echo Your existing folder should contain .venv and .env.
  pause
  exit /b 1
)
echo Stop any other running backend before continuing.
echo This upgrades the database schema and keeps existing records.
.venv\Scripts\python.exe -m alembic upgrade head
if errorlevel 1 (
  echo Migration failed. Read the error above before continuing.
  pause
  exit /b 1
)
.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
pause
