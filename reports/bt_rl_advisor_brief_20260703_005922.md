# AI Pilot Top Gun Challenge 2026 외부 조언 요청 브리프

작성일: 2026-07-03  
작성 목적: 현재 RL 정책과 Behavior Tree(BT) 상대의 교전 품질이 낮아, 전술 설계 및 학습/평가 방향에 대한 외부 조언을 요청하기 위함.

## 1. 프로젝트 개요

본 프로젝트는 F-16 단일기 1v1 근접 공중전(WVR dogfight)을 수행하는 AI 파일럿을 개발하는 과제입니다. 환경은 JSBSim 기반 비행역학 DLL을 사용하며, Python wrapper를 통해 강화학습 정책 또는 C++ Behavior Tree 정책을 각 기체에 연결할 수 있습니다.

주요 목표는 gun-only 교전에서 상대기를 추적하고, 유효 사격 영역(WEZ)에 진입 및 유지하여 상대를 격추하는 것입니다. 현재는 다음 두 계열의 에이전트를 다루고 있습니다.

- RL 에이전트: PPO 기반 학습 정책. lightweight bundle 형태로 저장되어 있으며 대표 후보는 `ic_s3_bt_v1`입니다.
- BT 에이전트: C++ DLL(`AIP_BASE_target.dll`)로 빌드되는 룰 기반 정책. XML(`Rule_forTraining.xml`)로 행동 트리를 구성합니다.

## 2. 현재 사용 중인 환경과 평가 방식

로컬 교전 스크립트는 `run_local_dogfight.py`이며, 원래 의도는 다음과 같습니다.

```powershell
python run_local_dogfight.py `
  --ownship-backend rl `
  --ownship-bundle-dir artifacts\models\team01\ic_s3_bt_v1 `
  --target-backend bt `
  --target-bt-dll AIP_BASE_target.dll `
  --observation-mode custom `
  --observation-module student.my_observation `
  --save-log
```

다만 현재 Codex 작업 환경에서는 RLlib Algorithm 전체 복원이 매우 오래 걸려 정식 실행이 실용적으로 막혔습니다. 그래서 최근 확인은 lightweight bundle의 MLP weight를 직접 계산하는 fast inference 경로로 수행했습니다. 이 fast 경로는 JSBSim 환경과 BT DLL은 실제로 사용하지만, RLlib의 모든 추론 wrapper를 완전히 재현한 정식 평가는 아닙니다.

## 3. 현재 관찰된 핵심 문제

3D 리플레이와 로그를 보면, RL과 BT가 서로 적극적으로 교전하지 못하고 큰 원을 그리며 빙빙 돌다가 제한시간 종료로 끝나는 현상이 나타납니다.

최근 fast 교전 결과:

- 시나리오: `ic_s3_bt_v1` RL 후보 vs 새 BT
- 결과: `max time out`
- ownship health: `1.0`
- target health: `1.0`
- 최소 거리: 약 `1088m`
- 해석: 양쪽 모두 격추되지 않았고, 상대를 WEZ 안에 안정적으로 넣지 못했습니다.

이전 관찰에서는 RL이 BT의 뒤쪽에 붙었을 때 BT가 제대로 회피하지 못하고 맞는 경향도 있었습니다. 이를 보완하기 위해 후방 위협 회피 분기를 추가했더니 “그냥 맞고만 있는” 문제는 줄었으나, 그 결과 교전이 더 소극적인 원형 선회/타임아웃으로 흐르는 듯합니다.

## 4. 현재 BT 구조 요약

기존 BT는 거의 비어 있던 상태였고, 최근 다음 전술 task/decorator를 추가했습니다.

주요 task:

- `Task_LeadPursuit`: 목표 선도 추적
- `Task_LagPursuit`: 과도한 closure를 줄이는 lag pursuit
- `Task_Extend`: 너무 가까울 때 이탈/거리 벌리기
- `Task_DefensiveBreak`: 근접/정면 위협에서 break turn
- `Task_ClimbRecover`: 저고도 회복
- `Task_RearThreatJink`: 뒤쪽에서 상대가 조준 중일 때 좌우/수직 jink

현재 BT 우선순위 개략:

1. 저고도면 상승 회복
2. 후방 근접 위협이면 jink
3. 근접 정면 위협이면 break
4. 너무 가까우면 extend
5. 사격권에 가까우면 lead pursuit
6. 근거리면 lag pursuit
7. 기본 lead pursuit

후방 위협 회피 조건은 대략 다음과 같습니다.

- 거리 `< 3200m`
- 내 LOS 기준 상대가 후방 영역
- 상대 LOS 기준 상대가 나를 조준 중
- 실행 행동: 좌우를 시간 기반으로 번갈아 꺾고, 고도 여유에 따라 수직 성분을 섞는 jink

후방 위협 smoke test에서는 새 분기가 정상 작동했습니다. 예를 들어 상대가 6시 방향 1500m 부근에 있을 때 VP가 측방으로 크게 튀고 roll/rudder command가 강하게 발생했습니다.

## 5. 현재 의심하는 원인

현재 문제는 단순히 “회피가 없어서 맞는다”에서 “회피/추적 전환 로직이 교전을 끝내지 못한다”로 바뀐 상태입니다. 가능한 원인은 다음과 같습니다.

1. BT의 방어 분기가 너무 넓거나 오래 유지되어, 공격 재진입 조건이 약할 수 있습니다.
2. `LeadPursuit`와 `LagPursuit`의 VP 설정이 상대를 실제 gun WEZ에 넣기보다 큰 원형 선회를 유도할 수 있습니다.
3. `Extend`/`Jink` 이후 재공격을 위한 “reset 후 재진입” 상태 또는 타이밍이 없습니다.
4. RL 정책 `ic_s3_bt_v1`도 특정 offensive saddle 학습 분포에 과적합되어, 방어적으로 움직이는 BT를 상대로는 각을 만들지 못할 수 있습니다.
5. BT가 고도/에너지 관리를 독립적으로 하지 않고 VP 기반 기하만 사용해서, 수평 선회 교착에 빠지는 듯합니다.
6. 현재 BT는 상태 메모리 없이 매 tick Fallback을 재평가하므로, 전술 maneuver가 충분한 지속시간을 갖지 못하고 흔들릴 수 있습니다.

## 6. 조언받고 싶은 질문

1. BT 방어기동은 “후방 위협 감지 즉시 jink”보다 어떤 구조가 더 적절할까요? 예: break turn, barrel roll, high/low yo-yo, scissors 유도, unload extension 등.
2. BT가 회피 후 다시 공격으로 전환하기 위한 상태 machine 또는 timer/hysteresis를 어떻게 설계하는 것이 좋을까요?
3. 현재처럼 VP를 하나 찍는 방식에서, gun-only dogfight에 필요한 pursuit guidance를 어떻게 개선해야 할까요?
4. RL이 뒤에 붙어도 격추하지 못하고 원형 선회를 하는 문제는 reward/observation/초기조건 중 어디를 먼저 의심해야 할까요?
5. `ic_s3_bt_v1`가 offensive saddle 학습에는 강하지만 방어적 BT 상대로 타임아웃이 나는 경우, 평가/재학습 커리큘럼을 어떻게 구성하는 것이 좋을까요?
6. BT 상대를 “맞고만 있는 타겟”이 아니라 학습에 도움이 되는 sparring partner로 만들려면, 어떤 난이도 단계가 적절할까요?
7. 단기적으로는 대회 제출 전 검증 가능한 개선이 필요합니다. BT를 더 공격적으로 만들어 RL 학습용 상대 품질을 높이는 것이 우선일지, 아니면 RL 정책을 방어적/교착 상황 커리큘럼으로 재학습하는 것이 우선일지 조언이 필요합니다.
8. 향후 계층적 강화학습(HRL)을 적용하고 싶습니다. 이 dogfight 문제에서 상위 정책과 하위 정책을 어떻게 나누는 것이 좋을지 조언이 필요합니다.

## 7. HRL 적용 아이디어와 질문

장기적으로는 단일 continuous-action PPO가 모든 것을 직접 해결하기보다, 계층적 구조를 적용하고 싶습니다. 현재 관찰되는 문제도 “조종 입력을 못 내는 것”보다는 “언제 추적하고, 언제 이탈하고, 언제 재공격해야 하는지”의 전술 상태 전환이 약한 문제로 보입니다.

검토 중인 HRL 구조 예시는 다음과 같습니다.

- 상위 정책(high-level policy): 전술 모드 선택
  - 예: `pursuit`, `lag`, `extend`, `jink`, `break`, `climb recover`, `re-commit`, `energy reset`
- 하위 정책(low-level policy): 선택된 전술 모드에 맞는 조종 입력 또는 VP 추종
  - 예: roll/pitch/rudder/throttle 직접 제어, 또는 BT primitive가 찍은 VP를 따라가는 controller
- 옵션 지속시간(option duration): 상위 정책이 매 tick 바뀌지 않도록 1~5초 정도의 commitment 또는 termination condition 사용
- termination condition:
  - 사격각 확보
  - 상대가 후방 위협에서 벗어남
  - 거리/고도/에너지 조건 회복
  - 너무 멀어짐 또는 교착 지속

HRL 관련 조언 요청 질문:

1. 이 WVR gun-only dogfight 문제에서 상위 option을 어떤 전술 단위로 정의하는 것이 적절할까요?
2. 하위 정책은 직접 조종 입력을 학습하는 것이 좋을까요, 아니면 BT/기하 기반 primitive가 만든 VP를 추종하게 하는 것이 좋을까요?
3. 현재 BT primitive들을 HRL option으로 재사용한다면, 어떤 primitive부터 유지/수정/폐기하는 것이 좋을까요?
4. option duration과 termination condition은 어떤 신호를 기준으로 설계하는 것이 좋을까요? 예: LOS, aspect angle, closure, range, energy, WEZ flag 등.
5. HRL 학습은 offline imitation/behavior cloning으로 시작하는 것이 좋을까요, 아니면 rule option을 고정하고 상위 selector만 먼저 RL로 학습하는 것이 좋을까요?
6. 현재처럼 교착 선회가 자주 발생하는 경우, HRL의 상위 reward에는 어떤 항목을 넣어야 “재공격/각도 창출”을 유도할 수 있을까요?
7. 대회 일정상 단기 구현이 필요하다면, 완전한 HRL보다 “BT option selector + RL low-level residual” 같은 hybrid 접근이 현실적인지 조언이 필요합니다.

## 8. 참고 파일

BT 관련:

- `AIP_LIB/AIP_DCS/BehaviorTree/BT_Content/Task/TacticalTasks.cpp`
- `AIP_LIB/AIP_DCS/BehaviorTree/BT_Content/Task/TacticalTasks.h`
- `AIP_LIB/Rule.xml`
- `AIP_LIB/DogFightEnv/Release_260529/Rule_forTraining.xml`
- `AIP_LIB/DogFightEnv/Release_260529/AIP_BASE_target.dll`

RL 후보:

- `AIP_LIB/DogFightEnv/Release_260529/artifacts/models/team01/ic_s3_bt_v1`

최근 생성된 fast 교전 로그:

- `AIP_LIB/DogFightEnv/Release_260529/artifacts/logs/2026_7_3_0_55_25_ownship_(F-16)[Blue].csv`
- `AIP_LIB/DogFightEnv/Release_260529/artifacts/logs/2026_7_3_0_55_25_target_(F-16)[Red].csv`
- `AIP_LIB/DogFightEnv/Release_260529/artifacts/logs/2026_7_3_0_55_25_summary.json`

3D 리플레이:

- `bt_vs_best_3d_viewer.html`
- `bt_vs_best_replay_data.js`

## 9. 현재 결론

후방 위협 회피기동 추가로 BT 생존성은 올라간 듯하지만, 양쪽이 적극적으로 WEZ를 만들지 못하고 원형 교착에 빠지는 문제가 남아 있습니다. 지금 필요한 조언은 단순 파라미터 튜닝보다, “BT의 전술 상태 전환 구조”와 “RL 재학습/평가 커리큘럼” 양쪽에 대한 방향성입니다.
