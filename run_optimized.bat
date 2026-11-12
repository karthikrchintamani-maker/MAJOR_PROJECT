@echo off
echo ============================================================
echo   RoadEye ADAS - INT8 Optimizer + Project Launcher
echo ============================================================
echo.

cd /d "C:\Users\Karthik R\Downloads\roadeye_models-karthik\backend"

echo [1/3] Running INT8 optimizer (this takes 2-5 minutes)...
echo       Converting 4 ONNX models to INT8 format...
echo.
python optimize_int8.py

echo.
echo [2/3] INT8 optimization done!
echo       Starting RoadEye backend server...
echo.
start "RoadEye Backend" python server.py

echo [3/3] Waiting for backend to start (5 seconds)...
timeout /t 5 /nobreak > nul

echo.
echo ============================================================
echo   RoadEye ADAS is running!
echo   Backend:  http://localhost:5001
echo   Frontend: http://localhost:5173  (start separately with npm run dev)
echo ============================================================
echo.
pause
