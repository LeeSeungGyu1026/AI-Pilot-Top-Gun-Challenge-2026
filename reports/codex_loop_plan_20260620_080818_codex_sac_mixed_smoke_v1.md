# Codex RL Experiment Plan: codex_sac_mixed_smoke_v1

## Hypothesis

Hypothesis codex-H4: SAC trained from scratch on a mixed BT/loiter target distribution with the project's custom 26-D observation and reward will show better early robustness signals than the failed PPO loiter-guard fine-tune.

Support codex-H4 if, after 40 SAC iterations, the final or tail training logs show:

- nonzero and improving win rate,
- crash/loss rate below 0.50 in the final 10 iterations,
- no NaN/inf or fatal Ray/FDM errors,
- a saved lightweight bundle that can run through a Codex validation ladder.

Reject codex-H4 if SAC fails to train, produces repeated fatal errors, keeps loss/crash above 0.80 after iteration 20, or saves no usable bundle.

## Plan

- Run tag: `codex_sac_mixed_smoke_v1`
- Config: `AIP_LIB/DogFightEnv/Release_260529/experiments/codex_sac_mixed_smoke_v1.yaml`
- Source strategy: train SAC from scratch; do not initialize from PPO weights.
- Target distribution: mixed `ref_old_random`, indices 0-4 BT and 5-7 loiter.
- Runtime: 40 SAC iterations, 2 env runners, replay capacity 50000.
- Wake interval: 20 minutes.

## Metrics To Inspect

- `training_log.csv` row count and tail metrics
- `win_rate`, `loss_rate`, `timeout_rate`, `crash_rate`
- `reward_mean`, `ep_reward_damage`, `ep_wez_steps`, `ep_min_distance`
- SAC stats: `actor_loss`, `critic_loss`, `alpha_loss`, `alpha`, `replay_buffer_size`
- saved bundle presence

## Kill / Stop Criteria

- Do not kill for slowness alone.
- Classify stalled if `training_log.csv` has no row growth for two wake cycles while the PID remains alive.
- Kill or stop if repeated fatal exceptions, NaNs/inf, missing replay buffer, or no usable bundle.
- If loss/crash remains above 0.80 after iteration 20 and no improvement trend exists, stop or ask before continuing.

## Decision After Completion

- If SAC smoke looks viable, run a Codex validation ladder against BT/autopilot/loiter and compare to `ic_s3_bt_v1`.
- If SAC smoke fails, roll back to `ic_s3_bt_v1` and design a less destructive mixed-target PPO branch instead of fine-tuning solely on loiter.
