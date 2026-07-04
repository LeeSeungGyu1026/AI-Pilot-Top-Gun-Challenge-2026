# Codex Result Summary: codex_ic_s4_loiter_guard_v1

## Classification

Finished. Training completed 30 iterations and saved the final lightweight bundle:

- `AIP_LIB/DogFightEnv/Release_260529/artifacts/models/team01/codex_ic_s4_loiter_guard_v1`
- `AIP_LIB/DogFightEnv/Release_260529/artifacts/logs/team01/codex_ic_s4_loiter_guard_v1/training_log.csv`
- `AIP_LIB/DogFightEnv/Release_260529/artifacts/logs/team01/codex_ic_s4_loiter_guard_v1/codex_train_console.log`
- `AIP_LIB/DogFightEnv/Release_260529/artifacts/logs/team01/codex_ic_s4_loiter_guard_v1/codex_train_error.log`

## Hypothesis

codex-H3: a short PPO fine-tune from `ic_s3_bt_v1` against a loiter target on the same offensive-saddle geometry, with stronger altitude shaping and modestly increased close-range pursuit pressure, will improve loiter/autopilot robustness without destroying BT performance.

## Training Tail

Tail metrics from `training_log.csv`:

| Iter | Reward | Win | Loss | Timeout | Crash | WEZ steps |
|---:|---:|---:|---:|---:|---:|---:|
| 22 | -126.0568 | 0.0417 | 0.9583 | 0.0000 | 0.0000 | 3.7417 |
| 23 | -87.7591 | 0.1667 | 0.8333 | 0.0000 | 0.0000 | 5.5583 |
| 24 | -109.4342 | 0.0833 | 0.9167 | 0.0000 | 0.0000 | 7.5167 |
| 25 | -75.1257 | 0.1458 | 0.7292 | 0.1250 | 0.0000 | 15.9167 |
| 26 | -65.2658 | 0.1750 | 0.8250 | 0.0000 | 0.0000 | 15.9500 |
| 27 | -97.9812 | 0.0625 | 0.8750 | 0.0625 | 0.0000 | 13.3750 |
| 28 | -33.3551 | 0.2625 | 0.5292 | 0.2083 | 0.0000 | 14.7208 |
| 29 | 16.8884 | 0.4083 | 0.3750 | 0.2167 | 0.0000 | 17.4583 |

The run improved substantially from the all-loss startup, but training metrics remain mixed: the final logged training slice is only 40.8% win, 37.5% loss, and 21.7% timeout. It is not enough to accept H3 without evaluation.

## Notes

Ray emitted a Windows access-violation warning during startup, but the process survived, wrote all 30 training rows, and saved the final bundle. Treat it as a startup/runtime warning unless repeated fatal errors appear in later runs.

## Next Step

Run a Codex validation ladder on the final `codex_ic_s4_loiter_guard_v1` bundle before any SAC branch:

- BT eval to check if BT performance survived the loiter fine-tune.
- Autopilot eval to see if ownship-altitude losses improved.
- Loiter eval to quantify whether the draw collapse improved.

H3 remains pending until those validation metrics are available.
