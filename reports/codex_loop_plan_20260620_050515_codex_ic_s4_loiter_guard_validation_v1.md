# Codex RL Experiment Plan: codex_ic_s4_loiter_guard_validation_v1

## Hypothesis

Hypothesis codex-H3-eval: the `codex_ic_s4_loiter_guard_v1` PPO fine-tune improved loiter/autopilot robustness versus `ic_s3_bt_v1` while preserving BT performance.

Support if:

- BT win rate >= 0.90.
- Autopilot win rate >= 0.90 and loss/crash rate <= 0.05.
- Loiter win rate >= 0.60, draw rate <= 0.30, and loss/crash rate <= 0.05.

Reject if any target slice misses those gates.

## Run

- Run tag: `codex_ic_s4_loiter_guard_validation_v1`
- Script: `AIP_LIB/DogFightEnv/Release_260529/scripts/codex_eval_ladder_s4_loiter_guard_v1.py`
- Bundle: `AIP_LIB/DogFightEnv/Release_260529/artifacts/models/team01/codex_ic_s4_loiter_guard_v1`
- Experiment YAML for eval geometry: `AIP_LIB/DogFightEnv/Release_260529/experiments/codex_ic_s4_loiter_guard_v1.yaml`
- Output directory: `AIP_LIB/DogFightEnv/Release_260529/artifacts/eval/codex_ic_s4_loiter_guard_validation_v1`
- Manifest: `codex_ladder_manifest.json`
- Summary: `codex_ladder_summary.md`

## Cases

1. `codex_ic_s4_loiter_guard_bt_eval_v1`: 30 episodes, BT target.
2. `codex_ic_s4_loiter_guard_autopilot_eval_v1`: 20 episodes, autopilot target.
3. `codex_ic_s4_loiter_guard_loiter_eval_v1`: 30 episodes, loiter target.

## Expected Runtime

Roughly 15-30 minutes.

Heartbeat interval: 15 minutes.

## Decision

- If gates pass, freeze `codex_ic_s4_loiter_guard_v1` as a PPO stabilization candidate and then consider a SAC branch.
- If gates fail, do not launch SAC immediately; compare against the prior ladder and either adjust the loiter fine-tune or branch to a more mixed target distribution.
