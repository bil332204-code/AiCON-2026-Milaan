@echo off
setlocal
cd /d "%~dp0"
echo Keep your Milaan backend running on port 8000.
echo Stop the old integration demo on port 8080 first, if it is still running.
echo Open http://localhost:8080 in your browser.
py -3 -m http.server 8080 --bind 127.0.0.1 --directory dist
if errorlevel 1 (
  echo Could not start. Check that Python is installed and port 8080 is free.
  pause
)
