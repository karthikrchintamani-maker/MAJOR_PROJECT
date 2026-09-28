@echo off
title RoadEye ADAS Backend
color 0A

echo ============================================================
echo   RoadEye ADAS Backend - Starting...
echo ============================================================
echo.

cd /d "%~dp0"

REM Install/update dependencies
echo [1/2] Checking Python dependencies...
pip install -r backend\requirements.txt --quiet

echo.
echo [2/2] Starting Flask inference server on http://localhost:5001
echo.
echo   MJPEG Stream  : http://localhost:5001/stream/video
echo   REST API      : http://localhost:5001/api/status
echo   WebSocket     : ws://localhost:5001/ws/telemetry
echo.
echo   Press Ctrl+C to stop.
echo ============================================================
echo.

cd backend
python server.py

pause
