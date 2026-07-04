# Codex Diagnostic Summary: codex_ic_s5_pbrs_altitude_curriculum_v1

Created: 2026-06-20T16:51:28+09:00

## Hypothesis

Hypothesis codex-H7b: a conservative PPO fine-tune from frozen H5 using moderate potential-based altitude shaping and controlled exposure to H7a failing slices will reduce ownship-altitude losses without collapsing BT/autopilot/loiter win rates.

Reject criteria:

- after iteration 5, crash/loss remains above 0.30 with no useful downward trend;
- win rate remains near 0.0;
- ownship-altitude failures continue to dominate completed episodes.

## Result

Reject codex-H7b before validation.

The run completed all 12 planned iterations and saved a final bundle, but the training tail is not viable for validation:

- final `crash_rate`: 0.7382
- final `win_rate`: 0.0
- tail-5 average `crash_rate`: 0.7522
- tail-5 average `win_rate`: 0.0
- final bundle exists, but should not be validated or frozen

## Tail Metrics

| Iter | Reward Mean | Win | Timeout | Crash |
|---:|---:|---:|---:|---:|
| 7 | -147.0460 | 0.0000 | 0.0000 | 0.9132 |
| 8 | -112.0249 | 0.0000 | 0.0313 | 0.7438 |
| 9 | -111.7835 | 0.0000 | 0.0000 | 0.7417 |
| 10 | -78.3157 | 0.0000 | 0.0417 | 0.6241 |
| 11 | -100.7725 | 0.0000 | 0.0000 | 0.7382 |

## Key Logs

Console tail still shows frequent `ownship altitude below min` terminations. It also shows some `target altitude below min` wins, but the aggregate training CSV does not report a viable win rate and the crash rate remains far above the stop threshold.

Startup Ray warnings matched previous runs and were not the primary failure mode.

## Artifacts

- Config: `AIP_LIB/DogFightEnv/Release_260529/experiments/codex_ic_s5_pbrs_altitude_curriculum_v1.yaml`
- Logs: `AIP_LIB/DogFightEnv/Release_260529/artifacts/logs/team01/codex_ic_s5_pbrs_altitude_curriculum_v1`
- Training CSV: `AIP_LIB/DogFightEnv/Release_260529/artifacts/logs/team01/codex_ic_s5_pbrs_altitude_curriculum_v1/training_log.csv`
- Rejected bundle: `AIP_LIB/DogFightEnv/Release_260529/artifacts/models/team01/codex_ic_s5_pbrs_altitude_curriculum_v1`

## Interpretation

H7b confirms that another PPO fine-tune on the failing slices is not enough. Even with moderate PBRS altitude shaping, the policy keeps entering low-altitude terminal states. This suggests the frozen H5 policy is already near a brittle pursuit mode: changing reward/exposure alone destabilizes it faster than it teaches recovery.

The next step should not be another PPO reward adjustment. Better next directions:

1. Investigate an inference-time safety shield that preserves frozen H5 but overrides/clamps only low-altitude dive actions.
2. Build a staged SAC/HSAC branch from easy high-altitude geometry, not from broad mixed failing slices.
3. Run a trajectory/action diagnostic on H5 failure cases to identify which action channel drives the dive.

## Decision

Stop this heartbeat loop before continuing. Do not validate H7b. Ask the user whether to proceed with a safety-shield diagnostic or a staged SAC/HSAC research branch.
