# run_experiment에서 커스텀 BT 적용하기

이 문서는 `Release_260529` 기준으로 `scripts\run_experiment.py`를 실행할 때 커스텀 Behavior Tree DLL/XML을 target 상대기로 적용하는 절차를 정리한 것이다.

## 핵심 구조

`scripts\run_experiment.py`는 experiment YAML을 읽어서 `train_rllib.py` 인자로 바꾼다.

YAML의 아래 항목들이 중요하다.

```yaml
env:
  target_mode: behavior_tree
  target_behavior_dll: AIP_BASE_target_circle_debug.dll
  bt_rule_xml: ..\..\Rule_Circle_Horizontal.xml
```

매핑은 다음처럼 된다.

```text
env.target_mode          -> --target-mode
env.target_behavior_dll  -> --target-behavior-dll
env.bt_rule_xml          -> --bt-rule-xml
```

`train_rllib.py`는 `--bt-rule-xml`로 받은 XML을 실행 중 `Rule_forTraining.xml`로 복사한다. 따라서 `Rule_forTraining.xml`을 직접 고치지 말고, 사용할 XML을 YAML의 `bt_rule_xml`로 지정한다.

## 기준 경로

```bat
cd C:\Users\biobe\desktop\aip\AI-Pilot-Top-Gun-Challenge-2026\AIP_LIB\DogFightEnv\Release_260529
```

권장 Python:

```bat
C:\Users\biobe\miniconda3\envs\aip\python.exe
```

## 1. 커스텀 BT 파일 준비

현재 커스텀 패턴용 DLL:

```text
AIP_BASE_target_circle_debug.dll
```

현재 커스텀 XML 예시:

```text
..\..\Rule_Straight.xml
..\..\Rule_Circle_Horizontal.xml
..\..\Rule_Circle.xml
..\..\Rule_Figure8.xml
```

주의:

```text
Rule_default.xml       -> AIP_BASE_target.dll 사용
커스텀 Pattern XML들   -> AIP_BASE_target_circle_debug.dll 사용
```

`AIP_BASE.dll`은 현재 `Rule_default.xml`의 `DECO_AltitudeCheck`를 모를 수 있으므로 기준 BT에도 쓰지 않는다.

## 2. YAML 수정

예: `experiments\student_sac_mlp.yaml`

```yaml
env:
  observation_mode: tactical16
  target_mode: behavior_tree
  target_behavior_dll: AIP_BASE_target_circle_debug.dll
  bt_rule_xml: ..\..\Rule_Circle_Horizontal.xml
  max_engage_time: 60.0
  episode_step_limit: 3600
```

다른 커스텀 BT로 바꾸려면 `bt_rule_xml`만 바꾼다.

```yaml
bt_rule_xml: ..\..\Rule_Straight.xml
```

```yaml
bt_rule_xml: ..\..\Rule_Circle.xml
```

```yaml
bt_rule_xml: ..\..\Rule_Figure8.xml
```

## 3. dry-run으로 인자 확인

학습을 시작하지 않고 `train_rllib.py`에 전달될 인자만 확인한다.

```bat
C:\Users\biobe\miniconda3\envs\aip\python.exe scripts\run_experiment.py experiments\student_sac_mlp.yaml --dry-run
```

출력에서 아래가 보여야 한다.

```text
--target-behavior-dll AIP_BASE_target_circle_debug.dll
--target-mode behavior_tree
--bt-rule-xml ..\..\Rule_Circle_Horizontal.xml
```

## 4. 오프라인 BT 생성 테스트

Viewer나 RL 학습을 켜기 전에 DLL/XML 조합이 파싱되는지 먼저 확인한다.

CMD에서는 한 줄로 실행한다.

```bat
set PYTHONPATH=%CD%\src;%CD%
C:\Users\biobe\miniconda3\envs\aip\python.exe -c "from pathlib import Path; from dogfight.ai.native_bt import AIPilot; from dogfight.ai.bt_rule_manager import activate_rule_xml; root=Path.cwd(); xml=root/'..'/'..'/'Rule_Circle_Horizontal.xml'; dll=root/'AIP_BASE_target_circle_debug.dll'; cm=activate_rule_xml(str(xml), root); cm.__enter__(); bt=AIPilot(str(dll)); bt.CreateBehaviorTree(0,1); print('BT CREATE OK'); cm.__exit__(None,None,None)"
```

정상 출력:

```text
Behavior Tree Initialized from ./Rule_forTraining.xml
BT CREATE OK
```

## 5. 실제 run_experiment 실행

## 5-1. Validate all custom BT rules before run_experiment

Run this before training when the BT DLL or custom XML files change.
It checks every custom rule in two phases:

1. `CreateBehaviorTree` must succeed.
2. A 60 second both-BT local JSBSim run must survive until `max time out`.

```bat
C:\Users\biobe\miniconda3\envs\aip\python.exe scripts\validate_custom_bt.py
```

Expected final line:

```text
ALL_CUSTOM_BT_OK: Rule_Straight.xml, Rule_Circle_Horizontal.xml, Rule_Circle.xml, Rule_Figure8.xml
```

To test only one XML:

```bat
C:\Users\biobe\miniconda3\envs\aip\python.exe scripts\validate_custom_bt.py --rule Rule_Circle_Horizontal.xml
```

## 5-2. Run both aircraft with the custom BT

Use this when you want to inspect the custom BT motion on both Blue and Red.
This is a replay/smoke run, not a meaningful RL training run.

```bat
C:\Users\biobe\miniconda3\envs\aip\python.exe scripts\run_experiment.py experiments\bt_vs_bt_circle_horizontal.yaml
```

Important: `run_experiment.py --dry-run` will show only the target BT CLI flags.
Blue BT is enabled through `env_config` in the YAML:

```yaml
env_config:
  ownship_control_mode: behavior_tree
  ownship_behavior_dll: AIP_BASE_target_circle_debug.dll
```

```bat
C:\Users\biobe\miniconda3\envs\aip\python.exe scripts\run_experiment.py experiments\student_sac_mlp.yaml
```

실험 로그/모델은 YAML의 `output.name`, `output.tag`, `dashboard.logdir` 설정을 따른다.

## 6. 저장된 다시보기 보기

다시보기는 YAML에서 `engagement_log.enabled: true`일 때 저장된다.

```yaml
engagement_log:
  enabled: true
  interval: 1
  steps: 600
  episodes: 1
  print: true
```

저장 위치는 보통 아래 형식이다.

```text
artifacts\logs\<output.name>\<output.tag>\engagement_replays
```

예를 들어 현재 `student_sac_mlp.yaml` 기준:

```yaml
output:
  name: test_mlp
  tag: sac_mlp_v1
```

다시보기 위치:

```text
artifacts\logs\test_mlp\sac_mlp_v1\engagement_replays
```

대시보드 Replay 탭으로 바로 열기:

```bat
C:\Users\biobe\miniconda3\envs\aip\python.exe tools\dashboard.py --default-tab replay --logdir artifacts\logs\test_mlp\sac_mlp_v1\engagement_replays --training-logdir artifacts\dashboard --port 7860
```

브라우저에서 접속:

```text
http://127.0.0.1:7860/?tab=replay
```

통합 대시보드에서 학습 그래프와 replay를 같이 볼 때:

```bat
C:\Users\biobe\miniconda3\envs\aip\python.exe tools\dashboard.py --training-logdir artifacts\dashboard --logdir artifacts\logs --port 7860
```

기존 replay 전용 호환 실행기:

```bat
C:\Users\biobe\miniconda3\envs\aip\python.exe tools\web_log_viewer.py --port 7870
```

브라우저:

```text
http://127.0.0.1:7870/?tab=replay
```

주의:

```text
engagement_log.enabled가 false이면 engagement_replays 폴더가 생기지 않는다.
interval이 10이면 10번째 iteration 전에는 replay가 생기지 않는다.
빠르게 확인하려면 interval: 1로 둔다.
iteration 하나가 끝나기 전에 학습을 끄면 replay가 아직 없을 수 있다.
학습 중 replay 저장은 추가 에피소드를 짧게 실행하므로 약간 느려질 수 있다.
```

## 7. 안전한 실험 복사본 만들기

기존 YAML을 직접 계속 바꾸기보다 복사해서 새 실험으로 만든다.

```bat
copy experiments\student_sac_mlp.yaml experiments\student_sac_mlp_circle_horizontal.yaml
```

복사본에서 최소한 아래를 바꾼다.

```yaml
name: student_sac_mlp_circle_horizontal

output:
  name: test_mlp
  tag: sac_mlp_circle_horizontal_v1

env:
  target_mode: behavior_tree
  target_behavior_dll: AIP_BASE_target_circle_debug.dll
  bt_rule_xml: ..\..\Rule_Circle_Horizontal.xml
```

실행:

```bat
C:\Users\biobe\miniconda3\envs\aip\python.exe scripts\run_experiment.py experiments\student_sac_mlp_circle_horizontal.yaml --dry-run
C:\Users\biobe\miniconda3\envs\aip\python.exe scripts\run_experiment.py experiments\student_sac_mlp_circle_horizontal.yaml
```

## 8. 빠른 문제 진단

`Node not recognized`

```text
XML에 있는 노드를 DLL이 모른다는 뜻이다.
Rule_default.xml은 AIP_BASE_target.dll을 쓰고,
Pattern/Radius/Speed를 쓰는 커스텀 XML은 AIP_BASE_target_circle_debug.dll을 쓴다.
```

`CreateBehaviorTree failed ... 0xe06d7363`

```text
DLL 내부 C++ 예외다.
대부분 XML 노드/포트와 DLL 빌드가 맞지 않거나, Rule_forTraining.xml이 의도와 다르게 덮인 경우다.
오프라인 BT 생성 테스트부터 다시 한다.
```

dry-run에는 맞게 나오는데 학습에서 다른 BT가 도는 경우:

```text
동시에 여러 실험/테스트가 Rule_forTraining.xml을 건드리지 않는지 확인한다.
run_experiment/train_rllib/run_unreal_inference는 모두 Rule_forTraining.xml을 활성 XML로 사용한다.
한 번에 하나만 실행하는 것이 안전하다.
```
