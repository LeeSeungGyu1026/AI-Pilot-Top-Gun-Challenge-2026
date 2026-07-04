# Codex Loop Plan: codex_ic_s5_pbrs_altitude_curriculum_v1

Created: 2026-06-20T16:36:02+09:00

## Hypothesis

Hypothesis codex-H7b: a conservative PPO fine-tune from frozen H5 using moderate potential-based altitude shaping and controlled exposure to H7a failing slices will reduce ownship-altitude losses without collapsing BT/autopilot/loiter win rates.

Reject if after iteration 5 the completed-episode crash/loss rate remains above 0.30 with no downward trend, or if win rate stays near 0.0 while ownship-altitude failures dominate.

## Evidence From H7a

H7a result summary: `reports/codex_result_summary_20260620_163025_codex_ic_s5_h5_altitude_failure_map_v1.md`

H7a found:

- BT idx0-4 all had ownship-altitude losses: 2, 8, 7, 1, 3 per 30 episodes.
- Loiter idx0-4 were clean.
- Loiter idx5-7 were severe: 8, 15, 13 per 30 episodes.
- Autopilot mixed had 2/20 ownship-altitude losses.
- FDM Update Fail was 0.

This means the next branch should not target one tiny case. It should repair low-altitude pursuit behavior across all BT slices and the hard loiter slices.

## Literature Reference

Local literature pack: `reports/codex_rl_literature_20260620/codex_literature_index_20260620.md`

Relevant takeaways:

- Ng et al. reward shaping: use potential-based shaping for safety gradients rather than large non-potential terminal penalties.
- GAE/PPO: use conservative LR/clip for fine-tuning an incumbent.
- Curriculum RL survey: oversample failing slices, but keep anchor cases to avoid catastrophic forgetting.
- Air-combat HSAC/self-play papers: staged exposure is preferred over broad mixed randomization when failures are geometry-dependent.

## Training Plan

Run tag: `codex_ic_s5_pbrs_altitude_curriculum_v1`

Source bundle:

- `artifacts/models/team01/codex_freeze_ic_s4_mixed_anchor_guard_v1_20260620_0853`

Config:

- `AIP_LIB/DogFightEnv/Release_260529/experiments/codex_ic_s5_pbrs_altitude_curriculum_v1.yaml`

Core choices:

- Algorithm remains PPO for incumbent repair.
- Reward module is `student.my_reward`.
- No `student.codex_reward_zero_altitude`.
- No extra large terminal altitude penalty.
- `pbrs_gamma: 1.0`
- `pbrs_alt_weight: 18.0`
- `safety_floor_m: 650.0`
- `safety_safe_m: 1800.0`
- `pursuit_dense_scale: 0.06`
- Conservative PPO:
  - `lr: 3.0e-5`
  - `clip_param: 0.04`
  - `iterations: 12`

Training exposure:

- heavily include BT idx1, idx2, loiter idx6, and loiter idx7;
- include all BT idx0-4;
- include loiter idx5-7;
- retain a small clean loiter idx0-4 anchor dose.

## Metrics

Inspect during training:

- `crash_rate`
- `loss_rate`
- `win_rate`
- reward mean
- safety reward, if present
- final bundle existence

## Stop Criteria

- If iter >= 5 and crash/loss stays above 0.30 with no downward trend, reject before validation.
- If win rate stays 0.0 and reward remains strongly negative, reject before validation.
- If fatal Ray/FDM errors repeat, stop and inspect.

## Validation Gates

Only validate if training tail is viable.

Hard validation gates:

- zero `ownship altitude below min`
- zero `FDM Update Fail`
- BT win >= 0.90
- autopilot win >= 0.90
- loiter win >= 0.70 and draw <= 0.25

## Wakeup

Use a 15-minute heartbeat while training.

On completion, write a result summary and run a validation ladder only if tail metrics are viable.
