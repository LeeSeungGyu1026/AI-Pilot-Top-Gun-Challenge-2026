# v12/v12b 결과 분석 및 win_rate 개선 조언 요청

작성일: 2026-07-04  
대상 run:

- `codex_ic_s3_v12_level_rear_gunnery_v1`
- `codex_ic_s3_v12b_level_rear_randomized_300_v1`

프로젝트 기본 소개는 생략한다. 아래 내용만 보고 다음 학습 전략에 대해 조언해 달라.

## 1. 실험 의도

v11까지는 target을 충분히 죽이지 못했다. 그래서 v12에서는 과제를 좁혀, RL ownship을 level/autopilot target 후방에 스폰하고 `target destroyed`를 안정적으로 만들도록 학습시켰다.

v12b는 v12 `bundle_000080`에서 이어받아, rear-spawn geometry를 조금 더 랜덤화하고 300 iteration까지 길게 학습했다.

## 2. 설정 차이

### v12

- seed: `artifacts/models/team01/ic_s3_bt_v11/bundle_000080`
- target: autopilot/level
- spawn: target 후방 `550-750m`, aspect `0-8deg`
- target weave: off
- iterations: 80

### v12b

- seed: `artifacts/models/team01/codex_ic_s3_v12_level_rear_gunnery_v1/bundle_000080`
- target: autopilot/level
- spawn: target 후방 `500-850m`, aspect `0-14deg`
- target weave: on, amplitude `6deg`, period `180 steps`
- iterations: 300

## 3. 주요 결과

### v12

v12는 target kill이 나오기 시작했지만 win_rate는 낮았다.

- final iter 79: `win_rate=0.149`, `loss_rate=0.674`, `timeout_rate=0.177`
- best single iter: iter 68, `win_rate=0.185`
- best 10-iter rolling win_rate: 약 `0.097`

즉 v12는 “kill이 가능해졌다”는 의미가 있었지만, 안정적인 승률은 아니었다.

### v12b

v12b는 초중반에 크게 좋아졌다가 후반에 붕괴했다.

- best single iter: iter 104, `win_rate=0.749`
- best 10-iter window: iter 110-119 구간 평균 `win_rate=0.651`
- final iter 299: `win_rate=0.175`, `loss_rate=0.558`, `timeout_rate=0.267`
- latest saved final: `bundle_000300`
- strongest candidate bundle: `bundle_000110` 또는 `bundle_000120/000130`

10-iteration window 기준:

| iter window | avg win | avg loss | avg timeout | 해석 |
|---|---:|---:|---:|---|
| 80-89 | 0.406 | 0.009 | 0.585 | kill 능력 급상승 시작 |
| 90-99 | 0.516 | 0.032 | 0.453 | 안정화 중 |
| 100-109 | 0.639 | 0.018 | 0.343 | 매우 좋음 |
| 110-119 | 0.651 | 0.054 | 0.296 | 최고 구간 |
| 120-129 | 0.629 | 0.059 | 0.313 | 아직 좋음 |
| 150-159 | 0.503 | 0.179 | 0.318 | 하락 시작 |
| 190-199 | 0.377 | 0.370 | 0.253 | loss 증가 |
| 240-249 | 0.083 | 0.666 | 0.251 | 사실상 붕괴 |
| 290-299 | 0.076 | 0.612 | 0.312 | 최종 정책은 좋지 않음 |

## 4. 관찰된 이상 현상

1. 최종 checkpoint가 최고 성능이 아니다.  
   `bundle_000110~000130` 부근이 훨씬 좋고, `bundle_000300`은 win_rate가 낮다.

2. reward_mean은 항상 win_rate와 같이 움직이지 않는다.  
   예를 들어 iter 208은 `reward_mean=1883`으로 매우 높지만 `win_rate=0.233`이다. 이는 reward shaping이 kill 대신 긴 WEZ 유지, pursuit, timeout episode에서도 높은 reward를 줄 가능성을 시사한다.

3. 후반으로 갈수록 entropy가 다시 커지고 loss_rate가 증가했다.  
   초중반 좋은 구간의 entropy는 대략 2 전후였는데, 후반에는 7-8 수준까지 커졌다. PPO가 좋은 gunnery policy에서 벗어나 더 noisy한 정책으로 drift한 것일 수 있다.

4. KL spike가 있었다.  
   iter 250 부근 KL이 `2.91`까지 튀었고, 이 무렵 win_rate는 `0.036` 수준이었다. PPO update가 과격해져 policy를 망가뜨린 가능성이 있다.

5. timeout과 loss의 의미를 분리해서 봐야 한다.  
   초반에는 timeout이 많아도 loss가 낮고 win_rate가 올라가는 과정이었다. 후반에는 timeout보다 loss가 증가하면서 실제로 나쁜 방향으로 이동했다.

## 5. 현재 판단

v12b는 “더 오래 학습하면 좋아진다”가 아니라 “좋은 checkpoint를 지나친 뒤 policy가 망가졌다”에 가깝다.

따라서 다음 실험은 `bundle_000300`에서 계속하지 말고, `bundle_000110` 또는 `bundle_000120/000130`에서 branching하는 것이 좋아 보인다.

## 6. 다음 학습에 대한 가설

### 가설 A: 조기 중단 및 best-checkpoint selection이 필요하다

현재 PPO 학습은 100-130 iteration 부근에서 좋은 정책을 얻었지만 이후 보존하지 못했다. 다음에는 validation eval을 주기적으로 돌려 best checkpoint를 고르고, train metric만 보고 final을 선택하지 않아야 한다.

### 가설 B: reward shaping이 timeout/WEZ 유지 exploit을 만든다

reward_mean이 높은데 win_rate가 낮은 구간이 있다. kill을 못 해도 긴 시간 target 근처에서 reward를 많이 얻는 행동이 남아 있을 수 있다. draw/timeout 또는 non-kill episode의 reward 상한을 낮추는 식의 보정이 필요할 수 있다.

### 가설 C: PPO update 안정화가 필요하다

후반 entropy 증가와 KL spike를 보면 policy update가 너무 커졌을 수 있다. learning rate, clip range, KL penalty/target, entropy coefficient, checkpoint selection 전략을 조정해야 할 수 있다.

## 7. reward 수식과 관련 코드 정보

아래는 `student/my_reward.py`의 핵심 reward 구조를 요약한 것이다. 외부 조언자는 특히 “kill 없이도 높은 reward_mean이 가능한가”와 “timeout/max-timeout episode가 reward를 과하게 얻는가”를 봐 달라.

### v12/v12b reward config

v12와 v12b는 같은 reward config를 쓴다.

```yaml
reward:
  win_reward: 220.0
  forced_ground_reward: 0.0
  loss_reward: -150.0
  draw_reward: -170.0
  damage_dealt_scale: 140.0
  damage_taken_scale: 3.0
  wez_entry_bonus: 20.0
  wez_shaping_cone_deg: 90.0
  wez_precision_bonus_min: 1.0
  wez_precision_bonus_max: 100.0
  pbrs_gamma: 0.997
  pbrs_ata_weight: 2.0
  pbrs_range_weight: 1.0
  pbrs_range_log_clip: 3.0
  pbrs_alt_weight: 10.0
  safety_floor_m: 300.0
  safety_safe_m: 900.0
  pursuit_dense_scale: 0.2
  pursuit_half_angle_deg: 45.0
  pursuit_range_m: 2500.0
  step_penalty: -0.005
  aspect_cone_deg: 30.0
  front_cone_penalty_scale: 0.1
  rear_cone_reward_scale: 0.15
  critical_alt_margin_m: 300.0
  altitude_floor_penalty_min: 1.0
  altitude_floor_penalty_max: 1000.0
  reward_output_scale: 0.05
```

### 최종 reward 합산 구조

`compute_reward()`는 component를 만든 뒤, 마지막에 모든 component에 `reward_output_scale=0.05`를 곱하고 합산한다.

```python
components["survival"] = survival_bonus
components["step"] = step_penalty

components["damage"] = (
    damage_dealt_scale * target_damage
    - damage_taken_scale * ownship_damage
)

components["pursuit"] = (
    pbrs_pursuit
    + dense
    + wez_bonus
    + aspect_term
)
components["safety"] = pbrs_alt + alt_floor_penalty
components["terminal"] = terminal

if reward_output_scale != 1.0:
    components = {k: v * reward_output_scale for k, v in components.items()}

reward = sum(components.values())
```

따라서 terminal reward도 실제 학습에는 아래처럼 scale된다.

- kill win: `220 * 0.05 = +11`
- loss: `-150 * 0.05 = -7.5`
- draw/timeout: `-170 * 0.05 = -8.5`
- forced-ground: `0`
- WEZ precision bonus max: `100 * 0.05 = +5 per step`
- damage dealt scale: `140 * 0.05 = +7 * target_damage`

여기서 중요한 의심점은 `WEZ precision bonus`가 per-step이고, dead-on 근처에서는 한 step당 최대 +5 scaled reward를 줄 수 있다는 점이다. kill terminal은 +11 scaled reward라서, kill을 빨리 끝내는 것보다 긴 시간 aim/WEZ shaping을 받는 행동이 더 좋아질 수 있는지 검토가 필요하다.

### pursuit potential

```python
def _pursuit_potential(distance, ata_deg, wez_config, cfg):
    ata_term = pbrs_ata_weight * abs(ata_deg) / 180.0
    wez_mid = (min_range_m + max_range_m) / 2.0
    range_off = min(abs(log(distance / wez_mid)), pbrs_range_log_clip)
    range_term = pbrs_range_weight * range_off / pbrs_range_log_clip
    return -(ata_term + range_term)
```

그리고 PBRS 항은 다음과 같다.

```python
pbrs_pursuit = gamma * phi_p_next - phi_p_prev
pbrs_alt = gamma * phi_h_next - phi_h_prev
```

v12/v12b에서는 `pbrs_gamma=0.997`를 사용한다. 코드 주석에는 `pbrs_gamma=1.0`이 더 깔끔하게 telescope된다고 적혀 있지만, 실험 config에서는 0.997로 덮어쓴 상태다. 이 차이가 긴 episode에서 shaping bleed 또는 unintended time pressure를 만들 수 있는지도 봐 달라.

### WEZ precision bonus

```python
in_range = min_range_m <= distance <= max_range_m
half_angle = wez_shaping_cone_deg / 2.0
if in_range and abs(ata) <= half_angle:
    frac = 1.0 - abs(ata) / half_angle
    bonus = bonus_min * (bonus_max / bonus_min) ** frac
else:
    bonus = 0.0
```

v12/v12b 값으로는:

- true WEZ range: `152.4-914.4m`
- true kill/damage cone: `wez.angle_deg=2deg`, 즉 `abs(ata) <= 1deg`
- reward-only shaping cone: `90deg`, 즉 `abs(ata) <= 45deg`
- bonus: `1 -> 100 raw`, 마지막에 `0.05` scale

대략적인 scaled bonus:

| ATA | raw bonus | scaled bonus |
|---:|---:|---:|
| 45deg | 1 | 0.05 |
| 30deg | 약 4.6 | 약 0.23 |
| 20deg | 약 13 | 약 0.65 |
| 10deg | 약 36 | 약 1.8 |
| 0deg | 100 | 5.0 |

질문: 이 per-step precision bonus가 kill terminal보다 너무 강해, hit/kill 없이도 좋은 reward trajectory를 만들 수 있는가?

### dense pursuit

```python
ata_factor = max(0.0, 1.0 - abs(ata) / pursuit_half_angle_deg)
range_factor = max(0.0, 1.0 - distance / pursuit_range_m)
dense = pursuit_dense_scale * ata_factor * range_factor
```

v12/v12b에서는 `pursuit_dense_scale=0.2`, `pursuit_half_angle_deg=45`, `pursuit_range_m=2500`이다. 마지막 scale 후 최대치는 `0.2 * 0.05 = 0.01` per step라서 크지는 않다.

### aspect shaping

```python
front_factor = max(0.0, 1.0 - target_nose_on_own / half_angle)
rear_factor = max(0.0, 1.0 - own_behind_target / half_angle)

aspect_term = (
    -front_cone_penalty_scale * front_factor
    + rear_cone_reward_scale * rear_factor
)
```

v12/v12b에서는 `aspect_cone_deg=30`, `front_cone_penalty_scale=0.1`, `rear_cone_reward_scale=0.15`다. 마지막 scale 후 최대치는 후방 보상 `0.0075` per step라서 크지는 않다.

### terminal reward

```python
if terminated:
    if target_hp <= 0.0 < own_hp:
        terminal = win_reward
    elif end_condition == "target altitude below min" and own_hp > 0.0:
        terminal = forced_ground_reward
    elif own_hp <= 0.0 < target_hp:
        terminal = loss_reward
    else:
        terminal = draw_reward
elif truncated:
    terminal = draw_reward
```

v12/v12b에서는 `forced_ground_reward=0`, `draw_reward=-170`이다. 따라서 target이 살아 있는데 altitude floor로 끝나는 forced-ground는 scaled reward 0이고, timeout/truncated는 -8.5다.

### range discipline wrapper

v12/v12b에는 reward 외에 `range_discipline`이 켜져 있다.

```yaml
range_discipline:
  enabled: true
  max_range_m: 3500.0
  grow_steps: 30
```

의도는 one-pass 후 멀리 도망가 timeout/draw를 만드는 exploit을 조기에 loss로 끝내는 것이다. 후반 loss_rate 증가가 이 wrapper 때문인지, 실제 crash/kill 실패 때문인지 engagement log에서 구분할 필요가 있다.

### PPO 설정

```yaml
algo:
  lr: 1.0e-4
  gamma: 0.997
  gae_lambda: 0.95
  clip_param: 0.12
  train_batch_size: 16384
  minibatch_size: 512

runtime:
  iterations: 300
  num_env_runners: 4
  lightweight_bundle_frequency: 10
```

후반 KL spike가 있었기 때문에, `lr`, `clip_param`, KL target/early stop, entropy schedule을 조정해야 하는지 조언이 필요하다.

## 8. 외부 조언자에게 묻고 싶은 질문

1. v12b의 `win_rate` 붕괴를 PPO drift, reward exploit, curriculum 난이도, 평가 노이즈 중 무엇으로 보는가?
2. `bundle_000110~000130`에서 branch한다면, 다음 학습은 어떤 설정으로 가는 것이 좋은가?
3. reward_mean과 win_rate가 어긋나는 상황에서 reward를 어떻게 고쳐야 하는가?
4. timeout episode가 높은 reward를 받지 못하도록 어떤 shaping/terminal reward 구조가 적절한가?
5. PPO 안정화를 위해 우선 조정할 항목은 무엇인가?
   - lr `1e-4`를 낮출지
   - clip `0.12`를 낮출지
   - entropy를 더 빨리 줄이거나 제한할지
   - KL target/early stop을 둘지
6. target rear-spawn curriculum은 현재 `500-850m`, `0-14deg`, weak weave인데, 더 좁혀야 하는가 아니면 유지해야 하는가?
7. 다음 단계에서 level/autopilot target을 계속 써야 하는가, 아니면 best checkpoint를 고정한 뒤 mild maneuver/loiter target으로 넘어가야 하는가?
8. best checkpoint 선택 기준은 무엇이 적절한가?
   - train rolling win_rate
   - held-out eval win_rate
   - kill time
   - timeout/loss tradeoff
   - WEZ time
   - damage_done

## 9. 내가 생각하는 다음 실험 후보

### 후보 1: v12c 안정화 branch

- seed: `bundle_000110` 또는 `bundle_000120`
- geometry: v12b와 동일하거나 약간 좁힘
- iterations: 40-80
- lr: `5e-5`
- clip: `0.08-0.10`
- entropy를 낮게 유지
- best checkpoint selection 필수

목표: 좋은 gunnery policy를 망가뜨리지 않고 win_rate 0.65 이상을 유지/개선.

### 후보 2: reward cap/timeout penalty branch

- seed: `bundle_000110`
- non-kill episode의 shaping reward 상한 또는 timeout penalty 강화
- kill bonus/damage reward는 유지
- timeout에서 높은 reward를 받는 경로를 차단

목표: reward_mean이 아니라 kill 중심으로 정책을 압박.

### 후보 3: validation-gated curriculum

- seed: `bundle_000110`
- 10 iteration마다 held-out eval
- best eval checkpoint만 다음 curriculum으로 승급
- 승급 전까지는 final checkpoint를 신뢰하지 않음

목표: 학습 중 policy drift를 허용하되, 산출물 선택은 검증 성능으로 결정.

## 10. 조언 요청의 핵심

가장 궁금한 점은 이것이다.

`v12b`는 초중반에 win_rate 0.65-0.75까지 올라갔는데, 왜 300 iteration까지 돌리자 0.1대까지 떨어졌는가?  
이 상황에서 다음 실험은 reward를 고쳐야 하는가, PPO 안정화를 먼저 해야 하는가, 아니면 best-checkpoint/validation-gating만 추가해도 충분한가?
