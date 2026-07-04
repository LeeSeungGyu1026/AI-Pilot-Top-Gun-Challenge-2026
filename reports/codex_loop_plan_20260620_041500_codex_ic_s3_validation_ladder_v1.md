# Codex RL Experiment Plan: codex_ic_s3_validation_ladder_v1

## Hypothesis

Hypothesis codex-H2: `ic_s3_bt_v1` is a promising PPO incumbent, but its apparent strength is scoring-sensitive because all mirrored BT wins in `codex_ic_s3_bt_mirror_eval_v1` were target-grounding wins. A small validation ladder should show whether the policy is robust across evaluation geometry and target modes before launching SAC.

Support codex-H2 if:

- mirrored BT long eval win rate is at least 0.90,
- no validation slice has loss/crash rate above 0.05,
- non-mirrored BT remains materially worse than mirrored BT, confirming geometry sensitivity,
- autopilot and loiter slices do not collapse.

Reject or pause if any slice fails to produce Codex summary outputs, if ownship losses/crashes exceed 0.05 in any slice, or if mirrored BT long eval drops below 0.90.

## Run

- Run tag: `codex_ic_s3_validation_ladder_v1`
- Script: `AIP_LIB/DogFightEnv/Release_260529/scripts/codex_eval_ladder.py`
- Source bundle: `AIP_LIB/DogFightEnv/Release_260529/artifacts/models/team01/ic_s3_bt_v1`
- Output directory: `AIP_LIB/DogFightEnv/Release_260529/artifacts/eval/codex_ic_s3_validation_ladder_v1`
- Manifest: `codex_ladder_manifest.json`
- Summary: `codex_ladder_summary.md`
- Console log: `codex_ladder_console.log`
- Error log: `codex_ladder_error.log`
- PID file: `codex_ladder_pid.txt`

## Cases

1. `codex_ic_s3_bt_nomirror_eval_v1`: 30 episodes, BT target, no experiment YAML.
2. `codex_ic_s3_bt_mirror_long_eval_v1`: 50 episodes, BT target, `experiments/ic_s3_bt.yaml`.
3. `codex_ic_s3_autopilot_eval_v1`: 20 episodes, autopilot target, `experiments/ic_s3_bt.yaml`.
4. `codex_ic_s3_loiter_eval_v1`: 20 episodes, loiter target, `experiments/ic_s3_bt.yaml`.

## Expected Runtime

Roughly 25-45 minutes, based on the previous 30-episode mirrored BT eval completing in about 8 minutes.

Heartbeat interval: 20 minutes.

## Metrics

- `win_rate`, `loss_rate`, `draw_rate`
- `end_conditions`
- `mean_reward`, `mean_steps`
- Per-case return code and summary file presence

## Stop / Kill Criteria

- Do not kill for slowness alone.
- Classify stalled if the PID is alive and `codex_ladder_manifest.json` plus logs have no modification for two wake cycles.
- Classify failed if a case exits nonzero or lacks `codex_summary.json`.
- Ask before terminating an ambiguous process.

## Decision After Completion

- If the ladder passes, freeze `ic_s3_bt_v1` as a PPO incumbent and prepare a SAC smoke branch: copy `experiments/ic_s3_bt.yaml` to `experiments/codex_ic_s3_sac_smoke_v1.yaml`, change `algo.name` to `sac`, remove the PPO `init_bundle`, use SAC MLP/replay settings, run 30-50 iterations, and evaluate with the same ladder.
- If the ladder fails, diagnose the weakest slice before launching SAC.
