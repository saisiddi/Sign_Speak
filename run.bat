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

:: Check venv (use its python.exe directly — no activate needed)
echo  [1/6] Checking virtual environment...
if not exist "venv\Scripts\python.exe" (
    echo  venv not found. Creating new venv...
    python -m venv venv
)
set PY=venv\Scripts\python.exe

:: Check Python dependencies — only install if imports actually fail
echo  [2/6] Checking Python dependencies...
%PY% -c "import mediapipe, cv2, fastapi, uvicorn, websockets, numpy, PIL, requests, sounddevice, soundfile, winsound" >nul 2>&1
if %errorlevel% neq 0 (
    echo  Installing missing Python packages...
    %PY% -m pip install -r requirements.txt -q --exists-action i
) else (
    echo  Python packages found.
)

:: Download Piper TTS if missing
echo  [3/6] Checking Piper TTS...
if not exist "piper\piper.exe" (
    echo  Piper not found. Downloading...
    %PY% -c "import urllib.request,os,zipfile,shutil,glob; os.makedirs('piper',exist_ok=True); urllib.request.urlretrieve('https://github.com/rhasspy/piper/releases/download/2023.11.14-2/piper_windows_amd64.zip','piper/piper.zip'); z=zipfile.ZipFile('piper/piper.zip'); z.extractall('piper/x'); [shutil.move(f,'piper/'+os.path.basename(f)) for f in glob.glob('piper/x/*')]; z.close(); shutil.rmtree('piper/x'); os.remove('piper/piper.zip'); print('Piper ready')"
) else (
    echo  Piper found.
)

if not exist "piper\en_US-lessac-high.onnx" (
    echo  Piper voice model not found. Downloading...
    %PY% -c "import urllib.request,os; base='https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/high/'; [urllib.request.urlretrieve(base+f,'piper/'+f) for f in ['en_US-lessac-high.onnx','en_US-lessac-high.onnx.json']]; print('Voice model ready')"
) else (
    echo  Piper voice model found.
)

:: Download ASL model if missing
echo  [4/6] Checking ASL gesture model...
if not exist "backend\model\gesture_recognizer.task" (
    echo  Downloading gesture recognizer model...
    %PY% backend\download_model.py
) else (
    echo  Model found.
)

:: Install frontend dependencies
echo  [5/6] Checking frontend dependencies...
if not exist "frontend\node_modules" (
    echo  Installing frontend packages...
    cd frontend
    npm install
    npm install react-router-dom
    cd ..
) else (
    echo  Frontend packages found.
)

:: Stop any leftover backend already listening on 8001, then start fresh
echo  [6/6] Starting SignSpeak services...
echo.
for /f "tokens=5" %%p in ('netstat -ano ^| findstr /r ":8001.*LISTENING"') do taskkill /PID %%p /F >nul 2>&1

echo  Starting backend on http://localhost:8001 ...
start "SignSpeak Backend" cmd /k "cd /d %~dp0backend && ..\venv\Scripts\python.exe -m uvicorn main:app --host 0.0.0.0 --port 8001"

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
