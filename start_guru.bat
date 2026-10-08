@echo off
echo =============================================
echo   ChronosMesh API + Dashboard Startup
echo   Author: Guru Sai Prasad Reddy
echo =============================================
echo.

cd /d "%~dp0"

echo [1/3] Installing API dependencies...
pip install fastapi "uvicorn[standard]" "python-jose[cryptography]" "passlib[bcrypt]" python-multipart --quiet
if errorlevel 1 (
    echo ERROR: pip install failed. Please check Python installation.
    pause
    exit /b 1
)

echo [2/3] Installing project core dependencies...
pip install -e . --quiet 2>nul || pip install networkx numpy scipy pydantic --quiet

echo [3/3] Starting API server...
echo.
echo  API:       http://localhost:8000
echo  Dashboard: http://localhost:8000
echo  API Docs:  http://localhost:8000/api/docs
echo.
echo  Login: guru / chronosmesh
echo.
echo Press Ctrl+C to stop the server.
echo =============================================

python -m uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload
