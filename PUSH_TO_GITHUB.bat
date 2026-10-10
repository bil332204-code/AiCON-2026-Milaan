@echo off
setlocal EnableDelayedExpansion
cd /d "%~dp0"
title AiCON 2026 - Upload to GitHub

echo =======================================================
echo  AiCON 2026 - Safe GitHub Upload
echo  Repo: bil332204-code/AiCON-2026-Milaan
echo =======================================================
echo.
where git >nul 2>&1
if errorlevel 1 (
 echo ERROR: Git for Windows is missing.
 echo Install it from https://git-scm.com/download/win
 pause
 exit /b 1
)

if not exist .git (
 git init
 if errorlevel 1 goto :failed
)

REM Configure local commit identity only if not already set.
for /f "delims=" %%A in ('git config user.name 2^>nul') do set "GIT_USER=%%A"
if not defined GIT_USER git config --local user.name "Bilal Ahmed"
for /f "delims=" %%A in ('git config user.email 2^>nul') do set "GIT_EMAIL=%%A"
if not defined GIT_EMAIL (
 echo.
 echo Git requires an email address for the commit author.
 set /p "MY_EMAIL=Enter your GitHub email: "
 if not defined MY_EMAIL (
  echo ERROR: Email is required.
  pause
  exit /b 1
 )
 git config --local user.email "!MY_EMAIL!"
)

git branch -M main
if errorlevel 1 goto :failed

git remote get-url origin >nul 2>&1
if errorlevel 1 (
 git remote add origin "https://github.com/bil332204-code/AiCON-2026-Milaan.git"
) else (
 git remote set-url origin "https://github.com/bil332204-code/AiCON-2026-Milaan.git"
)
if errorlevel 1 goto :failed

git add -A
if errorlevel 1 goto :failed

git diff --cached --quiet
if errorlevel 1 (
 git commit -m "Add AiCON project source and demo kit"
 if errorlevel 1 goto :failed
)

echo.
echo Uploading to GitHub. Sign in to GitHub if asked...
git push -u origin main
if errorlevel 1 goto :failed

echo.
echo SUCCESS - GitHub code has been uploaded!
echo https://github.com/bil332204-code/AiCON-2026-Milaan
pause
exit /b 0

:failed
echo.
echo Upload could not be completed.
echo Check Git installation, GitHub authentication, and whether the repository was created empty.
echo Do NOT force push or delete remote files. Send a screenshot of this window.
pause
exit /b 1
