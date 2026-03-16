@echo off
cd /d "%~dp0"
echo Starting LuminaIQ Services...

:: Start Frontend
echo Starting Frontend...
start "LuminaIQ - Frontend" cmd /k "cd frontend && npm run dev"

:: Start Backend Main API
echo Starting Backend (Main API)...
start "LuminaIQ - Backend Main" cmd /k "cd backend && uv run run.py"



echo All services started!
