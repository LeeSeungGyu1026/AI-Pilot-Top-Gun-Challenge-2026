# Codex RL Experiment Plan: codex_ic_s5_zero_altitude_guard_v1

## Hypothesis

Hypothesis codex-H6: a very small PPO safety-polish fine-tune from frozen H5, using an explicit Codex reward wrapper for ownship-altitude failures, will remove ownship-altitude losses across BT/autopilot/loiter validation while preserving the H5 stabilization candidate's useful win rates.

Support codex-H6 if validation has:

- zero `ownship altitude below min` end conditions across all validation cases
- zero `FDM Update Fail` end conditions across all validation cases
- BT win rate >= 0.90
- autopilot win rate >= 0.90
- loiter win rate >= 0.70 and draw rate <= 0.25

Reject codex-H6 if any ownship-altitude/FDM failure appears in validation, or if BT drops below 0.90.

## Plan

- Run tag: `codex_ic_s5_zero_altitude_guard_v1`
- Config: `AIP_LIB/DogFightEnv/Release_260529/experiments/codex_ic_s5_zero_altitude_guard_v1.yaml`
- Reward wrapper: `AIP_LIB/DogFightEnv/Release_260529/student/codex_reward_zero_altitude.py`
- Source bundle: `AIP_LIB/DogFightEnv/Release_260529/artifacts/models/team01/codex_freeze_ic_s4_mixed_anchor_guard_v1_20260620_0853`
- Algorithm: PPO, small safety-polish update only.
- Runtime: 15 iterations, 4 env runners, lightweight bundle every 5 iterations.
- Wake interval: 15 minutes.

## Changes Versus H5

- Use Codex-owned reward wrapper `student.codex_reward_zero_altitude`.
- Add extra terminal penalty for `ownship altitude below min` and `FDM Update Fail`.
- Raise altitude shaping to `pbrs_alt_weight: 30.0`, `safety_floor_m: 900.0`, `safety_safe_m: 2400.0`.
- Add mild live low-altitude guard below 1800 m.
- Reduce pursuit dense scale from 0.12 to 0.08.
- Lower PPO LR from `1.0e-4` to `5.0e-5` and clip from `0.1` to `0.05`.

## Metrics To Inspect

- `training_log.csv` row count and tail metrics
- `crash_rate`, `loss_rate`, `timeout_rate`
- `ep_reward_safety`, `ep_altitude_penalty_steps`
- end-condition text in engagement replay logs
- saved lightweight bundles

## Kill / Stop Criteria

- Do not kill before iteration 5 unless fatal Ray/FDM errors repeat.
- Stop or ask if post-iter5 crash remains above 0.20 with no downward trend.
- Stop if BT-like target-grounding disappears entirely and timeout/draw rises sharply.

## Decision After Completion

- If training tail is viable, launch `codex_ic_s5_zero_altitude_guard_validation_v1`.
- If validation has zero ownship-altitude/FDM failures and preserves gates, freeze as the next safety candidate.
- If validation still has any ownship-altitude loss, reject H6 and inspect the failing episodes before another branch.
