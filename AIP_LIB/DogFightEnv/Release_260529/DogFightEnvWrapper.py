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
        self._prev_action = None
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

        if self._action_slew_limit > 0.0:
            a = np.asarray(action, dtype=np.float32)
            if self._prev_action is not None:
                lo = self._prev_action - self._action_slew_limit
                hi = self._prev_action + self._action_slew_limit
                a = np.clip(a, lo, hi)
            self._prev_action = a.copy()
            action = a

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
