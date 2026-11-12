@echo off
echo ============================================================
echo   RoadEye ADAS - GPU Setup for RTX 4050
echo ============================================================
echo.

echo [1/3] Checking NVIDIA GPU and CUDA version...
nvidia-smi
echo.

echo [2/3] Installing onnxruntime-gpu (CUDA 12 compatible)...
pip uninstall onnxruntime -y
pip install onnxruntime-gpu

echo.
echo [3/3] Verifying CUDA is available in onnxruntime...
python -c "import onnxruntime as ort; providers = ort.get_available_providers(); print('Available providers:', providers); print('CUDA available:', 'CUDAExecutionProvider' in providers)"

echo.
echo ============================================================
echo   Done! Now run:  python server.py
echo ============================================================
pause
