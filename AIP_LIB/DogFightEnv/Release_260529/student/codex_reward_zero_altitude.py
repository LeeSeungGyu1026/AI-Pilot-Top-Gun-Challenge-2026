"""Codex safety-polish reward wrapper.

This keeps the existing team reward intact and adds a narrow guard for the
specific failure mode the user called out: ownship-altitude terminations.
"""
from __future__ import annotations

from dogfight.sim.state_schema import StateIndex
from student.my_reward import MY_REWARD_CONFIG as BASE_REWARD_CONFIG
from student.my_reward import compute_reward as base_compute_reward


MY_REWARD_CONFIG = {
    **BASE_REWARD_CONFIG,
    "pbrs_gamma": 1.0,
    "pbrs_alt_weight": 30.0,
    "safety_floor_m": 900.0,
    "safety_safe_m": 2400.0,
    "pursuit_dense_scale": 0.08,
    "pursuit_range_m": 3000.0,
    "ownship_altitude_loss_extra_penalty": -350.0,
    "fdm_fail_extra_penalty": -350.0,
    "low_altitude_guard_m": 1800.0,
    "low_altitude_guard_scale": 0.04,
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
) -> tuple[float, dict]:
    reward, components = base_compute_reward(
        ownship_state,
        target_state,
        ownship_damage,
        target_damage,
        geo_info,
        wez_config,
        reward_config,
        terminated,
        truncated,
        end_condition,
    )

    cfg = reward_config
    extra_safety = 0.0

    alt = float(ownship_state[StateIndex.ALT])
    guard_m = float(cfg.get("low_altitude_guard_m", 1800.0))
    floor_m = float(cfg.get("safety_floor_m", 900.0))
    if not terminated and guard_m > floor_m and alt < guard_m:
        frac = max(0.0, min(1.0, (guard_m - alt) / (guard_m - floor_m)))
        extra_safety -= float(cfg.get("low_altitude_guard_scale", 0.04)) * frac * frac

    if terminated and end_condition == "ownship altitude below min":
        extra_safety += float(cfg.get("ownship_altitude_loss_extra_penalty", -350.0))
    elif terminated and end_condition == "FDM Update Fail":
        extra_safety += float(cfg.get("fdm_fail_extra_penalty", -350.0))

    if extra_safety:
        components["safety"] = float(components.get("safety", 0.0)) + extra_safety
        reward += extra_safety

    return float(reward), components


__all__ = ["MY_REWARD_CONFIG", "compute_reward"]
