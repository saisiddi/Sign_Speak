@echo off
title SignSpeak - One Click Launcher
color 0A
cls

echo.
echo  ============================================
echo    SignSpeak - Sign Language to Speech
echo    Starting all services...
echo  ============================================
echo.

:: Check Python
where python >nul 2>&1
if %errorlevel% neq 0 (
    echo  [ERROR] Python not found. Please install Python 3.12.
    pause
    exit /b 1
)

:: Check Node
where node >nul 2>&1
if %errorlevel% neq 0 (
    echo  [ERROR] Node.js not found. Please install Node.js from nodejs.org
    pause
    exit /b 1
)

:: Activate venv
echo  [1/5] Activating virtual environment...
call venv\Scripts\activate
if %errorlevel% neq 0 (
    echo  [ERROR] venv not found. Creating new venv...
    python -m venv venv
    call venv\Scripts\activate
)

:: Install Python dependencies
echo  [2/5] Checking Python dependencies...
pip install -r requirements.txt -q --exists-action i

:: Download ASL model if missing
echo  [3/5] Checking ASL gesture model...
if not exist "backend\model\gesture_recognizer.task" (
    echo  Downloading gesture recognizer model...
    python backend\download_model.py
) else (
    echo  Model found.
)

:: Install frontend dependencies
echo  [4/5] Checking frontend dependencies...
if not exist "frontend\node_modules" (
    echo  Installing frontend packages...
    cd frontend
    npm install
    npm install react-router-dom
    cd ..
) else (
    echo  Frontend packages found.
)

:: Start backend in new terminal window
echo  [5/5] Starting SignSpeak services...
echo.
echo  Starting backend on http://localhost:8001 ...
start "SignSpeak Backend" cmd /k "cd /d %~dp0 && call venv\Scripts\activate && cd backend && uvicorn main:app --host 0.0.0.0 --port 8001"

:: Wait for backend to start
echo  Waiting for backend to initialize...
timeout /t 4 /nobreak >nul

:: Start frontend in new terminal window
echo  Starting frontend on http://localhost:5173 ...
start "SignSpeak Frontend" cmd /k "cd /d %~dp0frontend && npm run dev"

:: Wait for frontend to start
timeout /t 4 /nobreak >nul

:: Open browser
echo  Opening SignSpeak in browser...
start http://localhost:5173

echo.
echo  ============================================
echo    SignSpeak is running!
echo.
echo    Frontend : http://localhost:5173
echo    Backend  : http://localhost:8001
echo    Health   : http://localhost:8001/health
echo    Video    : http://localhost:8001/video_feed
echo.
echo    Close the Backend and Frontend windows
echo    to stop SignSpeak.
echo  ============================================
echo.

:: Keep this window open
pause
