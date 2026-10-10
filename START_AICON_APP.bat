@echo off
setlocal
title AiCON Unified Reconciliation Web App

echo ============================================================
echo   AiCON — Autonomous Payment Reconciliation App
echo ============================================================
echo.
echo Starting Web UI on http://localhost:7860...
echo.

start "" "http://localhost:7860"
python aicon_unified_app.py

pause
