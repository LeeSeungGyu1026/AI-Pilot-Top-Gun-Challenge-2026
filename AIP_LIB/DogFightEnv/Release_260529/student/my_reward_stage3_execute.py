# -*- coding: utf-8 -*-
"""Stage 3 execution reward.

The current best policy already survives and gets quick kills in some fixed
tail-chase starts, but later continuations often trade those kills for low-health
timeouts. This wrapper keeps the proven Stage 3 kill reward and adds a narrow
low-health pressure term that activates only after the target is already hurt.
"""
from __future__ import annotations

import math

import numpy as np

from student import my_reward_stage3_kill as base_reward


STATE_HEALTH = 45


MY_REWARD_CONFIG = {
    **base_reward.MY_REWARD_CONFIG,
    "mode": "stage3_execute",
    "execute_health_threshold": 0.55,
    "execute_wez_scale": 2.20,
    "execute_damage_scale": 150.0,
    "execute_range_center_m": 620.0,
    "execute_range_half_width_m": 430.0,
    "execute_nose_half_angle_deg": 8.0,
    "execute_precision_sigma_deg": 4.0,
    "execute_far_penalty_scale": 0.35,
    "execute_far_range_m": 1800.0,
    "execute_timeout_penalty_scale": 35.0,
}


def _clip01(value: float) -> float:
    return float(np.clip(float(value), 0.0, 1.0))


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
    reward, components = base_reward.compute_reward(
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

    target_health = _clip01(float(target_state[STATE_HEALTH]))
    threshold = max(float(cfg.get("execute_health_threshold", 0.55)), 0.01)
    pressure = _clip01((threshold - target_health) / threshold)

    distance_m = float(geo_info._get_distance(ownship_state, target_state))
    track_angle_deg = abs(
        float(geo_info._get_antenna_train_angle(ownship_state, target_state, False))
    )

    center_m = float(cfg.get("execute_range_center_m", 620.0))
    half_width_m = max(float(cfg.get("execute_range_half_width_m", 430.0)), 1.0)
    range_score = _clip01(1.0 - abs(distance_m - center_m) / half_width_m)

    nose_half_deg = max(float(cfg.get("execute_nose_half_angle_deg", 8.0)), 0.1)
    nose_score = _clip01(1.0 - track_angle_deg / nose_half_deg)

    sigma_deg = max(float(cfg.get("execute_precision_sigma_deg", 4.0)), 0.1)
    precision_score = math.exp(-0.5 * (track_angle_deg / sigma_deg) ** 2)

    low_health_wez = (
        float(cfg.get("execute_wez_scale", 0.0))
        * pressure
        * range_score
        * (0.35 * (nose_score**2) + 0.65 * precision_score)
    )
    low_health_damage = (
        float(cfg.get("execute_damage_scale", 0.0))
        * pressure
        * max(float(target_damage), 0.0)
    )

    far_start_m = max(float(cfg.get("execute_far_range_m", 1800.0)), 1.0)
    far_score = _clip01((distance_m - far_start_m) / far_start_m)
    low_health_far = -float(cfg.get("execute_far_penalty_scale", 0.0)) * pressure * far_score

    low_health_timeout = 0.0
    if terminated or truncated:
        ownship_health = float(ownship_state[STATE_HEALTH])
        killed_target = target_health <= 0.0 < ownship_health
        if not killed_target and pressure > 0.0 and end_condition == "max time out":
            low_health_timeout = -float(
                cfg.get("execute_timeout_penalty_scale", 0.0)
            ) * pressure

    components["low_health_wez"] = low_health_wez
    components["low_health_damage"] = low_health_damage
    components["low_health_far"] = low_health_far
    components["low_health_timeout"] = low_health_timeout
    return float(
        reward
        + low_health_wez
        + low_health_damage
        + low_health_far
        + low_health_timeout
    ), components


__all__ = ["MY_REWARD_CONFIG", "compute_reward"]
