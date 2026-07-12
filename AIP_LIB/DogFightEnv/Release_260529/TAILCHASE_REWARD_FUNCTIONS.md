# Tail-Chase Reward Function Summary

Last updated: 2026-07-12

This note summarizes the reward modules used for the straight-BT tail-chase SAC
pipeline.

## Current Best Reward

The current best model was trained with:

```text
reward_module: student.my_reward_stage3_kill
experiment: experiments/tailchase_s3_b050_stabilize_micro_sac_v1.yaml
bundle: artifacts/models/team01/tailchase_s3_b050_stabilize_micro_sac_v1/bundle_000005
```

Use it at runtime/eval with:

```text
experiments/eval_tailchase_s3_b050_late_emergency.yaml
```

Important distinction:

- `student.my_reward_stage3_kill` is the training reward.
- `eval_tailchase_s3_b050_late_emergency.yaml` is not a reward function. It is
  runtime action postprocess/safety logic that prevents late altitude losses.

Fixed-seed benchmark:

```text
seed=260529, episodes=30
win 40% / loss 0% / draw 60%
end: target destroyed 12, max time out 18
```

## Reward Stack

Most tail-chase rewards are wrappers around `student.my_reward_table1`.

```text
my_reward_table1
  -> my_reward_stage1_survival
  -> my_reward_stage2_pursuit
       -> my_reward_stage2_anchor
  -> my_reward_stage3_kill
       -> my_reward_stage3_finish
       -> my_reward_stage3_reacquire
       -> my_reward_stage3_execute
```

## Base Reward: `student.my_reward_table1`

Purpose: Table-I-style air-combat shaping adapted to this environment.

Main components returned in `components`:

- `survival`: small per-step survival bonus.
- `step`: time/step penalty.
- `adverse_angle`: aspect-angle term.
- `track_angle`: nose-to-target angle term.
- `relative_position`: rear-position geometry term.
- `closure`: positive when closing distance in useful geometry.
- `gunsnap_blue`: ownship gun-snapshot opportunity.
- `gunsnap_red`: opponent gun-snapshot penalty.
- `deck`: low deck/ground penalty.
- `too_close`: penalty for unsafe close geometry.
- `damage`: `damage_scale * (target_damage - ownship_damage)`.
- `safety`: altitude hold, low-altitude guard, attitude guard, speed guard.
- `attitude_envelope_guard`: pitch/roll envelope penalty.
- `nose_down_guard`: nose-down penalty when altitude is deficient.
- `descent_rate_guard`: descent-rate penalty when altitude is deficient.
- `low_altitude_roll_guard`: roll penalty when altitude is deficient.
- `action_pitch_down_guard`, `action_pitch_guard`, `action_roll_guard`,
  `action_roll_global_guard`: action-shaping penalties.
- `wez_band`: soft range/nose score around the desired WEZ band.
- `wez_hold`: bonus when inside the official WEZ.
- `official_wez_aim`: wider aim shaping near official WEZ.
- `precision_aim`: Gaussian precision aim shaping.
- `terminal`: win/loss/draw/crash terminal reward.

The stage-specific modules mostly change weights for these components.

## Stage 1: `student.my_reward_stage1_survival`

Goal: keep the jet flyable before teaching pursuit or gunnery.

Key choices:

- Very strong altitude/safety shaping.
- Damage and WEZ rewards disabled or near zero.
- Weak pursuit terms.
- Heavy own-crash penalty.

Use this stage only for basic survival recovery. It is not the current attack
model reward.

## Stage 2: `student.my_reward_stage2_pursuit`

Goal: stable rear pursuit geometry.

Key choices:

- Stronger `track_angle`, `relative_position`, and `closure`.
- Wide training WEZ shaping through `wez_band`, `official_wez_aim`, and
  `precision_aim`.
- Safety guards remain active.
- Damage reward is introduced but not yet dominant.

Use this stage to learn how to stay behind the target and enter useful gun
geometry.

## Stage 2 Anchor: `student.my_reward_stage2_anchor`

Goal: hold a rear saddle instead of briefly crossing WEZ.

Adds explicit anchor components:

- `anchor_nose`: ownship nose stays near the target.
- `anchor_rear`: target sees ownship behind its tail.
- `anchor_saddle`: range + nose + rear geometry together.
- `anchor_bad_geometry`: penalty when geometry degrades.
- `anchor_terminal`: terminal bonus/penalty based on final saddle quality.

This was useful as a curriculum idea, but the current best stage-3 model does
not directly use this reward.

## Stage 3 Current Best: `student.my_reward_stage3_kill`

Goal: convert rear pursuit into target destruction while staying safe.

This is the current best reward family.

Defaults in the module emphasize:

- Larger `win_reward`.
- Strong loss/draw penalties.
- High `damage_scale`.
- Stronger gun/WEZ aim shaping.
- Safety shaping for altitude, pitch, roll, nose-down attitude, descent rate,
  and speed.

The current best experiment further overrides the module defaults in YAML:

```yaml
reward:
  win_reward: 380.0
  loss_reward: -340.0
  draw_reward: -110.0
  own_crash_penalty: -560.0
  target_crash_reward: -20.0
  damage_scale: 225.0
  altitude_target_m: 7400.0
  safe_altitude_m: 4700.0
  altitude_hold_scale: 0.22
  low_altitude_guard_scale: 6.3
  track_angle_scale: 0.85
  relative_position_scale: 1.50
  closure_scale: 0.35
  gunsnap_blue_scale: 1.70
  gunsnap_red_scale: 0.10
  wez_band_scale: 1.20
  wez_band_center_m: 650.0
  wez_band_half_width_m: 400.0
  wez_hold_bonus: 1.10
  official_wez_aim_scale: 3.90
  precision_aim_scale: 2.45
```

Why this is best so far:

- It preserves quick target kills.
- With late-emergency runtime safety, it removes altitude losses without
  reducing the deterministic kill count on the fixed seed benchmark.

## Stage 3 Finish: `student.my_reward_stage3_finish`

Goal: turn near-kills into deterministic kills.

Adds to `stage3_kill`:

- `fast_kill_bonus`: terminal bonus for faster target destruction.
- `target_health_remaining`: terminal penalty proportional to remaining target
  health if the target is not killed.

Result:

- Small 3-iteration continuation did not change behavior.
- Stronger/longer continuation collapsed into safe timeouts.
- `tailchase_s3_b050_safe_finish10_sac_v1/bundle_000010` is not kept as best:
  `win 0% / loss 0% / draw 100%`.

Conclusion: terminal health penalty alone is dangerous here.

## Stage 3 Reacquire: `student.my_reward_stage3_reacquire`

Goal: improve post-pass pressure and re-attack.

Adds to `stage3_kill`:

- `reacquire`: bonus for being in useful re-attack range and pointed near the
  target.
- `extension_penalty`: penalty for extending too far after contact.
- Both are scaled up after the target has already taken damage.

Result:

- `bundle_000004`: same fixed-seed result as the safe best.
- `bundle_000008`: lower target health in timeout draws, but win rate dropped
  to `17%`.

Conclusion: it can increase damage pressure, but it loses quick kills when
continued too far.

## Stage 3 Execute: `student.my_reward_stage3_execute`

Goal: finish low-health targets without broad terminal penalties.

Adds to `stage3_kill`:

- `low_health_wez`: low-health WEZ/aim pressure.
- `low_health_damage`: extra reward for damage while target health is low.
- `low_health_far`: penalty for being far away when target health is low.
- `low_health_timeout`: small timeout penalty only when the target was already
  hurt.

Result:

- `bundle_000004`: same as safe best.
- `bundle_000008`: collapsed to `win 0% / loss 0% / draw 100%` and converted
  all 12 baseline wins into draws.

Conclusion: this shaping was worse than expected and should not be continued.

## Legacy Team Reward: `student.my_reward`

This is an older advisor/team reward used by many `ic_s*` and `codex_*`
experiments.

It includes PBRS-style pursuit/altitude shaping, WEZ-entry bonuses, precision
WEZ shaping, altitude floor bumpers, and terminal handling for forced-ground vs
true target health kills.

It is important historical context, but it is not the reward used by the current
straight-tail-chase best model.

## Practical Rule

For the current project goal:

```text
Target: straight BT
Ownship: tail-chase SAC
Observation: tactical16
Goal: chase and destroy target without falling
```

Use this reward unless a new fixed-seed eval clearly beats it:

```text
student.my_reward_stage3_kill
```

Do not replace the current best unless a candidate beats:

- fixed-seed 30 episodes: `win >= 40%`
- fixed-seed 30 episodes: `loss == 0%`
- preferably fewer than 18 draws

Avoid continuing reward-shaping branches past iteration 4 without eval. In the
latest runs, iteration 8 repeatedly drifted into timeout behavior.
