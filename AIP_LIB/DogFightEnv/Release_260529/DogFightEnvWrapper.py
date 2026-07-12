from pathlib import Path
import math
import sys

import numpy as np

_ROOT = Path(__file__).resolve().parent
_SRC = _ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from dogfight.envs.single_agent_env import DogFightEnv


class DogFightWrapper(DogFightEnv):
    """Thin wrapper that adds an optional per-step ACTION SLEW LIMITER.

    The reward function never sees the action, but here it is in scope. A hard
    rate-limit on |a_t - a_{t-1}| prevents the bang-bang control reversals that
    (with action-repeat 6) drive the F-16 into physically impossible states and
    trigger "FDM update fail" episode crashes. Enabled via
    env_config["action_slew_limit"] (max change per component per policy step;
    0 or absent = disabled, i.e. original behavior). This touches neither the
    platform core nor the reward signature.
    """

    def __init__(
        self,
        env_config: dict | None = None,
        AIP_ownship=None,
        AIP_target=None,
        ownship_action_provider=None,
        target_action_provider=None,
        reward_fn=None,
        observation_fn=None,
        observation_size=None,
        observation_low=None,
        observation_high=None,
    ):
        super().__init__(
            env_config=env_config,
            AIP_ownship=AIP_ownship,
            AIP_target=AIP_target,
            ownship_action_provider=ownship_action_provider,
            target_action_provider=target_action_provider,
            reward_fn=reward_fn,
            observation_fn=observation_fn,
            observation_size=observation_size,
            observation_low=observation_low,
            observation_high=observation_high,
        )
        self._action_slew_limit = float(self.config.get("action_slew_limit", 0.0))
        self._action_abs_limit = self._resolve_action_abs_limit(
            self.config.get("action_abs_limit", 0.0)
        )
        self._prev_action = None
        self._action_postprocess_cfg = self.config.get("action_postprocess") or {}
        self._saddle_rng = np.random.default_rng()
        # Range-discipline: end the "extend to infinity" exploit early so the
        # departure penalty lands while it's still credit-assignable.
        self._rd_cfg = self.config.get("range_discipline") or {}
        self._rd_prev_range = None
        self._rd_counter = 0
        # Weave curriculum: oscillate the autopilot target's heading (left/right)
        # AND altitude (up/down) so the agent must track a 3D-maneuvering opponent
        # instead of a straight-flyer. Horizontal and vertical use independent
        # periods so the motion does not collapse into a flat diagonal. A fraction
        # of episodes (straight_prob) fly perfectly straight & level to stop the
        # policy from forgetting the level-target skill it already mastered.
        self._weave_cfg = self.config.get("target_weave") or {}
        _ap = self.config.get("target_autopilot") or {}
        self._weave_base = float(_ap.get("heading_cmd", 0.0))
        self._weave_alt_base = float(_ap.get("altitude_cmd", -7000.0))
        self._weave_step = 0
        self._weave_active = True  # per-episode; may be disabled to fly straight

    @staticmethod
    def _resolve_action_abs_limit(value):
        if value is None:
            return None
        if np.isscalar(value):
            limit = float(value)
            if limit <= 0.0:
                return None
            return np.full(4, limit, dtype=np.float32)
        arr = np.asarray(value, dtype=np.float32)
        if arr.size != 4:
            raise ValueError("action_abs_limit must be a scalar or a 4-element list")
        if np.any(arr <= 0.0):
            raise ValueError("action_abs_limit values must be positive")
        return arr

    @staticmethod
    def _cfg_enabled(cfg: dict | None) -> bool:
        return bool(cfg and cfg.get("enabled", False))

    @staticmethod
    def _signed_unit(value: float, ref: float) -> float:
        ref = max(float(ref), 1.0e-6)
        return float(np.clip(float(value) / ref, -1.0, 1.0))

    def _apply_action_postprocess(self, action: np.ndarray) -> np.ndarray:
        cfg = self._action_postprocess_cfg
        if not self._cfg_enabled(cfg):
            return np.asarray(action, dtype=np.float32)

        a = np.asarray(action, dtype=np.float32).copy()
        az_deg, el_deg = self._geo_info._get_los_angle(
            self._ownship_state,
            self._target_state,
        )
        distance_m = float(
            self._geo_info._get_distance(self._ownship_state, self._target_state)
        )

        los = cfg.get("los_assist") or {}
        if self._cfg_enabled(los):
            az = self._signed_unit(az_deg, float(los.get("az_ref_deg", 8.0)))
            el = self._signed_unit(el_deg, float(los.get("el_ref_deg", 6.0)))
            max_delta = float(los.get("max_delta", 0.35))
            roll_sign = float(los.get("roll_sign", 1.0))
            rudder_sign = float(los.get("rudder_sign", 1.0))
            pitch_sign = float(los.get("pitch_sign", -1.0))
            a[0] += np.clip(roll_sign * float(los.get("roll_gain", 0.0)) * az, -max_delta, max_delta)
            a[1] += np.clip(pitch_sign * float(los.get("pitch_gain", 0.0)) * el, -max_delta, max_delta)
            a[2] += np.clip(rudder_sign * float(los.get("rudder_gain", 0.0)) * az, -max_delta, max_delta)

        bank = cfg.get("bank_turn_assist") or {}
        if self._cfg_enabled(bank):
            ata = abs(float(self._geo_info._get_antenna_train_angle(
                self._ownship_state,
                self._target_state,
                False,
            )))
            if ata > float(bank.get("disable_ata_deg", 0.0)):
                az = self._signed_unit(az_deg, float(bank.get("az_ref_deg", 12.0)))
                a[0] += float(bank.get("roll_gain", 0.0)) * az
                a[1] -= float(bank.get("pull_gain", 0.0)) * abs(az)

        rng = cfg.get("range_assist") or {}
        if self._cfg_enabled(rng):
            target_m = float(rng.get("target_m", 720.0))
            band_m = max(float(rng.get("band_m", 350.0)), 1.0)
            err = self._signed_unit(distance_m - target_m, band_m)
            a[3] += float(rng.get("throttle_gain", 0.0)) * err
            a[3] = np.clip(
                a[3],
                float(rng.get("min_throttle_action", -1.0)),
                float(rng.get("max_throttle_action", 1.0)),
            )

        safety = cfg.get("safety_filter") or {}
        if self._cfg_enabled(safety):
            altitude = float(self._ownship_state[44])
            roll_deg = float(self._ownship_state[3])
            pitch_deg = float(self._ownship_state[4])
            floor_m = float(safety.get("floor_m", 2500.0))
            safe_m = max(float(safety.get("safe_m", 3500.0)), floor_m + 1.0)
            if altitude < safe_m:
                severity = float(np.clip((safe_m - altitude) / (safe_m - floor_m), 0.0, 1.0))
                a[1] -= float(safety.get("pitch_up_gain", 0.0)) * severity
                a[3] = max(a[3], float(safety.get("min_throttle_action", 0.4)))
                roll_ref = max(float(safety.get("roll_ref_deg", 90.0)), 1.0)
                a[0] -= float(safety.get("roll_level_gain", 0.0)) * np.clip(
                    roll_deg / roll_ref,
                    -1.0,
                    1.0,
                ) * severity
                if pitch_deg < -float(safety.get("nose_down_deg", 10.0)):
                    a[1] -= float(safety.get("nose_down_pitch_gain", 0.0)) * severity

        return np.clip(a, -1.0, 1.0)

    def _process_ownship_rl_action(self, action: np.ndarray) -> np.ndarray:
        action = self._apply_action_postprocess(action)

        if self._action_slew_limit > 0.0:
            a = np.asarray(action, dtype=np.float32)
            if self._prev_action is not None:
                lo = self._prev_action - self._action_slew_limit
                hi = self._prev_action + self._action_slew_limit
                a = np.clip(a, lo, hi)
            action = a

        if self._action_abs_limit is not None:
            action = np.clip(
                np.asarray(action, dtype=np.float32),
                -self._action_abs_limit,
                self._action_abs_limit,
            )
        action = self._apply_emergency_recovery(action)
        if self._action_slew_limit > 0.0:
            self._prev_action = np.asarray(action, dtype=np.float32).copy()
        return np.asarray(action, dtype=np.float32)

    def _apply_emergency_recovery(self, action: np.ndarray) -> np.ndarray:
        cfg = self._action_postprocess_cfg
        emergency = (cfg.get("emergency_recovery") or {}) if cfg else {}
        if not self._cfg_enabled(emergency):
            return np.asarray(action, dtype=np.float32)

        altitude = float(self._ownship_state[44])
        trigger_m = float(emergency.get("trigger_m", 4800.0))
        floor_m = float(emergency.get("floor_m", 3600.0))
        if altitude >= trigger_m:
            return np.asarray(action, dtype=np.float32)

        hazard_gates = []
        require_nose_down = emergency.get("require_nose_down_deg")
        if require_nose_down is not None:
            pitch_deg = float(self._ownship_state[4])
            hazard_gates.append(pitch_deg < -abs(float(require_nose_down)))

        require_descent = emergency.get("require_descent_mps")
        if require_descent is not None:
            velocity_index = int(emergency.get("vertical_velocity_index", 8))
            if 0 <= velocity_index < len(self._ownship_state):
                descent_sign = float(emergency.get("vertical_velocity_descent_sign", 1.0))
                descent_mps = descent_sign * float(self._ownship_state[velocity_index])
                hazard_gates.append(descent_mps > abs(float(require_descent)))

        if hazard_gates and not any(hazard_gates):
            return np.asarray(action, dtype=np.float32)

        span = max(trigger_m - floor_m, 1.0)
        severity = float(np.clip((trigger_m - altitude) / span, 0.0, 1.0))
        a = np.asarray(action, dtype=np.float32).copy()

        min_pitch_up = -abs(float(emergency.get("pitch_up_action", 0.50)))
        a[1] = min(float(a[1]), min_pitch_up * severity)
        a[3] = max(float(a[3]), float(emergency.get("min_throttle_action", 0.75)))

        roll_ref = max(float(emergency.get("roll_ref_deg", 80.0)), 1.0)
        roll_deg = float(self._ownship_state[3])
        a[0] -= float(emergency.get("roll_level_gain", 0.35)) * np.clip(
            roll_deg / roll_ref,
            -1.0,
            1.0,
        ) * severity
        return np.clip(a, -1.0, 1.0)

    def _step_controlled_aircraft(self, action: np.ndarray) -> None:
        if self._ownship_action_provider is not None:
            context = self._build_action_context(
                self._sim,
                self._target_sim,
                self._ownship_state,
                self._target_state,
                self.pre_obs,
            )
            result = self._ownship_action_provider.compute_action(context)
            provider_action = np.asarray(result.action, dtype=np.float32)
            if result.info.get("action_space") == "rl":
                provider_action = self._process_ownship_rl_action(provider_action)
                self._sim.step(self._to_sim_action(provider_action))
            else:
                self._sim.step(provider_action)
            return

        super()._step_controlled_aircraft(action)

    def _place_offensive_saddle(self, cfg: dict) -> None:
        """Spawn the agent in an OFFENSIVE SADDLE: a few hundred metres behind a
        slow, level target, pointed at it (sustained gun-range start). This
        manufactures first contact geometrically — the bootstrap the from-1.4km
        spawn never reached. Range/aspect/side are randomized within bands each
        episode so the policy generalizes instead of memorizing one picture.

        Pair with env.target_mode: autopilot (slow, level, non-evading) and an
        initial_scenario that does NOT reposition (omit it / mode: default), so
        these placements survive to sim.reset(). Set positions BEFORE
        super().reset() runs the (no-op) scenario dispatch and sim.reset().
        """
        rng = self._saddle_rng
        r_lo, r_hi = cfg.get("range_m", [250.0, 450.0])
        a_lo, a_hi = cfg.get("aspect_deg", [0.0, 12.0])
        alt = float(cfg.get("altitude_m", 7000.0))
        tgt_speed = float(cfg.get("target_speed_mps", 180.0))
        own_speed = float(cfg.get("own_speed_mps", 300.0))

        R = float(rng.uniform(r_lo, r_hi))
        A = math.radians(float(rng.uniform(a_lo, a_hi)))
        side = float(rng.choice([-1.0, 1.0]))

        # Target flies due north (heading 0), level; autopilot holds it there.
        self.change_init_position(
            "target", init_n=0.0, init_e=0.0, init_d=-alt,
            init_roll=0.0, init_pitch=0.0, init_heading=0.0, init_speed=tgt_speed,
        )
        # Ownship R behind, offset by aspect A to the chosen side, pointed at target.
        own_n = -R * math.cos(A)
        own_e = side * R * math.sin(A)
        own_heading = math.degrees(math.atan2(0.0 - own_e, 0.0 - own_n)) % 360.0
        self.change_init_position(
            "ownship", init_n=own_n, init_e=own_e, init_d=-alt,
            init_roll=0.0, init_pitch=0.0, init_heading=own_heading, init_speed=own_speed,
        )

    def _apply_random_jink(self, ap: dict) -> None:
        """Random-jink target motion: hold a random turn/climb rate for a random
        number of wrapper-steps, then re-roll a NEW random magnitude, direction,
        and switch interval. Randomizing all three (size, direction, switch
        timing) makes the evader unpredictable, unlike the fixed sinusoid. The
        heading integrates continuously; the altitude command random-walks within
        a bounded band so it never drifts into the ground or absurd heights."""
        cfg = self._weave_cfg
        rng = self._saddle_rng
        if self._wv_switch_left <= 0:
            # New maneuver segment: random horizontal turn rate (deg/step) and a
            # random vertical rate (m/step), each with a random sign, held for a
            # random duration between switch_min_steps and switch_max_steps.
            hr_lo = float(cfg.get("hdg_rate_min_deg", 2.0))
            hr_hi = float(cfg.get("hdg_rate_max_deg", 9.0))
            vr_lo = float(cfg.get("vert_rate_min_m", 4.0))
            vr_hi = float(cfg.get("vert_rate_max_m", 18.0))
            s_lo = int(cfg.get("switch_min_steps", 25))
            s_hi = max(s_lo, int(cfg.get("switch_max_steps", 90)))
            self._wv_hdg_rate = float(rng.choice([-1.0, 1.0])) * float(rng.uniform(hr_lo, hr_hi))
            self._wv_v_rate = float(rng.choice([-1.0, 1.0])) * float(rng.uniform(vr_lo, vr_hi))
            self._wv_switch_left = int(rng.integers(s_lo, s_hi + 1))
        # Integrate the current segment's rates into absolute commands.
        self._wv_heading = (self._wv_heading + self._wv_hdg_rate) % 360.0
        v_dev_max = float(cfg.get("vertical_dev_max_m", 1200.0))
        # altitude_cmd is Down-positive; keep it within +/- v_dev_max of the base.
        new_alt = self._wv_alt + self._wv_v_rate
        lo = self._weave_alt_base - v_dev_max
        hi = self._weave_alt_base + v_dev_max
        if new_alt < lo or new_alt > hi:
            self._wv_v_rate = -self._wv_v_rate  # bounce off the band edge
            new_alt = min(max(new_alt, lo), hi)
        self._wv_alt = new_alt
        ap["heading_cmd"] = self._wv_heading
        ap["altitude_cmd"] = self._wv_alt
        self._wv_switch_left -= 1

    def reset(self, *args, **kwargs):
        seed = kwargs.get("seed")
        if seed is not None:
            self._saddle_rng = np.random.default_rng(int(seed))
        # Start each episode from a neutral action so the first step is also
        # slew-limited (no violent input out of the gate).
        self._prev_action = np.zeros(4, dtype=np.float32)
        self._rd_prev_range = None
        self._rd_counter = 0
        self._weave_step = 0
        # Decide once per episode whether the target weaves or flies straight.
        # straight_prob fraction of episodes are straight & level (anti-forgetting);
        # on those we also pin the autopilot commands back to their base values.
        straight_prob = float(self._weave_cfg.get("straight_prob", 0.0))
        self._weave_active = bool(self._saddle_rng.uniform() >= straight_prob)
        # Random-jink state (only used when target_weave.random_jink is true): the
        # target integrates a random turn/climb rate for a random number of steps,
        # then re-rolls a NEW random magnitude + direction + switch interval. This
        # makes size, direction, and turn-switch timing all unpredictable, unlike
        # the fixed-amplitude/period sinusoid. Current absolute heading/altitude
        # commands are integrated from the base each episode.
        self._wv_heading = self._weave_base
        self._wv_alt = self._weave_alt_base
        self._wv_hdg_rate = 0.0
        self._wv_v_rate = 0.0
        self._wv_switch_left = 0
        if self._weave_cfg.get("enabled") and self.config.get("target_mode") == "autopilot":
            ap = self.config.get("target_autopilot") or {}
            ap["heading_cmd"] = self._weave_base
            ap["altitude_cmd"] = self._weave_alt_base
        saddle = self.config.get("offensive_saddle") or {}
        if saddle.get("enabled"):
            self._place_offensive_saddle(saddle)
        return super().reset(*args, **kwargs)

    def step(self, action):
        if (
            self._weave_active
            and self._weave_cfg.get("enabled")
            and self.config.get("target_mode") == "autopilot"
        ):
            ap = self.config["target_autopilot"]
            if self._weave_cfg.get("random_jink"):
                self._apply_random_jink(ap)
            else:
                # Horizontal (left/right) heading weave.
                amp = float(self._weave_cfg.get("amplitude_deg", 20.0))
                period = max(1.0, float(self._weave_cfg.get("period_steps", 120.0)))
                heading = self._weave_base + amp * math.sin(2.0 * math.pi * self._weave_step / period)
                ap["heading_cmd"] = heading % 360.0
                # Vertical (up/down) altitude weave. amplitude in METERS; independent
                # period so the 3D path is not a flat diagonal. altitude_cmd is
                # Down-positive (base -alt), so oscillating it around the base moves
                # the target up and down through +/- vertical_amplitude_m.
                v_amp = float(self._weave_cfg.get("vertical_amplitude_m", 0.0))
                if v_amp > 0.0:
                    v_period = max(1.0, float(self._weave_cfg.get("vertical_period_steps", period)))
                    ap["altitude_cmd"] = self._weave_alt_base + v_amp * math.sin(
                        2.0 * math.pi * self._weave_step / v_period
                    )
                self._weave_step += 1

        if self._ownship_action_provider is None:
            action = self._process_ownship_rl_action(action)

        result = super().step(action)
        if self._rd_cfg.get("enabled") and isinstance(result, tuple) and len(result) == 5:
            result = self._apply_range_discipline(result)
        return result

    def _apply_range_discipline(self, result):
        """Terminate (as a LOSS) once the agent has flown far from the target and
        kept opening for K steps — the "one pass then extend to a 900-step draw"
        exploit. Discounted at gamma=0.997 a step-900 draw is ~-12 PV at the
        moment of the overshoot (invisible to the value head); ending early makes
        the same -150 land at PV ~-105, so departure becomes credit-assignable.
        Hysteresis (large AND increasing AND sustained) spares legitimate reversals
        that transiently open range before turning back to re-attack.
        """
        obs, reward, terminated, truncated, info = result
        if terminated or truncated:
            return result

        dist = float(self._geo_info._get_distance(self._ownship_state, self._target_state))
        max_r = float(self._rd_cfg.get("max_range_m", 2500.0))
        grow_k = int(self._rd_cfg.get("grow_steps", 30))

        opening = self._rd_prev_range is not None and dist > self._rd_prev_range
        if dist > max_r and opening:
            self._rd_counter += 1
        else:
            self._rd_counter = 0
        self._rd_prev_range = dist

        if self._rd_counter >= grow_k:
            loss = float((self.config.get("reward") or {}).get("loss_reward", -150.0))
            reward = float(reward) + loss
            terminated = True
            if isinstance(info, dict):
                info = {**info, "end_condition": "range discipline", "outcome": "loss"}
            self._rd_counter = 0
            return (obs, reward, terminated, truncated, info)
        return result


__all__ = ["DogFightWrapper"]
