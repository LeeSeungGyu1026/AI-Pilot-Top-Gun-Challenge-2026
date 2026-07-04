# Advisor report — 2026-06-12 (night): curriculum stalls at stage 0, need a design call

## Project context (brief, for grounding)

University competition: RL policy for **1v1 within-visual-range gun-only F-16 dogfights**.
JSBSim flight-dynamics DLL + Ray RLlib 2.54 (new API stack), PPO. Action = Box([-1,1]^4)
(roll/pitch/yaw/throttle), action-repeat 6, episodes up to 300 s. Gun WEZ = 2 deg half-angle
cone, 150-900 m. **Final metric = win rate** on an Unreal server; training opponent is an
organizer behavior tree (BT). Hardware: RTX 3070 laptop (GPU idle, JSBSim is CPU-bound),
16 threads, 2 parallel runs.

Design so far (from your prior advice): custom 26-D obs (sin/cos angles, log range,
finite-diff closure/LOS rates, lead-angle error, specific energy); reward = dense bounded
pursuit (annealed) + PBRS + asymmetric damage (dealt 30 / taken 12) + altitude-ramp safety +
win/loss/draw 150/-150/-20; metric-gated curriculum (survival -> fixed-target pursuit ->
WEZ-approach -> autopilot -> 10 head-on stages -> full BT) with a WEZ-width schedule
(8->2 deg) and dense-pursuit anneal.

## Where we are

We chased down a string of infrastructure failures (all fixed now): a stage-0 env
crash-loop (NumPy `integers(0,0)` on zero randomization), a stale-state relaunch latch,
dead metric gates (Ray 2.54 reports custom metrics under bare names, not `<name>_mean`, so
every advance condition read NaN), a UnicodeEncodeError that killed the run at each stage
boundary (cp949 console can't encode the platform's "✓" print), and a NaN-advancement bug
(NaN metrics passed the gate because `nan > x` and `nan < x` are both False). Infra is solid
now: stages advance correctly, runs survive boundaries, gates read real numbers.

**But the curriculum cannot get past stage 0 ("flight survival"), and the reason is a reward
flaw, not infra.** Two PPO runs (identical except dense-pursuit cap 0.2 vs 0.1) both collapse:
crash rate climbs 67% -> 100% over ~25 iterations and episode reward *falls* (57 -> 26) — the
policy is actively learning to crash *sooner*. ~100% of terminations are "ownship altitude
below min" (diving into the ground) in one arm and "FDM Update Fail" (control surfaces driven
to simulator-breaking extremes) in the other.

## The diagnosis (fairly confident)

Stage 0 strips out all directional shaping (pursuit and PBRS set to 0) to isolate "just learn
to stay airborne," leaving only:

- survival bonus: **+0.05 / step**
- low-altitude penalty (active below 900 m, ramping to the 300 m floor): **up to -1.0 / step**
- crash terminal: **-50** (once)
- (start: 7000 m, 300 m/s, fixed non-threatening target)

Once exploration pushes the aircraft below 900 m, it bleeds up to -1.0/step. Lingering low
for ~50 steps costs as much as crashing outright. So **crashing immediately becomes the
reward-optimal action** once descending — and with no shaping gradient teaching recovery or
level flight, PPO collapses straight into the "dive and die fast" attractor. Entropy was
rising, not falling (policy getting more random), consistent with no useful gradient.

## The key contrast that points the way

Our **week-1 flat run — same 26-D observation, same reward module, but with the FULL reward
active (pursuit + PBRS + damage all on), target = BT — reached 0% crash rate.** It flew
cleanly and stably; its only failure was tactical (it loitered at 1.2-1.6 km and never
entered the WEZ — the "no contact" problem your curriculum advice was meant to solve).

So: the observation and reward machinery are fine. **The flat full-reward setup flies; the
curriculum's survival-only stage 0 cannot.** The shaping the curriculum deliberately removes
in stage 0 is exactly what was stabilizing flight in the flat run.

## Questions for you (this is a design call, hence pausing)

1. **Is a pure-survival stage 0 worth keeping at all?** Our instinct now is that it's
   counterproductive: it removes the very signal that makes flight learnable, and the flat
   run proves the agent flies fine *with* shaping. Options we see:
   - (A) **Drop the curriculum**, return to the flat full-reward run (proven 0% crash), and
     attack the real problem — loitering / no WEZ contact — directly there (e.g. stronger or
     differently-shaped dense pursuit, WEZ-width annealing on the flat run, harsher draw
     penalty once it can shoot).
   - (B) **Keep the curriculum but fix stage 0**: rebalance so survival dominates (raise
     survival bonus and/or cut the low-altitude penalty so it never rivals the crash cost),
     OR leave light pursuit/PBRS shaping on in stage 0 so there's a flight gradient.
   - (C) **Skip stage 0 entirely** and start the curriculum at the first pursuit stage with
     full shaping, seeded from a short flat warm-start.
   Which would you pursue, and is there an option we're missing?

2. **The altitude-penalty / fast-crash perverse incentive** seems likely to recur in *any*
   stage whenever the policy gets into an unrecoverable low state (crashing to stop the
   per-step bleed is always locally optimal). Is the standard remedy to (a) cap the
   cumulative altitude penalty below the crash cost, (b) make the floor penalty a one-time
   terminal rather than per-step, or (c) something else? We want flight-safety pressure
   without teaching suicide.

3. **Given the flat run already flies and only lacks engagement**, is the curriculum even the
   right tool here, or is it over-engineering for a 1v1 gun-only task on a 2-parallel-run
   budget? Would you put the remaining days into curriculum debugging, or into shaping the
   flat run toward WEZ contact + self-play diversity?

4. **Entropy behavior**: in the failing stage 0, entropy *rose* (~5.5 -> 8). In the working
   flat run it was also high (~5.5, sigma ~1, near-random actuation) but crash still hit 0.
   Does "high entropy but low crash" in the flat run mean the value/advantage signal was
   doing the work despite a diffuse policy — and is rising entropy in stage 0 simply the
   signature of "no usable gradient," confirming the reward flaw?

## Constraints / notes

- We must not modify the JSBSim/DLL assets; Python platform code we've patched only for clear
  bugs. Reward, observation, curriculum, and YAML are ours to design.
- Budget: ~14-30 s/iteration (varies with batch), 2 parallel runs, days remaining.
- We have a working flat-run baseline (0% crash, 0% WEZ contact) to fall back to.
