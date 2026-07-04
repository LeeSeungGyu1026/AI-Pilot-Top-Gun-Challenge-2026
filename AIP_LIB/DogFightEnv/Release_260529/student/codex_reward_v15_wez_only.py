# -*- coding: utf-8 -*-
"""v15 reward: kill-aligned, exploit-stripped.

Diagnosis from v14 (ic_s3_v14_seedfix, training_log): reward_mean kept climbing
(pursuit slot 154 -> 195) while win_rate FELL (0.84 @iter20 -> 0.67-0.71 @iter30-50)
and ep_reward_damage stayed flat at ~17. The policy was trading kills for a
non-lethal shaping stream that dwarfed the win signal (win_reward 220 * output
scale 0.05 = 11 logged, vs a ~154-195 logged farm stream). Two farmable terms
produced it, both folded into the platform's "pursuit" slot:

  1. rear-cone reward (`rear_cone_reward_scale`, in _aspect_shaping): pays every
     step the ownship sits in the target's rear cone -- collectable by loitering
     behind the target without ever firing.
  2. wide-cone aim-precision bonus (`_wez_precision_bonus`,
     `wez_precision_bonus_*`, 90deg reward-only cone): pays for rough aim inside
     the WEZ RANGE band without requiring a real hit (the true kill cone is 2deg).

v15 removes both, plus the small non-potential dense pursuit term (also an
in-cone/in-range non-damage payout). The ATTACK reward is now ONLY the damage
differential, which accrues exclusively inside the true 2deg WEZ cone
(single_agent_env.update_damage), i.e. reward only when actually attacking in the
WEZ -- exactly the requested shaping. What remains besides damage is
un-farmable / non-exploitable:
  - PBRS pursuit potential (range + boresight): a potential DIFFERENCE, so its
    episode sum telescopes to boundary terms independent of dwell time -- it
    shapes closure without a farmable per-step floor.
  - PBRS altitude potential + hard altitude-floor penalty (anti-crash safety).
  - front-cone PENALTY (defensive; a penalty, not a farmable reward).
  - terminal win_reward + fast-kill bonus (drive toward FAST 100% kills).

Seed: v14 bundle_000020 (highest-win saved checkpoint, win 0.84; already knows
how to close and kill, so stripping the scaffolding reinforces rather than
collapses). Bundle carries the critic (14 keys) thanks to the checkpoint_io save
fix, so the value function restores too.
"""
from __future__ import annotations

from dogfight.sim.state_schema import StateIndex
from student import my_reward as base_reward


MY_REWARD_CONFIG = {
    **base_reward.MY_REWARD_CONFIG,
    # ── terminal / outcome ────────────────────────────────────────────────
    "win_reward": 220.0,
    "forced_ground_reward": 0.0,
    "loss_reward": -150.0,
    "draw_reward": -100.0,
    # ── attack reward: real WEZ damage ONLY ───────────────────────────────
    "damage_dealt_scale": 350.0,
    "damage_taken_scale": 3.0,
    # ── EXPLOIT TERMS REMOVED (v15) ───────────────────────────────────────
    "rear_cone_reward_scale": 0.0,      # was 0.15 -- loiter-behind-target farm
    "wez_precision_bonus_min": 0.0,
    "wez_precision_bonus_max": 0.0,     # was 10 -- wide-cone rough-aim farm
    "pursuit_dense_scale": 0.0,         # was 0.2  -- in-cone/in-range non-damage payout
    "wez_entry_bonus": 0.0,             # one-time; drop so only damage/kill pays
    # ── kept: defensive penalty (not a farmable reward) ───────────────────
    "front_cone_penalty_scale": 0.1,
    "aspect_cone_deg": 30.0,
    # ── kept: un-farmable PBRS closure + altitude safety ──────────────────
    "pbrs_gamma": 0.997,
    "pbrs_ata_weight": 4.0,
    "pbrs_range_weight": 1.0,
    "pbrs_range_log_clip": 3.0,
    "pbrs_alt_weight": 10.0,
    "safety_floor_m": 300.0,
    "safety_safe_m": 900.0,
    "critical_alt_margin_m": 300.0,
    "altitude_floor_penalty_min": 1.0,
    "altitude_floor_penalty_max": 1000.0,
    # ── time pressure toward fast kills ───────────────────────────────────
    "step_penalty": -0.005,
    "survival_bonus": 0.0,
    "fast_kill_bonus_max": 110.0,
    "fast_kill_horizon_s": 90.0,
    "fast_kill_bonus_floor_frac": 0.2,
    # ── output scale (unchanged; keeps value targets in vf_clip range) ────
    "reward_output_scale": 0.05,
    # platform describe_reward compat keys
    "damage_scale": 0.0,
    "low_altitude_penalty": 0.0,
}


def _fast_kill_bonus(ownship_state, target_state, terminated: bool, cfg: dict) -> float:
    if not terminated:
        return 0.0
    own_hp = float(ownship_state[StateIndex.HEALTH])
    tgt_hp = float(target_state[StateIndex.HEALTH])
    if not (tgt_hp <= 0.0 < own_hp):
        return 0.0
    horizon = max(float(cfg.get("fast_kill_horizon_s", 90.0)), 1e-6)
    sim_time = max(float(ownship_state[StateIndex.SIM_TIME]), 0.0)
    floor = max(0.0, min(1.0, float(cfg.get("fast_kill_bonus_floor_frac", 0.2))))
    frac = max(floor, 1.0 - sim_time / horizon)
    return float(cfg.get("fast_kill_bonus_max", 0.0)) * frac


def compute_reward(
    ownship_state,
    target_state,
    ownship_damage: float,
    target_damage: float,
    geo_info,
    wez_config: dict,
    reward_config: dict,
    terminated: bool,
    truncated: bool,
    end_condition: str,
) -> tuple[float, dict]:
    cfg = {**MY_REWARD_CONFIG, **(reward_config or {})}
    total, components = base_reward.compute_reward(
        ownship_state,
        target_state,
        ownship_damage,
        target_damage,
        geo_info,
        wez_config,
        cfg,
        terminated,
        truncated,
        end_condition,
    )

    out_scale = float(cfg.get("reward_output_scale", 1.0))
    fast_bonus = _fast_kill_bonus(ownship_state, target_state, terminated, cfg) * out_scale
    if fast_bonus:
        components["terminal"] = components.get("terminal", 0.0) + fast_bonus
        total += fast_bonus

    return float(total), components


__all__ = ["MY_REWARD_CONFIG", "compute_reward"]
