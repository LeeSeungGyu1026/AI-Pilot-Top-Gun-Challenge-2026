# Follow-up report for external advisor — 2026-06-12

**Subject: First reward-shaping sweep finished: crashing solved, but zero engagement. Need advice on next move.**

This is a follow-up on the fighter-dogfight RL competition (1v1 F-16, JSBSim DLL sim, RLlib 2.54 new API stack, gun-only WEZ = 2° half-angle cone at 150–900 m, win rate is the final metric, opponent during training is an organizer behavior tree). Previous advice: PBRS reward, engineered observation, locked PPO config, week-1 reward sweep, curriculum, eval ladder. All implemented; first diagnostic sweep complete.

## What's implemented

- **Observation "tgc26" (26-D)**: sin/cos for all wrapping angles, log-scaled range, closure rate, climb rate, LOS az/el rates, estimated target velocity (finite-differenced — state vector exposes no velocities), lead-angle error to predicted gun intercept, specific energy, WEZ flag. Fixed normalizers, clipped to [−1,1].
- **Reward**: PBRS pursuit shaping r = γΦ(s′)−Φ(s), Φ = −(w_ata·|ATA|/180 + w_range·|log(d/WEZ_mid)|/3 clipped); asymmetric damage (dealt +30/unit, taken −12); altitude penalty ramping from 900 m to the 300 m kill-floor (max −0.5/step); step −0.005; win +150 / loss −150 / draw −20 (draws also on timeout).
- **Locked PPO**: γ 0.997, GAE λ 0.95, lr 3e-4, clip 0.2, batch 8192, minibatch 512, tanh [256,256], separate value head, 2–4 env runners, 300 s episodes (18,000 steps, action repeat 6), mixed initial geometry (8 randomized scenarios, BT + loiter targets).
- **Infra**: parallel sweep launcher, N-episode eval ladder (vs fixed/loiter/autopilot/BT/RL bundles), dashboard with 3D replay.
- **Platform constraints discovered**: reward fn receives no actions (no smoothness penalty); no entropy-coef / action-std knobs; no RL opponent in training; telemetry logs only fixed component names (pursuit/damage/safety/survival) — custom names (pbrs, damage_dealt, damage_taken) silently dropped → will rename to fixed names for per-component dashboards.

## Sweep results

2×2 grid: pbrs_ata_weight ∈ {1,2} × damage_taken_scale ∈ {12,30}; 30 iterations × 245,760 steps each (~1M env steps total, ~25 min wall, 2 parallel; ~12 min per run).

| variant (ata/taken) | reward iter0→29 | crash 0→29 | timeout@29 | min_dist@29 | WEZ steps | win/loss |
|---|---|---|---|---|---|---|
| 1 / 12 | −25.9 → −22.2 | 0.77 → **0.00** | 0.67 | 1.40 km | 0 | 0 / 0 |
| 1 / 30 | −25.9 → −22.4 | 0.79 → **0.00** | 0.00 | 1.59 km | 0 | 0 / 0 |
| 2 / 12 | −26.0 → −20.7 | 1.00 → **0.00** | 0.17 | 1.25 km | 0 | 0 / 0 |
| 2 / 30 | −22.1 → **−16.4** | 0.67 → **0.00** | 0.50 | 1.21 km | 0 | 0 / 0 |

Episode lengths grew ~470 → 1,400–2,200 steps; action saturation 27–43%; entropy ≈ 5.5.

## Interpretation

The altitude-ramp safety reward worked — crash rate hit zero by ~iter 15 in all variants. But the policies converged to "fly safely at 1.2–1.6 km and run out the clock." Zero WEZ entries in a million steps → the agent has never experienced damage-dealt or a win; the terminal +150 and damage rewards are invisible. PBRS telescopes — total shaping per episode is bounded by Φ(start)−Φ(end) ≈ ±3 — a whisper against the −20 timeout draw, with no sustained gradient into a 2° cone at 150–900 m. The anti-hacking property that makes PBRS safe also makes it weak as an exploration driver.

## Questions

1. **How to get the first WEZ entries / first kills?** Candidates in current preference order: (a) switch to the staged curriculum now (metric-gated stages: fixed target → pursuit → WEZ approach vs loiter → moving target → head-on variants → full BT — already tuned); (b) crank PBRS weights ×3–5; (c) add a small non-potential bounded per-step pursuit term (≤0.3/step, like the platform default's ATA×range gradient), accepting hackability for exploration; (d) harshen timeout draw (−20 → −60), risking crash/wall-hug resurgence. Which combination first, and what is a waste of a slot?
2. Is per-episode-bounded PBRS fundamentally insufficient as the only dense pursuit signal in sparse-contact air combat? Treat PBRS as a refinement tool for later stages and use plain dense shaping early?
3. Entropy stuck ~5.5 with no entropy-coefficient knob — problem or helpful exploration at this stage?
4. The 2° WEZ is brutally narrow. Train with a widened `wez.angle_deg` annealed down — legitimate curriculum trick or distribution-shift trap?
5. Any red flags in the numbers I'm not seeing (entropy, saturation rate, episode-length growth)?

Budget context: ~12 min per 245k-step run, 2 runs parallel, RTX 3070 laptop (GPU unused — learner on CPU; workload is JSBSim-sampling-bound). Weeks 2–3 remain.
