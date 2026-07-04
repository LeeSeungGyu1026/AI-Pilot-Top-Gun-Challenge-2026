# Codex Eval Plan: codex_ic_s4_mixed_anchor_guard_validation_v1

## Hypothesis

Hypothesis codex-H5-eval: `codex_ic_s4_mixed_anchor_guard_v1` improves robustness relative to the failed loiter-only PPO branch while preserving BT behavior from `ic_s3_bt_v1`.

Support if:

- BT win rate >= 0.90
- autopilot win rate >= 0.90 with loss/crash <= 0.05
- loiter win rate >= 0.50 with draw <= 0.40 and loss/crash <= 0.05

Reject if BT drops below 0.90 or any validation slice has loss/crash above 0.05.

## Plan

- Eval run tag: `codex_ic_s4_mixed_anchor_guard_validation_v1`
- Bundle: `AIP_LIB/DogFightEnv/Release_260529/artifacts/models/team01/codex_ic_s4_mixed_anchor_guard_v1`
- Experiment YAML: `AIP_LIB/DogFightEnv/Release_260529/experiments/codex_ic_s4_mixed_anchor_guard_v1.yaml`
- Script: `AIP_LIB/DogFightEnv/Release_260529/scripts/codex_eval_ladder_s4_mixed_anchor_guard_v1.py`
- Cases:
  - BT: 30 episodes
  - autopilot: 20 episodes
  - loiter: 30 episodes
- Expected runtime: 15-30 minutes.
- Wake interval: 15 minutes.

## Decision After Completion

- If all gates pass, freeze as a PPO stabilization candidate.
- If BT collapses or autopilot/loiter loss remains high, reject H5 and roll back to `ic_s3_bt_v1`.
- If results are mixed, use the weakest case logs before selecting a next branch.
