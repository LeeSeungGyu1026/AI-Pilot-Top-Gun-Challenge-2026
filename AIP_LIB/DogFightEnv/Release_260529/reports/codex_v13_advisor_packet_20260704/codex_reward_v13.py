# -*- coding: utf-8 -*-
"""Codex v13 reward wrapper.

v12b learned to farm the wide WEZ precision bonus instead of finishing kills.
This module preserves the existing reward implementation but removes that
per-step precision bonus for v13, then adds a bounded fast-kill terminal bonus.
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
    "wez_precision_bonus_enabled": False,
    "fast_kill_bonus_max": 110.0,
    "fast_kill_horizon_s": 90.0,
    "reward_output_scale": 0.05,
}


def _removed_precision_bonus(ownship_state, target_state, geo_info, wez_config: dict, cfg: dict) -> float:
    if cfg.get("wez_precision_bonus_enabled", False):
        return 0.0
    distance = float(geo_info._get_distance(ownship_state, target_state))
    ata = float(geo_info._get_antenna_train_angle(ownship_state, target_state, False))
    return float(base_reward._wez_precision_bonus(distance, ata, wez_config, cfg))


def _fast_kill_bonus(ownship_state, target_state, terminated: bool, cfg: dict) -> float:
    if not terminated:
        return 0.0
    own_hp = float(ownship_state[StateIndex.HEALTH])
    tgt_hp = float(target_state[StateIndex.HEALTH])
    if not (tgt_hp <= 0.0 < own_hp):
        return 0.0
    horizon = max(float(cfg.get("fast_kill_horizon_s", 90.0)), 1e-6)
    sim_time = max(float(ownship_state[StateIndex.SIM_TIME]), 0.0)
    frac = max(0.0, 1.0 - sim_time / horizon)
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
    # Force the base reward to include the precision term, then remove exactly
    # that term below. Today my_reward.py ignores wez_precision_bonus_enabled,
    # but this keeps v13 correct if the base module later learns that flag.
    base_cfg = {**cfg, "wez_precision_bonus_enabled": True}
    total, components = base_reward.compute_reward(
        ownship_state,
        target_state,
        ownship_damage,
        target_damage,
        geo_info,
        wez_config,
        base_cfg,
        terminated,
        truncated,
        end_condition,
    )

    out_scale = float(cfg.get("reward_output_scale", 1.0))

    precision_to_remove = _removed_precision_bonus(ownship_state, target_state, geo_info, wez_config, cfg) * out_scale
    if precision_to_remove:
        components["pursuit"] = components.get("pursuit", 0.0) - precision_to_remove
        total -= precision_to_remove

    fast_bonus = _fast_kill_bonus(ownship_state, target_state, terminated, cfg) * out_scale
    if fast_bonus:
        components["terminal"] = components.get("terminal", 0.0) + fast_bonus
        total += fast_bonus

    return float(total), components


__all__ = ["MY_REWARD_CONFIG", "compute_reward"]
