# -*- coding: utf-8 -*-
"""Stage 3 finish reward: turn near-kills into deterministic kills.

The first kill-capable Stage 3 policy often leaves the target at low health on
timeout. This wrapper keeps the tested Stage 3 reward intact, then adds two
small terminal-only signals:

* penalize remaining target health when the episode ends without a kill;
* reward fast target destruction when the kill is achieved.
"""
from __future__ import annotations

import numpy as np

from student import my_reward_stage3_kill as base_reward


STATE_SIM_TIME = 41
STATE_HEALTH = 45


MY_REWARD_CONFIG = {
    **base_reward.MY_REWARD_CONFIG,
    "mode": "stage3_finish",
    "target_health_remaining_penalty_scale": 180.0,
    "fast_kill_bonus_scale": 80.0,
    "finish_max_time_s": 100.0,
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
    ownship_health = float(ownship_state[STATE_HEALTH])
    finish_bonus = 0.0
    health_remaining_penalty = 0.0

    if terminated or truncated:
        if target_health <= 0.0 < ownship_health:
            max_time = max(float(cfg.get("finish_max_time_s", 100.0)), 1.0)
            sim_time = max(float(ownship_state[STATE_SIM_TIME]), 0.0)
            finish_bonus = float(cfg.get("fast_kill_bonus_scale", 0.0)) * _clip01(
                1.0 - sim_time / max_time
            )
        else:
            health_remaining_penalty = -float(
                cfg.get("target_health_remaining_penalty_scale", 0.0)
            ) * target_health

    components["fast_kill_bonus"] = finish_bonus
    components["target_health_remaining"] = health_remaining_penalty
    return float(reward + finish_bonus + health_remaining_penalty), components


__all__ = ["MY_REWARD_CONFIG", "compute_reward"]
