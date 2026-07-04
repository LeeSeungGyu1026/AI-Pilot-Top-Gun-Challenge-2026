# Codex Loop Plan: codex_ic_s5_h5_altitude_failure_map_v1

Created: 2026-06-20T15:32:23+09:00

## Hypothesis

Hypothesis codex-H7a: the remaining ownship-altitude losses in the frozen H5 candidate are concentrated in a small set of target/scenario slices. If true, per-scenario evaluation will identify those slices so the next training branch can use a narrow curriculum instead of a broad harsh-penalty fine-tune.

Reject H7a if ownship-altitude/FDM failures appear broadly across most BT and loiter slices, because that would imply a general flight-envelope defect rather than a localized curriculum gap.

## Baseline

- Bundle: `artifacts/models/team01/codex_freeze_ic_s4_mixed_anchor_guard_v1_20260620_0853`
- Source config: `experiments/codex_ic_s4_mixed_anchor_guard_v1.yaml`
- Literature reference pack: `reports/codex_rl_literature_20260620/codex_literature_index_20260620.md`
- Prior result:
  - H5 validation: BT had 3/30 ownship-altitude losses; loiter had 1/30; autopilot had 0/20.
  - H6 harsh terminal-penalty PPO polish collapsed, with tail-5 crash rate 0.771.

## Diagnostic Plan

Create a Codex evaluation ladder script:

- Script: `scripts/codex_eval_h5_altitude_failure_map_v1.py`
- Run tag: `codex_ic_s5_h5_altitude_failure_map_v1`
- Output: `artifacts/eval/codex_ic_s5_h5_altitude_failure_map_v1`
- Generated per-case YAMLs: `experiments/codex_generated_ic_s5_h5_altitude_failure_map_v1`

Cases:

- BT target, scenario indices 0 through 4, 30 episodes each.
- Loiter target, scenario indices 0 through 7, 30 episodes each.
- Autopilot target, original H5 mixed scenario list, 20 episodes as a sanity control.

The ladder writes a manifest and summary after every case so heartbeat wakeups can classify progress.

## Metrics

Primary:

- `ownship altitude below min` count by case
- `FDM Update Fail` count by case

Secondary:

- win/loss/draw rate
- timeout count
- mean steps
- mean reward

## Decision Rules

If failures are concentrated:

- proceed to `codex_ic_s5_pbrs_altitude_curriculum_v1`
- oversample only failing slices plus BT anchors
- keep `student.my_reward`
- use moderate potential-based altitude shaping rather than terminal-punishment escalation

If failures are broad:

- do not launch PPO polish
- prepare a broader control/observation diagnosis or staged SAC/HSAC branch

If there are zero ownship-altitude/FDM failures in this diagnostic:

- rerun a larger confirmatory validation before training
- do not train just to train

## Runtime / Heartbeat

Expected runtime: about 30 to 45 minutes.

Heartbeat: every 15 minutes while running. On wake, inspect:

- `artifacts/eval/codex_ic_s5_h5_altitude_failure_map_v1/codex_ladder_pid.txt`
- `codex_ladder_console.log`
- `codex_ladder_error.log`
- `codex_ladder_manifest.json`
- `codex_ladder_summary.md`
- per-case `codex_ladder_*_stdout.log` and `codex_ladder_*_stderr.log`

## Stop Criteria

- Stop immediately if the process exits with a nonzero code.
- Stop if logs stall for two heartbeat cycles with no manifest update.
- Do not kill merely because the ladder is slow; eval cases can vary heavily by timeout frequency.

## Web GPT Audit Prompt

After H7a completes, ask Web GPT to critique whether the failure distribution supports a narrow PBRS/curriculum PPO repair or a staged SAC/HSAC branch. Include only summarized metrics and cite the local literature pack topics, not private source code.
