@echo off
setlocal
set "ROOT=%~dp0.."
pushd "%ROOT%"
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
set "PYTHON=C:\Users\GYU\AppData\Local\miniconda3\envs\aip\python.exe"
set "RUNDIR=%ROOT%\artifacts\watch\codex_v13_rewardfix_rear_gunnery_v1"
if not exist "%RUNDIR%" mkdir "%RUNDIR%"
powershell -NoProfile -Command "Get-Date -Format o" > "%RUNDIR%\codex_started.txt"
del /q "%RUNDIR%\codex_train.exit" 2>nul
start "codex_v13_rewardfix_rear_gunnery" /b "%PYTHON%" scripts\run_experiment.py experiments\codex_ic_s3_v13_rewardfix_rear_gunnery_v1.yaml 1> "%RUNDIR%\codex_train.log" 2> "%RUNDIR%\codex_train.err.log"
echo started > "%RUNDIR%\codex_run.pid"
popd
endlocal
