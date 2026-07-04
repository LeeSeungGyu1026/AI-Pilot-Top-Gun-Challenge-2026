@echo off
setlocal
cd /d "%~dp0\.."
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
"C:\Users\GYU\AppData\Local\miniconda3\envs\aip\python.exe" tools\train_monitor.py --rundir "artifacts\watch\codex_v13b_reduced_precision_rear_gunnery_v1" --experiment-yaml "experiments\codex_ic_s3_v13b_reduced_precision_rear_gunnery_v1.yaml" --port 7865
