# Codex Result Summary: codex_ic_s5_h5_altitude_failure_map_v1

Created: 2026-06-20T16:30:25+09:00

## Hypothesis

Hypothesis codex-H7a: ownship-altitude losses in frozen H5 are concentrated in a small set of target/scenario slices.

Support condition: per-scenario evaluation should identify localized failing slices suitable for a narrow curriculum fine-tune.

Reject condition: failures appear broadly across most BT/loiter/autopilot slices, implying a general low-altitude pursuit or flight-envelope issue.

## Baseline

- Bundle: `AIP_LIB/DogFightEnv/Release_260529/artifacts/models/team01/codex_freeze_ic_s4_mixed_anchor_guard_v1_20260620_0853`
- Plan: `reports/codex_loop_plan_20260620_153223_codex_ic_s5_h5_altitude_failure_map_v1.md`
- Script: `AIP_LIB/DogFightEnv/Release_260529/scripts/codex_eval_h5_altitude_failure_map_v1.py`
- Eval output: `AIP_LIB/DogFightEnv/Release_260529/artifacts/eval/codex_ic_s5_h5_altitude_failure_map_v1`

## Results

| Target | Scenario | Episodes | Win | Loss | Draw | Ownship Alt | FDM Fail | Timeouts | Mean Steps |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| BT | 0 | 30 | 0.9333 | 0.0667 | 0.0000 | 2 | 0 | 0 | 625.57 |
| BT | 1 | 30 | 0.7333 | 0.2667 | 0.0000 | 8 | 0 | 0 | 633.50 |
| BT | 2 | 30 | 0.7667 | 0.2333 | 0.0000 | 7 | 0 | 0 | 604.70 |
| BT | 3 | 30 | 0.9667 | 0.0333 | 0.0000 | 1 | 0 | 0 | 590.37 |
| BT | 4 | 30 | 0.9000 | 0.1000 | 0.0000 | 3 | 0 | 0 | 650.57 |
| Loiter | 0 | 30 | 1.0000 | 0.0000 | 0.0000 | 0 | 0 | 0 | 1.00 |
| Loiter | 1 | 30 | 1.0000 | 0.0000 | 0.0000 | 0 | 0 | 0 | 1.00 |
| Loiter | 2 | 30 | 1.0000 | 0.0000 | 0.0000 | 0 | 0 | 0 | 1.00 |
| Loiter | 3 | 30 | 1.0000 | 0.0000 | 0.0000 | 0 | 0 | 0 | 1.00 |
| Loiter | 4 | 30 | 1.0000 | 0.0000 | 0.0000 | 0 | 0 | 0 | 1.00 |
| Loiter | 5 | 30 | 0.0000 | 0.2667 | 0.7333 | 8 | 0 | 22 | 2658.67 |
| Loiter | 6 | 30 | 0.0000 | 0.5000 | 0.5000 | 15 | 0 | 15 | 2447.37 |
| Loiter | 7 | 30 | 0.0000 | 0.4333 | 0.5667 | 13 | 0 | 17 | 2621.10 |
| Autopilot | mixed | 20 | 0.9000 | 0.1000 | 0.0000 | 2 | 0 | 0 | 191.65 |

Totals:

- Episodes: 410
- Ownship altitude below min: 59
- FDM Update Fail: 0

## Interpretation

H7a is partially rejected. The failures are not confined to a tiny handful of cases:

- all BT indices had at least one ownship-altitude loss;
- BT indices 1 and 2 were especially weak;
- loiter indices 0-4 were perfectly clean but indices 5-7 were severe;
- autopilot mixed was no longer clean at 2/20 ownship-altitude losses.

This points to a broad low-altitude pursuit / flight-envelope problem under harder geometry, not a single bad random seed. It also confirms that H6's harsh terminal penalty was the wrong mechanism: the next branch needs a learnable altitude recovery gradient and controlled exposure, not larger punishment.

## Decision

Launch a cautious H7b training branch:

- Run tag: `codex_ic_s5_pbrs_altitude_curriculum_v1`
- Start from frozen H5.
- Use `student.my_reward`, not `student.codex_reward_zero_altitude`.
- Train on all failing slices: BT 0-4, loiter 5-7, plus a small clean anchor dose.
- Use moderate potential-based altitude shaping and reduced pursuit dense pressure.
- Stop early if post-iter5 crash/loss remains high with no downward trend.

Do not launch SAC immediately. The failure is broad enough that a staged SAC/HSAC branch remains useful, but the faster incumbent-repair path is a conservative PBRS altitude curriculum first.
