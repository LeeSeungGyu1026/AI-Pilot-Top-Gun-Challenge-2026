# AI Pilot Top Gun win_rate 개선을 위한 외부 조언 요청서

작성일: 2026-07-04  
작성 목적: 현재 RL vs Behavior Tree(BT) 학습 상황을 외부 조언자에게 공유하고, `win_rate`를 실제 `target destroyed`로 끌어올리기 위한 다음 학습 설정 조언을 받기 위함.

## 1. 한 줄 요약

현재 가장 중요한 문제는 **학습 안정성은 회복됐지만 실제 격추로 이어지지 않는다**는 점입니다. 최신 `ic_s3_bt_v11`은 PPO critic 붕괴를 해결해 `explained_var`가 회복됐고 crash도 줄었지만, `target destroyed` 기준 win은 아직 0%입니다. 기체가 너무 가까이 붙어 true WEZ 최소거리 안쪽으로 overshoot하거나, 오래 버티다 timeout으로 끝나는 패턴이 남아 있습니다.

## 2. 프로젝트와 목표

- 과제: F-16 1v1 WVR gun-only dogfight AI 개발
- 환경: JSBSim 기반 비행역학 + Python RL wrapper + C++ Behavior Tree 상대
- 현재 주력 알고리즘: RLlib PPO, custom 26-D observation, custom reward
- 성공 기준: 단순 `target altitude below min` 유도 또는 timeout이 아니라, **damage로 target HP를 0까지 깎는 실제 `target destroyed` 증가**
- 현재 상대: `AIP_BASE_target.dll` BT
- 최신 실험: `ic_s3_bt_v11`

## 3. 지금까지의 주요 흐름

### 3.1 초기 성공과 과적합 위험

`ic_s3_bt_v1`은 특정 offensive saddle 조건에서 BT 상대로 높은 win을 보였지만, 이후 분석상 이 성과는 일반 dogfight 능력이라기보다 **가까운 dead-six 시작 조건과 BT의 취약 반응을 강하게 이용한 결과**일 가능성이 컸습니다. 외부 조언자는 당시 `ic_s3_bt_v1`을 frozen fallback candidate로 보존하고, trainer/submission parity와 true 2-degree cone 검증을 먼저 하라고 권고했습니다.

### 3.2 forced-ground exploit 제거

초기 spawn이 너무 가까운 탓에 BT가 거의 즉시 지면으로 꽂히는 `target altitude below min` exploit이 있었습니다. C++ BT hardening만으로는 충분하지 않았고, 실제 원인은 가까운 offensive saddle geometry 자체였습니다. `offensive_saddle.range_m`을 3600~4200m로 넓히면서 forced-ground는 크게 줄었습니다.

대표 변화:

- v3/v4: forced-ground 약 81~82%, real kill 0%
- v5: forced-ground 0.21%까지 감소
- 그러나 v5는 timeout plateau로 이동했고, win은 계속 0%

### 3.3 공격성 강화 시도와 부작용

v6~v9 계열에서는 pursuit/damage/WEZ shaping을 키워 공격성을 끌어올리려 했습니다.

- v7 중반: 최소거리 115~290m, damage 신호가 양수로 나타나며 가장 공격적인 구간이 생김
- 그러나 후반에는 다시 570~850m standoff로 후퇴
- v9b: reward-only wide cone bonus가 너무 커져 reward는 크게 올랐지만 실제 WEZ/damage 없이 근접/rough aim을 farming했고, own-crash가 76.51%로 재발

결론: **공격 보상을 크게 주면 붙기는 하지만, 실제 2-degree cone을 유지하지 못하고 crash 또는 overshoot/farming으로 무너진다.**

### 3.4 v10/v10b: reward 형태는 좋아졌지만 scale이 PPO critic을 망가뜨림

v10은 두 exploit을 동시에 막으려 했습니다.

- precision bonus: 90도 shaping cone 안에서 exponential, dead-on aim에 보상 집중
- altitude penalty: 600m부터 300m까지 exponential, 300m 근처에서 매우 큰 패널티
- true WEZ는 2도, 152.4~914.4m 유지

하지만 reward scale이 너무 커져 PPO value function이 학습하지 못했습니다. 로컬 Ray/RLlib 2.54.0의 PPO 기본 `vf_clip_param=10.0`은 reward scale에 민감하고, v10 계열 return은 수천 단위까지 커졌습니다. v10의 `explained_var`는 거의 0에 머물렀고 crash가 끝까지 noisy하게 진동했습니다.

v10b 최종:

- `target destroyed`: 0.00%
- `target altitude below min`: 4.90%
- `ownship altitude below min`: 57.19%
- `max time out`: 37.75%
- 의미 있는 true-WEZ/damage 신호는 매우 드물게만 발생

### 3.5 v11: reward_output_scale=0.05로 critic 회복

v11은 v10b와 같은 reward 구조를 유지하되, 모든 reward component와 total에 uniform scale 0.05를 곱했습니다. 보상 비율과 최적 정책은 유지하고 value target magnitude만 줄이는 목적입니다.

현재 최신 CSV 기준: `ic_s3_bt_v11`, iter 41, sampled_steps 688,128, episodes 682.

최근 10 iteration 평균:

| 지표 | 값 |
|---|---:|
| reward_mean | 67.8189 |
| win_rate | 0.0000 |
| loss_rate | 0.0000 |
| timeout_rate | 0.8542 |
| crash_rate | 0.0917 |
| ep_wez_steps | 0.3333 |
| ep_min_distance | 45.2420 m |
| ep_mean_distance | 2153.2653 m |
| ep_reward_damage | 0.0186 |
| vf_loss | 0.6549 |
| entropy | 4.8237 |
| KL | 0.0109 |
| explained_var | 0.7115 |

iter 41 단일 행:

- reward_mean: 62.38
- win_rate: 0.0
- timeout_rate: 0.625
- crash_rate: 0.1667
- `ep_wez_steps`: 1.125
- `ep_min_distance`: 37.8m
- `ep_reward_damage`: 0.058
- `explained_var`: 0.875

해석:

- 좋은 점: critic 회복은 확실합니다. `explained_var`가 0.7~0.9 수준으로 올라왔고, v10의 scale 문제는 거의 해결된 것으로 보입니다.
- 좋은 점: v9b/v10b처럼 crash가 완전히 지배하지는 않고, true WEZ와 damage 신호가 간헐적으로 생겼습니다.
- 문제점: win은 아직 0입니다.
- 문제점: `ep_min_distance`가 30~70m 수준으로 너무 작습니다. true WEZ 최소거리 152.4m보다 안쪽으로 지나치게 파고드는 overshoot/inside-min-range 문제가 의심됩니다.
- 문제점: 평균거리는 여전히 2km대라, episode 전체로 보면 접근-이탈-재접근 또는 긴 timeout 구조가 남아 있을 수 있습니다.

## 4. 현재 병목 가설

1. **range-band 유지 실패**
   - target을 향해 붙는 능력은 생겼지만, 152~914m true WEZ band 안에 머무르지 못하고 152m 안쪽으로 빨려 들어갑니다.
   - `ep_min_distance`가 너무 낮아 real gun solution을 만들 시간보다 overshoot가 먼저 오는 것으로 보입니다.

2. **2-degree cone hold가 아직 안 됨**
   - reward-only shaping cone 안으로 접근하거나 rough aim을 만들 수는 있지만, 실제 damage가 나는 2도 cone을 안정적으로 유지하지 못합니다.

3. **close-range risk가 아직 음수**
   - 가까이 붙으면 BT가 더 안정적으로 쏘거나, ownship이 자세/고도/에너지 관리를 잃습니다.
   - PPO는 crash를 줄이며 안정화됐지만, kill을 위해 더 오래 머무르는 행동은 아직 배우지 못했습니다.

4. **initial-condition curriculum이 너무 먼 거리 위주**
   - 3600~4200m spawn은 forced-ground exploit을 막는 데 효과적이었지만, 매 episode 대부분을 closure에 쓰게 만들 수 있습니다.
   - kill 직전 상태를 충분히 자주 샘플링하지 못해 cone hold와 range hold 학습 밀도가 낮을 수 있습니다.

5. **BT 상대가 학습 파트너로는 너무 불연속적일 수 있음**
   - BT가 특정 threat gate에서 급격히 회피/급강하/이탈하며, RL이 안정적인 gunnery manifold를 배우기 전에 engagement가 깨질 수 있습니다.

## 5. 다음 학습 설정에 대한 현재 내부 제안

### 5.1 먼저 v11을 조금 더 관찰

v11은 scale fix 효과가 명확하므로 즉시 버리기보다 iter 60~80까지는 관찰할 가치가 있습니다.

계속 볼 조건:

- tail-10 `explained_var >= 0.5`
- tail-10 `crash_rate <= 0.10~0.15`
- `ep_wez_steps` 또는 `ep_reward_damage` 상승
- KL이 0.02 아래에서 안정

중단/분기 조건:

- win이 계속 0이고 `ep_min_distance`가 50m 안팎으로만 유지됨
- `ep_wez_steps`와 damage가 늘지 않음
- timeout이 대부분이고 range-band 체류가 늘지 않음

### 5.2 1순위 분기: `ic_s3_bt_v12_range_hold_codex_v1`

목표: 더 세게 붙는 정책이 아니라, **true WEZ range band 안에서 overshoot하지 않고 2-degree cone을 유지하는 정책**을 학습.

seed:

- v11의 iter 60 또는 iter 80 bundle 중 `explained_var`, crash, WEZ/damage가 가장 좋은 checkpoint

초기조건 mixture 제안:

| 비율 | 분포 | 목적 |
|---:|---|---|
| 45% | 기존 3600~4200m offensive saddle | 현재 BT 교전 분포 유지 |
| 25% | 1800~2800m mid-range offensive | closure 시간을 줄이고 contact 빈도 증가 |
| 20% | 950~1400m WEZ-entry prep, aspect 0~20도 | cone hold 직전 상태 반복 노출 |
| 10% | 500~900m overshoot recovery, aspect 10~45도 | 너무 붙었을 때 range를 다시 벌리는 기술 학습 |

reward는 크게 바꾸지 않고, 아주 작은 anti-overshoot 항만 고려:

- range < 150m 또는 range < 170m에서 작은 penalty
- 250~700m에서 aspect/ATA 개선 보너스 약간 강화
- 단, v9b처럼 per-step shaping이 episode 전체를 지배하지 않도록 scale은 v11 기준으로 작게 유지

### 5.3 2순위 분기: target curriculum 완화

BT가 너무 불연속적이면, target mix를 넣어 gunnery skill을 먼저 만들 수 있습니다.

예시:

| 비율 | target |
|---:|---|
| 50% | 현재 BT |
| 20% | gentle weave |
| 15% | level/autopilot target |
| 10% | climbing/diving but safety-bounded target |
| 5% | 쉬운 이전 target |

목표는 BT를 이기는 exploit이 아니라, cone hold와 range hold의 기초를 먼저 안정화하는 것입니다.

### 5.4 검증 ladder

후보가 생기면 training reward가 아니라 아래 기준으로 평가해야 합니다.

- trainer vs submission parity
- true 2-degree cone only
- range sweep: 900, 1300, 1800, 2400, 3600, 4200m
- aspect sweep: 0, 15, 30, 45, 60도
- altitude offset: -300, 0, +300m
- speed offset: -50, 0, +50m/s
- end-condition breakdown: `target destroyed`, `target altitude below min`, `ownship altitude below min`, `ownship destroyed`, `max time out`
- overshoot metric: range < 152.4m 비율, time-in-band 152.4~914.4m

## 6. 외부 조언자에게 묻고 싶은 질문

1. v11처럼 critic은 회복됐지만 win이 0인 상황에서, 다음 병목을 **range-band 유지**, **2-degree cone hold**, **BT 난이도**, **reward 구조** 중 무엇으로 우선 진단해야 할까요?

2. `ep_min_distance`가 true WEZ 최소거리 152.4m보다 훨씬 작은 30~70m로 반복되는 경우, anti-overshoot를 reward로 넣는 것이 좋을까요, 아니면 초기조건 curriculum으로 500~900m recovery 상황을 더 자주 보여주는 것이 좋을까요?

3. reward-only wide cone shaping은 v9b에서 farming/crash를 만들었습니다. v11의 exponential precision shaping은 유지하되, true cone hold를 늘리려면 어떤 형태의 dense signal이 가장 안전할까요?

4. 3600~4200m spawn은 exploit을 막았지만 학습 밀도를 낮춥니다. 위 mixture처럼 950~1400m, 500~900m 구간을 섞는 것이 적절할까요? 비율을 어떻게 잡는 것이 좋을까요?

5. 현재 BT를 계속 상대시키는 것이 맞을까요, 아니면 level/weave/easier target을 섞어서 먼저 gunnery skill을 안정화한 뒤 BT 비중을 다시 늘리는 것이 좋을까요?

6. PPO 설정 측면에서 reward scale fix 외에 조정할 만한 것은 무엇일까요? 예: lower LR, smaller clip, longer rollout, curriculum stage별 iteration, vf_clip_param을 직접 노출하도록 train script 수정 등.

7. win_rate 자체가 희소하므로, 다음 run의 keep/kill 기준을 무엇으로 잡는 것이 합리적일까요? 예: time-in-WEZ-band, range <152m overshoot rate, first-WEZ time, ep_reward_damage, crash_rate, true target HP 감소량.

8. 최종 제출 관점에서 pure RL만 고집해야 할까요, 아니면 altitude/NaN/action smoothing 같은 최소 safety wrapper를 허용하고, pursuit/gunnery는 RL이 맡게 하는 hybrid wrapper가 더 현실적일까요?

## 7. 조언자가 바로 답해주면 좋은 형태

아래 형식으로 답변을 요청합니다.

1. 현재 병목 우선순위 1~3위
2. 다음 학습 run의 구체 YAML-level 변경안
3. reward를 바꿔야 한다면 바꿀 항목과 권장 scale
4. curriculum mixture 권장 비율
5. 20/40/60 iteration에서의 keep/kill 기준
6. win_rate가 오르기 전 선행지표로 무엇을 봐야 하는지
7. 최종 제출 후보를 고르는 validation matrix와 hard gate

## 8. 현재 내부 결론

지금은 reward를 크게 다시 설계하기보다, `ic_s3_bt_v11`을 iter 60~80까지 관찰한 뒤 **range hold / overshoot recovery curriculum**으로 분기하는 것이 가장 안전해 보입니다. v11은 학습이 다시 가능해졌다는 점에서 중요한 전환점이지만, win_rate를 올리려면 “붙기” 다음 단계인 “WEZ band 안에 머무르며 2-degree cone을 유지하기”를 직접 훈련해야 합니다.
