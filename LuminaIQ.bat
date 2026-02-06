@echo off
cd /d "%~dp0"
echo Starting LuminaIQ Services...

:: Start Backend Main API
echo Starting Backend (Main API)...
start "LuminaIQ - Backend Main" cmd /k "cd backend && uv run run.py"

:: Start PDF Processing Service
echo Starting Backend (PDF Process)...
start "LuminaIQ - PDF Process" cmd /k "cd pdfprocess && uv run run.py"

:: Start Frontend
echo Starting Frontend...
start "LuminaIQ - Frontend" cmd /k "cd frontend && npm run dev"

echo All services started!
