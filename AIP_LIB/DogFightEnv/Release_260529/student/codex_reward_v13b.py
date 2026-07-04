# -*- coding: utf-8 -*-
"""Codex v13b reward wrapper.

v13 removed the wide WEZ precision bonus entirely, but frozen eval showed the
chosen seed was not a stable deterministic kill policy. v13b keeps a small
precision gradient so the policy can still learn aim, while capping the farming
payoff far below a kill.
"""
from __future__ import annotations

from dogfight.sim.state_schema import StateIndex
from student import my_reward as base_reward


MY_REWARD_CONFIG = {
    **base_reward.MY_REWARD_CONFIG,
    "win_reward": 220.0,
    "forced_ground_reward": 0.0,
    "loss_reward": -150.0,
    "draw_reward": -100.0,
    "damage_dealt_scale": 350.0,
    "damage_taken_scale": 3.0,
    "pbrs_ata_weight": 4.0,
    "wez_precision_bonus_min": 0.2,
    "wez_precision_bonus_max": 10.0,
    "fast_kill_bonus_max": 110.0,
    "fast_kill_horizon_s": 90.0,
    "fast_kill_bonus_floor_frac": 0.2,
    "reward_output_scale": 0.05,
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
