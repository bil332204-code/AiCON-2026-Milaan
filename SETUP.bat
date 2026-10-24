@echo off
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" goto install
py -3.12 -m venv .venv
if errorlevel 1 python -m venv .venv
if errorlevel 1 goto fail
:install
".venv\Scripts\python.exe" -m pip install -r milaan\backend\requirements.txt
if errorlevel 1 goto fail
".venv\Scripts\python.exe" setup_admin.py
if errorlevel 1 goto fail
echo Setup complete. Run START_DEMO.bat next.
pause
exit /b 0
:fail
echo Setup failed. Read the error above before continuing.
pause
exit /b 1
