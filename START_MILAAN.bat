@echo off
cd /d "%~dp0milaan\backend"
"%~dp0.venv\Scripts\python.exe" -m alembic upgrade head
if errorlevel 1 goto fail
"%~dp0.venv\Scripts\python.exe" -m uvicorn app.main:app --host 127.0.0.1 --port 8000
:fail
pause
