# Codex RL Experiment Plan: codex_ic_s4_mixed_anchor_guard_v1

## Hypothesis

Hypothesis codex-H5: a conservative PPO fine-tune from `ic_s3_bt_v1` with mostly-BT mixed initial scenarios, stronger altitude guard, lower LR, and tighter PPO clip will improve loiter/autopilot robustness without erasing the proven BT behavior.

Support codex-H5 if the post-run validation ladder shows:

- BT win rate >= 0.90
- autopilot win rate >= 0.90 with loss/crash <= 0.05
- loiter win rate >= 0.50 with draw <= 0.40 and loss/crash <= 0.05

Reject codex-H5 if training tail collapses to win_rate < 0.50 or crash/loss > 0.30 after iteration 10, or if validation drops BT below 0.90.

## Plan

- Run tag: `codex_ic_s4_mixed_anchor_guard_v1`
- Config: `AIP_LIB/DogFightEnv/Release_260529/experiments/codex_ic_s4_mixed_anchor_guard_v1.yaml`
- Source bundle: `AIP_LIB/DogFightEnv/Release_260529/artifacts/models/team01/ic_s3_bt_v1`
- Algorithm: PPO, continuing the incumbent policy family rather than extending failed from-scratch SAC.
- Scenario distribution: `ref_old_random` with duplicated BT indices and two loiter indices, about 13 percent loiter exposure.
- Guardrails: lower LR `1.0e-4`, tighter `clip_param: 0.1`, `pbrs_alt_weight: 12.0`, floor `450m`, safe altitude `1200m`.
- Runtime: 20 iterations, 4 env runners, lightweight bundle every 10 iterations.
- Wake interval: 15 minutes.

## Metrics To Inspect

- `training_log.csv` row count and tail metrics
- `win_rate`, `loss_rate`, `timeout_rate`, `crash_rate`
- `ep_reward_safety`, `ep_altitude_penalty_steps`, `ep_wez_steps`, `ep_min_distance`
- PPO stats: `policy_loss`, `vf_loss`, `entropy`, `kl`, `clip_frac`
- saved bundle presence

## Kill / Stop Criteria

- Do not kill for slow rows alone.
- Classify stalled if `training_log.csv` has no row growth for two wake cycles while the PID remains alive.
- Stop or ask if repeated fatal Ray/FDM errors appear.
- Stop if, after iteration 10, completed metric windows still show crash/loss above 0.30 with no improving trend.

## Decision After Completion

- If training tail is viable, run a Codex validation ladder against BT/autopilot/loiter.
- If validation passes, freeze as PPO stabilization candidate.
- If validation fails BT or altitude safety, roll back to `ic_s3_bt_v1` and diagnose reward/initial-state geometry before another training branch.
