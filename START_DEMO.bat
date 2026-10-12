@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" goto missing
if not exist "milaan\backend\.env" goto missing
start "Milaan - receipt checker" cmd /k ""%~dp0START_MILAAN.bat""
start "Separate demo store" cmd /k ""%~dp0START_DEMO_STORE.bat""
echo Wait until both windows say Application startup complete.
echo Open http://127.0.0.1:8000 and http://127.0.0.1:8090 in your browser.
pause
exit /b 0
:missing
echo First run SETUP.bat.
pause
exit /b 1
