# Codex Result Summary: codex_ic_s4_mixed_anchor_guard_v1

Created: 2026-06-20T08:39:21+09:00

## Hypothesis

Hypothesis codex-H5: a conservative PPO fine-tune from `ic_s3_bt_v1` with mostly-BT mixed initial scenarios, stronger altitude guard, lower LR, and tighter PPO clip will improve loiter/autopilot robustness without erasing the proven BT behavior.

Training support criteria from the plan: continue to validation if the tail avoids a clear post-iter10 crash/loss collapse and shows an improving trend.

Validation gates:

- BT win rate >= 0.90
- autopilot win rate >= 0.90 with loss/crash <= 0.05
- loiter win rate >= 0.50 with draw <= 0.40 and loss/crash <= 0.05

## Plan And Launch

- Plan: `reports/codex_loop_plan_20260620_081800_codex_ic_s4_mixed_anchor_guard_v1.md`
- Config: `AIP_LIB/DogFightEnv/Release_260529/experiments/codex_ic_s4_mixed_anchor_guard_v1.yaml`
- Source bundle: `AIP_LIB/DogFightEnv/Release_260529/artifacts/models/team01/ic_s3_bt_v1`
- CWD: `AIP_LIB/DogFightEnv/Release_260529`
- PID: 25384
- Start observed: 2026-06-20T08:20:26+09:00
- End observed: 2026-06-20T08:35:07+09:00
- Command: `python scripts/run_experiment.py experiments/codex_ic_s4_mixed_anchor_guard_v1.yaml`

## Tail Metrics

`training_log.csv` contains 20 rows, iter 0 through iter 19.

| Iter | Reward mean | Win | Loss | Timeout | Crash | WEZ steps | Safety reward | Alt penalty steps |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 15 | -24.9534 | 0.0 | 0.0 | 0.0 | 0.4583 | 0.1181 | -31.4710 | 505.28 |
| 16 | -55.3826 | 0.0 | 0.0 | 0.0 | 0.5214 | 0.4286 | -32.6742 | 485.55 |
| 17 | 24.7653 | 0.0 | 0.0 | 0.0 | 0.2465 | 0.0000 | -33.2765 | 491.43 |
| 18 | 4.4665 | 0.0 | 0.0 | 0.0417 | 0.2986 | 0.1944 | -34.0781 | 564.51 |
| 19 | 2.2340 | 0.0 | 0.0 | 0.0 | 0.3056 | 0.1250 | -33.0874 | 465.26 |

Tail aggregates:

- Last-5 average reward: -9.7741
- Last-5 average crash rate: 0.3661
- Last-5 average timeout rate: 0.0083
- Last-3 average crash rate: about 0.2836

## Artifacts

- Logs: `AIP_LIB/DogFightEnv/Release_260529/artifacts/logs/team01/codex_ic_s4_mixed_anchor_guard_v1`
- Training CSV: `AIP_LIB/DogFightEnv/Release_260529/artifacts/logs/team01/codex_ic_s4_mixed_anchor_guard_v1/training_log.csv`
- Final bundle: `AIP_LIB/DogFightEnv/Release_260529/artifacts/models/team01/codex_ic_s4_mixed_anchor_guard_v1`
- Periodic bundles: `bundle_000010`, `bundle_000020`
- Training record: `AIP_LIB/DogFightEnv/Release_260529/artifacts/records/team01/codex_ic_s4_mixed_anchor_guard_v1`

## Decision

Do not freeze as a candidate from training metrics alone.

Run a validation ladder as a diagnostic because the tail improved enough to avoid immediate rejection: crash dropped from 0.5184 at iter10 to 0.2465-0.3056 in the last three completed windows, and rewards became positive in the last three rows. The tail is still too fragile for promotion: last-5 average crash is 0.3661, win_rate remains 0.0 in training logs, and altitude penalty steps remain high.

Next action: run `codex_ic_s4_mixed_anchor_guard_validation_v1` against BT/autopilot/loiter. Freeze only if validation gates pass; otherwise reject H5 and roll back to `ic_s3_bt_v1`.
