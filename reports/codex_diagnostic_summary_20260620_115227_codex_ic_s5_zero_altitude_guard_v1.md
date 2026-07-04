# Codex Diagnostic Summary: codex_ic_s5_zero_altitude_guard_v1

Created: 2026-06-20T11:52:27+09:00

## Hypothesis

Hypothesis codex-H6: a small PPO safety-polish fine-tune from frozen H5 with `student.codex_reward_zero_altitude` will remove ownship-altitude/FDM losses across BT/autopilot/loiter validation while preserving useful win rates.

Hard gates for eventual validation:

- zero `ownship altitude below min` end conditions
- zero `FDM Update Fail` end conditions
- BT win rate >= 0.90
- autopilot win rate >= 0.90
- loiter win rate >= 0.70 and draw <= 0.25

## Result

Reject codex-H6 before validation.

The run completed 15 iterations and saved a final bundle, but the post-iter5 crash trend did not improve. The plan's stop criterion was triggered: crash remained far above 0.20 after iteration 5 with no useful downward trend.

## Tail Metrics

| Iter | Reward mean | Win | Loss | Timeout | Crash | Safety reward | Alt penalty steps |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 5 | -375.8025 | 0.0 | 0.0 | 0.0 | 0.7422 | -319.2017 | 66.35 |
| 6 | -392.0197 | 0.0 | 0.0 | 0.0 | 0.7652 | -330.1632 | 64.77 |
| 7 | -396.6765 | 0.0 | 0.0 | 0.0 | 0.7854 | -321.4939 | 60.52 |
| 8 | -390.7172 | 0.0 | 0.0 | 0.0313 | 0.7597 | -305.4390 | 61.54 |
| 9 | -387.5030 | 0.0 | 0.0 | 0.0 | 0.7478 | -350.1760 | 58.16 |
| 10 | -472.4170 | 0.0 | 0.0 | 0.0 | 0.8944 | -370.3066 | 69.59 |
| 11 | -427.2808 | 0.0 | 0.0 | 0.0 | 0.8222 | -349.6147 | 68.87 |
| 12 | -383.4424 | 0.0 | 0.0 | 0.0 | 0.7378 | -351.9881 | 58.17 |
| 13 | -347.1568 | 0.0 | 0.0 | 0.0 | 0.6874 | -319.0906 | 54.72 |
| 14 | -357.4356 | 0.0 | 0.0 | 0.0 | 0.7139 | -309.3635 | 59.53 |

Tail aggregates:

- Last-5 average reward: -397.5465
- Last-5 average crash rate: 0.7711
- Last-5 average timeout rate: 0.0

## Artifacts

- Config: `AIP_LIB/DogFightEnv/Release_260529/experiments/codex_ic_s5_zero_altitude_guard_v1.yaml`
- Reward wrapper: `AIP_LIB/DogFightEnv/Release_260529/student/codex_reward_zero_altitude.py`
- Logs: `AIP_LIB/DogFightEnv/Release_260529/artifacts/logs/team01/codex_ic_s5_zero_altitude_guard_v1`
- Training CSV: `AIP_LIB/DogFightEnv/Release_260529/artifacts/logs/team01/codex_ic_s5_zero_altitude_guard_v1/training_log.csv`
- Rejected bundle: `AIP_LIB/DogFightEnv/Release_260529/artifacts/models/team01/codex_ic_s5_zero_altitude_guard_v1`

## Interpretation

The explicit terminal penalty made ownship-altitude failures much more expensive in the reward, but it did not create a recoverable behavior gradient fast enough. The policy continued to enter the same low-altitude failure mode, now with very negative safety rewards. Continuing this branch or validating its final bundle would waste time.

## Recommendation

Roll back to the frozen H5 candidate. The next attempt should not simply increase terminal penalties further. Prefer a diagnostic branch that changes exposure or control before another full safety-polish run, for example:

- evaluate H5 failed episodes by scenario index to identify whether BT indices or loiter indices dominate ownship-altitude losses;
- reduce dive-following incentives by lowering pursuit pressure only near low altitude rather than globally;
- add a curriculum slice that starts from the failing geometry at higher altitude margin and validates zero ownship losses before mixing back into BT.
