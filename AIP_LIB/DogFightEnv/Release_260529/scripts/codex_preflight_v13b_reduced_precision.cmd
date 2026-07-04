@echo off
setlocal
cd /d "%~dp0\.."
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8

rem NumPy-only gates keep working even when Windows Smart App Control blocks torch DLLs.
"C:\Users\GYU\AppData\Local\miniconda3\envs\aip\python.exe" scripts\codex_pre_v12_diagnostics.py --eval-name codex_v13b_seed_bundle090_preflight_det_10_numpy_v1 --episodes 10 --ownship-bundle-dir artifacts\models\team01\codex_ic_s3_v12b_level_rear_randomized_300_v1\bundle_000090 --target-backend autopilot --observation-mode custom --observation-module student.my_observation --experiment-yaml experiments\codex_ic_s3_v13b_reduced_precision_rear_gunnery_v1.yaml --max-engage-time 90 --episode-step-limit 2700 --sample-stride 120 --numpy-inference
if errorlevel 1 exit /b %errorlevel%

"C:\Users\GYU\AppData\Local\miniconda3\envs\aip\python.exe" scripts\codex_pre_v12_diagnostics.py --eval-name codex_v13b_seed_bundle090_preflight_stoch_10_numpy_v1 --episodes 10 --ownship-bundle-dir artifacts\models\team01\codex_ic_s3_v12b_level_rear_randomized_300_v1\bundle_000090 --target-backend autopilot --observation-mode custom --observation-module student.my_observation --experiment-yaml experiments\codex_ic_s3_v13b_reduced_precision_rear_gunnery_v1.yaml --max-engage-time 90 --episode-step-limit 2700 --sample-stride 120 --numpy-inference --explore
