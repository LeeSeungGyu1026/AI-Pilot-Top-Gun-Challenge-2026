# AI Pilot Top Gun 현재 상황 및 다음 학습 설정 제안

작성일: 2026-07-04  
작성자: Codex  
범위: 2026-07-03 BT/RL 실험 라인부터 `ic_s3_bt_v11` 진행 중 지표까지

## 1. 한 줄 결론

현재 가장 좋은 다음 수는 `ic_s3_bt_v11`을 일단 60~80 iteration까지 더 보되, “승리”가 아니라 `explained_var`, crash 수렴, true-WEZ/damage 증가를 기준으로 판단하는 것이다. v11은 v10b의 전술 설계를 버린 실험이 아니라, PPO critic을 망가뜨린 보상 스케일만 1/20로 줄인 실험이다. 지금까지의 지표는 critic 회복에는 성공했고, 전술 성과는 아직 승리로 전환되지 않은 상태다.

## 2. 현재까지의 흐름

### 2.1 기존 강점: `ic_s3_bt_v1`

초기 BT 전환 실험인 `ic_s3_bt_v1`은 offensive saddle 조건에서 tail-10 기준 win rate 1.0, crash 0.0, WEZ steps 약 62, 최소거리 약 680 m를 기록했다. 다만 이후 분석상 이 성과는 “진짜 일반 dogfight 능력”이라기보다 가까운 후방 시작 조건과 BT의 특정 반응을 강하게 이용한 결과일 가능성이 컸다.

외부 조언자(Web GPT, 2026-07-03)의 핵심 권고도 이 지점에 맞춰져 있었다.

- `ic_s3_bt_v1`은 즉시 동결해서 fallback candidate로 보존한다.
- 더 학습하기 전에 trainer/submission parity, true 2도 cone, range/aspect/altitude/speed perturbation 검증을 먼저 한다.
- 관측/보상 구조를 크게 바꾸기보다, validation과 보수적 분포 확장에 집중한다.
- 넓히는 학습은 기존 saddle 분포를 50% 이상 유지해 policy regression을 막는다.

### 2.2 BT self-destruct exploit 제거: v3~v5

좁은 offensive saddle에서는 BT가 거의 즉시 지면으로 떨어지는 forced-ground exploit이 나타났다. C++ BT hardening만으로는 해결되지 않았고, 실제 원인은 가까운 dead-six geometry 자체에 가까웠다. 그래서 `offensive_saddle.range_m`을 3600~4200 m로 넓힌 v5에서 forced-ground는 사실상 해결됐다.

v5 결과:

- forced-ground: 약 82%에서 0.21%로 감소
- own-crash: 초기 reseed 구간 이후 0 근처
- 하지만 win rate 0.0, timeout 대부분, WEZ 거의 없음
- 정책은 “안전하게 접근 후 교착”하는 plateau에 머물렀다.

### 2.3 공격성 강화: v6~v9b

v6/v7은 pursuit/damage 보상을 키워 교착을 깨려 했다. v7 중반에는 최소거리 115~290 m, damage 양수 구간이 나타나며 가장 공격적인 양상을 보였지만, 후반에는 다시 standoff로 회귀했다. 해석은 “가까이 가면 배울 기회는 생기지만, 아직 cone hold 능력이 부족해서 손해를 보고 물러난다”였다.

v9/v9b는 true 2도 kill cone은 유지하고, reward-only wide cone precision bonus를 도입했다. 그러나 보상이 너무 커서 wide-cone farming과 own-crash attractor가 재발했다.

v9b 실패 신호:

- reward_mean: 600~970까지 상승
- win rate: 계속 0.0
- true WEZ/damage: 거의 없음
- ownship altitude below min: 76.51%
- target destroyed: 0.00%

즉 “보상은 잘 받지만 실제 격추는 안 하는” 전형적인 shaping exploit이었다.

### 2.4 v10/v10b: 좋은 구조, 너무 큰 스케일

v10은 사용자가 보상 구조를 다시 설계했다.

- precision bonus: 90도 shaping cone 안에서 exponential 1(edge) -> 100(dead-on)
- altitude penalty: 600 m부터 300 m까지 exponential -1 -> -1000
- true kill cone: 2도 유지

이 구조는 v9b의 wide-cone farming과 forced-ground exploit을 줄이는 방향으로는 맞았다. 그러나 reward scale이 너무 커졌다. v10/v10b는 총 200 iteration가량 진행했지만 target destroyed는 0%, crash는 끝까지 noisy하게 흔들렸다.

v10b 최종 요약:

- ownship altitude below min: 57.19%
- max time out: 37.75%
- target altitude below min: 4.90%
- ownship destroyed: 0.16%
- target destroyed: 0.00%
- 드물게 true-WEZ/damage 신호는 나타났지만 지속되지 않았다.

핵심 의심점은 PPO value function scale 문제였다. 로컬 Ray/RLlib 2.54.0의 PPO 기본 `vf_clip_param=10.0`은 reward scale에 민감하다. v10처럼 return이 수천 단위로 튀면 critic update가 사실상 따라가지 못해 advantage가 noisy해질 수 있다.

### 2.5 v11: reward output scale 0.05

`ic_s3_bt_v11`은 v10b와 같은 전술 보상 구조를 유지하되, 최종 reward total에 `reward_output_scale=0.05`를 곱하는 단일 변수 실험이다. 즉 보상 비율과 최적 정책은 그대로 두고, value target magnitude만 PPO critic이 학습 가능한 범위로 낮춘다.

현재 최신 로그: `ic_s3_bt_v11`, iter 35, 589,824 sampled steps, 624 episodes.

최근 10 iteration 평균:

| 지표 | 값 |
|---|---:|
| reward_mean | 67.85 |
| win_rate | 0.000 |
| loss_rate | 0.0167 |
| timeout_rate | 0.925 |
| crash_rate | 0.000 |
| ep_wez_steps | 0.3125 |
| ep_min_distance | 42.0 m |
| ep_mean_distance | 2174 m |
| vf_loss | 0.556 |
| entropy | 4.66 |
| KL | 0.0108 |
| explained_var | 0.734 |

해석:

- 성공한 점: `explained_var`가 v10의 거의 0 수준에서 0.5~0.86대로 회복했다. critic scale fix 가설은 강하게 지지된다.
- 성공한 점: crash가 최근 구간에서 0이다. v10b의 noisy crash attractor는 일단 진정됐다.
- 아직 부족한 점: win은 0이고 timeout이 대부분이다.
- 이상 신호: 최소거리가 30~60 m로 너무 작다. true WEZ range 하한 152.4 m보다 안쪽으로 파고들어 overshoot/inside-min-range 문제가 있을 수 있다.
- 좋은 신호: `ep_reward_damage`가 작지만 양수로 튀는 row가 생겼고, WEZ step도 간헐적으로 0.3~0.6 수준까지 나온다.

## 3. 외부 조언자 의견을 현재 상황에 맞게 갱신

기존 외부 조언자의 권고는 “챔피언 동결, 검증 우선, 보수적 분포 확장”이었다. 지금 v11까지 본 뒤에는 이를 다음처럼 갱신하는 것이 맞다.

1. `ic_s3_bt_v1`은 계속 fallback으로 보존한다. 단, 제출 후보로 믿으려면 trainer/submission parity와 true-cone validation이 필요하다.
2. v11은 버릴 실험이 아니다. critic 회복이 너무 명확하므로 최소 60~80 iteration까지는 관찰할 가치가 있다.
3. v11이 60~80 iteration까지도 win 0이면, 보상 스케일 문제가 아니라 “근접 후 kill geometry 유지” 문제가 남은 것이다.
4. 다음 학습은 reward 구조를 또 크게 바꾸기보다, overshoot 방지와 true-WEZ 유지 시간을 직접 겨냥하는 작은 curriculum 조정이 낫다.
5. 완전한 cold-start/generalization으로 바로 넓히면 안 된다. 현재도 kill skill이 완성되지 않았으므로 먼저 wide saddle에서 “죽지 않고, 안쪽으로 지나치지 않고, 152~914 m range band에 머무르며 2도 cone을 맞추는” 능력을 만들어야 한다.

## 4. 다음 학습 설정 권장안

### 4.1 즉시 할 일: v11을 더 본다

권장:

- 현재 `ic_s3_bt_v11`을 최소 iter 60, 가능하면 iter 80까지 계속 관찰한다.
- iter 60에서 bundle이 저장되면, 그 시점에 짧은 evaluation을 별도로 돌린다.
- 판단 지표는 training reward가 아니라 아래 순서로 본다.

계속 학습 조건:

- `explained_var` tail-10 평균 >= 0.5
- crash_rate tail-10 평균 <= 0.05
- `ep_wez_steps` 또는 `ep_reward_damage`가 상승 추세
- KL이 0.02 아래에서 안정

중단 조건:

- crash_rate가 두 번의 10-iteration 구간 연속으로 0.15 이상
- `explained_var`가 다시 0.2 아래로 붕괴
- `ep_min_distance`가 50 m 안팎으로만 유지되고 WEZ/damage가 증가하지 않음
- reward_mean만 상승하고 win/damage/WEZ가 같이 오르지 않음

### 4.2 v11 이후 1순위 분기: `ic_s3_bt_v12_range_hold_v1`

목표는 “가까이 붙는 능력”이 아니라 “WEZ range band 안에서 overshoot하지 않고 cone을 유지하는 능력”이다.

추천 설정:

- seed: `ic_s3_bt_v11/bundle_000060` 또는 v11에서 `explained_var`, crash, WEZ/damage가 가장 좋은 bundle
- target: behavior_tree 유지
- true WEZ: 2도, 152.4~914.4 m 유지
- spawn range: 3600~4200 m 유지하되, 일부 쉬운 재접촉 구간을 섞는다.

초기조건 mixture:

| 비율 | 분포 | 목적 |
|---:|---|---|
| 50% | v11 그대로, range 3600~4200 m | 현재 넓은 BT 교전 유지 |
| 25% | mid-range offensive, 1800~2800 m | closure 시간을 줄여 학습 밀도 증가 |
| 15% | WEZ-entry prep, 950~1400 m, aspect 0~20도 | cone hold 직전 상태 반복 노출 |
| 10% | overshoot recovery, 500~900 m, aspect 10~45도 | 지나치게 파고든 뒤 재정렬 학습 |

보상은 크게 바꾸지 않는다. 바꾼다면 “새로운 큰 보상”이 아니라 아주 작은 anti-overshoot shaping만 고려한다.

가능한 작은 수정:

- true WEZ range 하한보다 안쪽, 예: range < 170 m에서 작은 penalty
- range 250~700 m에서 aspect/ATA 개선 보너스를 조금 더 선명하게
- penalty 규모는 v11 scale 이후 기준으로 episode 전체를 지배하지 않게 제한

주의: 지금 가장 위험한 실수는 다시 큰 per-step shaping을 넣는 것이다. v9b가 이미 그 길의 실패를 보여줬다.

### 4.3 2순위 분기: `ic_s3_bt_v12_eval_ladder_codex`

v11 또는 v12 후보가 조금이라도 나아지면 바로 학습을 더 하기보다 검증 ladder를 돌린다.

최소 검증:

| ID | 검증 | Episode | 목적 |
|---|---:|---:|---|
| V0 | trainer vs submission parity | 30 | wrapper mismatch 제거 |
| V1 | current v11/v12 training geometry | 50 | 학습 분포 성능 확인 |
| V2 | true 2도 cone only | 50 | hidden wide-cone 의존 제거 |
| V3 | range 1800/2400/3000/3600/4200 | 각 20 | range robustness |
| V4 | aspect 0/15/30/45도 | 각 20 | dead-six 과적합 확인 |
| V5 | altitude offset -300/0/+300 m | 각 20 | ground chase 확인 |
| V6 | speed offset -50/0/+50 m/s | 각 20 | overshoot/energy 문제 확인 |

통과 기준은 아직 “win rate 높음”보다 다음이 현실적이다.

- crash <= 0.05
- timeout이 줄어드는 추세
- true-WEZ step과 damage가 v11 baseline보다 증가
- range < 152 m overshoot 비율 감소
- trainer/submission 결과 차이 5%p 이내

## 5. 운영 계획: 다음 24시간

### Phase A: 현재 v11 마저 관찰

1. v11을 iter 60~80까지 진행한다.
2. iter 60 bundle을 기준으로 training_log tail-20을 집계한다.
3. `engagement_replays`에서 2~3개를 시각 확인한다.

확인 질문:

- target을 실제로 조준하려는가, 아니면 지나쳐서 원형 교착으로 가는가?
- range 152~914 m 안에 들어갔을 때 ATA가 줄어드는가?
- target과 ownship 중 누가 먼저 low-altitude 위험에 빠지는가?

### Phase B: 둘 중 하나 선택

v11이 iter 60~80에서 다음 중 하나라도 만족하면 v11을 계속한다.

- win이 한 번이라도 의미 있게 발생
- `ep_wez_steps` tail 평균이 1.0 이상
- `ep_reward_damage`가 안정적으로 양수
- overshoot가 줄고 min distance가 150~700 m 근처로 올라옴

반대로 v11이 계속 crash 0, win 0, min distance 30~60 m, timeout 대부분이면 v12로 분기한다.

### Phase C: v12는 curriculum 조정 중심

v12는 새 reward 철학 실험이 아니라, 같은 reward 아래서 학습 상태 분포를 바꾸는 실험이어야 한다. 핵심은 closure 시간이 긴 3600~4200 m만 계속 보여주지 말고, kill 직전의 상태를 더 자주 샘플링하는 것이다.

권장 이름:

- `ic_s3_bt_v12_range_hold_codex_v1`

단, 실제 실험 파일을 만들 때는 기존 프로젝트 네이밍과 충돌하지 않게 사용한다.

## 6. 가장 큰 리스크

1. overshoot attractor: 너무 가까이 들어가 true WEZ 최소거리 아래로 빠져버린다.
2. timeout plateau: crash는 사라졌지만 kill도 없이 오래 버틴다.
3. reward-only progress 착시: reward_mean은 오르지만 win/WEZ/damage가 안 오른다.
4. BT-specific exploit: 특정 BT 행동에만 맞춘다.
5. submission wrapper mismatch: action slew, observation ordering, deterministic inference가 훈련과 다르면 후보가 무너질 수 있다.
6. reward 스케일 재오염: 큰 보상 항을 다시 넣으면 v9b/v10 문제가 재발할 수 있다.

## 7. 최종 권고

지금 당장 새 reward를 크게 바꾸지 말고 `ic_s3_bt_v11`을 iter 60~80까지 더 본다. v11은 이미 critic 회복이라는 중요한 가설을 통과했다. 다만 win이 아직 없으므로 “좋은 모델”이 아니라 “학습이 다시 가능해진 모델”로 취급해야 한다.

다음 실험은 `v12_range_hold` 성격이 좋다. v11의 보상 스케일은 유지하고, 초기조건을 kill 직전 상태와 overshoot recovery 쪽으로 섞어 true-WEZ range band에서 머무르는 시간을 늘린다. 외부 조언자의 기존 원칙처럼 챔피언은 동결하고, 제출 후보 판단은 training reward가 아니라 validation matrix와 wrapper parity로 해야 한다.

실무적으로는 다음 순서가 가장 안전하다.

1. `ic_s3_bt_v11` iter 60 또는 80까지 진행
2. tail-20 지표와 리플레이 확인
3. 개선 신호가 있으면 v11 지속
4. 없으면 `ic_s3_bt_v12_range_hold_codex_v1` 분기
5. 후보가 생기면 바로 validation ladder
6. fallback으로 `ic_s3_bt_v1`은 계속 보존

