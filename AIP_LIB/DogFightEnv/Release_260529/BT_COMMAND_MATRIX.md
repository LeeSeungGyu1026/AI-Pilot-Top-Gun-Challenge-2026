# Final BT Usage Guide

Release base:

```bat
cd C:\Users\biobe\desktop\aip\AI-Pilot-Top-Gun-Challenge-2026\AIP_LIB\DogFightEnv\Release_260529
```

This guide keeps only the final supported BT set:

| Name | Motion | DLL | XML |
|---|---|---|---|
| `default_combat` | Actual combat BT | `AIP_BASE_target.dll` | `..\..\Rule_default.xml` |
| `straight` | Fly straight | `AIP_BASE_target_circle_debug.dll` | `..\..\Rule_Straight.xml` |
| `circle_horizontal` | Horizontal circle | `AIP_BASE_target_circle_debug.dll` | `..\..\Rule_Circle_Horizontal.xml` |
| `circle_vertical` | Vertical loop/circle | `AIP_BASE_target_circle_debug.dll` | `..\..\Rule_Circle.xml` |

Do not use `Rule_Figure8.xml` as a final RL target yet. It is experimental and currently does not produce a reliable figure-8 motion.

Important:

```text
Only one Rule XML is active at a time.
run_unreal_inference.py, run_local_dogfight.py, run_experiment.py, and train_rllib.py copy the selected XML into Rule_forTraining.xml / Rule.xml while running.
If both aircraft use BT in one run, both use the same active XML.
```

## 1. Verify Setup

Run this first after pulling changes, rebuilding DLLs, or changing XML files:

```bat
C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe -NoProfile -ExecutionPolicy Bypass -File "C:\Users\biobe\desktop\aip\AI-Pilot-Top-Gun-Challenge-2026\AIP_LIB\DogFightEnv\Release_260529\verify_env.ps1"
```

Validate the final custom BT set:

```bat
C:\Users\biobe\miniconda3\envs\aip\python.exe scripts\validate_custom_bt.py
```

Expected final line:

```text
ALL_CUSTOM_BT_OK: Rule_Straight.xml, Rule_Circle_Horizontal.xml, Rule_Circle.xml
```

Validate one custom BT:

```bat
C:\Users\biobe\miniconda3\envs\aip\python.exe scripts\validate_custom_bt.py --rule Rule_Circle.xml
```

## 2. Quick Replay Checks: BT vs BT

These commands run local JSBSim, save CSV replay logs, and are the best way to check motion before training.

### 2-1. Default Combat BT

```bat
C:\Users\biobe\miniconda3\envs\aip\python.exe run_local_dogfight.py --ownship-backend bt --ownship-bt-dll AIP_BASE_target.dll --target-backend bt --target-bt-dll AIP_BASE_target.dll --bt-rule-xml "..\..\Rule_default.xml" --max-engage-time 60 --episode-step-limit 3600 --save-log
```

### 2-2. Straight BT

```bat
C:\Users\biobe\miniconda3\envs\aip\python.exe run_local_dogfight.py --ownship-backend bt --ownship-bt-dll AIP_BASE_target_circle_debug.dll --target-backend bt --target-bt-dll AIP_BASE_target_circle_debug.dll --bt-rule-xml "..\..\Rule_Straight.xml" --max-engage-time 60 --episode-step-limit 3600 --save-log
```

### 2-3. Horizontal Circle BT

```bat
C:\Users\biobe\miniconda3\envs\aip\python.exe run_local_dogfight.py --ownship-backend bt --ownship-bt-dll AIP_BASE_target_circle_debug.dll --target-backend bt --target-bt-dll AIP_BASE_target_circle_debug.dll --bt-rule-xml "..\..\Rule_Circle_Horizontal.xml" --max-engage-time 60 --episode-step-limit 3600 --save-log
```

Latest checked result:

```text
Approx radius: 2.9 km
Survives 60 s
```

### 2-4. Vertical Circle BT

```bat
C:\Users\biobe\miniconda3\envs\aip\python.exe run_local_dogfight.py --ownship-backend bt --ownship-bt-dll AIP_BASE_target_circle_debug.dll --target-backend bt --target-bt-dll AIP_BASE_target_circle_debug.dll --bt-rule-xml "..\..\Rule_Circle.xml" --max-engage-time 60 --episode-step-limit 3600 --save-log
```

Latest checked result:

```text
Altitude span: about 3.7-3.8 km for Radius=1800
Survives 60 s
```

## 3. Viewer/Unreal Commands

Run these after `DogFightViewer.exe` is open and waiting.

### 3-1. Default Combat BT

```bat
C:\Users\biobe\miniconda3\envs\aip\python.exe run_unreal_inference.py --mode bt --bt-dll AIP_BASE_target.dll --bt-rule-xml "..\..\Rule_default.xml" --team-name team01 --server-ip 127.0.0.1 --server-port 9999 --packet-monitor --action-repeat 6 --ai-type rule
```

### 3-2. Straight BT

```bat
C:\Users\biobe\miniconda3\envs\aip\python.exe run_unreal_inference.py --mode bt --bt-dll AIP_BASE_target_circle_debug.dll --bt-rule-xml "..\..\Rule_Straight.xml" --team-name team01 --server-ip 127.0.0.1 --server-port 9999 --packet-monitor --action-repeat 6 --ai-type rule
```

### 3-3. Horizontal Circle BT

```bat
C:\Users\biobe\miniconda3\envs\aip\python.exe run_unreal_inference.py --mode bt --bt-dll AIP_BASE_target_circle_debug.dll --bt-rule-xml "..\..\Rule_Circle_Horizontal.xml" --team-name team01 --server-ip 127.0.0.1 --server-port 9999 --packet-monitor --action-repeat 6 --ai-type rule
```

### 3-4. Vertical Circle BT

```bat
C:\Users\biobe\miniconda3\envs\aip\python.exe run_unreal_inference.py --mode bt --bt-dll AIP_BASE_target_circle_debug.dll --bt-rule-xml "..\..\Rule_Circle.xml" --team-name team01 --server-ip 127.0.0.1 --server-port 9999 --packet-monitor --action-repeat 6 --ai-type rule
```

## 4. RL Training Against a BT Target

In `experiments\student_sac_mlp.yaml`, Blue is RL and Red is the BT target.

Set one of these XML/DLL pairs:

```yaml
env:
  target_mode: behavior_tree
  target_behavior_dll: AIP_BASE_target_circle_debug.dll
  bt_rule_xml: ..\..\Rule_Circle_Horizontal.xml
```

For vertical circle:

```yaml
env:
  target_mode: behavior_tree
  target_behavior_dll: AIP_BASE_target_circle_debug.dll
  bt_rule_xml: ..\..\Rule_Circle.xml
```

For straight:

```yaml
env:
  target_mode: behavior_tree
  target_behavior_dll: AIP_BASE_target_circle_debug.dll
  bt_rule_xml: ..\..\Rule_Straight.xml
```

For default combat:

```yaml
env:
  target_mode: behavior_tree
  target_behavior_dll: AIP_BASE_target.dll
  bt_rule_xml: ..\..\Rule_default.xml
```

Dry-run:

```bat
C:\Users\biobe\miniconda3\envs\aip\python.exe scripts\run_experiment.py experiments\student_sac_mlp.yaml --dry-run
```

Run:

```bat
C:\Users\biobe\miniconda3\envs\aip\python.exe scripts\run_experiment.py experiments\student_sac_mlp.yaml
```

## 5. Both Aircraft Use BT in run_experiment

Use this only for smoke/replay. It is not meaningful RL training because Blue is also BT-controlled.

```bat
C:\Users\biobe\miniconda3\envs\aip\python.exe scripts\run_experiment.py experiments\bt_vs_bt_circle_horizontal.yaml
```

The YAML must contain:

```yaml
env:
  target_mode: behavior_tree
  target_behavior_dll: AIP_BASE_target_circle_debug.dll
  bt_rule_xml: ..\..\Rule_Circle_Horizontal.xml

env_config:
  ownship_control_mode: behavior_tree
  ownship_behavior_dll: AIP_BASE_target_circle_debug.dll
  target_mode: behavior_tree
  target_behavior_dll: AIP_BASE_target_circle_debug.dll
```

To make both aircraft use another final BT, change only `bt_rule_xml` and, if using `default_combat`, change both DLL fields to `AIP_BASE_target.dll`.

## 6. Evaluate a Trained RL Bundle Against a BT

Replace `<bundle_dir>` with a real trained bundle folder.

```bat
C:\Users\biobe\miniconda3\envs\aip\python.exe scripts\run_eval.py --episodes 20 --eval-name rl_vs_circle_horizontal_bt --ownship-backend rl --ownship-bundle-dir "<bundle_dir>" --target-backend bt --target-bt-dll AIP_BASE_target_circle_debug.dll --bt-rule-xml "..\..\Rule_Circle_Horizontal.xml" --observation-mode tactical16 --max-engage-time 60 --episode-step-limit 3600 --experiment-yaml experiments\student_sac_mlp.yaml
```

Example bundle shape:

```text
artifacts\models\team01\<tag>\bundle_000050
```

## 7. Open Replay Dashboard

For local `run_local_dogfight.py --save-log` logs:

```bat
C:\Users\biobe\miniconda3\envs\aip\python.exe tools\dashboard.py --default-tab replay --logdir artifacts\logs --port 7860
```

Open:

```text
http://127.0.0.1:7860/?tab=replay
```

For `run_experiment.py` engagement logs:

```bat
C:\Users\biobe\miniconda3\envs\aip\python.exe tools\dashboard.py --default-tab replay --logdir artifacts\logs\test_mlp\sac_mlp_v1\engagement_replays --training-logdir artifacts\dashboard --port 7860
```

## 8. Rebuild Custom BT DLL After C++ Changes

Build:

```bat
C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe -Command "& 'C:\Program Files\Microsoft Visual Studio\2022\Community\MSBuild\Current\Bin\amd64\MSBuild.exe' 'C:\Users\biobe\desktop\aip\AI-Pilot-Top-Gun-Challenge-2026\AIP_LIB\AIP_DCS\AIP_DCS.sln' /t:Build /p:Configuration=Debug /p:Platform=x64"
```

Copy built DLL to the Release custom DLL name:

```bat
C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe -Command "Copy-Item -LiteralPath 'C:\Users\biobe\desktop\aip\AI-Pilot-Top-Gun-Challenge-2026\AIP_LIB\bin\debug.x64\AIP_DCS.dll' -Destination 'C:\Users\biobe\desktop\aip\AI-Pilot-Top-Gun-Challenge-2026\AIP_LIB\DogFightEnv\Release_260529\AIP_BASE_target_circle_debug.dll' -Force"
```
