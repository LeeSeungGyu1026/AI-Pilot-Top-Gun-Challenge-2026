# -*- coding: utf-8 -*-
"""Stage 3 tail-chase reward: convert rear pursuit into target destruction.

This stage keeps the Stage 2 pursuit geometry, narrows the aiming signal, and
raises damage/terminal rewards. Safety remains strong because recent Stage 3
runs learned useful attack windows but still lost altitude discipline.
"""
from __future__ import annotations

from student import my_reward_table1 as base_reward


MY_REWARD_CONFIG = {
    **base_reward.MY_REWARD_CONFIG,
    "mode": "stage3_kill",
    "win_reward": 320.0,
    "loss_reward": -220.0,
    "draw_reward": -140.0,
    "own_crash_penalty": -420.0,
    "target_crash_reward": -30.0,
    "guard_fail_penalty": -150.0,
    "survival_bonus": 0.004,
    "step_penalty": -0.004,
    "adverse_angle_scale": 0.40,
    "track_angle_scale": 0.75,
    "relative_position_scale": 1.40,
    "closure_scale": 0.35,
    "gunsnap_blue_scale": 1.60,
    "gunsnap_red_scale": 0.12,
    "deck_scale": 0.80,
    "too_close_scale": 1.60,
    "damage_scale": 180.0,
    "altitude_target_m": 7200.0,
    "altitude_band_m": 2400.0,
    "safe_altitude_m": 4300.0,
    "altitude_hold_scale": 0.18,
    "low_altitude_guard_scale": 6.0,
    "attitude_envelope_guard_scale": 0.65,
    "pitch_envelope_ref_deg": 26.0,
    "roll_envelope_ref_deg": 85.0,
    "nose_down_guard_scale": 1.8,
    "nose_down_pitch_ref_deg": 13.0,
    "descent_rate_guard_scale": 1.4,
    "descent_rate_ref_mps": 42.0,
    "speed_penalty_scale": 0.07,
    "speed_target_kcas": 320.0,
    "speed_band_kcas": 200.0,
    "wez_band_scale": 1.0,
    "wez_band_center_m": 570.0,
    "wez_band_half_width_m": 380.0,
    "wez_nose_half_angle_deg": 9.0,
    "wez_hold_bonus": 1.0,
    "official_wez_aim_scale": 3.50,
    "official_wez_aim_half_angle_deg": 7.0,
    "precision_aim_scale": 2.20,
    "precision_aim_sigma_deg": 5.0,
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
