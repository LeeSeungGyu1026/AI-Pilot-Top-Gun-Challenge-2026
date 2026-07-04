# -*- coding: utf-8 -*-
"""Engineered 26-D observation ("tgc26") for WVR gun-only dogfighting.

Design notes (vs the provided tactical16):
  - All wrapping angles (roll, yaw, ATA, AA, LOS az) are encoded as sin/cos
    pairs so the policy never sees a +/-180 deg discontinuity.
  - Range is log-scaled: most precision is needed inside ~1 km.
  - The state vector exposes no velocities, so closure rate, climb rate,
    LOS rates, and target velocity are finite-differenced from positions
    using SIM_TIME. Derived state lives in a module-level cache keyed by
    id(geo_info) (one geo_info per env instance), and resets whenever
    SIM_TIME goes backwards (= new episode).
  - "lead_error" is the angle between the ownship nose and the predicted
    gun intercept point (target position advanced by estimated target
    velocity x bullet time-of-flight). Pure pursuit never yields gun
    solutions on a maneuvering target; this feature points at the fix.

Used with:
  python train_rllib.py --observation-mode custom --observation-module student.my_observation
The SAME module must be passed to run_local_dogfight.py / run_unreal_inference.py.
"""
from __future__ import annotations

import math

import numpy as np

from dogfight.sim.state_schema import StateIndex


OBSERVATION_MODE = "tgc26"
OBSERVATION_SIZE = 26
OBSERVATION_LOW = -1.0
OBSERVATION_HIGH = 1.0

KNOTS_TO_MPS = 0.514444
BULLET_SPEED_MPS = 700.0   # effective bullet closing speed for TOF estimate
GRAVITY = 9.80665

# Fixed normalizers (advice: fixed, not running, for reproducibility).
MAX_ALT_M = 15000.0
MAX_KCAS = 600.0
MAX_CLIMB_MPS = 150.0
MAX_SPEC_ENERGY_M = 20000.0
MIN_RANGE_M = 50.0
MAX_RANGE_M = 20000.0
MAX_CLOSURE_MPS = 300.0
MAX_LOS_RATE_DPS = 30.0
MAX_DELTA_D_M = 8000.0
MAX_SPEED_ADV_MPS = 200.0
MAX_PLAUSIBLE_VEL_MPS = 450.0  # clamp finite-diff velocity (guards UDP/reset glitches)

# The competition's REAL gun cone. The in_wez feature is always computed
# against these constants — NOT the runtime wez_config — so curriculum WEZ
# widening changes only the reward/damage side, never feature semantics.
TRUE_WEZ_ANGLE_DEG = 2.0
TRUE_WEZ_MIN_RANGE_M = 152.4
TRUE_WEZ_MAX_RANGE_M = 914.4

# Per-env derived state: id(geo_info) -> dict of previous-step values.
_DERIVED: dict[int, dict] = {}
_DERIVED_MAX_ENTRIES = 64


def _clip1(value: float) -> float:
    return float(np.clip(value, -1.0, 1.0))


def _nose_vector_ned(state) -> np.ndarray:
    """Unit body-x (nose) direction in NED from yaw/pitch (degrees)."""
    yaw = math.radians(float(state[StateIndex.YAW]))
    pitch = math.radians(float(state[StateIndex.PITCH]))
    return np.array(
        [
            math.cos(pitch) * math.cos(yaw),
            math.cos(pitch) * math.sin(yaw),
            -math.sin(pitch),
        ],
        dtype=np.float64,
    )


def _clamp_vel(vel: np.ndarray) -> np.ndarray:
    speed = float(np.linalg.norm(vel))
    if speed > MAX_PLAUSIBLE_VEL_MPS:
        return vel * (MAX_PLAUSIBLE_VEL_MPS / speed)
    return vel


def _angle_between_deg(u: np.ndarray, v: np.ndarray) -> float:
    nu = float(np.linalg.norm(u))
    nv = float(np.linalg.norm(v))
    if nu < 1e-6 or nv < 1e-6:
        return 0.0
    cos_val = float(np.dot(u, v) / (nu * nv))
    return math.degrees(math.acos(max(-1.0, min(1.0, cos_val))))


def _get_derived(key: int, sim_time: float) -> dict:
    """Fetch per-env derived state, resetting on episode restart."""
    if len(_DERIVED) > _DERIVED_MAX_ENTRIES:
        _DERIVED.clear()  # stale env instances (e.g., after re-creation)
    state = _DERIVED.get(key)
    if state is None or sim_time <= state["sim_time"]:
        state = {"sim_time": sim_time, "fresh": True}
        _DERIVED[key] = state
    return state


def build_observation(ownship_state, target_state, geo_info, wez_config=None):
    own_pos = np.asarray(ownship_state[:3], dtype=np.float64)
    tgt_pos = np.asarray(target_state[:3], dtype=np.float64)
    sim_time = float(ownship_state[StateIndex.SIM_TIME])

    distance = float(geo_info._get_distance(ownship_state, target_state))
    ata = float(geo_info._get_antenna_train_angle(ownship_state, target_state, False))
    aa = float(geo_info._get_aspect_angle(ownship_state, target_state, False))
    az, el = geo_info._get_los_angle(ownship_state, target_state)
    az, el = float(az), float(el)
    alt = float(ownship_state[StateIndex.ALT])
    kcas = float(ownship_state[StateIndex.KCAS])
    speed_mps = kcas * KNOTS_TO_MPS

    derived = _get_derived(id(geo_info), sim_time)
    dt = sim_time - derived["sim_time"]
    if derived.pop("fresh", False) or dt <= 1e-6:
        climb_rate = 0.0
        closure_rate = 0.0
        az_rate = 0.0
        el_rate = 0.0
        own_vel = np.zeros(3)
        tgt_vel = np.zeros(3)
    else:
        climb_rate = (alt - derived["alt"]) / dt
        closure_rate = -(distance - derived["distance"]) / dt  # + = closing
        d_az = (az - derived["az"] + 180.0) % 360.0 - 180.0     # unwrap
        az_rate = d_az / dt
        el_rate = (el - derived["el"]) / dt
        own_vel = _clamp_vel((own_pos - derived["own_pos"]) / dt)
        tgt_vel = _clamp_vel((tgt_pos - derived["tgt_pos"]) / dt)

    derived.update(
        sim_time=sim_time,
        alt=alt,
        distance=distance,
        az=az,
        el=el,
        own_pos=own_pos,
        tgt_pos=tgt_pos,
    )

    # Lead angle error: nose vs predicted intercept direction.
    tof = distance / BULLET_SPEED_MPS
    predicted = tgt_pos + tgt_vel * tof
    lead_error = _angle_between_deg(_nose_vector_ned(ownship_state), predicted - own_pos)

    spec_energy = alt + (speed_mps**2) / (2.0 * GRAVITY)
    speed_adv = float(np.linalg.norm(own_vel) - np.linalg.norm(tgt_vel))

    log_lo, log_hi = math.log10(MIN_RANGE_M), math.log10(MAX_RANGE_M)
    log_range = math.log10(max(distance, MIN_RANGE_M))

    # Always the true competition cone (see TRUE_WEZ_* note above);
    # wez_config is intentionally ignored here.
    in_wez = (
        1.0
        if (
            TRUE_WEZ_MIN_RANGE_M <= distance <= TRUE_WEZ_MAX_RANGE_M
            and abs(ata) <= TRUE_WEZ_ANGLE_DEG / 2.0
        )
        else -1.0
    )

    roll = math.radians(float(ownship_state[StateIndex.ROLL]))
    yaw = math.radians(float(ownship_state[StateIndex.YAW]))
    ata_r, aa_r, az_r = math.radians(ata), math.radians(aa), math.radians(az)

    obs = np.array(
        [
            math.sin(roll),
            math.cos(roll),
            _clip1(float(ownship_state[StateIndex.PITCH]) / 90.0),
            math.sin(yaw),
            math.cos(yaw),
            _clip1(2.0 * kcas / MAX_KCAS - 1.0),
            _clip1(2.0 * alt / MAX_ALT_M - 1.0),
            _clip1(climb_rate / MAX_CLIMB_MPS),
            _clip1(2.0 * spec_energy / MAX_SPEC_ENERGY_M - 1.0),
            _clip1(2.0 * float(ownship_state[StateIndex.HEALTH]) - 1.0),
            _clip1(2.0 * float(target_state[StateIndex.HEALTH]) - 1.0),
            _clip1(2.0 * (log_range - log_lo) / (log_hi - log_lo) - 1.0),
            _clip1(closure_rate / MAX_CLOSURE_MPS),
            math.sin(ata_r),
            math.cos(ata_r),
            math.sin(aa_r),
            math.cos(aa_r),
            math.sin(az_r),
            math.cos(az_r),
            _clip1(el / 90.0),
            _clip1(az_rate / MAX_LOS_RATE_DPS),
            _clip1(el_rate / MAX_LOS_RATE_DPS),
            _clip1(2.0 * lead_error / 180.0 - 1.0),
            _clip1((tgt_pos[2] - own_pos[2]) / MAX_DELTA_D_M),
            in_wez,
            _clip1(speed_adv / MAX_SPEED_ADV_MPS),
        ],
        dtype=np.float32,
    )
    return obs


def describe_observation():
    return {
        "mode": OBSERVATION_MODE,
        "size": OBSERVATION_SIZE,
        "features": [
            "sin_roll",
            "cos_roll",
            "pitch_norm",
            "sin_yaw",
            "cos_yaw",
            "kcas_norm",
            "alt_norm",
            "climb_rate_norm",
            "specific_energy_norm",
            "own_health_norm",
            "target_health_norm",
            "log_range_norm",
            "closure_rate_norm",
            "sin_ata",
            "cos_ata",
            "sin_aa",
            "cos_aa",
            "sin_los_az",
            "cos_los_az",
            "los_el_norm",
            "los_az_rate_norm",
            "los_el_rate_norm",
            "lead_error_norm",
            "delta_d_norm",
            "in_wez",
            "speed_advantage_norm",
        ],
        "description": (
            "26-D engineered WVR observation: wrap-safe sin/cos angles, log range, "
            "finite-differenced closure/climb/LOS rates and target velocity, "
            "lead-angle error to predicted gun intercept, specific energy, WEZ flag."
        ),
    }
