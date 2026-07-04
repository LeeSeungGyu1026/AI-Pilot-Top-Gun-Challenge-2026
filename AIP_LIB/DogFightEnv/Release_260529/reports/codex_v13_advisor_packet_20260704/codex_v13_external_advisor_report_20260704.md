# v13 실험 분석 및 다음 방향 조언 요청

이 문서는 외부 조언자에게 바로 전달하기 위한 요약입니다. 프로젝트 자체 소개는 생략하고, v12b 이후 reward 수정 실험인 v13의 실패 양상과 관련 코드를 중심으로 정리합니다.

## 1. 결론 요약

v13은 v12b `bundle_000110`에서 분기하여 reward farming으로 의심된 per-step WEZ precision bonus를 제거하고, damage reward 및 fast-kill terminal bonus를 강화한 실험입니다.

실험 결과는 실패입니다.

- run tag: `codex_ic_s3_v13_rewardfix_rear_gunnery_v1`
- seed/init bundle: `artifacts/models/team01/codex_ic_s3_v12b_level_rear_randomized_300_v1/bundle_000110`
- 목표 iteration: 80
- 실제 중지 시점: iter 64
- 총 steps: 1,064,960
- 총 episodes: 1,704
- 전체 관측 win_rate: 0.000
- 저장 bundle: `bundle_000010` ~ `bundle_000060`
- 마지막 지표: `Reward=0.0988`, `WinRate=0.000`, `WEZ_ep=4.1`, `Entropy=2.9102`, `VF_loss=0.0545`, `KL=0.0029`
- best reward: iter 63, `Reward=1.9662`, `WinRate=0.000`, `WEZ_ep=6.9`

핵심 질문은 다음입니다.

1. v13처럼 precision bonus를 제거하는 방식이 기존 v12b kill 정책을 즉시 망가뜨린 원인이 무엇인가?
2. v12b `bundle_000110`이 정말 높은 win_rate 후보였다면, v13 학습 시작부터 win_rate 0이 나온 것은 reward 변경 때문인가, 평가/로그/환경 차이 때문인가?
3. 다음 실험은 reward를 어떻게 줄여야 하는가? 완전 제거가 아니라 축소, PBRS화, terminal-only 강화, imitation-like warm start, freeze/evaluate가 필요한가?

## 2. v12b에서 얻은 가설

이전 조언의 핵심 진단은 다음이었습니다.

- v12b의 wide per-step WEZ precision bonus가 실제 kill보다 "거의 조준 상태를 유지하며 보상을 농사짓는 행동"을 더 유리하게 만들었다.
- kill terminal + full damage reward보다, 매 step 지급되는 precision reward 누적치가 훨씬 커질 수 있다.
- 그래서 v12b는 초반에 win_rate가 높게 보이다가 후반으로 갈수록 aim-farming / timeout 방향으로 붕괴했다.

v13은 이 진단을 반영하여 precision bonus를 제거하고 damage 및 fast-kill 보상을 키웠습니다.

## 3. v13 설정

주요 환경과 PPO 설정은 다음과 같습니다.

```yaml
name: codex_ic_s3_v13_rewardfix_rear_gunnery_v1

env:
  observation_mode: custom
  observation_module: student.my_observation
  reward_module: student.codex_reward_v13
  target_mode: autopilot
  max_engage_time: 90.0
  episode_step_limit: 2700

env_config:
  offensive_saddle:
    enabled: true
    range_m: [500.0, 850.0]
    aspect_deg: [0.0, 14.0]
    altitude_m: 7000.0
    target_speed_mps: 250.0
    own_speed_mps: 260.0
  target_weave:
    enabled: true
    amplitude_deg: 6.0
    period_steps: 180.0
  wez:
    angle_deg: 2.0
    min_range_m: 152.4
    max_range_m: 914.4
  reward:
    win_reward: 220.0
    forced_ground_reward: 0.0
    loss_reward: -150.0
    draw_reward: -100.0
    damage_dealt_scale: 350.0
    damage_taken_scale: 3.0
    wez_entry_bonus: 20.0
    wez_precision_bonus_enabled: false
    fast_kill_bonus_max: 110.0
    fast_kill_horizon_s: 90.0
    pbrs_gamma: 0.997
    pbrs_ata_weight: 4.0
    pbrs_range_weight: 1.0
    pbrs_alt_weight: 10.0
    pursuit_dense_scale: 0.2
    step_penalty: -0.005
    reward_output_scale: 0.05

algo:
  name: ppo
  framework: torch
  lr: 5.0e-5
  gamma: 0.997
  gae_lambda: 0.95
  clip_param: 0.10
  train_batch_size: 16384
  minibatch_size: 512

runtime:
  iterations: 80
  init_bundle: artifacts/models/team01/codex_ic_s3_v12b_level_rear_randomized_300_v1/bundle_000110
```

전체 설정 파일은 zip 안의 `codex_ic_s3_v13_rewardfix_rear_gunnery_v1.yaml`에 포함했습니다.

## 4. v13 reward wrapper 코드

v13은 base reward 전체를 재작성하지 않고 wrapper로 구성했습니다.

```python
from dogfight.sim.state_schema import StateIndex
from student import my_reward as base_reward


MY_REWARD_CONFIG = {
    **base_reward.MY_REWARD_CONFIG,
    "win_reward": 220.0,
    "forced_ground_reward": 0.0,
    "loss_reward": -150.0,
    "draw_reward": -100.0,
    "damage_dealt_scale": 350.0,
    "damage_taken_scale": 3.0,
    "pbrs_ata_weight": 4.0,
    "wez_precision_bonus_enabled": False,
    "fast_kill_bonus_max": 110.0,
    "fast_kill_horizon_s": 90.0,
    "reward_output_scale": 0.05,
}
```

precision bonus 제거 부분:

```python
def _removed_precision_bonus(ownship_state, target_state, geo_info, wez_config: dict, cfg: dict) -> float:
    if cfg.get("wez_precision_bonus_enabled", False):
        return 0.0
    distance = float(geo_info._get_distance(ownship_state, target_state))
    ata = float(geo_info._get_antenna_train_angle(ownship_state, target_state, False))
    return float(base_reward._wez_precision_bonus(distance, ata, wez_config, cfg))
```

fast-kill bonus:

```python
def _fast_kill_bonus(ownship_state, target_state, terminated: bool, cfg: dict) -> float:
    if not terminated:
        return 0.0
    own_hp = float(ownship_state[StateIndex.HEALTH])
    tgt_hp = float(target_state[StateIndex.HEALTH])
    if not (tgt_hp <= 0.0 < own_hp):
        return 0.0
    horizon = max(float(cfg.get("fast_kill_horizon_s", 90.0)), 1e-6)
    sim_time = max(float(ownship_state[StateIndex.SIM_TIME]), 0.0)
    frac = max(0.0, 1.0 - sim_time / horizon)
    return float(cfg.get("fast_kill_bonus_max", 0.0)) * frac
```

wrapper의 최종 계산:

```python
def compute_reward(
    ownship_state,
    target_state,
    ownship_damage: float,
    target_damage: float,
    geo_info,
    wez_config: dict,
    reward_config: dict,
    terminated: bool,
    truncated: bool,
    end_condition: str,
) -> tuple[float, dict]:
    cfg = {**MY_REWARD_CONFIG, **(reward_config or {})}
    # Force the base reward to include the precision term, then remove exactly
    # that term below. Today my_reward.py ignores wez_precision_bonus_enabled,
    # but this keeps v13 correct if the base module later learns that flag.
    base_cfg = {**cfg, "wez_precision_bonus_enabled": True}
    total, components = base_reward.compute_reward(
        ownship_state,
        target_state,
        ownship_damage,
        target_damage,
        geo_info,
        wez_config,
        base_cfg,
        terminated,
        truncated,
        end_condition,
    )

    out_scale = float(cfg.get("reward_output_scale", 1.0))

    precision_to_remove = _removed_precision_bonus(ownship_state, target_state, geo_info, wez_config, cfg) * out_scale
    if precision_to_remove:
        components["pursuit"] = components.get("pursuit", 0.0) - precision_to_remove
        total -= precision_to_remove

    fast_bonus = _fast_kill_bonus(ownship_state, target_state, terminated, cfg) * out_scale
    if fast_bonus:
        components["terminal"] = components.get("terminal", 0.0) + fast_bonus
        total += fast_bonus

    return float(total), components
```

주의: base `my_reward.py`는 현재 `wez_precision_bonus_enabled` 플래그를 직접 처리하지 않습니다. 즉 v13 wrapper는 현재 기준으로 "이미 제거된 precision bonus를 또 빼는 anti-precision penalty"는 아닙니다. 다만 나중에 base가 해당 flag를 처리하게 될 가능성에 대비해 wrapper에서 `base_cfg = {**cfg, "wez_precision_bonus_enabled": True}`를 사용하도록 방어 패치를 넣었습니다.

전체 파일은 zip 안의 `codex_reward_v13.py`에 포함했습니다.

## 5. base reward의 precision bonus 구조

base reward는 `compute_reward()` 안에서 WEZ entry bonus와 wide precision bonus를 `pursuit` component에 더합니다.

```python
components["damage"] = (
    float(cfg.get("damage_dealt_scale", 30.0)) * float(target_damage)
    - float(cfg.get("damage_taken_scale", 12.0)) * float(ownship_damage)
)

distance = float(geo_info._get_distance(ownship_state, target_state))
ata = float(geo_info._get_antenna_train_angle(ownship_state, target_state, False))
alt = float(ownship_state[StateIndex.ALT])
sim_time = float(ownship_state[StateIndex.SIM_TIME])
gamma = float(cfg.get("pbrs_gamma", 0.997))

in_wez = (
    float(wez_config["min_range_m"]) <= distance <= float(wez_config["max_range_m"])
    and abs(ata) <= float(wez_config["angle_deg"]) / 2.0
)
wez_bonus = 0.0
if in_wez and not wez_entered:
    wez_bonus = float(cfg.get("wez_entry_bonus", 0.0))
    wez_entered = True

wez_bonus += _wez_precision_bonus(distance, ata, wez_config, cfg)
```

base reward의 config 기본값 일부:

```python
MY_REWARD_CONFIG = {
    "win_reward": 150.0,
    "forced_ground_reward": 50.0,
    "loss_reward": -150.0,
    "draw_reward": -150.0,
    "damage_dealt_scale": 30.0,
    "damage_taken_scale": 12.0,
    "wez_entry_bonus": 20.0,
    "reward_output_scale": 0.05,
}
```

중요한 점:

- v13은 `damage_dealt_scale`을 30에서 350으로 크게 키웠습니다.
- 대신 precision bonus를 제거했습니다.
- 전체 reward는 `reward_output_scale=0.05`로 축소됩니다.
- kill terminal bonus와 fast-kill bonus는 실제 kill이 발생해야만 작동합니다.
- v13에서 kill이 거의 또는 전혀 발생하지 않으면, terminal/fast-kill 강화는 학습 신호가 되지 못합니다.

## 6. 훈련 로그 핵심 지표

초기:

```text
iter=[0] | Steps=[16384] | Eps=[49] | Reward=[-147.8424] | WinRate=[0.000] | WEZ_ep=[2.8] | Entropy=[5.6878] | VF_loss=[2.1138] | KL=[0.0031]
iter=[1] | Steps=[32768] | Eps=[99] | Reward=[-147.6791] | WinRate=[0.000] | WEZ_ep=[2.6] | Entropy=[5.6754] | VF_loss=[2.1846] | KL=[0.0041]
iter=[2] | Steps=[49152] | Eps=[151] | Reward=[-147.7394] | WinRate=[0.000] | WEZ_ep=[3.0] | Entropy=[5.7062] | VF_loss=[2.1548] | KL=[0.0033]
```

중반:

```text
iter=[30] | Steps=[507904] | Eps=[1038] | Reward=[-104.9128] | WinRate=[0.000] | WEZ_ep=[3.1] | Entropy=[4.9047] | VF_loss=[1.0358] | KL=[0.0066]
iter=[40] | Steps=[671744] | Eps=[1260] | Reward=[-69.7881] | WinRate=[0.000] | WEZ_ep=[3.8] | Entropy=[4.8856] | VF_loss=[1.0907] | KL=[0.0054]
iter=[50] | Steps=[835584] | Eps=[1449] | Reward=[-7.7532] | WinRate=[0.000] | WEZ_ep=[4.1] | Entropy=[2.5833] | VF_loss=[0.0776] | KL=[0.0055]
```

후반:

```text
iter=[60] | Steps=[999424] | Eps=[1632] | Reward=[-1.1230] | WinRate=[0.000] | WEZ_ep=[3.6] | Entropy=[2.6359] | VF_loss=[0.0392] | KL=[0.0025]
iter=[62] | Steps=[1032192] | Eps=[1668] | Reward=[0.4766] | WinRate=[0.000] | WEZ_ep=[5.1] | Entropy=[3.0411] | VF_loss=[0.0492] | KL=[0.0029]
iter=[63] | Steps=[1048576] | Eps=[1686] | Reward=[1.9662] | WinRate=[0.000] | WEZ_ep=[6.9] | Entropy=[3.3390] | VF_loss=[0.1197] | KL=[0.0028]
iter=[64] | Steps=[1064960] | Eps=[1704] | Reward=[0.0988] | WinRate=[0.000] | WEZ_ep=[4.1] | Entropy=[2.9102] | VF_loss=[0.0545] | KL=[0.0029]
```

전체 CSV는 zip 안의 `codex_v13_metrics.csv`, 전체 로그는 `codex_v13_train.log`에 포함했습니다.

## 7. 현재 해석

v13은 reward farming을 제거하려는 방향은 타당했지만, 결과적으로 kill policy를 보존하지 못했습니다. 특히 seed가 v12b `bundle_000110`임에도 iter 0부터 win_rate가 0이라는 점이 이상합니다.

가능한 원인 후보:

1. v12b `bundle_000110`의 win_rate가 동일한 v13 환경/평가 조건에서는 실제로 높지 않았을 수 있습니다.
2. reward module 변경이 학습 전 평가 지표에는 직접 영향을 주지 않아야 할 것 같지만, RLlib restore/initialization 또는 환경 구성 차이가 있었을 수 있습니다.
3. precision bonus 제거가 기존 정책의 near-kill aiming behavior를 보상적으로 완전히 무가치하게 만들어, 초기 policy가 빠르게 다른 행동으로 drift했을 수 있습니다.
4. terminal kill/fast-kill 보상은 kill이 발생해야만 학습되므로, 초기에 kill이 끊긴 상태에서는 sparse reward 문제가 다시 생겼을 수 있습니다.
5. `damage_dealt_scale=350`은 커졌지만 실제 damage event가 충분히 발생하지 않으면 신호가 거의 없습니다.
6. `draw_reward=-100`, `loss_reward=-150`, `win_reward=220`, `reward_output_scale=0.05` 조합이 PPO advantage scale에서 어떤 효과를 냈는지 재점검이 필요합니다.

## 8. 조언 요청

다음 실험을 어떻게 설계해야 할지 조언을 부탁드립니다.

특히 아래 질문에 답해주시면 좋겠습니다.

1. v13처럼 precision bonus를 완전히 제거한 것이 너무 급격했나요? 그렇다면 다음은 어느 정도로 줄이는 것이 좋습니까?
2. wide WEZ precision bonus를 per-step reward가 아니라 PBRS 형태로 바꾸는 구체적인 수식을 추천해주실 수 있나요?
3. v12b `bundle_000110`이 실제로 좋은 시작점인지 확인하기 위해, 학습 전 별도 evaluation을 어떻게 구성해야 하나요?
4. terminal kill 보상을 강화해도 kill이 sparse하면 학습이 안 됩니다. rear-spawn gunnery curriculum에서 kill event를 유지하려면 어떤 dense signal이 안전합니까?
5. `damage_dealt_scale=350`, `win_reward=220`, `fast_kill_bonus_max=110`, `reward_output_scale=0.05`의 상대 크기가 적절한가요?
6. v13b는 아래 중 어떤 방향이 가장 안전할까요?
   - v12b reward에서 precision bonus max만 100 -> 5 또는 10으로 축소
   - precision bonus를 potential-based shaping으로 대체
   - v12b `bundle_000110`을 fixed-policy eval 후, best checkpoint만 validation-gated 저장
   - target weave를 잠시 끄고 deterministic rear-spawn에서 kill behavior를 복원
   - PPO lr/clip을 더 낮추고 KL early-stop/entropy schedule 추가
   - reward 변경 없이 평가/체크포인트 selection만 먼저 고침

## 9. 첨부 파일

이 보고서와 함께 zip에 포함된 파일:

- `codex_v13_external_advisor_report_20260704.md`: 이 보고서
- `codex_reward_v13.py`: v13 reward wrapper 전체 코드
- `codex_my_reward_base.py`: base reward 전체 코드 복사본
- `codex_ic_s3_v13_rewardfix_rear_gunnery_v1.yaml`: v13 실험 설정
- `codex_v13_metrics.csv`: v13 iteration별 지표
- `codex_v13_train.log`: v13 전체 훈련 로그

