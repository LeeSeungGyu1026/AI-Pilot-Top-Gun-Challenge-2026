# Request for deep RL advisor review

Please act as a senior reinforcement-learning advisor for a time-constrained university competition. Think as deeply as possible before answering. You do not need to reveal hidden chain-of-thought; give a concise but rigorous final recommendation with concrete next experiments and decision rules.

## Project

We are training an RL policy for an F-16 1v1 within-visual-range gun-only dogfight competition.

- Stack: JSBSim flight dynamics simulator wrapped by the organizers, Ray RLlib 2.54, PyTorch, PPO.
- Action: Box([-1, 1]^4) = roll, pitch, yaw/rudder, throttle. Action repeat = 6.
- Observation: custom 26-D engineered WVR observation: wrap-safe sin/cos angles, log range, finite-difference closure/climb/LOS rates, lead-angle error to predicted gun intercept, specific energy, and WEZ flag.
- Reward: pursuit PBRS from range + boresight, small dense pursuit, one-time WEZ-entry bonus, asymmetric damage, altitude safety shaping, terminal win/loss/draw.
- Gun WEZ: true competition cone is 2 deg half-angle, 150-3000 ft / 152.4-914.4 m. Some curriculum runs used widened runtime cones early, but the observation's `in_wez` feature is pinned to the true 2 deg cone.
- Compute: laptop, CPU-bound JSBSim, about 15-30 seconds per training iteration, 2 runs in parallel. We have days left, not weeks.
- Constraints: PPO only. No exposed entropy coefficient or action-std knobs. We can edit reward, observation, curriculum/initial-condition config, and submission wrapper. We avoid platform core edits except clear bug fixes.

## History and current state

Initial flat PPO run:
- Learned stable flight, but loitered/passively orbited at about 1.2-1.6 km.
- It almost never entered WEZ, did no damage, and had 0 wins.

Stage-0 curriculum attempt:
- A pure survival stage diverged into a crash-fast attractor because the low-altitude penalty dominated survival reward.
- We repaired this by using potential-based altitude shaping, keeping pursuit PBRS on, adding first-WEZ bonus, treating draw as loss, and adding an action slew limiter in the environment wrapper.
- Result: crash rate fell to about 0.05-0.10, FDM blowups disappeared, but from the original ~1400 m spawn the policy still only closed to about ~1130 m and never reached the 914 m max WEZ.

Bootstrap decision:
- Diagnosis: reward tweaks alone could not teach contact because the policy never experienced WEZ.
- We moved to geometrically guaranteed contact via offensive/tail/saddle starts, then widened separation/aspect.
- This worked. Close saddle starts produced the first wins and confirmed control authority was not the main blocker.

Key recent training results, all values are recent tail-10 iteration averages:

| Run | Meaning | Win | Crash | Loss | WEZ steps | Min distance | Reward |
|---|---|---:|---:|---:|---:|---:|---:|
| ppo_tgc26_pbrs_v1 | flat/PBRS fix, original-ish spawn | 0.000 | 0.128 | 0.000 | 0.0 | 1129 m | -152.0 |
| ppo_tgc26_close_v2 | dense reward range-gated | 0.000 | 0.063 | 0.000 | 0.0 | 1153 m | -158.5 |
| saddle_test_v1 | close offensive start | 0.067 | 0.041 | 0.000 | 5.9 | 93 m | 160.9 |
| saddle_level_v6 | easier level target | 0.251 | 0.000 | 0.005 | 8.5 | 176 m | -39.8 |
| ic_s2_level_v7 | widened level curriculum | 0.114 | 0.026 | 0.000 | 11.4 | 347 m | -86.8 |
| ic_s2_cone5_v1 | 5 deg cone rung | 0.000 | 0.000 | 0.000 | 5.8 | 486 m | -129.2 |
| ic_s2_finish_v1 | finishing rung | 0.077 | 0.010 | 0.000 | 10.1 | 448 m | -102.1 |
| ic_s2_rangedisc_v2 | range-discipline fix | 0.996 | 0.000 | 0.004 | 25.1 | 482 m | 191.9 |
| ic_s2_weave_v3 | gentle weave target | 0.326 | 0.000 | 0.129 | 15.4 | 222 m | -33.2 |
| ic_s2_sep950_v1 | separation widened to 950 m-ish | 0.952 | 0.000 | 0.042 | 29.6 | 464 m | 179.7 |
| ic_s2_sep1150_v2 | separation widened | 0.984 | 0.000 | 0.014 | 49.7 | 602 m | 189.4 |
| ic_s2_sep1250_v1 | separation widened | 1.000 | 0.000 | 0.000 | 55.8 | 646 m | 194.8 |
| ic_s2_sep1350_v1 | separation widened | 0.929 | 0.000 | 0.068 | 35.2 | 559 m | 171.3 |
| ic_s2_sep1450_v1 | covers ~1400 m competition spawn band | 0.939 | 0.000 | 0.044 | 43.1 | 548 m | 176.5 |
| ic_s3_bt_v1 | opponent swap to behavior-tree target, seeded from sep1450 champion | 1.000 | 0.000 | 0.000 | 62.0 | 680 m | 196.3 |

Current `ic_s3_bt_v1` setup:
- Seeded from `ic_s2_sep1450_v1`.
- Opponent is the organizer behavior-tree target.
- Initial-condition band keeps the agent in an offensive saddle behind the BT at competition-like range: range_m [1100, 1450].
- Range discipline is enabled to prevent extending into a safe draw.
- The run looks excellent on the training distribution: tail-10 win rate 100%, crash 0%, WEZ steps ~62, min distance ~680 m.

Important caveat:
- `ic_s3_bt_v1` is not yet proof of final competition readiness. It may be overfit to the offensive initial geometry, the specific BT behavior, and/or the training distribution. Earlier a cold jump to BT caused the agent to chase a diving BT into the ground, so this BT success is probably conditional on the current offensive start and shaped distribution.

## What I need from you

Please advise on the highest-leverage next steps before submission.

Specific questions:

1. Given the sudden tail-10 100% win against the BT from offensive saddle starts, what validation matrix should we run immediately to distinguish genuine dogfighting competence from curriculum/initial-condition overfitting?

2. How should we stress-test generalization with limited compute? Candidate axes: random seeds, initial range 900-1800 m, aspect/heading offsets, altitude offsets, speed offsets, target modes, BT scenario indices, true 2 deg cone only, no widened runtime cone, and cold starts without offensive saddle.

3. Should we continue training from `ic_s3_bt_v1`, broaden the initial-condition distribution now, or freeze it as a candidate and branch new runs from it?

4. What are the most dangerous failure modes at this stage? Examples we worry about: overfitting to starting behind the target, chasing the BT into the ground, learning reward-specific range discipline that does not transfer, exploiting the training BT, policy regression if we broaden too fast, and submission wrapper mismatch.

5. What exact run plan would you execute over the next 24-48 hours with 2 parallel runs? Please include stopping criteria and model-selection criteria.

6. Should we consider a hybrid submission wrapper that falls back to or blends with the provided BT in out-of-distribution states, or is that likely to harm the trained RL policy? If yes, what simple trigger conditions would be safest?

7. Are there any reward/observation changes still worth making, or should we avoid touching them now and focus only on validation, distribution broadening, and packaging?

Please give a prioritized, practical plan. Assume the final metric is win rate on an Unreal server against other teams or organizer evaluation policies, and that training time is scarce.
