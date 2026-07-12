# -*- coding: utf-8 -*-
"""Stage 2 tail-chase reward: stable rear pursuit geometry.

Stage 2 assumes Stage 1 has produced a policy that can stay airborne. The
reward therefore shifts most shaping pressure toward rear-aspect pursuit,
range control, and a wide training WEZ, while keeping altitude guards active.
"""
from __future__ import annotations

from student import my_reward_table1 as base_reward


MY_REWARD_CONFIG = {
    **base_reward.MY_REWARD_CONFIG,
    "mode": "stage2_pursuit",
    "win_reward": 120.0,
    "loss_reward": -190.0,
    "draw_reward": -90.0,
    "own_crash_penalty": -320.0,
    "target_crash_reward": -20.0,
    "guard_fail_penalty": -120.0,
    "survival_bonus": 0.01,
    "step_penalty": -0.003,
    "adverse_angle_scale": 0.35,
    "track_angle_scale": 0.85,
    "relative_position_scale": 1.80,
    "closure_scale": 0.55,
    "gunsnap_blue_scale": 0.60,
    "gunsnap_red_scale": 0.10,
    "deck_scale": 0.75,
    "too_close_scale": 1.40,
    "damage_scale": 20.0,
    "altitude_target_m": 7000.0,
    "altitude_band_m": 2300.0,
    "safe_altitude_m": 3800.0,
    "altitude_hold_scale": 0.14,
    "low_altitude_guard_scale": 4.0,
    "attitude_envelope_guard_scale": 0.55,
    "pitch_envelope_ref_deg": 28.0,
    "roll_envelope_ref_deg": 90.0,
    "nose_down_guard_scale": 1.2,
    "nose_down_pitch_ref_deg": 16.0,
    "descent_rate_guard_scale": 0.9,
    "descent_rate_ref_mps": 50.0,
    "speed_penalty_scale": 0.07,
    "speed_target_kcas": 320.0,
    "speed_band_kcas": 200.0,
    "wez_band_scale": 1.60,
    "wez_band_center_m": 600.0,
    "wez_band_half_width_m": 420.0,
    "wez_nose_half_angle_deg": 14.0,
    "wez_hold_bonus": 0.50,
    "official_wez_aim_scale": 1.80,
    "official_wez_aim_half_angle_deg": 10.0,
    "precision_aim_scale": 0.80,
    "precision_aim_sigma_deg": 8.0,
    "precision_aim_power": 1.0,
}


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
    *,
    action=None,
) -> tuple[float, dict]:
    cfg = {**MY_REWARD_CONFIG, **(reward_config or {})}
    return base_reward.compute_reward(
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
        action=action,
    )


__all__ = ["MY_REWARD_CONFIG", "compute_reward"]
