# Codex RL Experiment Plan: codex_ic_s4_loiter_guard_v1

## Hypothesis

Hypothesis codex-H3: a short PPO fine-tune from `ic_s3_bt_v1` against a loiter target on the same offensive-saddle geometry, with stronger altitude shaping and modestly increased close-range pursuit pressure, will improve loiter/autopilot robustness without destroying BT performance.

Support codex-H3 if the post-run validation ladder reaches:

- loiter win rate at least 0.60,
- loiter loss/crash rate at or below 0.05,
- autopilot win rate at least 0.90,
- autopilot loss/crash rate at or below 0.05,
- mirrored BT win rate at least 0.90.

Reject codex-H3 if loiter loss/crash remains above 0.05, loiter draw remains above 0.30, or mirrored BT win rate drops below 0.90.

## Plan

- Run tag: `codex_ic_s4_loiter_guard_v1`
- Config: `AIP_LIB/DogFightEnv/Release_260529/experiments/codex_ic_s4_loiter_guard_v1.yaml`
- Source bundle: `AIP_LIB/DogFightEnv/Release_260529/artifacts/models/team01/ic_s3_bt_v1`
- Training target: loiter
- Geometry: offensive saddle `[1100, 1450] m`, aspect `[0, 30] deg`, altitude `7000 m`
- Runtime: 30 PPO iterations
- Wake interval: 20 minutes

## Key Changes Versus ic_s3_bt_v1

- `target_mode: loiter`
- `target_loiter.bank: 45.0`
- `pbrs_alt_weight: 10.0 -> 15.0`
- `safety_floor_m: 300.0 -> 450.0`
- `safety_safe_m: 900.0 -> 1200.0`
- `pursuit_dense_scale: 0.1 -> 0.16`
- `pursuit_range_m: 4000.0 -> 3500.0`
- `lr: 3.0e-4 -> 2.0e-4`

## Stop / Kill Criteria

- Do not kill for slowness alone.
- Classify stalled if `training_log.csv` does not grow for two wake cycles while the process remains alive.
- Classify failed on exceptions, missing output artifacts, repeated NaN/inf, or FDM failures.
- If crash/loss remains catastrophically high after 20 iterations and logs show no improvement, stop or ask before continuing.

## Metrics To Inspect

- `training_log.csv` row count and tail metrics
- `win_rate`, `loss_rate`, `timeout_rate`, `crash_rate`
- `reward_mean`, `ep_reward_damage`, `ep_min_distance`, `ep_wez_steps`
- action saturation and altitude penalty signals
- post-run validation ladder results

## Web GPT / SAC Note

Do not launch SAC until this stabilization run is evaluated. The user wants SAC considered, but the current blocker is robustness/scoring sensitivity in the PPO incumbent, not lack of an off-policy branch.
