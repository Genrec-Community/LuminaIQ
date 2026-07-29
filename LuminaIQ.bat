@echo off
echo Starting LuminaIQ Backend...
start cmd /k "cd backend && python run.py"

echo Starting LuminaIQ Frontend...
start cmd /k "cd frontend && npm run dev"

echo ==================================================
echo LuminaIQ is starting up!
echo Frontend will be at http://localhost:5173
echo Backend will be at http://localhost:8000
echo ==================================================
