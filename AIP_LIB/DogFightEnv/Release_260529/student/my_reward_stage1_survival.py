# -*- coding: utf-8 -*-
"""Stage 1 tail-chase reward: survive and keep the jet flyable.

This wrapper keeps the Table-I-style component implementation in
student.my_reward_table1, but changes the default weight set so Stage 1 does
not try to solve pursuit and gunnery before basic altitude/speed stability.
"""
from __future__ import annotations

from student import my_reward_table1 as base_reward


MY_REWARD_CONFIG = {
    **base_reward.MY_REWARD_CONFIG,
    "mode": "stage1_survival",
    "win_reward": 40.0,
    "loss_reward": -220.0,
    "draw_reward": -20.0,
    "own_crash_penalty": -450.0,
    "target_crash_reward": -20.0,
    "guard_fail_penalty": -180.0,
    "survival_bonus": 0.03,
    "step_penalty": -0.001,
    "adverse_angle_scale": 0.05,
    "track_angle_scale": 0.05,
    "relative_position_scale": 0.10,
    "closure_scale": 0.05,
    "gunsnap_blue_scale": 0.0,
    "gunsnap_red_scale": 0.10,
    "deck_scale": 0.80,
    "too_close_scale": 0.40,
    "damage_scale": 0.0,
    "altitude_target_m": 7000.0,
    "altitude_band_m": 1800.0,
    "safe_altitude_m": 4500.0,
    "altitude_hold_scale": 0.30,
    "low_altitude_guard_scale": 6.0,
    "attitude_envelope_guard_scale": 0.90,
    "pitch_envelope_ref_deg": 24.0,
    "roll_envelope_ref_deg": 80.0,
    "nose_down_guard_scale": 2.0,
    "nose_down_pitch_ref_deg": 12.0,
    "descent_rate_guard_scale": 1.8,
    "descent_rate_ref_mps": 35.0,
    "speed_penalty_scale": 0.10,
    "speed_target_kcas": 320.0,
    "speed_band_kcas": 180.0,
    "wez_band_scale": 0.0,
    "wez_hold_bonus": 0.0,
    "official_wez_aim_scale": 0.0,
    "precision_aim_scale": 0.0,
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
