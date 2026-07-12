# -*- coding: utf-8 -*-
"""Stage 3 reacquisition reward.

This module keeps the current kill-capable Stage 3 reward intact, then adds
small dense signals for post-pass pressure:

* reward staying in a useful re-attack range while pointed near the target;
* penalize extending far away after contact;
* scale both terms up slightly after the target has already taken damage.

It intentionally avoids the strong terminal health penalty used by
``my_reward_stage3_finish`` because that experiment collapsed into safe
timeouts and lost all deterministic kills.
"""
from __future__ import annotations

import numpy as np

from student import my_reward_stage3_kill as base_reward


STATE_HEALTH = 45


MY_REWARD_CONFIG = {
    **base_reward.MY_REWARD_CONFIG,
    "mode": "stage3_reacquire",
    "reacquire_scale": 1.15,
    "reacquire_range_center_m": 1350.0,
    "reacquire_range_half_width_m": 1450.0,
    "reacquire_nose_half_angle_deg": 30.0,
    "reacquire_pressure_scale": 1.15,
    "extension_penalty_scale": 0.85,
    "extension_range_m": 2800.0,
    "extension_far_range_m": 4400.0,
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

    distance_m = float(geo_info._get_distance(ownship_state, target_state))
    track_angle_deg = abs(
        float(geo_info._get_antenna_train_angle(ownship_state, target_state, False))
    )
    target_health = _clip01(float(target_state[STATE_HEALTH]))

    damage_pressure = 1.0 + float(cfg.get("reacquire_pressure_scale", 0.0)) * (
        1.0 - target_health
    )
    center_m = float(cfg.get("reacquire_range_center_m", 1350.0))
    half_width_m = max(float(cfg.get("reacquire_range_half_width_m", 1450.0)), 1.0)
    nose_half_deg = max(float(cfg.get("reacquire_nose_half_angle_deg", 30.0)), 1.0)

    range_score = _clip01(1.0 - abs(distance_m - center_m) / half_width_m)
    nose_score = _clip01(1.0 - track_angle_deg / nose_half_deg)
    reacquire = (
        float(cfg.get("reacquire_scale", 0.0))
        * damage_pressure
        * range_score
        * (nose_score**2)
    )

    extension_start = float(cfg.get("extension_range_m", 2800.0))
    extension_far = max(float(cfg.get("extension_far_range_m", 4400.0)), extension_start + 1.0)
    extension_score = _clip01((distance_m - extension_start) / (extension_far - extension_start))
    extension_penalty = (
        -float(cfg.get("extension_penalty_scale", 0.0))
        * damage_pressure
        * extension_score
    )

    components["reacquire"] = reacquire
    components["extension_penalty"] = extension_penalty
    return float(reward + reacquire + extension_penalty), components


__all__ = ["MY_REWARD_CONFIG", "compute_reward"]
