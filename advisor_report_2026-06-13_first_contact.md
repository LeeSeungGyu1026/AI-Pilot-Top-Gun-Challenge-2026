# Advisor update — flight solved, but the agent can't reach the WEZ (2026-06-13)

(You've been advising this project — F-16 1v1 gun-only dogfight, PPO + RLlib 2.54,
custom 26-D obs, PBRS reward, flat single-stage run vs a behavior-tree/loiter target.
Quick continuation; only the new results and one crux question below.)

## What we did since your last advice

Acted on your "fix the flat run, fold in the goal-radius idea" guidance:
- **Altitude → potential-based** (Phi increasing in altitude, gamma*Phi'-Phi recovery
  gradient, Phi(terminal)=0). Replaced the flat penalty that was rewarding fast suicide.
- **Pursuit PBRS always on** (range + boresight), plus a small dense pursuit term.
- **First-WEZ-entry bonus** (+20, one-time, vs the runtime cone).
- **draw = loss = -150** (removed the safe-draw attractor).
- **Action slew-limiter** in the env wrapper (cap |a_t - a_{t-1}|) — your robust fix
  for the FDM-blowup crashes.
- **WEZ widened to 5 deg** (goal-radius), to be narrowed to 2 deg later.
- Set PBRS shaping gamma=1.0 after a smoke run showed the (gamma-1)*Phi bleed made
  long-episode reward logs misleading.

## Results: two 50-iteration runs

**The good (flight is solved):** crash rate fell from ~0.64 to ~0.05-0.10 and stayed
there; episodes lengthened; **zero FDM blowups** (the slew-limiter held, action
saturation steady ~0.30). The divergence/"crash-fast" pathology is gone.

**The wall (no engagement, both runs):**

| metric | v1 (dense range 4 km) | v2 (dense range-gated to 1.2 km, scale 0.3) |
|---|---|---|
| spawn distance | ~1400 m | ~1400 m |
| ep_min_distance (closest approach) | ~1130 m | ~1130 m |
| win_rate / wez_steps / damage | 0 / ~0 / 0 | 0 / ~0 / 0 |

The decisive number: **they spawn ~1400 m apart and the agent closes only ~270 m on
average, ending at ~1130 m — it never reaches the 914 m max WEZ range, in any episode,
across 100 iterations.** v2 (range-gating the dense reward to force closure) didn't move
it; the agent just collected less pursuit reward and kept its distance.

## Our read

This is not loitering-by-preference (your earlier framing of the flat run). It's that
the agent **cannot solve the pursuit-to-intercept control problem from 1.4 km**, and no
shaping gradient from out there is strong enough to teach it — so it never experiences
the WEZ, never deals damage, never wins, and the +150 outcome stays entirely outside its
experienced distribution. Reward tweaks (v1, v2) are treating a symptom: you can't reward
a behavior the policy never stumbles into. First contact seems to need to be made
**geometrically guaranteed**, not coaxed.

The spawn geometry comes from fixed scenario tables (~1400 m, mixed BT/loiter targets,
roughly co-altitude). We have two usable initial-condition levers:
1. A **head-on merge** mode with an explicit spawn separation + heading offset (alpha) —
   set it close and the jets pass through gun range every episode (brief, high-closure
   window though).
2. We could likely also script a **close offensive/tail start** (agent spawned a few
   hundred meters behind a slow/level target, already near a gun solution) for sustained,
   easy first kills.

## Questions

1. **Bootstrap geometry: head-on merge vs offensive tail-start vs something else?** A
   head-on guarantees WEZ exposure but only for a sub-second high-closure flash — is that
   enough to bootstrap, or is a sustained offensive start (spawn close behind a
   slow/level target) the better first lesson, with separation/aspect widened over runs
   as an initial-condition curriculum? If tail-start, any guidance on not over-fitting to
   a trivial "sit in the saddle" that collapses against a maneuvering opponent later?

2. **Is an initial-distance/aspect curriculum the right frame** (start in-WEZ, widen
   spawn separation and off-boresight aspect as win-rate climbs), analogous to the
   goal-radius cone-widening you suggested — or would you keep spawn fixed and instead
   make the pursuit signal itself far stronger / non-telescoping?

3. **Opponent for bootstrapping**: start against a **stationary or constant-velocity
   target** (so closure is a pure pursuit problem) before reintroducing the maneuvering
   BT? Currently it's mixed BT + loiter from the first iteration.

4. Anything in the **flight-is-fine-but-won't-close** signature that suggests the
   pursuit/intercept is a *control-authority* problem (e.g. the slew limiter at 0.25/step
   or action-repeat 6 making hard turns too sluggish to convert an intercept) rather than
   an exploration problem? We'd hate to bootstrap contact and then find the policy
   physically can't turn tight enough to hold a gun solution.

## Constraints (unchanged)
PPO only; no entropy-coef / action-std knobs exposed; reward fn doesn't see the action
(slew limit lives in the env wrapper). ~15-30 s/iteration, 2 runs in parallel, days left.
We can freely edit reward / observation / initial-scenario config; platform core only for
clear bug fixes.
