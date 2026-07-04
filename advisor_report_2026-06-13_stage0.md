# Advisor report — curriculum stage-0 divergence (2026-06-13)

## Project context (the advisor has no prior knowledge of this project)

University competition: train an RL policy to fly an **F-16 in 1v1 within-visual-range,
gun-only dogfights**. Stack: a JSBSim flight-dynamics simulator wrapped as a DLL + Ray
**RLlib 2.54** (new API stack) + PyTorch, algorithm **PPO**. Runs on a laptop (RTX 3070,
16 CPU threads, 16 GB RAM); the GPU is idle because the workload is JSBSim-CPU-bound, ~2
training runs in parallel.

- **Action**: Box([-1,1]^4) = roll, pitch, yaw, throttle. Action-repeat 6 (policy acts
  every 6 sim steps). Episodes up to 300 s.
- **Win condition / metric**: gun WEZ = 2° half-angle cone, 150–900 m; you damage the
  opponent by holding them in the cone. **Final competition metric = win rate** vs other
  teams on an Unreal server. Training opponent is an organizer-provided behavior tree (BT).
- **Observation** (custom, 26-D): wrap-safe sin/cos of all angles, log-scaled range,
  finite-differenced closure / climb / LOS rates, lead-angle error to predicted gun
  intercept, specific energy, WEZ flag.
- **Reward** (custom, component-based): potential-based shaping (PBRS) for pursuit + a
  bounded dense pursuit term (annealed by curriculum) + asymmetric damage (dealt 30 /
  taken 12) + an **altitude-floor safety penalty** + terminal win/loss/draw.
- **Curriculum** (metric-gated stages): stage 0 `flight_survival` → 1 `target_pursuit`
  (fixed target) → 2 `wez_approach` (loiter target) → 3 `autopilot_pursuit` → 4–13
  two-circle head-on vs BT → 14 `full_dogfight`. Each stage advances when rolling-window
  metrics meet thresholds (e.g. stage 0: crash_rate < 0.05) or hits a max-iteration cap.
  A WEZ-width "goal radius" schedule (8°→2°) widens the damage cone early, narrows to the
  true 2° in the final stages.

## Where we are

Earlier this week a **flat single-stage run** (full reward, all shaping on, vs BT) drove
**crash rate to 0%** — but the policy just loitered at 1.2–1.6 km and never entered the WEZ
(0 wins). Diagnosis (with prior advice): the shaping was too weak/too telescoped to drive
first contact. The prescribed fix was to move to the **staged curriculum** + a dense pursuit
term early, to manufacture WEZ contact in easy stages before facing the BT.

After clearing a string of infrastructure bugs (Windows path limits, a Unicode crash at
stage boundaries, a metric-extraction bug that made all stage gates read NaN, and a
NaN-comparison bug that let stages falsely advance), the curriculum finally ran cleanly —
**and stage 0 diverges.**

## The stage-0 problem (the actual question)

Stage 0 is supposed to be the *easiest* stage: a fixed (non-threatening) target, the only
goal is "stay airborne." All directional shaping is deliberately **off** in stage 0
(pursuit = 0, PBRS = 0); the reward is just:

| signal (stage 0) | value |
|---|---|
| survival bonus | **+0.05 / step** |
| altitude penalty (active below 900 m, ramps to floor at 300 m) | **up to −1.0 / step** |
| crash (terminal, once) | −50 |
| start altitude / speed | 7000 m, 300 m/s |

Observed over ~23 iterations (8192→16384-step batches): **crash rate climbs to 100%**,
episode reward *falls* (≈57 → 26), episodes get *shorter*, and policy entropy *rises*
(≈5.5 → 8) rather than collapsing. The dominant episode ending is "ownship altitude below
min" (diving into the ground); in one variant it was "FDM update fail" (control inputs
violent enough to break the simulator).

Our read: there is a **perverse incentive**. Once exploration pushes the aircraft below
900 m, it bleeds −1.0/step. Lingering low even briefly (~50 steps) costs as much as the
−50 crash, so **crashing immediately becomes the reward-optimal action** to stop the
bleeding — and with no shaping to teach recovery/level flight, PPO collapses into a
"crash fast" attractor. The altitude penalty (meant as a safety guardrail) dominates the
+0.05 survival bonus by 20×.

The striking contrast: the **same observation and reward module, run flat with all shaping
ON, reached 0% crash.** So the network/inputs can clearly learn stable flight — it's
specifically the curriculum's stripped-down, survival-only stage 0 that breaks it. The
shaping the curriculum removes in stage 0 appears to be exactly what was stabilizing flight.

## Questions

1. **Is a pure-survival stage 0 a good idea at all?** Given the full-reward flat run flies
   cleanly (0% crash), is the survival-only warm-up stage solving a problem we don't have —
   should we delete it and start the curriculum at a shaped stage, or keep light pursuit/PBRS
   shaping on throughout (including stage 0) so there's always a directional gradient?

2. **Altitude-penalty calibration.** If we keep a survival stage, how would you balance it so
   it doesn't reward fast suicide? Options we see: make survival ≫ the low-altitude penalty;
   cap the per-episode altitude penalty; make the penalty a function of *descent rate* near
   the floor rather than a flat per-step cost; or fold "stay alive" into a potential-based
   altitude term so it can't be farmed by terminating. Which is least likely to create a new
   pathology?

3. **Curriculum vs. just fixing the flat run.** Strategically, the flat run already gives us
   a stable-flying-but-passive policy. Is the higher-leverage path (a) repair the curriculum
   so it manufactures WEZ contact stage by stage, or (b) abandon the staged curriculum and
   attack the real failure — loitering / no WEZ entry — directly on the flat run that works
   (e.g. stronger or differently-shaped contact incentive, opponent that forces engagement)?

4. **Entropy rising during divergence** — is that diagnostic of anything specific (e.g.
   value-function collapse, advantage sign issues) beyond "the objective rewards crashing"?

## Constraints / notes for your answer

- We can freely edit the reward, observation, and curriculum-stage definitions (they're our
  files). We avoid editing the platform's core training loop except for clear bug fixes.
- PPO only; no entropy-coefficient or action-std knobs are exposed by the platform's
  config mapping. No RL/self-play opponent is available in training (BT or scripted targets
  only).
- Compute: ~15–30 s per training iteration, 2 runs in parallel, days (not weeks) remaining.
- The reward function does **not** receive the action, so action-smoothness penalties aren't
  possible (relevant to the "FDM blowup from violent inputs" failure).
