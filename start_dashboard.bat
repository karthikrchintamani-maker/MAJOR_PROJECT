@echo off
title RoadEye Dashboard
color 0B

echo ============================================================
echo   RoadEye ADAS Dashboard - Starting...
echo ============================================================
echo.

cd /d "%~dp0\frontend"

REM Install node dependencies if needed
if not exist "node_modules" (
  echo [1/2] Installing npm dependencies...
  call npm install
) else (
  echo [1/2] node_modules found, skipping install.
)

echo.
echo [2/2] Starting React dashboard on http://localhost:5173
echo.
echo   Open browser: http://localhost:5173
echo   Tip: Start start_backend.bat first for live inference!
echo.
echo   Press Ctrl+C to stop.
echo ============================================================
echo.

call npm run dev

pause
