# codex_ic_s3_v12_level_rear_gunnery_v1 plan

Date: 2026-07-04

## Hypothesis

`codex-H8`: If the v11 policy is fine-tuned against a straight level target from a rear, near-WEZ spawn, then it will learn stable range/aim control and produce nonzero `target destroyed` wins before returning to BT.

Support criteria:

- At or before iter 20: nonzero `ep_wez_steps` and positive `ep_reward_damage` in tail rows.
- At or before iter 40: at least one `target destroyed` in engagement logs or training summary.
- Tail crash rate stays <= 0.10 after the reseed transient.

Reject criteria:

- Tail rows continue to show 0 true WEZ/damage and 0 wins against the easy level target.
- Crash rate remains > 0.20 after iter 20.
- Reward rises while `ep_reward_damage` stays near zero, indicating shaping-only farming.

## Training Setup

- Run tag: `codex_ic_s3_v12_level_rear_gunnery_v1`
- Seed bundle: `artifacts/models/team01/ic_s3_bt_v11/bundle_000080`
- Target: `autopilot`, straight and level
- Spawn: rear offensive saddle, 550-750 m, aspect 0-8 deg
- Speeds: target 250 m/s, ownship 260 m/s to reduce violent closure/overshoot
- True WEZ: unchanged 2 deg, 152.4-914.4 m
- Reward: v11 scale fix preserved; damage pressure increased moderately for the easy gunnery curriculum
- Iterations: 80

## Operational Notes

- The previous v11 process was explicitly stopped by user request before launch.
- Do not overwrite any champion artifact.
- Monitor with `tools/train_monitor.py` after launch.
