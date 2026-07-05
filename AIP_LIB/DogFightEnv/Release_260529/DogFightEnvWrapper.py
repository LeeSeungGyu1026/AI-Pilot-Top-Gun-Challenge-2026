from pathlib import Path
import math
import sys

import numpy as np

_ROOT = Path(__file__).resolve().parent
_SRC = _ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from dogfight.envs.single_agent_env import DogFightEnv
from dogfight.sim.state_schema import StateIndex


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
        # Altitude-discipline: end a dive-to-the-deck early (same credit-assignment
        # logic as range-discipline, applied to the vertical). Seeds trained vs a
        # non-threatening autopilot pure-pursue a maneuvering/diving BT straight
        # into the ground ("ownship altitude below min" dominates), because from a
        # 7000m spawn the per-step altitude-floor reward only bites in the last few
        # hundred metres -- far too late to arrest a committed dive. Ending the
        # episode as a LOSS the moment own altitude drops below floor_m makes
        # "chasing the bandit down" an EARLY, salient, credit-assignable loss.
        self._ad_cfg = self.config.get("altitude_discipline") or {}
        self._ad_counter = 0
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
        # Python-BT opponent: a scripted pursue/evade brain that drives the
        # AUTOPILOT backend (heading/altitude/speed commands) instead of the
        # closed BT DLL. Motivation (2026-07-05, ic_s6 v1-v6 autopsy): the DLL
        # BT's task->control loop rolls inverted and dives into the ground under
        # close-range pressure (64.5% of v6 episodes ended "target altitude
        # below min"), which no XML parameter can prevent. The autopilot backend
        # never leaves controlled flight (0 target crashes across the whole
        # ic_s4/s5 weave curriculum), so building the opponent on top of it
        # makes the no-suicide property structural. update_damage() is
        # backend-symmetric, so this opponent SHOOTS whenever its nose is on the
        # agent inside the WEZ band. Difficulty = target_bt.max_turn_rate_deg_s
        # (one number), not a ladder of XML files.
        self._bt_cfg = self.config.get("target_bt") or {}
        self._bt_dt = float(self.config.get("step_ratio", 6)) / float(
            self.config.get("sim_hz", 60)
        )
        self._bt_active = bool(self._bt_cfg.get("enabled"))
        self._bt_hdg_cmd = None
        self._bt_alt_cmd = None
        self._bt_mode = "attack"
        self._bt_mode_age = 0
        self._bt_jink_side = 1.0
        self._bt_jink_vert = 0.0
        self._bt_jink_left = 0
        self._bt_prev_own_pos = None

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

    def _apply_python_bt(self, ap: dict) -> None:
        """Scripted pursue/evade opponent on the autopilot backend.

        Runs once per wrapper step from the LAST completed frame's states.
        ATTACK: lead-pursuit the agent (bearing to its dead-reckoned future
        position) and match its altitude. EVADE: when the agent is saddled in
        our rear hemisphere, nose-on, inside threat range, break across its
        line of sight (side re-rolled per jink segment) with a bounded vertical
        offset. All commands pass through two hard governors that make the
        opponent both tunable and un-killable-by-itself:
          - heading command slews at <= max_turn_rate_deg_s  (THE difficulty dial)
          - altitude command slews at <= max_climb_rate_mps and is CLAMPED to
            [min_altitude_m, max_altitude_m], so a ground impact cannot even be
            commanded, let alone flown.
        """
        cfg = self._bt_cfg
        own = getattr(self, "_ownship_state", None)
        tgt = getattr(self, "_target_state", None)
        if own is None or tgt is None:
            return
        own = np.asarray(own, dtype=np.float64)
        tgt = np.asarray(tgt, dtype=np.float64)
        if not (np.isfinite(own[:6]).all() and np.isfinite(tgt[:6]).all()):
            return
        rng = self._saddle_rng
        dt = self._bt_dt

        # --- geometry (2D angles for heading decisions) ---
        dist = float(self._geo_info._get_distance(tgt, own))
        # agent's angle off OUR nose: 0 = we point at agent, 180 = agent astern
        ata_us_to_agent = abs(float(self._geo_info._get_antenna_train_angle(tgt, own, True)))
        # our angle off the AGENT's nose: 0 = agent points at us (tracking)
        ata_agent_to_us = abs(float(self._geo_info._get_antenna_train_angle(own, tgt, True)))
        own_pos = own[:3].copy()
        own_alt = float(own[StateIndex.ALT])
        tgt_alt = float(tgt[StateIndex.ALT])

        # first BT step of the episode: seed commands from the target's actual state
        if self._bt_hdg_cmd is None:
            self._bt_hdg_cmd = float(tgt[StateIndex.YAW]) % 360.0
        if self._bt_alt_cmd is None:
            self._bt_alt_cmd = tgt_alt

        # --- threat assessment / mode with hysteresis ---
        threat_range = float(cfg.get("threat_range_m", 1500.0))
        rear_deg = float(cfg.get("threat_rear_deg", 90.0))
        track_deg = float(cfg.get("threat_track_deg", 40.0))
        mode_hold = int(cfg.get("mode_min_steps", 20))
        evade_enabled = bool(cfg.get("evade_enabled", True))
        threatened = (
            evade_enabled
            and dist < threat_range
            and ata_us_to_agent > rear_deg
            and ata_agent_to_us < track_deg
        )
        self._bt_mode_age += 1
        if self._bt_mode_age >= mode_hold:
            want = "evade" if threatened else "attack"
            if want != self._bt_mode:
                self._bt_mode = want
                self._bt_mode_age = 0
                self._bt_jink_left = 0  # force a fresh jink segment on entry

        # --- desired heading / altitude / speed per mode ---
        bearing_to_agent = math.degrees(
            math.atan2(own_pos[1] - tgt[1], own_pos[0] - tgt[0])
        ) % 360.0
        if self._bt_mode == "evade":
            # jink segments: re-roll break side + vertical offset at random intervals
            if self._bt_jink_left <= 0:
                self._bt_jink_side = float(rng.choice([-1.0, 1.0]))
                v_dev = float(cfg.get("evade_vertical_m", 500.0))
                self._bt_jink_vert = float(rng.uniform(-v_dev, v_dev))
                j_lo = int(cfg.get("jink_min_steps", 25))
                j_hi = max(j_lo, int(cfg.get("jink_max_steps", 70)))
                self._bt_jink_left = int(rng.integers(j_lo, j_hi + 1))
            self._bt_jink_left -= 1
            break_deg = float(cfg.get("break_angle_deg", 100.0))
            desired_hdg = (bearing_to_agent + self._bt_jink_side * break_deg) % 360.0
            desired_alt = tgt_alt + self._bt_jink_vert
            speed_cmd = float(cfg.get("speed_evade_mps", 270.0))
        else:
            # lead pursuit: dead-reckon the agent lead_time_s ahead. Lead is
            # capped at HALF the current range: with a full-range cap a head-on
            # merge dead-reckons the aim point onto (or past) our own position
            # and the bearing to it whips around, winding the heading command.
            lead_time = float(cfg.get("lead_time_s", 3.0))
            aim = own_pos
            if self._bt_prev_own_pos is not None and dt > 0.0:
                vel = (own_pos - self._bt_prev_own_pos) / dt
                if np.isfinite(vel).all():
                    lead_vec = vel * lead_time
                    lead_len = float(np.linalg.norm(lead_vec))
                    lead_cap = 0.5 * dist
                    if lead_len > lead_cap > 0.0:
                        lead_vec *= lead_cap / lead_len
                    aim = own_pos + lead_vec
            desired_hdg = math.degrees(math.atan2(aim[1] - tgt[1], aim[0] - tgt[0])) % 360.0
            desired_alt = own_alt
            speed_cmd = float(cfg.get("speed_attack_mps", 260.0))
        self._bt_prev_own_pos = own_pos
        # Speed commands outside the airframe/autopilot's achievable band are
        # actively dangerous: chasing an unreachable speed_cmd made the JSBSim
        # autopilot trade ~3000m of altitude for airspeed in one diving spiral
        # (observed with speed_cmd=340). The weave/jink curriculum flew its whole
        # life at 250 with benign +/-300m excursions, so clamp near that band.
        speed_cmd = min(max(speed_cmd, 180.0), float(cfg.get("speed_max_mps", 290.0)))

        # --- governors: turn-rate slew (difficulty), climb slew + hard altitude clamp ---
        max_turn = float(cfg.get("max_turn_rate_deg_s", 8.0)) * dt
        hdg_err = ((desired_hdg - self._bt_hdg_cmd + 180.0) % 360.0) - 180.0
        self._bt_hdg_cmd = (self._bt_hdg_cmd + max(-max_turn, min(max_turn, hdg_err))) % 360.0
        # Never let the COMMAND wind further than command_lead_max_deg beyond the
        # aircraft's ACTUAL heading. The autopilot plant turns slower than the
        # command slew; without this clamp a 180-deg bearing flip at the merge
        # leaves the command 100+ deg ahead of the airframe, and the fight is
        # over before the plane finishes chasing its own command around.
        lead_max = float(cfg.get("command_lead_max_deg", 45.0))
        actual_hdg = float(tgt[StateIndex.YAW]) % 360.0
        cmd_off = ((self._bt_hdg_cmd - actual_hdg + 180.0) % 360.0) - 180.0
        self._bt_hdg_cmd = (actual_hdg + max(-lead_max, min(lead_max, cmd_off))) % 360.0

        max_climb = float(cfg.get("max_climb_rate_mps", 40.0)) * dt
        alt_err = desired_alt - self._bt_alt_cmd
        self._bt_alt_cmd += max(-max_climb, min(max_climb, alt_err))
        alt_lo = float(cfg.get("min_altitude_m", 3000.0))
        alt_hi = float(cfg.get("max_altitude_m", 11000.0))
        self._bt_alt_cmd = min(max(self._bt_alt_cmd, alt_lo), alt_hi)

        ap["heading_cmd"] = self._bt_hdg_cmd
        ap["altitude_cmd"] = -self._bt_alt_cmd  # NED: Down-positive
        ap["speed_cmd"] = speed_cmd

    def reset(self, *args, **kwargs):
        # Start each episode from a neutral action so the first step is also
        # slew-limited (no violent input out of the gate).
        self._prev_action = np.zeros(4, dtype=np.float32)
        self._rd_prev_range = None
        self._rd_counter = 0
        self._ad_counter = 0
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
        # Python-BT per-episode state: commands re-seed from the target's actual
        # attitude on the first step; every episode opens in ATTACK.
        # target_bt.prob (default 1.0) = fraction of episodes the BT drives the
        # target; the rest fall through to the weave/random-jink path so the
        # mastered autopilot-evader skill keeps getting on-policy positive
        # reward (anti-forgetting + keeps wins in every PPO batch).
        self._bt_active = bool(self._bt_cfg.get("enabled")) and (
            self._saddle_rng.uniform() < float(self._bt_cfg.get("prob", 1.0))
        )
        self._bt_hdg_cmd = None
        self._bt_alt_cmd = None
        self._bt_mode = "attack"
        self._bt_mode_age = 0
        self._bt_jink_left = 0
        self._bt_prev_own_pos = None
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
            self._bt_active
            and self._bt_cfg.get("enabled")
            and self.config.get("target_mode") == "autopilot"
        ):
            self._apply_python_bt(self.config["target_autopilot"])
        elif (
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
        if self._ad_cfg.get("enabled") and isinstance(result, tuple) and len(result) == 5:
            result = self._apply_altitude_discipline(result)
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

    def _apply_altitude_discipline(self, result):
        """Terminate (as a LOSS) once own altitude has stayed below floor_m for
        `sustain_steps` consecutive steps. Mirrors _apply_range_discipline but on
        the vertical axis: it makes "pure-pursuing the bandit into a dive" an
        EARLY, salient, credit-assignable loss instead of a late "ownship altitude
        below min" crash the value head cannot foresee from 7000m up.

        floor_m sits well above the ground (e.g. 2500m from a 7000m co-altitude
        start) so it ends losing energy states without clipping a legitimate high
        gun pass. `sustain_steps` (default 1) adds optional hysteresis so a brief
        transient dip that immediately recovers does not false-trigger.
        """
        obs, reward, terminated, truncated, info = result
        if terminated or truncated:
            return result

        alt = float(self._ownship_state[StateIndex.ALT])
        floor_m = float(self._ad_cfg.get("floor_m", 2500.0))
        sustain = max(1, int(self._ad_cfg.get("sustain_steps", 1)))

        if alt < floor_m:
            self._ad_counter += 1
        else:
            self._ad_counter = 0

        if self._ad_counter >= sustain:
            loss = float((self.config.get("reward") or {}).get("loss_reward", -150.0))
            reward = float(reward) + loss
            terminated = True
            if isinstance(info, dict):
                info = {**info, "end_condition": "altitude discipline", "outcome": "loss"}
            self._ad_counter = 0
            return (obs, reward, terminated, truncated, info)
        return result


__all__ = ["DogFightWrapper"]
