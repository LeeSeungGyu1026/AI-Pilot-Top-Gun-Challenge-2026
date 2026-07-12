# -*- coding: utf-8 -*-
"""Stage 2 anchor reward: hold a rear saddle instead of briefly crossing WEZ.

The previous Stage 2 reward produced short WEZ windows but did not reliably end
episodes with a low ATA / rear-aspect geometry. This wrapper keeps the Stage 2
Table-I reward and adds explicit tail-chase anchor terms:

  - ownship nose close to target
  - target sees ownship behind its tail
  - range near the desired gun-saddle band
"""
from __future__ import annotations

import math

from student import my_reward_stage2_pursuit as stage2_reward


MY_REWARD_CONFIG = {
    **stage2_reward.MY_REWARD_CONFIG,
    "mode": "stage2_anchor",
    "anchor_range_center_m": 820.0,
    "anchor_range_half_width_m": 520.0,
    "anchor_nose_sigma_deg": 16.0,
    "anchor_rear_min_deg": 120.0,
    "anchor_nose_scale": 1.40,
    "anchor_rear_scale": 1.10,
    "anchor_saddle_scale": 3.20,
    "anchor_terminal_scale": 18.0,
    "anchor_bad_geometry_scale": 0.60,
}


def _clip01(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def _angle_180(value: float) -> float:
    value = abs(float(value)) % 360.0
    return 360.0 - value if value > 180.0 else value


def _anchor_components(ownship_state, target_state, geo_info, reward_config: dict) -> dict[str, float]:
    distance_m = float(geo_info._get_distance(ownship_state, target_state))
    track_angle_deg = _angle_180(
        geo_info._get_antenna_train_angle(ownship_state, target_state, False)
    )
    target_track_angle_deg = _angle_180(
        geo_info._get_antenna_train_angle(target_state, ownship_state, False)
    )

    center = float(reward_config.get("anchor_range_center_m", 820.0))
    half_width = max(float(reward_config.get("anchor_range_half_width_m", 520.0)), 1.0)
    sigma = max(float(reward_config.get("anchor_nose_sigma_deg", 16.0)), 0.1)
    rear_min = max(min(float(reward_config.get("anchor_rear_min_deg", 120.0)), 179.0), 0.0)

    range_score = _clip01(1.0 - abs(distance_m - center) / half_width)
    nose_score = math.exp(-0.5 * (track_angle_deg / sigma) ** 2)
    rear_score = _clip01((target_track_angle_deg - rear_min) / max(180.0 - rear_min, 1.0))
    saddle_score = range_score * nose_score * rear_score

    bad_geometry = _clip01((track_angle_deg - 75.0) / 75.0) * (1.0 - rear_score)

    return {
        "anchor_nose": float(reward_config.get("anchor_nose_scale", 0.0)) * range_score * nose_score,
        "anchor_rear": float(reward_config.get("anchor_rear_scale", 0.0)) * range_score * rear_score,
        "anchor_saddle": float(reward_config.get("anchor_saddle_scale", 0.0)) * saddle_score,
        "anchor_bad_geometry": -float(reward_config.get("anchor_bad_geometry_scale", 0.0))
        * bad_geometry,
        "anchor_terminal": 0.0,
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
    total, components = stage2_reward.compute_reward(
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

    anchor = _anchor_components(ownship_state, target_state, geo_info, cfg)
    if terminated or truncated:
        terminal_scale = float(cfg.get("anchor_terminal_scale", 0.0))
        saddle_scale = max(float(cfg.get("anchor_saddle_scale", 1.0)), 1.0e-6)
        saddle_score = anchor["anchor_saddle"] / saddle_scale
        # Positive if the episode ends in a useful rear saddle, negative if it
        # ends with the target escaped from our nose/tail geometry.
        anchor["anchor_terminal"] = terminal_scale * (2.0 * saddle_score - 1.0)

    components.update(anchor)
    total += sum(anchor.values())
    return float(total), components


__all__ = ["MY_REWARD_CONFIG", "compute_reward"]
