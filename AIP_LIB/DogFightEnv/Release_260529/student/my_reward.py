# -*- coding: utf-8 -*-
"""Team reward (advisor round 3): all-PBRS shaping + first-WEZ-entry bonus +
asymmetric damage, with the safe-draw attractor removed.

Why this shape (the key lesson):
  A constant reward carries no gradient. PPO does not learn "hold attitude,
  keep energy" from a flat +survival/step; it learns flight from a signal that
  DISTINGUISHES good geometry from bad. Pursuit shaping is that signal — you
  cannot pursue a target while tumbling earthward — so it implicitly organizes
  coordinated, energy-conserving flight. We therefore keep potential-based
  shaping ON at all times and never run a gradient-free "survival only" reward.

Components (all potential-based shaping is policy-invariant, so it cannot
distort the true win/loss objective):
  - pursuit : gamma*Phi_p(s') - Phi_p(s), Phi_p from ATA + log-range
              (continuous range-closure + boresight signal) + a small optional
              dense term + a one-time first-WEZ-entry bonus (strongly reinforce
              making contact, evaluated against the runtime/widened cone).
  - safety  : gamma*Phi_h(s') - Phi_h(s), Phi_h increasing in altitude. For
              gamma~=1 this ~= Phi'(h)*climb_rate -> reward climbing, penalize
              sinking: a RECOVERY gradient near the floor. Phi(terminal)=0, so a
              crash forfeits only the small remaining Phi (cannot be farmed by
              terminating), and leveling off nets ~0. Replaces the old flat
              penalty ramp, which had no recovery gradient and was farmable by
              crashing fast to stop the per-step bleed.
  - damage  : asymmetric (dealt >> taken) so pure evasion does not dominate.
  - terminal: win / loss / draw. Draw <= loss by default to remove the
              "stall for a safe draw" attractor that made the flat policy loiter.

Two additions on top of the round-3 shape (both continuous, not gated, for the
same reason as the dense pursuit term above — a hard on/off condition creates
a flat zero-gradient region right where the policy most needs signal):
  - aspect shaping (folded into "pursuit"): a linear ramp-to-zero-at-cone-edge
    threat penalty when the BT's nose is inside its forward `aspect_cone_deg`
    cone (BT can gun us) and a reward ramp when the ownship sits in the BT's
    rear `aspect_cone_deg` cone (ownship is in the BT's six). Both use the
    same "angle_deg = full cone width" convention as the WEZ config. This is
    independent of the existing ATA/range pursuit term, which only rewards
    OUR aim on the BT, not the BT's aim on us.
  - altitude floor bumper (folded into "safety"): a REAL (non-potential) per-
    step penalty that switches on once altitude is within `critical_alt_margin_m`
    of the floor and grows with `altitude_floor_penalty_exponent` as it nears
    the floor. Added because the PBRS altitude potential alone did not stop the
    agent from following the BT's defensive dive into the ground (observed:
    ownship crashed at full health chasing the BT's low-altitude break) — PBRS
    nets to ~0 over an episode by design, so it discourages sinking but never
    makes "keep chasing into the ground" strictly worse than breaking off. This
    term does.

Telemetry: the platform logs only the fixed component names pursuit/damage/
safety/survival, so shaping is folded into those slots (pursuit-PBRS+dense+
wez-bonus+aspect -> "pursuit"; altitude-PBRS+floor-bumper -> "safety").
step/terminal still count toward the total but are not surfaced on the
dashboard. Direct tactical signals to actually watch live: ep_min_distance,
ep_wez_steps, win_rate, crash_rate.

Third addition (v4, terminal reward only): split "target destroyed" (real
kill, tgt_hp<=0) from "target altitude below min while target still alive"
(forced-ground) into `win_reward` vs `forced_ground_reward`. Both used to pay
the same `win_reward` on the theory that forcing an opponent into the ground
is a legitimate competition win — true, but ic_s3_bt_v3 (BT given a hard 900m
maneuver floor, so it should rarely self-crash) showed PPO exploiting the
equal payoff instead: near-100% "wins" via forced-ground with ep_wez_steps
~8-11 of a ~240-step episode and ep_reward_damage ~3-4 (of a possible ~30 for
a full kill) — i.e. camp in the BT's six (which the aspect-shaping reward
already encourages) and let it panic itself into the ground, rather than
closing for a shot. The actual training objective is a real kill, not this
metric; forced_ground_reward is set well below win_reward so a genuine kill
is unambiguously the better outcome.

Fourth addition (v9->v10, folded into "pursuit"): a per-step aim-precision
bonus active within the TRUE WEZ range band and inside a WIDE, reward-only
cone (`wez_shaping_cone_deg`) -- the real, symmetric damage/kill criteria
(`wez_config["angle_deg"]`, platform default 2deg) are UNCHANGED. v7/v8
showed the RL reaching true WEZ range but never holding the narrow true cone
(no gradient toward precision). v9's first cut (linear, 30 at the 45deg cone
edge -> 60 dead-on) proved the predicted failure mode within 44 iterations:
rough aim anywhere in the cone paid several win_rewards per second, so PPO
farmed proximity and even accepted guaranteed self-crashes (own-crash 76.5%,
kills 0%). v10 (user redesign): 90deg cone, edge pays only 1, rising
EXPONENTIALLY to 100 at dead-on -- sloppy aim ~worthless, payoff concentrated
where the true kill cone (and its automatic damage) lives. Paired with the
altitude bumper rebalance (600m->300m band, 1 -> 1000 exponential, replacing
the max-25 polynomial the bonus had been outbidding) so no shaping payoff can
ever again make crashing a rational trade.
"""
from __future__ import annotations

import math

from dogfight.sim.state_schema import StateIndex


MY_REWARD_CONFIG = {
    # terminal — draw <= loss kills the safe-draw / loiter attractor
    "win_reward": 150.0,          # paid ONLY for a genuine kill (target_hp <= 0)
    "forced_ground_reward": 50.0,  # target crashed on its own while still alive;
                                    # still a legal competition win, but paid far
                                    # less than a real kill so PPO doesn't settle
                                    # for harassing the BT into panicking instead
                                    # of closing for the shot (see v4 notes below).
    "loss_reward": -150.0,
    "draw_reward": -150.0,        # was -20; equal to loss so stalling never pays
    "guard_fail_penalty": -50.0,
    # damage (asymmetric: dealing >> taking)
    "damage_dealt_scale": 30.0,
    "damage_taken_scale": 12.0,
    # one-time bonus the first time the agent enters the TRUE (competition)
    # WEZ cone -- unchanged kill/damage criteria, wez_config["angle_deg"].
    "wez_entry_bonus": 20.0,
    # Per-step aim-precision bonus (v10 shape): active whenever in true WEZ
    # RANGE (unchanged range gate) and inside a WIDE, reward-ONLY cone
    # (wez_shaping_cone_deg) -- the actual kill/damage model still only uses
    # wez_config["angle_deg"], symmetric for both aircraft, untouched.
    # v10 rebalance after v9b's failure (flat-ish 30-60/step made "rough aim
    # anywhere in the cone" worth more than winning, and PPO started
    # accepting guaranteed self-crashes to farm it -- own-crash hit 76.5%):
    # the edge now pays only wez_precision_bonus_min (1) and the bonus rises
    # EXPONENTIALLY to wez_precision_bonus_max (100) at dead-on, i.e.
    # bonus = min * (max/min)^(1 - |ata|/half_angle). Sloppy aim is nearly
    # worthless (90deg cone edge: 1, 45deg off: 10) while precision pays
    # steeply (10deg off: ~60, dead-on: 100) -- and dead-on inside range IS
    # the true 2deg kill cone dealing automatic damage, so the gradient
    # funnels into actual kills instead of cone-loitering.
    "wez_shaping_cone_deg": 90.0,
    "wez_precision_bonus_min": 1.0,
    "wez_precision_bonus_max": 100.0,
    # pursuit PBRS potential (continuous range-closure + boresight; always on)
    # NOTE: pbrs_gamma = 1.0 (NOT the training gamma). With gamma<1 a saturated
    # potential bleeds (gamma-1)*Phi every step, which over an 18k-step episode
    # reaches ~-540 in the logged reward and makes longer/better episodes look
    # worse. gamma=1 makes F=Phi(s')-Phi(s) telescope exactly (clean logs); the
    # policy-invariance bias vs the true gamma is negligible and standard.
    "pbrs_gamma": 1.0,
    "pbrs_ata_weight": 2.0,
    "pbrs_range_weight": 1.0,
    "pbrs_range_log_clip": 3.0,
    # altitude PBRS potential (recovery gradient; replaces the flat penalty)
    "pbrs_alt_weight": 10.0,      # max altitude potential (episode shaping bound)
    "safety_floor_m": 300.0,      # = env min_altitude (Phi=0 at/below)
    "safety_safe_m": 900.0,       # Phi saturates above this (no pressure when safe)
    # small dense pursuit term; range kept WIDE (continuous pull, NOT gated to
    # a region the policy may not visit — v2 proved gating just deletes signal).
    "pursuit_dense_scale": 0.1,
    "pursuit_half_angle_deg": 45.0,
    "pursuit_range_m": 4000.0,
    # aspect shaping: nose-threat penalty + six-o'clock reward, both a linear
    # ramp from 0 at the cone edge to the scale at boresight (angle_deg = full
    # cone width, matching the wez.angle_deg convention).
    "aspect_cone_deg": 30.0,
    "front_cone_penalty_scale": 0.3,   # max penalty when BT's nose is dead on us
    "rear_cone_reward_scale": 0.3,     # max reward when we sit dead astern of BT
    # hard (non-PBRS) altitude floor bumper: kicks in critical_alt_margin_m
    # above safety_floor_m (i.e. at 600m for floor=300/margin=300), paying
    # -altitude_floor_penalty_min at the 600m edge and growing EXPONENTIALLY
    # to -altitude_floor_penalty_max at/below the 300m floor. v10 rebalance:
    # the old polynomial max-25 version was outbid by the v9 precision bonus
    # (PPO happily ate it to farm 30-60/step near the ground); 1 -> 1000
    # exponential makes low flight catastrophically unprofitable no matter
    # what shaping is active.
    "critical_alt_margin_m": 300.0,
    "altitude_floor_penalty_min": 1.0,
    "altitude_floor_penalty_max": 1000.0,
    # time pressure
    "step_penalty": -0.005,
    # curriculum compat (a survival stage may set this; deprecated path)
    "survival_bonus": 0.0,
    # Uniform output scale applied to the TOTAL and every logged component at
    # the very end of compute_reward (v11). Why: RLlib PPO's vf_clip_param
    # defaults to 10.0 and is documented as "sensitive to the scale of the
    # rewards" -- with v10's raw returns spanning ±1000..4600 the value
    # function's updates were clipped into uselessness (explained_var ~0.004
    # across all of v10, vs 0.639 in v7 whose returns stayed within ~±300),
    # which wrecks advantage estimates and shows up as noisy, non-converging
    # policies. Uniform positive scaling preserves the optimal policy and all
    # designed reward RATIOS exactly (PPO also standardizes advantages, so the
    # policy gradient is scale-invariant); only the value-target magnitude
    # changes. 0.05 (=1/20) maps v10's return range back into v7's proven-
    # healthy one. Set to 1.0 to disable.
    "reward_output_scale": 0.05,
    # NOT used — kept because the platform record writer (describe_reward)
    # hard-indexes these default-reward keys.
    "damage_scale": 0.0,
    "low_altitude_penalty": 0.0,
}

# Per-env episode state, keyed by id(geo_info): prev potentials + WEZ-entry flag.
_EP_STATE: dict[int, dict] = {}
_EP_STATE_MAX_ENTRIES = 64


def _pursuit_potential(distance: float, ata_deg: float, wez_config: dict, cfg: dict) -> float:
    """Phi_p <= 0; closer to 0 = better attacking geometry (boresight + range)."""
    ata_term = float(cfg.get("pbrs_ata_weight", 2.0)) * abs(ata_deg) / 180.0
    wez_mid = (float(wez_config["min_range_m"]) + float(wez_config["max_range_m"])) / 2.0
    log_clip = float(cfg.get("pbrs_range_log_clip", 3.0))
    range_off = min(abs(math.log(max(distance, 1.0) / wez_mid)), log_clip)
    range_term = float(cfg.get("pbrs_range_weight", 1.0)) * range_off / log_clip
    return -(ata_term + range_term)


def _altitude_potential(alt: float, cfg: dict) -> float:
    """Phi_h >= 0, increasing in altitude; flat (no pressure) above safe_m."""
    floor = float(cfg.get("safety_floor_m", 300.0))
    safe = float(cfg.get("safety_safe_m", 900.0))
    if safe <= floor:
        return 0.0
    frac = (alt - floor) / (safe - floor)
    return float(cfg.get("pbrs_alt_weight", 10.0)) * min(max(frac, 0.0), 1.0)


def _altitude_floor_penalty(alt: float, cfg: dict) -> float:
    """Real (non-PBRS) per-step penalty inside the last critical_alt_margin_m
    above the floor. v10 shape (rebalanced after v9b, where the precision
    bonus outbid the old max-25 polynomial penalty and own-crash returned at
    76.5%): pays -altitude_floor_penalty_min right at the margin edge and
    grows EXPONENTIALLY (geometric interpolation) to
    -altitude_floor_penalty_max at/below the floor:
    penalty = -min * (max/min)^closeness, closeness = (floor+margin-alt)/margin.
    With min=1 @ 600m and max=1000 @ 300m, diving through the band costs
    ~-31/step at 450m and ~-316/step at 350m -- no few-step shaping payoff
    can outbid that, so "crash for the bonus" stops being a rational gamble."""
    floor = float(cfg.get("safety_floor_m", 300.0))
    margin = float(cfg.get("critical_alt_margin_m", 300.0))
    if margin <= 0.0:
        return 0.0
    closeness = min(1.0, max(0.0, (floor + margin - alt) / margin))
    if closeness <= 0.0:
        return 0.0
    pen_min = max(float(cfg.get("altitude_floor_penalty_min", 1.0)), 1e-6)
    pen_max = float(cfg.get("altitude_floor_penalty_max", 1000.0))
    return -pen_min * (pen_max / pen_min) ** closeness


def _wez_precision_bonus(distance: float, ata: float, wez_config: dict, cfg: dict) -> float:
    """Per-step aim-precision reward, active within the TRUE WEZ range band
    (wez_config's min/max range, unchanged) and inside a wide, reward-only
    cone (wez_shaping_cone_deg) -- never touches wez_config["angle_deg"], the
    real symmetric kill/damage criteria. Pays wez_precision_bonus_min at the
    cone's edge, rising EXPONENTIALLY (geometric interpolation) to
    wez_precision_bonus_max at ata=0: bonus = min * (max/min)^frac with
    frac = 1 - |ata|/half_angle. The exponential shape keeps sloppy aim
    nearly worthless while concentrating the payoff tightly around dead-on --
    the v9b lesson: a fat floor (30/step anywhere in the cone) made
    cone-loitering worth more than winning and even worth guaranteed
    self-crashes; this shape only pays big where the true kill cone (and its
    automatic damage) actually lives."""
    bonus_max = float(cfg.get("wez_precision_bonus_max", 100.0))
    if bonus_max <= 0.0:
        # Fully disable the wide-cone aim-precision shaping (v15): rewards aim in
        # a wide reward-only cone even without dealing real damage, so it can be
        # farmed for reward while win_rate falls. When max<=0 we pay nothing and
        # let the damage term (true 2deg WEZ hits only) carry the attack signal.
        return 0.0
    in_range = float(wez_config["min_range_m"]) <= distance <= float(wez_config["max_range_m"])
    if not in_range:
        return 0.0
    half_angle = float(cfg.get("wez_shaping_cone_deg", 90.0)) / 2.0
    if half_angle <= 0.0 or abs(ata) > half_angle:
        return 0.0
    frac = 1.0 - abs(ata) / half_angle  # 1.0 at ata=0, 0.0 at the cone edge
    bonus_min = max(float(cfg.get("wez_precision_bonus_min", 1.0)), 1e-6)
    return bonus_min * (bonus_max / bonus_min) ** frac


def _aspect_shaping(ownship_state, target_state, geo_info, cfg: dict) -> float:
    """Continuous nose-threat penalty + six-o'clock reward, folded into "pursuit".

    target_nose_on_own: BT's ATA toward the ownship (0deg = BT's nose is
    pointed straight at us). own_behind_target: the ownship's aspect angle
    relative to the BT (0deg = we sit dead astern of the BT). Both ramp
    linearly to 0 at the edge of aspect_cone_deg, same style as the existing
    dense pursuit term, so there is no flat/gated region.
    """
    half_angle = float(cfg.get("aspect_cone_deg", 30.0)) / 2.0
    if half_angle <= 0.0:
        return 0.0

    target_nose_on_own = abs(float(
        geo_info._get_antenna_train_angle(target_state, ownship_state, False)
    ))
    own_behind_target = abs(float(
        geo_info._get_aspect_angle(ownship_state, target_state, False)
    ))

    front_factor = max(0.0, 1.0 - target_nose_on_own / half_angle)
    rear_factor = max(0.0, 1.0 - own_behind_target / half_angle)

    penalty = -float(cfg.get("front_cone_penalty_scale", 0.3)) * front_factor
    reward = float(cfg.get("rear_cone_reward_scale", 0.3)) * rear_factor
    return penalty + reward


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
    cfg = reward_config
    components: dict[str, float] = {}

    components["survival"] = float(cfg.get("survival_bonus", 0.0))
    components["step"] = float(cfg.get("step_penalty", -0.005))

    # ── Damage differential, asymmetric ───────────────────────────────────
    components["damage"] = (
        float(cfg.get("damage_dealt_scale", 30.0)) * float(target_damage)
        - float(cfg.get("damage_taken_scale", 12.0)) * float(ownship_damage)
    )

    distance = float(geo_info._get_distance(ownship_state, target_state))
    ata = float(geo_info._get_antenna_train_angle(ownship_state, target_state, False))
    alt = float(ownship_state[StateIndex.ALT])
    sim_time = float(ownship_state[StateIndex.SIM_TIME])
    gamma = float(cfg.get("pbrs_gamma", 0.997))

    phi_p = _pursuit_potential(distance, ata, wez_config, cfg)
    phi_h = _altitude_potential(alt, cfg)

    # ── Episode state (reset when sim_time goes backwards) ────────────────
    if len(_EP_STATE) > _EP_STATE_MAX_ENTRIES:
        _EP_STATE.clear()
    key = id(geo_info)
    prev = _EP_STATE.get(key)
    new_episode = prev is None or sim_time <= prev.get("sim_time", float("-inf"))
    wez_entered = False if new_episode else prev.get("wez_entered", False)

    # ── First-WEZ-entry bonus (true kill cone, unchanged) ──────────────────
    in_wez = (
        float(wez_config["min_range_m"]) <= distance <= float(wez_config["max_range_m"])
        and abs(ata) <= float(wez_config["angle_deg"]) / 2.0
    )
    wez_bonus = 0.0
    if in_wez and not wez_entered:
        wez_bonus = float(cfg.get("wez_entry_bonus", 0.0))
        wez_entered = True
    # Continuous aim-precision bonus (v9, wide shaping-only cone) -- see
    # _wez_precision_bonus. Replaces a flat per-step in-true-WEZ bonus (v8),
    # which only rewarded the cone once already held dead-on and gave no
    # gradient toward getting there against a maneuvering BT (observed in v7:
    # ep_min_distance reached 115-290m while ep_wez_steps stayed ~0-0.75).
    wez_bonus += _wez_precision_bonus(distance, ata, wez_config, cfg)

    # ── PBRS: gamma*Phi(s') - Phi(s); Phi(terminal)=0 (true terminations) ─
    if new_episode:
        pbrs_pursuit = 0.0
        pbrs_alt = 0.0
    else:
        next_p = 0.0 if terminated else phi_p
        next_h = 0.0 if terminated else phi_h
        pbrs_pursuit = gamma * next_p - prev["phi_p"]
        pbrs_alt = gamma * next_h - prev["phi_h"]

    if terminated or truncated:
        _EP_STATE.pop(key, None)
    else:
        _EP_STATE[key] = {
            "sim_time": sim_time,
            "phi_p": phi_p,
            "phi_h": phi_h,
            "wez_entered": wez_entered,
        }

    # ── Optional small dense pursuit (non-potential) ──────────────────────
    dense_scale = float(cfg.get("pursuit_dense_scale", 0.0))
    dense = 0.0
    if dense_scale > 0.0:
        half_angle = float(cfg.get("pursuit_half_angle_deg", 45.0))
        pursuit_range = float(cfg.get("pursuit_range_m", 4000.0))
        ata_factor = max(0.0, 1.0 - abs(ata) / half_angle)
        range_factor = max(0.0, 1.0 - distance / pursuit_range)
        dense = dense_scale * ata_factor * range_factor

    aspect_term = _aspect_shaping(ownship_state, target_state, geo_info, cfg)
    alt_floor_penalty = _altitude_floor_penalty(alt, cfg)

    # Fold shaping into the platform's logged component slots.
    components["pursuit"] = pbrs_pursuit + dense + wez_bonus + aspect_term
    components["safety"] = pbrs_alt + alt_floor_penalty

    # ── Terminal ──────────────────────────────────────────────────────────
    terminal = 0.0
    if terminated:
        own_hp = float(ownship_state[StateIndex.HEALTH])
        tgt_hp = float(target_state[StateIndex.HEALTH])
        if end_condition == "two circle headon guard fail":
            terminal = float(cfg.get("guard_fail_penalty", -50.0))
        elif tgt_hp <= 0.0 < own_hp:
            terminal = float(cfg.get("win_reward", 150.0))
        elif end_condition == "target altitude below min" and own_hp > 0.0:
            # Forcing the opponent into the ground (while surviving) IS a win
            # per the competition rules — not a draw. But it is a DIFFERENT and
            # lesser-valued outcome than a genuine kill (see forced_ground_reward
            # above): the "tgt_hp <= 0.0" branch above already wins the full
            # win_reward for a target that was actually shot down, even if it
            # also happened to cross the altitude floor on the way in. This
            # branch only fires when the target is still alive on health and
            # simply panicked into the ground on its own — real training data
            # (ic_s3_bt_v3) showed PPO exploiting this: near-100% "wins" with
            # ep_wez_steps ~8-11/240 and ep_reward_damage ~3-4 (of a possible
            # ~30), i.e. harassing the BT into a self-inflicted crash instead of
            # closing for a kill. Paying it less pushes the gradient toward
            # actually shooting the target down.
            terminal = float(cfg.get("forced_ground_reward", 50.0))
        elif own_hp <= 0.0 < tgt_hp:
            terminal = float(cfg.get("loss_reward", -150.0))
        else:
            terminal = float(cfg.get("draw_reward", -150.0))
    elif truncated:
        terminal = float(cfg.get("draw_reward", -150.0))
    components["terminal"] = terminal

    # ── Uniform output scale (v11) ─────────────────────────────────────────
    # Applied to every component (and therefore the total) so all designed
    # ratios stay exact while value targets shrink back into the range RLlib
    # PPO's default vf_clip_param=10 can actually learn -- see the
    # reward_output_scale entry in MY_REWARD_CONFIG for the full rationale.
    out_scale = float(cfg.get("reward_output_scale", 1.0))
    if out_scale != 1.0:
        components = {k: v * out_scale for k, v in components.items()}

    return float(sum(components.values())), components


__all__ = ["MY_REWARD_CONFIG", "compute_reward"]
