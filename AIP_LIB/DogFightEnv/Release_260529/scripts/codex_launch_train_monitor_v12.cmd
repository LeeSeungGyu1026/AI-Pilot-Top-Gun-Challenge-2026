@echo off
setlocal
set "ROOT=%~dp0.."
pushd "%ROOT%"
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
set "PYTHON=C:\Users\GYU\AppData\Local\miniconda3\envs\aip\python.exe"
set "RUNDIR=artifacts\watch\codex_v12_level_rear_gunnery_v1"
set "YAML=experiments\codex_ic_s3_v12_level_rear_gunnery_v1.yaml"
set "MONDIR=artifacts\watch\codex_v12_level_rear_gunnery_v1"
if not exist "%MONDIR%" mkdir "%MONDIR%"
start "train-monitor-codex-v12" /b "%PYTHON%" tools\train_monitor.py --rundir "%RUNDIR%" --experiment-yaml "%YAML%" --port 7865 1> "%MONDIR%\codex_train_monitor.log" 2> "%MONDIR%\codex_train_monitor.err.log"
echo started > "%MONDIR%\codex_train_monitor.pid"
popd
endlocal
