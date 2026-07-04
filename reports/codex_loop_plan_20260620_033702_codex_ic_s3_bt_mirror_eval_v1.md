# Codex RL Experiment Plan: codex_ic_s3_bt_mirror_eval_v1

## Hypothesis

Hypothesis codex-H1: `ic_s3_bt_v1` is stronger than the existing `bt_v1_check` result suggests, and the 0% win / 100% draw eval was caused by evaluation geometry mismatch. If `ic_s3_bt_v1` is evaluated against the BT target while merging the training geometry from `experiments/ic_s3_bt.yaml`, it should reach at least 70% win rate over 30 episodes, with draw rate at or below 20% and loss/crash rate at or below 10%.

Reject codex-H1 if mirrored BT eval win rate is below 70%, if draw rate remains above 20%, or if loss/crash rate exceeds 10%.

## Baseline

- Source bundle: `artifacts/models/team01/ic_s3_bt_v1`
- Source experiment YAML: `experiments/ic_s3_bt.yaml`
- Training tail: iterations 92-99 reported `win_rate=1.0`, `loss_rate=0.0`, `timeout_rate=0.0`, `crash_rate=0.0`.
- Existing non-Codex eval: `artifacts/eval/bt_v1_check` reported 30/30 draws, `win_rate=0.0`, `draw_rate=1.0`, all `max time out`.

## Run

- Run tag: `codex_ic_s3_bt_mirror_eval_v1`
- Working directory: `AIP_LIB/DogFightEnv/Release_260529`
- Codex wrapper: `scripts/codex_run_eval.py`
- Output directory: `artifacts/eval/codex_ic_s3_bt_mirror_eval_v1`
- Expected output files: `codex_summary.json`, `codex_episodes.csv`
- Console log: `artifacts/eval/codex_ic_s3_bt_mirror_eval_v1/codex_eval_console.log`
- PID file: `artifacts/eval/codex_ic_s3_bt_mirror_eval_v1/codex_eval_pid.txt`

Command:

```powershell
& $py scripts\codex_run_eval.py --ownship-bundle-dir artifacts\models\team01\ic_s3_bt_v1 --episodes 30 --target-backend bt --observation-mode custom --observation-module student.my_observation --experiment-yaml experiments\ic_s3_bt.yaml --eval-name codex_ic_s3_bt_mirror_eval_v1
```

## Runtime And Wake

- Expected runtime: roughly 5-10 minutes based on the existing 30 episode eval at about 9-10 seconds per episode.
- Heartbeat interval: 15 minutes.
- Healthy-running signal: PID exists and `codex_eval_console.log` is growing or has recent episode lines.
- Finished signal: process has exited and `codex_summary.json` plus `codex_episodes.csv` exist.

## Metrics To Inspect

- `win_rate`, `loss_rate`, `draw_rate`
- `end_conditions`
- `mean_reward`, `mean_steps`
- episode-level timeout/crash patterns in `codex_episodes.csv`

## Stop / Kill Criteria

- Do not kill only for slowness.
- Classify stalled if the PID is still alive and `codex_eval_console.log` has no new episode output for two heartbeat cycles.
- Classify failed if the process exits without `codex_summary.json`, or if the log contains an exception traceback.
- Ask the user before terminating any ambiguous process.

## Web GPT Audit

After completion, write a Codex result summary locally. The user approved asking Web GPT for literature-grounded insight for this project during the current loop, including looking for related papers and advising whether SAC is worth trying rather than staying with PPO.

The audit prompt should ask Web GPT to:

- Search for and cite related papers or reliable technical references on close-range air-combat RL, pursuit/evasion, curriculum learning, self-play, sparse terminal rewards, and continuous-control algorithms.
- Compare PPO versus SAC for this environment's symptoms: training-log success versus eval timeout/draw mismatch, continuous 4-D control, deterministic-ish pursuit behavior, reward shaping, and sample efficiency.
- Recommend whether the next Codex branch should try SAC, and if so, specify a concrete SAC YAML plan seeded from the best available bundle or trained from scratch.
- Keep private workspace details minimal: include only the hypothesis, summarized config choices, run metrics, and failure/success modes needed for the audit.
