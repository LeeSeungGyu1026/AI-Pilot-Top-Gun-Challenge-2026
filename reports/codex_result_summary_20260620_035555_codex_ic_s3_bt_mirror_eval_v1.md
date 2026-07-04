# Codex Result Summary: codex_ic_s3_bt_mirror_eval_v1

## Classification

Finished. The expected Codex-named outputs exist:

- `AIP_LIB/DogFightEnv/Release_260529/artifacts/eval/codex_ic_s3_bt_mirror_eval_v1/codex_summary.json`
- `AIP_LIB/DogFightEnv/Release_260529/artifacts/eval/codex_ic_s3_bt_mirror_eval_v1/codex_episodes.csv`
- `AIP_LIB/DogFightEnv/Release_260529/artifacts/eval/codex_ic_s3_bt_mirror_eval_v1/codex_eval_console.log`
- `AIP_LIB/DogFightEnv/Release_260529/artifacts/eval/codex_ic_s3_bt_mirror_eval_v1/codex_eval_error.log`

## Hypothesis

codex-H1: `ic_s3_bt_v1` is stronger than the existing non-mirrored `bt_v1_check` result suggests, and the 0% win / 100% draw eval was caused by evaluation geometry mismatch. If `ic_s3_bt_v1` is evaluated against the BT target while merging the training geometry from `experiments/ic_s3_bt.yaml`, it should reach at least 70% win rate over 30 episodes, with draw rate at or below 20% and loss/crash rate at or below 10%.

## Plan

Plan artifact: `reports/codex_loop_plan_20260620_033702_codex_ic_s3_bt_mirror_eval_v1.md`

Command:

```powershell
& $py scripts\codex_run_eval.py --ownship-bundle-dir artifacts\models\team01\ic_s3_bt_v1 --episodes 30 --target-backend bt --observation-mode custom --observation-module student.my_observation --experiment-yaml experiments\ic_s3_bt.yaml --eval-name codex_ic_s3_bt_mirror_eval_v1
```

## Results

- Episodes: 30
- Win rate: 1.0
- Loss rate: 0.0
- Draw rate: 0.0
- End conditions: `target altitude below min`: 30
- Mean reward: -28.08501
- Mean steps: 1088.0

## Baseline Comparison

Existing non-Codex eval `bt_v1_check` used the same bundle against BT but did not merge the training geometry. It reported:

- Episodes: 30
- Win rate: 0.0
- Loss rate: 0.0
- Draw rate: 1.0
- End conditions: `max time out`: 30
- Mean reward: 2.9123533333333333
- Mean steps: 900.0

The mirrored Codex eval flips the result from all timeouts to all wins. This supports codex-H1 and shows the prior eval was not measuring the same distribution as the training geometry.

## Caveat

All wins were by forcing the target below minimum altitude, not by direct target-health kill. This may be valid under the local competition-aligned classifier, but it is a fragile-looking strategy unless the final server scoring treats target-grounding the same way. The next validation should stress broader spawn distributions and confirm official scoring assumptions.

## Recommendation Before Web GPT

Do not branch blindly from the non-mirrored draw result. Treat `ic_s3_bt_v1` as a promising PPO candidate on mirrored BT geometry, then ask Web GPT for literature-grounded critique and next-action advice. The user specifically asked to include related papers/references and to consider a SAC branch instead of staying only with PPO.
