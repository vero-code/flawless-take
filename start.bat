@echo off
echo Starting Flawless Take...
echo.

:: Frontend
echo [1/2] Starting frontend...
start "Frontend" cmd /k "npm install && npm run dev"

:: Backend
echo [2/2] Starting backend...
start "Backend" cmd /k "backend\.venv\Scripts\activate.bat && uvicorn backend.main:app --reload --port 8000"

echo.
echo Both servers are starting in separate windows.
echo   Frontend: http://localhost:5173
echo   Backend:  http://localhost:8000
echo.
