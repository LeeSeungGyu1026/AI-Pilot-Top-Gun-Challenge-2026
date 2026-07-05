"""Smoke test for the Python-BT target (target_bt on the autopilot backend).

Two scenarios, ownship flying open-loop (neutral stick) so only the BT acts:
  A) spawn far behind the target (outside threat range) -> BT must ATTACK:
     turn in, close range, and eventually put its nose in the WEZ and damage
     the ownship. Target altitude must never approach the ground.
  B) spawn saddled at gun range on the target's six -> BT must EVADE:
     mode flips to evade, jink side re-rolls over time, and the altitude
     clamp keeps the fight off the floor (the DLL BT died here 64.5% of the
     time in ic_s6 v6).

Run:  python scripts/smoke_python_bt_target.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
for p in (str(ROOT), str(SRC)):
    if p not in sys.path:
        sys.path.insert(0, p)

from DogFightEnvWrapper import DogFightWrapper  # noqa: E402
from dogfight.sim.state_schema import StateIndex  # noqa: E402


def build_env(saddle_range, aspect, turn_rate, own_speed=300.0, attack_speed=280.0):
    env_config = {
        "target_mode": "autopilot",
        "target_autopilot": {"heading_cmd": 0.0, "altitude_cmd": -7000.0, "speed_cmd": 250.0},
        "step_ratio": 6,
        "episode_step_limit": 3000,
        # training-stage WEZ (v5/v6): 8 deg cone, ~950m gun range, so the BT's
        # gunnery can actually register during the smoke
        "wez": {"angle_deg": 8.0, "min_range_m": 150.0, "max_range_m": 950.0},
        "offensive_saddle": {
            "enabled": True,
            "range_m": list(saddle_range),
            "aspect_deg": list(aspect),
            "altitude_m": 7000.0,
            "target_speed_mps": 250.0,
            "own_speed_mps": own_speed,
        },
        "target_bt": {
            "enabled": True,
            "max_turn_rate_deg_s": turn_rate,
            "max_climb_rate_mps": 40.0,
            "min_altitude_m": 3000.0,
            "max_altitude_m": 11000.0,
            "threat_range_m": 1500.0,
            "threat_rear_deg": 90.0,
            "threat_track_deg": 40.0,
            "speed_attack_mps": attack_speed,
        },
        # keep the platform from ending the episode early for this smoke
        "geometry_guard": {"enabled": False},
        "lufbery_guard": {"enabled": False},
        "timeout_guard": {"enabled": False},
    }
    return DogFightWrapper(env_config=env_config)


def level_hold_action(state, alt_target=7000.0, throttle=0.55):
    """Crude wings-level altitude-hold so the ownship neither dives nor
    outruns the BT (neutral action = ZERO throttle = accelerating descent,
    which made every chase geometry untestable). Action convention
    (FighterSim.step): roll -1 left/+1 right, pitch -1 aft(up)/+1 fwd(down),
    rudder, throttle 0..1."""
    roll = float(state[StateIndex.ROLL])
    pitch = float(state[StateIndex.PITCH])
    alt = float(state[StateIndex.ALT])
    pitch_target = max(-10.0, min(10.0, (alt_target - alt) * 0.02))
    return np.array(
        [
            max(-1.0, min(1.0, -roll / 45.0)),
            max(-1.0, min(1.0, (pitch - pitch_target) / 20.0)),
            0.0,
            throttle,
        ],
        dtype=np.float32,
    )


def run_episode(env, n_steps, label, throttle=0.55):
    env.reset()
    min_tgt_alt = float("inf")
    min_dist = float("inf")
    own_health_end = tgt_health_end = None
    modes = []
    end_condition = None
    for i in range(n_steps):
        action = level_hold_action(env._ownship_state, throttle=throttle)
        obs, reward, terminated, truncated, info = env.step(action)
        tgt_alt = float(env._target_state[StateIndex.ALT])
        dist = float(env._geo_info._get_distance(env._ownship_state, env._target_state))
        min_tgt_alt = min(min_tgt_alt, tgt_alt)
        min_dist = min(min_dist, dist)
        if i % 100 == 0 or terminated or truncated:
            own_h = float(env._ownship_state[StateIndex.HEALTH])
            tgt_h = float(env._target_state[StateIndex.HEALTH])
            print(
                f"[{label}] step {i:4d} mode={env._bt_mode:6s} dist={dist:7.1f}m "
                f"tgt_alt={tgt_alt:7.1f}m own_hp={own_h:5.2f} tgt_hp={tgt_h:5.2f} "
                f"hdg_cmd={env._bt_hdg_cmd:6.1f}"
            )
        modes.append(env._bt_mode)
        if terminated or truncated:
            end_condition = (info or {}).get("end_condition")
            break
    own_health_end = float(env._ownship_state[StateIndex.HEALTH])
    tgt_health_end = float(env._target_state[StateIndex.HEALTH])
    return {
        "min_tgt_alt": min_tgt_alt,
        "min_dist": min_dist,
        "own_hp": own_health_end,
        "tgt_hp": tgt_health_end,
        "modes": set(modes),
        "end_condition": end_condition,
    }


def main():
    print("=== Scenario A: head-on merge (aspect 165-180) -> BT must point, close, and shoot ===")
    # A stern chase vs the open-loop ownship is untestable (neutral stick =
    # accelerating descent that outruns any interceptor), so gunnery is
    # verified on a head-on merge: the BT starts near nose-on and must hold
    # its nose through the closing pass to register WEZ damage on us.
    # slow ownship (throttle 0.35) vs fast BT (340 m/s): after the head-on
    # pass the BT must convert to the ownship's six, saddle, and gun it.
    env = build_env((2500.0, 3000.0), (165.0, 180.0), turn_rate=12.0,
                    own_speed=250.0, attack_speed=280.0)
    a = run_episode(env, 3000, "A", throttle=0.35)
    print(f"A summary: {a}")

    print("=== Scenario B: saddled 600-800m on its six -> BT should EVADE, never crash ===")
    env = build_env((600.0, 800.0), (0.0, 10.0), turn_rate=10.0)
    b = run_episode(env, 1500, "B")
    print(f"B summary: {b}")

    print("=== Scenario C: BT starts on OUR six at 600m -> BT gunnery must register ===")
    env = build_env((600.0, 800.0), (0.0, 10.0), turn_rate=10.0)
    env.config["offensive_saddle"]["enabled"] = False
    # place the BT 600m directly behind a slow ownship, both level heading north
    env.change_init_position("ownship", init_n=0.0, init_e=0.0, init_d=-7000.0,
                             init_roll=0.0, init_pitch=0.0, init_heading=0.0,
                             init_speed=200.0)
    env.change_init_position("target", init_n=-600.0, init_e=0.0, init_d=-7000.0,
                             init_roll=0.0, init_pitch=0.0, init_heading=0.0,
                             init_speed=280.0)
    c = run_episode(env, 900, "C", throttle=0.35)
    print(f"C summary: {c}")

    ok = True
    def check(name, cond):
        nonlocal ok
        print(f"{'PASS' if cond else 'FAIL'}: {name}")
        ok = ok and cond

    check("A: BT closed to gun range (min_dist < 950m)", a["min_dist"] < 950.0)
    check("A: target never below 2000m", a["min_tgt_alt"] > 2000.0)
    check("B: evade mode engaged", "evade" in b["modes"])
    check("B: target never below 2000m", b["min_tgt_alt"] > 2000.0)
    check("B: target did not self-destruct",
          (b["end_condition"] or "").find("target altitude") < 0)
    check("C: BT gunnery registered (own_hp < 1.0)", c["own_hp"] < 1.0)
    check("C: target never below 2000m", c["min_tgt_alt"] > 2000.0)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
