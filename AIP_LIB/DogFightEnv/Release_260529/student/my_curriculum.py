# -*- coding: utf-8 -*-
"""Team curriculum (advisor round 2): metric-gated stages + dense-pursuit
anneal + WEZ-width (goal radius) curriculum.

Built on the platform's default get_stages(). Per-stage schedule:

  stage                | WEZ angle | dense pursuit      | PBRS
  ---------------------+-----------+--------------------+---------
  0 flight_survival    |   8 deg   | off                | off
  1 target_pursuit     |   8 deg   | DENSE_SCALE        | on
  2 wez_approach       |   8 deg   | DENSE_SCALE        | on
  3 autopilot_pursuit  |   8 deg   | DENSE_SCALE        | on
  two_circle a000-a060 |   5 deg   | anneal -> 0        | on
  two_circle a080-a120 |   3 deg   | anneal -> 0        | on
  two_circle a140-a180 |   2 deg   | 0                  | on
  full_dogfight        |   2 deg   | 0                  | on

Rationale:
  - WEZ width is BOTH the reward gradient and the damage model (symmetric for
    both aircraft, see single_agent_env.update_damage), so widening directly
    accelerates first kills -> terminal-reward exposure. Stage advancement is
    metric-gated, so each narrowing happens only after the wider cone is
    mastered. The final three head-on stages + full_dogfight train at the
    TRUE 2 deg cone (budget real time at the real cone).
  - The observation's in_wez feature is pinned to the true 2 deg cone in
    student/my_observation.py, so feature semantics never drift.
  - Dense pursuit (hackable scaffolding) is annealed to zero across the
    two-circle stages; PBRS stays on everywhere as the safe refinement layer.
  - Stage 0 crash gate tightened to 5% (crash rate is the first boss).
  - full_dogfight keeps mixed initial geometry permanently on.

Variant modules for sweeps (run_parallel grid over curriculum.stages_module):
  student.my_curriculum          -> dense scale 0.2
  student.my_curriculum_dense01  -> dense scale 0.1
"""
from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
for path in (ROOT, SRC):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from dogfight.ai.curriculum import CurriculumStage, get_stages as get_default_stages


DENSE_SCALE = 0.2  # max per-step dense pursuit reward (see my_curriculum_dense01)

MIXED_INITIAL_SCENARIO = {
    "initial_scenario": {
        "mode": "ref_old_random",
        "legacy_use_random_scenario": True,
        "legacy_use_first_scenario_only": False,
        "legacy_scenario_indices": [0, 1, 2, 3, 4, 5, 6, 7],
        "legacy_randomization": {
            "aircraft_radius_m": 100.0,
            "roll_deg": 5.0,
            "pitch_deg": 5.0,
            "heading_deg": 5.0,
            "shared_n_m": 4000.0,
            "shared_e_m": 4000.0,
            "shared_d_m": 4000.0,
            "target_distance_n_m": 300.0,
            "speed_mps": 50.0,
            "loiter_bank_deg_range": [40.0, 70.0],
        },
    },
}

PBRS_ON = {"pbrs_ata_weight": 2.0, "pbrs_range_weight": 1.0}
PBRS_OFF = {"pbrs_ata_weight": 0.0, "pbrs_range_weight": 0.0}


def _wez_override(angle_deg: float) -> dict:
    return {"wez": {"angle_deg": angle_deg}}


def _sanitize_randomization(stage: CurriculumStage) -> None:
    """Clamp zero randomization ranges to 1 (platform bug workaround).

    single_agent_env.add_random_init_position calls np_random.integers(0, x)
    for radius/r_roll/r_pitch/r_heading; NumPy raises ValueError("high <= 0")
    when x == 0. The default stage 0 ships radius=0.0 with enabled=True, which
    crash-loops every env reset. A 1 m / 1 deg jitter is functionally zero.
    """
    rand = stage.randomization
    if not rand or not rand.get("enabled", False):
        return
    for key in ("radius", "r_roll", "r_pitch", "r_heading"):
        if float(rand.get(key, 0.0)) < 1.0:
            rand[key] = 1.0


def build_stages(dense_scale: float = DENSE_SCALE) -> list[CurriculumStage]:
    stages = get_default_stages()
    two_circle = [s for s in stages if s.name.startswith("two_circle_headon")]
    n_tc = len(two_circle)
    tc_pos = {s.name: i for i, s in enumerate(two_circle)}

    for stage in stages:
        _sanitize_randomization(stage)
        if stage.name == "flight_survival":
            stage.advance_conditions["crash_rate_max"] = 0.05
            stage.reward_overrides.update(
                damage_dealt_scale=0.0,
                damage_taken_scale=0.0,
                pursuit_dense_scale=0.0,
                **PBRS_OFF,
            )
            stage.env_overrides.update(_wez_override(8.0))
        elif stage.name == "target_pursuit":
            stage.reward_overrides.update(
                damage_dealt_scale=0.0,
                damage_taken_scale=0.0,
                pursuit_dense_scale=dense_scale,
                **PBRS_ON,
            )
            stage.env_overrides.update(_wez_override(8.0))
        elif stage.name in ("wez_approach", "autopilot_pursuit"):
            stage.reward_overrides.update(
                damage_dealt_scale=30.0,
                damage_taken_scale=12.0,
                pursuit_dense_scale=dense_scale,
                **PBRS_ON,
            )
            stage.env_overrides.update(_wez_override(8.0))
        elif stage.name.startswith("two_circle_headon"):
            i = tc_pos[stage.name]
            # dense scaffold anneals to 0; last 3 stages run with none
            frac = max(0.0, 1.0 - i / max(n_tc - 3, 1))
            stage.reward_overrides.update(
                pursuit_dense_scale=round(dense_scale * frac, 4),
                **PBRS_ON,
            )
            if i < 4:
                wez_angle = 5.0
            elif i < 7:
                wez_angle = 3.0
            else:
                wez_angle = 2.0  # true cone for the final head-on block
            stage.env_overrides.update(_wez_override(wez_angle))
        elif stage.name == "full_dogfight":
            stage.reward_overrides.update(
                pursuit_dense_scale=0.0,
                **PBRS_ON,
            )
            stage.env_overrides.update(_wez_override(2.0))
            stage.env_overrides.update(MIXED_INITIAL_SCENARIO)

    return stages


def get_stages() -> list[CurriculumStage]:
    return build_stages(DENSE_SCALE)


__all__ = ["get_stages", "build_stages", "DENSE_SCALE"]
