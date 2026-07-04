# v13 후속 점검: bundle restore 및 고정 평가 결과

## 결론

조언자의 핵심 가설 중 일부는 반박되고, 일부는 확인되었습니다.

1. `bundle_000110`이 v13 학습 프로세스에 조용히 partial load 또는 fresh init로 들어갔다는 가설은 현재 증거상 반박됩니다.
2. 그러나 `bundle_000110`이 v13 동일 평가 환경에서 0.65 win_rate급 seed였다는 전제는 반박됩니다.
3. `bundle_000110`은 deterministic 및 stochastic frozen eval 모두에서 10/10 timeout draw였고, terminal kill은 0건이었습니다.
4. 따라서 v13 실패의 직접 원인은 "reward 변경으로 좋은 kill policy를 망가뜨림"이라기보다, "v12b train metric의 win_rate 후보가 실제 제출/고정 평가 조건에서 kill policy가 아니었음"에 가깝습니다.

## 1. Loader autopsy

추가한 진단 스크립트:

- `scripts/codex_bundle_restore_autopsy.py`

실행:

```powershell
C:\Users\GYU\AppData\Local\miniconda3\envs\aip\python.exe scripts\codex_bundle_restore_autopsy.py `
  --experiment-yaml experiments\codex_ic_s3_v13_rewardfix_rear_gunnery_v1.yaml `
  --bundle artifacts\models\team01\codex_ic_s3_v12b_level_rear_randomized_300_v1\bundle_000110 `
  --output-json reports\codex_v13_restore_autopsy_20260704.json
```

핵심 결과:

```json
{
  "bundle_metadata_iteration": 110,
  "train_module_matches_bundle_after": true,
  "env_runner_module_matches_bundle_after": true,
  "train_module_changed_by_apply": true,
  "env_runner_module_changed_by_apply": true,
  "train_compare_after": {
    "expected_key_count": 7,
    "actual_key_count": 7,
    "common_key_count": 7,
    "missing_keys": [],
    "unexpected_keys": [],
    "mismatch_count": 0,
    "max_abs_diff": 0.0
  }
}
```

해석:

- production loader는 v13 build에서 `bundle_000110`을 train module과 env runner module 양쪽에 정확히 적용했습니다.
- missing/unexpected key는 없었습니다.
- hash도 bundle과 완전히 일치했습니다.
- 따라서 이번 v13의 "fresh init처럼 보임"은 실제 loader 실패로 설명하기 어렵습니다.

주의:

- `bundle_000110`의 `pi.net.mlp.0.bias` 뒤 4개 값을 log_std로 단순 추정하면 entropy는 약 `5.7129`입니다.
- 즉 v13 iter 0 entropy `5.6878`은 fresh init의 결정적 증거로 쓰기 어렵습니다.

## 2. Frozen deterministic eval

실행:

```powershell
C:\Users\GYU\AppData\Local\miniconda3\envs\aip\python.exe scripts\codex_pre_v12_diagnostics.py `
  --eval-name codex_v13_bundle110_fixed_eval_det_10_v1 `
  --episodes 10 `
  --ownship-bundle-dir artifacts\models\team01\codex_ic_s3_v12b_level_rear_randomized_300_v1\bundle_000110 `
  --target-backend autopilot `
  --observation-mode custom `
  --observation-module student.my_observation `
  --experiment-yaml experiments\codex_ic_s3_v13_rewardfix_rear_gunnery_v1.yaml `
  --max-engage-time 90 `
  --episode-step-limit 2700 `
  --sample-stride 30
```

결과 파일:

- `artifacts/eval/codex_v13_bundle110_fixed_eval_det_10_v1/codex_summary.json`
- `artifacts/eval/codex_v13_bundle110_fixed_eval_det_10_v1/codex_episodes_diagnostics.csv`

요약:

```json
{
  "episodes": 10,
  "outcomes": {"draw": 10},
  "end_conditions": {"max time out": 10},
  "real_win_rate": 0.0,
  "forced_ground_rate": 0.0,
  "loss_rate": 0.0,
  "draw_rate": 1.0,
  "mean_total_reward": 127.4833868,
  "mean_time_in_band_steps": 314.2,
  "mean_time_in_band_ata10_steps": 268.6,
  "mean_true_cone_steps": 45.3,
  "mean_reward_components": {
    "step": -9.0,
    "pursuit": 130.4255147,
    "damage": 6.0578721,
    "safety": 0.0,
    "terminal": 0.0
  }
}
```

해석:

- deterministic 제출형 inference에서는 10/10 timeout draw입니다.
- true cone에는 평균 45.3 step 들어가지만 target destroyed가 없습니다.
- terminal reward는 0입니다.
- pursuit reward가 평균 130 이상으로 매우 큽니다. 이는 v12b reward farming 진단과 잘 맞습니다.

## 3. Frozen stochastic eval

`scripts/codex_pre_v12_diagnostics.py`에 `--explore` 옵션을 추가했습니다.

실행:

```powershell
C:\Users\GYU\AppData\Local\miniconda3\envs\aip\python.exe scripts\codex_pre_v12_diagnostics.py `
  --eval-name codex_v13_bundle110_fixed_eval_stoch_10_v1 `
  --episodes 10 `
  --ownship-bundle-dir artifacts\models\team01\codex_ic_s3_v12b_level_rear_randomized_300_v1\bundle_000110 `
  --target-backend autopilot `
  --observation-mode custom `
  --observation-module student.my_observation `
  --experiment-yaml experiments\codex_ic_s3_v13_rewardfix_rear_gunnery_v1.yaml `
  --max-engage-time 90 `
  --episode-step-limit 2700 `
  --sample-stride 30 `
  --explore
```

결과 파일:

- `artifacts/eval/codex_v13_bundle110_fixed_eval_stoch_10_v1/codex_summary.json`
- `artifacts/eval/codex_v13_bundle110_fixed_eval_stoch_10_v1/codex_episodes_diagnostics.csv`

요약:

```json
{
  "episodes": 10,
  "explore": true,
  "outcomes": {"draw": 10},
  "end_conditions": {"max time out": 10},
  "real_win_rate": 0.0,
  "forced_ground_rate": 0.0,
  "loss_rate": 0.0,
  "draw_rate": 1.0,
  "mean_total_reward": 126.4909801,
  "mean_time_in_band_steps": 352.7,
  "mean_time_in_band_ata10_steps": 265.3,
  "mean_true_cone_steps": 48.5,
  "mean_reward_components": {
    "step": -9.0,
    "pursuit": 128.2399502,
    "damage": 7.2510299,
    "safety": 0.0,
    "terminal": 0.0
  }
}
```

해석:

- stochastic action sampling에서도 10/10 timeout draw입니다.
- action 변화량은 deterministic보다 훨씬 크지만 kill은 없습니다.
- 따라서 deterministic inference만의 문제도 아닙니다.

## 4. v13 실패 재해석

기존 해석:

- v13 reward가 v12b의 좋은 kill policy를 망가뜨렸다.

현재 증거 기반 해석:

- v13은 실제로 `bundle_000110`을 로드했습니다.
- 하지만 `bundle_000110` 자체가 v13 동일 rear-spawn/autopilot/weave 평가에서 kill policy가 아니었습니다.
- v12b의 높은 train win_rate 또는 특정 로그 지표는 제출형/frozen eval에서 재현되지 않는 metric일 가능성이 큽니다.
- `bundle_000110`은 target을 오래 조준권에 두고 pursuit reward를 크게 얻지만, damage/terminal로 마무리하지 못합니다.

즉 다음 우선순위는 reward 추가 수정이 아니라 checkpoint selection/evaluation parity입니다.

## 5. 다음 실행안

## 5. v12b checkpoint ladder 추가 결과

Smart App Control이 새 Python 프로세스의 `torch\lib\c10.dll` 로드를 차단하는 상태가 발생했습니다.

관련 이벤트:

- `Microsoft-Windows-CodeIntegrity/Operational`
- `Smart App Control Block Details`
- `c10.dll`이 Enterprise signing level requirements를 만족하지 못했다는 메시지

그래서 `scripts/codex_pre_v12_diagnostics.py`에 `--numpy-inference` 모드를 추가했습니다. PPO lightweight bundle의 기본 MLP 구조를 NumPy로 직접 forward합니다.

```text
obs
 -> tanh(actor_encoder.mlp.0)
 -> tanh(actor_encoder.mlp.2)
 -> pi.net.mlp.0
 -> mean = logits[:4]
 -> stochastic이면 logits[4:]를 log_std로 사용
 -> clip_action()
```

이 경로는 torch/Ray를 로드하지 않으므로 OS 정책 차단 상태에서도 frozen eval을 계속할 수 있습니다.

요약 CSV:

- `reports/codex_v12b_frozen_eval_ladder_20260704.csv`

### Deterministic NumPy eval

동일 조건:

- target: autopilot
- geometry: `experiments/codex_ic_s3_v13_rewardfix_rear_gunnery_v1.yaml`의 rear-spawn/weave 설정
- episodes: 10
- max engage time: 90s

| bundle | deterministic real_win_rate | draw_rate | loss_rate | 요약 |
|---|---:|---:|---:|---|
| `bundle_000080` | 0.0 | 1.0 | 0.0 | kill 없음 |
| `bundle_000090` | 0.1 | 0.9 | 0.0 | 1 kill |
| `bundle_000100` | 0.0 | 1.0 | 0.0 | kill 없음 |
| `bundle_000110` | 0.1 | 0.9 | 0.0 | 1 kill |
| `bundle_000120` | 0.0 | 1.0 | 0.0 | kill 없음 |
| `bundle_000130` | 0.1 | 0.9 | 0.0 | 1 kill |

해석:

- v12b train CSV에서 0.55~0.71 win_rate를 보였던 구간도 제출형 deterministic frozen eval에서는 0~0.1 수준입니다.
- 따라서 train metric의 `win_rate`는 checkpoint selection 지표로 그대로 쓰기 어렵습니다.
- deterministic mean action은 target을 오래 WEZ band에 두지만 kill까지 안정적으로 마무리하지 못합니다.

### Stochastic NumPy eval

kill이 한 번이라도 나온 후보를 stochastic sampling으로 추가 확인했습니다.

| bundle | stochastic real_win_rate | draw_rate | loss_rate | 요약 |
|---|---:|---:|---:|---|
| `bundle_000090` | 0.4 | 0.6 | 0.0 | 10회 중 4 kill |
| `bundle_000110` | 0.1 | 0.9 | 0.0 | 10회 중 1 kill |
| `bundle_000130` | 0.0 | 0.9 | 0.1 | kill 없음, crash/loss 1 |

해석:

- `bundle_000090`은 policy distribution 안에 kill-capable 행동이 남아 있습니다.
- 하지만 deterministic mean action은 그 행동을 안정적으로 꺼내지 못합니다.
- `bundle_000110` 이후는 stochastic에서도 좋아지지 않습니다.
- 기존에 "v12b best region = 110~130"으로 봤던 판단은 train metric 기준이었고, frozen eval 기준으로는 `bundle_000090`이 더 유망합니다.

## 6. 수정된 다음 실행안

1. v12b 주요 checkpoint를 frozen eval로 ladder 평가합니다.
   - 완료: `bundle_000080`, `bundle_000090`, `bundle_000100`, `bundle_000110`, `bundle_000120`, `bundle_000130`
   - deterministic 10 episode 완료
   - stochastic 10 episode 일부 완료: `bundle_000090`, `bundle_000110`, `bundle_000130`
   - metric: real_win_rate, forced_ground_rate, draw_rate, terminal damage, true_cone_steps, pursuit/damage/terminal reward

2. train metric의 win_rate 정의를 점검합니다.
   - `target destroyed`와 `target altitude below min`이 섞였는지 확인
   - timeout인데 win으로 카운트되는 경로가 없는지 확인
   - training custom metric과 eval classifier를 같은 기준으로 맞춥니다.

3. 다음 training run에는 preflight gate를 둡니다.
   - init bundle autopsy: missing/unexpected/mismatch가 있으면 중단
   - frozen eval: deterministic 10 episode에서 real_win_rate가 기준 미만이면 중단
   - stochastic eval은 정책 분포의 잠재력 확인용으로만 사용하고, 제출 후보 기준은 deterministic을 우선합니다.
   - seeded run의 iter 0 지표만 믿지 않습니다.

4. v13 reward 실험은 유효한 seed checkpoint를 찾은 뒤 재개합니다.
   - 현재 `bundle_000110`에서 v13을 이어가는 것은 추천하지 않습니다.
   - 후보를 고른다면 `bundle_000090`이 더 낫습니다. 단, deterministic 0.1이라 아직 약합니다.
   - 다음 실험은 `bundle_000090`에서 entropy/variance를 낮추거나 deterministic mean이 kill 행동을 대표하도록 만드는 방향이 필요합니다.
   - reward를 완전 sparse하게 만들지 말고 precision bonus를 축소형으로 남기는 v13b가 더 안전합니다.

5. 가장 가까운 다음 실험 후보:
   - seed: `bundle_000090`
   - reward: v12b reward에서 `wez_precision_bonus_max`를 100에서 8~12로 축소
   - `fast_kill_bonus`는 유지하되 최소 바닥을 둠: `frac = max(0.2, 1 - sim_time / horizon)`
   - preflight: NumPy deterministic frozen eval 10회, stochastic eval 10회 저장
   - checkpoint selection: train win_rate가 아니라 frozen deterministic eval로 선택

## 7. v13b 구성 완료

생성한 파일:

- `student/codex_reward_v13b.py`
- `experiments/codex_ic_s3_v13b_reduced_precision_rear_gunnery_v1.yaml`
- `scripts/codex_launch_v13b_reduced_precision_rear_gunnery.cmd`
- `scripts/codex_launch_train_monitor_v13b.cmd`
- `scripts/codex_preflight_v13b_reduced_precision.cmd`
- `scripts/codex_check_torch_ready.py`

v13b reward 핵심:

```python
MY_REWARD_CONFIG = {
    **base_reward.MY_REWARD_CONFIG,
    "win_reward": 220.0,
    "forced_ground_reward": 0.0,
    "loss_reward": -150.0,
    "draw_reward": -100.0,
    "damage_dealt_scale": 350.0,
    "damage_taken_scale": 3.0,
    "pbrs_ata_weight": 4.0,
    "wez_precision_bonus_min": 0.2,
    "wez_precision_bonus_max": 10.0,
    "fast_kill_bonus_max": 110.0,
    "fast_kill_horizon_s": 90.0,
    "fast_kill_bonus_floor_frac": 0.2,
    "reward_output_scale": 0.05,
}
```

fast-kill floor:

```python
floor = max(0.0, min(1.0, float(cfg.get("fast_kill_bonus_floor_frac", 0.2))))
frac = max(floor, 1.0 - sim_time / horizon)
```

v13b YAML 핵심:

- seed: `artifacts/models/team01/codex_ic_s3_v12b_level_rear_randomized_300_v1/bundle_000090`
- reward module: `student.codex_reward_v13b`
- PPO: `lr=3e-5`, `clip_param=0.08`
- runtime: 60 iterations
- same rear-spawn/autopilot/weave geometry as v13

정적 검증:

- `python -m py_compile student\codex_reward_v13b.py scripts\codex_pre_v12_diagnostics.py scripts\codex_bundle_restore_autopsy.py` 통과
- `python scripts\run_experiment.py experiments\codex_ic_s3_v13b_reduced_precision_rear_gunnery_v1.yaml --dry-run` 통과

현재 차단:

- `import torch`가 Windows Smart App Control에 의해 막힙니다.
- 오류: `[WinError 4551] 애플리케이션 제어 정책에서 이 파일을 차단했습니다`
- 대상: `C:\Users\GYU\AppData\Local\miniconda3\envs\aip\Lib\site-packages\torch\lib\c10.dll`
- 따라서 v13b 학습은 아직 시작하지 않았습니다.
- `scripts/codex_launch_v13b_reduced_precision_rear_gunnery.cmd`는 이제 훈련 전에 `scripts/codex_check_torch_ready.py`를 실행하여 이 상태를 먼저 감지합니다.
- 최신 상태 리포트: `reports/codex_torch_ready_status.json`

## 8. v13b preflight 결과

실행:

```powershell
cmd /c scripts\codex_preflight_v13b_reduced_precision.cmd
```

결과:

| eval | real_win_rate | draw_rate | loss_rate | 비고 |
|---|---:|---:|---:|---|
| `codex_v13b_seed_bundle090_preflight_det_10_numpy_v1` | 0.1 | 0.9 | 0.0 | deterministic mean action |
| `codex_v13b_seed_bundle090_preflight_stoch_10_numpy_v1` | 0.2 | 0.8 | 0.0 | stochastic sampling |

요약:

- v13b seed인 `bundle_000090`은 deterministic에서 약하지만 최소 kill 가능성은 있습니다.
- stochastic에서 kill rate가 deterministic보다 높아, policy distribution 내부에는 유효한 kill 행동이 남아 있습니다.
- v13b의 목적은 이 stochastic kill potential을 deterministic/submission behavior로 끌어오는 것입니다.

다음 실행 조건:

1. Torch/Smart App Control 차단 해소
2. 가능하면 `codex_bundle_restore_autopsy.py`를 v13b YAML + `bundle_000090`으로 다시 실행
3. `scripts/codex_launch_v13b_reduced_precision_rear_gunnery.cmd`로 학습 시작
4. `scripts/codex_launch_train_monitor_v13b.cmd`로 monitor 실행
5. iter 0~10에서 deterministic frozen eval과 train metric 괴리를 계속 확인
