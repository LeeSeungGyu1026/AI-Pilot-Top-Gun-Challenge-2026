@echo off
setlocal
cd /d "%~dp0\.."
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
"C:\Users\GYU\AppData\Local\miniconda3\envs\aip\python.exe" scripts\codex_check_torch_ready.py
if errorlevel 1 exit /b %errorlevel%
"C:\Users\GYU\AppData\Local\miniconda3\envs\aip\python.exe" scripts\run_experiment.py experiments\codex_ic_s3_v13b_reduced_precision_rear_gunnery_v1.yaml
