# Status report for external advisor — 2026-06-12 (evening)

## Project context (brief)

University competition: train an RL policy to fly an F-16 in **1v1 within-visual-range
gun-only dogfights**. Stack: JSBSim flight-dynamics DLL + Ray RLlib 2.54 (new API stack),
PyTorch, PPO. Action = Box([-1,1]^4) (roll/pitch/yaw/throttle), action-repeat 6, episodes
up to 300 s. Gun WEZ = 2 deg half-angle cone, 150-900 m. **Final metric = win rate** vs
other teams on an Unreal server; training opponent is an organizer behavior tree (BT).
Hardware: RTX 3070 laptop (GPU idle — workload is JSBSim-CPU-bound), 16 threads, 16 GB RAM,
2 parallel runs feasible.

Current design (from prior advice): custom 26-D observation (sin/cos angles, log range,
finite-diff closure/LOS rates, lead-angle error, specific energy); reward = dense bounded
pursuit term (annealed) + potential-based shaping (PBRS) + asymmetric damage (dealt 30 /
taken 12) + altitude-ramp safety + win/loss/draw 150/-150/-20; metric-gated curriculum
(survival -> fixed pursuit -> WEZ-approach -> autopilot -> 10 head-on stages -> full BT)
with a WEZ-width schedule (8->5->3->2 deg) and dense-pursuit anneal.

## What happened since last report

The week-1 flat reward sweep finished: crash rate driven to 0%, but **zero WEZ entries**
(policies loiter at 1.2-1.6 km and run out the clock). Advisor diagnosis accepted: PBRS
telescopes to a bounded per-episode total, too weak to drive first contact. Fix = move to
the staged curriculum with dense (hackable) shaping early, annealed out later; widen the
WEZ as a goal-radius curriculum; success gate for the week = nonzero damage + first wins in
the early stages, entropy starting to fall.

That curriculum sweep was then blocked by **three infrastructure bugs**, now all fixed:

1. **Stage-0 crash loop** — the platform's default randomization ships `radius=0` with
   randomization enabled; `np.random.integers(0, 0)` raises `ValueError: high<=0` on every
   env reset. Worked around by clamping zero ranges to 1 in our stages module.
2. **Stale-state relaunch failure** — `train_curriculum.py` refuses to start over an
   existing `curriculum_state.json` without `--resume`. Hardened our parallel launcher to
   auto-archive stale state dirs at launch.
3. **(The important one) Dead stage gates** — `train_curriculum.py._extract_custom_metrics`
   only read `<name>_mean` keys, but RLlib 2.54 new API reports custom metrics under bare
   names. So **every advance-condition metric was permanently `n/a`** and stages could
   never advance on merit — each would consume its full `max_iterations` (~20 h for the
   ladder). The earlier curriculum run had in fact mastered stage 0 (reward pinned at the
   survival ceiling) but was stuck there. Patched to mirror the working `train_rllib.py`
   lookup. Verified via a short probe: gate metrics now read `Crash=[1.000] WinRate=[0.000]
   WEZ=[0.0]` (numeric, as needed).

Also confirmed: `train_curriculum.py` writes no dashboard metrics.jsonl, so curriculum runs
are invisible in the dashboard Training tab — we monitor via per-run logs, training_log.csv,
and the Replay tab pointed at `artifacts/curriculum`.

## Current status

All fixes verified in short probes. The full 2-arm curriculum sweep (dense-pursuit cap 0.2
vs 0.1, everything else identical, metric-gated stages, WEZ 8->2 deg schedule) is ready to
launch — no real training results yet. So we are at the **starting line of the curriculum
phase**, with the contact problem addressed in design but not yet observed in a real run.

## Questions for the advisor

1. **Sanity of the gate thresholds.** Stage gates: stage 0 crash_rate < 0.05; pursuit
   stages on ep_min_distance / wez_steps; head-on stages on win_rate > 0.7 + crash < 0.3
   over a 10-iteration window. With ~14 s/iteration and 8,192-step batches (~4-6 episodes
   each), is a 10-iteration window large enough to gate reliably on win_rate, or will noise
   cause premature/erratic advancement? Should early gates be on counts (e.g. cumulative
   WEZ steps) rather than rates?

2. **WEZ-width curriculum is symmetric.** We confirmed `wez.angle_deg` is the actual damage
   model and applies to *both* aircraft, so widening to 8 deg also makes the BT lethal at 8
   deg. In the early stages the targets are non-shooting (fixed/loiter/autopilot), so this
   only bites from the head-on/BT stages onward — where we've set it back to the true 2 deg.
   Is that the right call, or is there value in the agent experiencing a widened *incoming*
   threat earlier?

3. **Dense-cap sweep (0.2 vs 0.1) — is this the highest-value axis** for our 2 parallel
   slots right now, or would you spend one slot differently (e.g. one with dense shaping,
   one pure-PBRS-from-the-start as a control; or varying the anneal *schedule* rather than
   the cap)?

4. **Reward telemetry.** The platform only logs four fixed component names
   (pursuit/damage/safety/survival); we renamed our components to match. Net damage is one
   signed component (dealt minus taken), so we cannot watch dealt vs taken separately on the
   dashboard. Is splitting them worth a logging workaround, or is net damage + win/loss
   enough to catch evasion-collapse?

5. **What single metric trajectory would most convince you the curriculum is working** in
   the first few hours, beyond "stages advance"? We plan to watch: crash_rate (stage 0),
   then ep_min_distance + wez_steps climbing, then nonzero damage, then win_rate in the
   loiter/autopilot stages, with entropy declining throughout.

Compute budget for context: ~14 s/iteration, 2 arms parallel, days available before the
deadline.
