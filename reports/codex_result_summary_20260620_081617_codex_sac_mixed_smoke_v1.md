# Codex Result Summary: codex_sac_mixed_smoke_v1

Created: 2026-06-20T08:16:17+09:00

## Hypothesis

Hypothesis codex-H4: SAC trained from scratch on a mixed BT/loiter target distribution with the project's custom 26-D observation and reward will show better early robustness signals than the failed PPO loiter-guard fine-tune.

Support criteria from the plan: after 40 SAC iterations, final or tail logs should show nonzero/improving win rate, final-10 loss/crash below 0.50, no fatal Ray/FDM errors, and a saved runnable bundle.

Reject criteria from the plan: SAC fails to train, produces repeated fatal errors, keeps loss/crash above 0.80 after iteration 20, or saves no usable bundle.

## Plan And Launch

- Plan: `reports/codex_loop_plan_20260620_080818_codex_sac_mixed_smoke_v1.md`
- Config: `AIP_LIB/DogFightEnv/Release_260529/experiments/codex_sac_mixed_smoke_v1.yaml`
- CWD: `AIP_LIB/DogFightEnv/Release_260529`
- PID: 13976
- Start observed: 2026-06-20T08:10:53+09:00
- End observed: 2026-06-20T08:14:41+09:00
- Command: `python train_rllib.py --algorithm sac --iterations 40 --output-name team01 --output-tag codex_sac_mixed_smoke_v1 ... --experiment-yaml experiments/codex_sac_mixed_smoke_v1.yaml`

## Final Metrics

`training_log.csv` contains 40 rows, iter 0 through iter 39. The process exited and saved a final lightweight bundle.

Tail completed episode windows:

| Iter | Episodes | Reward mean | Win | Loss | Timeout | Crash | WEZ steps |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 20 | 6 | -166.3201 | 0.0 | 0.0 | 0.0 | 1.0 | 0.0 |
| 22 | 7 | -163.7632 | 0.0 | 0.0 | 0.0 | 1.0 | 0.0 |
| 28 | 8 | -169.8790 | 0.0 | 0.0 | 0.0 | 1.0 | 0.0 |
| 31 | 9 | -170.4914 | 0.0 | 0.0 | 0.0 | 1.0 | 0.0 |
| 37 | 10 | -171.4003 | 0.0 | 0.0 | 0.0 | 1.0 | 0.0 |

Last row, iter 39:

- sampled_steps: 4142
- episodes: 10
- actor_loss: -14.0599
- critic_loss: 1.0973
- alpha_loss: -2.5767
- alpha: 0.6783
- replay_buffer_size: 4142

## Artifacts

- Logs: `AIP_LIB/DogFightEnv/Release_260529/artifacts/logs/team01/codex_sac_mixed_smoke_v1`
- Training CSV: `AIP_LIB/DogFightEnv/Release_260529/artifacts/logs/team01/codex_sac_mixed_smoke_v1/training_log.csv`
- Final bundle: `AIP_LIB/DogFightEnv/Release_260529/artifacts/models/team01/codex_sac_mixed_smoke_v1`
- Periodic bundles: `bundle_000010`, `bundle_000020`, `bundle_000030`, `bundle_000040`
- Training record: `AIP_LIB/DogFightEnv/Release_260529/artifacts/records/team01/codex_sac_mixed_smoke_v1`

## Decision

Reject codex-H4.

The SAC training path itself is viable: Ray/RLlib ran to completion, SAC losses stayed numeric, and a final lightweight bundle was saved. The policy signal is not viable yet: after iteration 20, all completed episode windows still have 0.0 win rate and 1.0 crash rate, with repeated `ownship altitude below min` terminations and no WEZ improvement.

Do not run a validation ladder for this SAC bundle as an incumbent candidate. Keep the bundle only as a forensic smoke artifact.

Recommended next run: roll back to `artifacts/models/team01/ic_s3_bt_v1` and use a less destructive mixed-target PPO branch rather than a loiter-only fine-tune or longer from-scratch SAC. The branch should preserve the BT anchor, reduce update size, and introduce autopilot/loiter cases gradually so altitude behavior can be corrected without erasing the proven BT behavior.
