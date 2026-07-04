# codex pre-v12 diagnostic plan

Date: 2026-07-04

Constraint:

- Do not touch the currently running `ic_s3_bt_v11` training process.
- Do not launch any v12 training experiment.
- Use only read-only evaluation from stable `ic_s3_bt_v11/bundle_000060`.
- Write new artifacts only under names containing `codex`.

External-advisor requirements translated into experiments:

1. Straight/level target gunnery sanity check
   - Eval: `codex_pre_v12_inband_autopilot_v11_bundle60`
   - YAML: `experiments/codex_pre_v12_inband_autopilot_eval.yaml`
   - Purpose: decide whether the policy can kill an easy level target from near-WEZ geometry.

2. Timeout/reward farming check
   - Eval: `codex_pre_v12_wide_autopilot_v11_bundle60`
   - YAML: `experiments/ic_s3_bt_v11.yaml`
   - Target: autopilot
   - Purpose: separate long-range closure failure from target evasive behavior and inspect reward components by end condition.

3. BT geometry and overshoot/action-jitter check
   - Eval: `codex_pre_v12_bt_v11_bundle60`
   - YAML: `experiments/ic_s3_bt_v11.yaml`
   - Target: BT
   - Purpose: measure time-in-band, true-cone steps, overshoot rate, band-entry closure, action jitter, end-condition distribution, and reward component mix under the actual opponent.

Primary metrics:

- real win rate: `target_health <= 0`
- forced-ground rate: `target altitude below min`
- time in true range band: 152.4m to 914.4m
- time in band with ATA <= 10deg
- true-cone steps: in band and ATA <= 1deg
- overshoot rate: range < 152.4m
- band-entry closure rate
- action delta L1
- reward components: step, pursuit, damage, safety, terminal
