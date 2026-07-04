# Autonomous IC-S3-vs-BT training log

**Goal (set 2026-07-03 via /goal):** keep iterating training autonomously.
Success = the RL ownship genuinely shoots the BT target down ("target destroyed"
via damage), NOT "target altitude below min" (forcing/getting a self-crash out
of the BT). Tune reward + hyperparameters as needed. Before every new run:
write a plan (this file) and a fresh experiment YAML. After every run: append
the result here. Use watch-train wakeups to intervene on a clearly broken run;
otherwise idling while waiting for a run to finish is fine, as long as a
wakeup is guaranteed around the run's end.

**Why this metric matters:** the platform's own damage/termination model
already lets the agent legitimately force an opponent into the ground (a
"kill" in the competition's own rules), and earlier training explicitly
rewarded that path (`compute_reward` pays `win_reward` for
`end_condition == "target altitude below min"`). But investigation on
2026-07-03 (ic_s3_bt_v2 log, first ~30 min) showed a big chunk of these
"wins" are the BT panicking into an evasive dive that overshoots its own
recovery logic — an artifact of the very close/aggressive `offensive_saddle`
spawn, not skillful RL gunnery. `training_log.csv`'s `win_rate` column comes
from the platform's own classifier and does not separate real kills from
forced-ground outcomes, so it is not sufficient on its own to judge progress
against this goal — per-run evaluation needs to split `end_condition` counts
(`target destroyed` vs `target altitude below min` vs `ownship *` vs
timeout) explicitly, e.g. from engagement-replay logs or a dedicated eval
pass, not just the aggregate rate.

---

## History (context for future runs)

| tag | seed | change vs prior | result |
|---|---|---|---|
| `ic_s3_bt_v1` | `ic_s2_sep1450_v1` | first BT opponent swap (old reward, old BT) | 0% win / ~87% loss, ALL "ownship altitude below min" — RL pure-pursuit-chases BT's defensive dive into the ground |
| `ic_s3_bt_v2` | `ic_s2_sep1450_v1` | reward fix: aspect-cone shaping (penalty when BT threatens our front, reward when we sit in BT's six) + altitude-floor bumper (real per-step penalty near the 300m floor) in `student/my_reward.py` | early log (~30 min in, iter ~40): crash-into-ground still frequent on the RL side, BT self-crash ("target altitude below min") ~18% of terminations (176/967). Stopped early to fix the BT-side issue instead of running to completion (see below). |
| `ic_s3_bt_v3` | `ic_s2_sep1450_v1` | BT-side fix: `TacticalTasks.cpp` `SetCommand()` (single chokepoint every BT task funnels through) hard-clamps every commanded waypoint's Z to >=900m, so no evasive maneuver can aim the BT into the ground in the first place. Same reward as v2. Rebuilt DLL via MSBuild, deployed, smoke-tested. | **IN PROGRESS** (started 2026-07-03 03:43, RUNDIR `artifacts/watch/20260703_034324`) |

**Known confound to keep watching for:** `offensive_saddle` spawns the RL
locked on at the BT's six (1100-1450m, aspect 0-30°) from step 0 — this is a
*very* aggressive starting geometry that forces the BT into its hardest
defensive maneuvers almost immediately, every episode. That's useful for
bootstrapping contact/pursuit skill, but it may be inherently biased toward
forced-ground outcomes over sustained gunnery, since the BT is thrown into a
panic response before the RL has had to demonstrate any tracking skill. If
v3's real-kill rate stays low even with the BT floor fixed, consider: (a)
widening the spawn band so not every episode starts in the BT's most extreme
threat envelope, or (b) shaping the reward to explicitly prefer sustained
WEZ-tracking-then-damage over any single-instant terminal condition.

---

## Next steps (plan, written before starting v3's evaluation)

1. Let `ic_s3_bt_v3` finish (100 iterations). Watcher already armed
   (train-watch, RUNDIR above).
2. On completion, evaluate with an end-condition breakdown, not just
   `training_log.csv` win_rate:
   - Pull `end_condition` counts from the run's engagement-replay logs /
     `train.log` (or run a dedicated `scripts/run_eval.py` pass with
     `--experiment-yaml experiments/ic_s3_bt_v3.yaml`) and report:
     `target destroyed` (real kill) vs `target altitude below min`
     (forced-ground) vs `ownship *` (RL loss) vs timeout, as separate rates.
   - Judge success by the `target destroyed` rate specifically, trending up
     run over run — not the aggregate win_rate.
3. Based on v3's real-kill rate:
   - If still near-zero and forced-ground still dominates the "wins": adjust
     `student/my_reward.py` so a genuine `target destroyed` pays more than
     `target altitude below min` (currently both pay flat `win_reward=150`),
     giving PPO a gradient toward sustained gunnery over induced crashes.
     Candidate: keep forced-ground as a smaller positive (it's still a legal
     competition win, just not the skill we're training) and raise real-kill
     reward, e.g. via a `target_destroyed_bonus` on top of `win_reward`.
   - If real kills are happening but rare: consider hyperparameter tuning
     (entropy coefficient / lr schedule for more exploration around the WEZ
     cone) before touching reward shape again, to avoid repeating the
     project's earlier "gating deletes signal" mistake.
   - If healthy and improving: continue the previously-planned IC curriculum
     (WEZ cone narrowing 8→5→3→2°, only in final stages) from this bundle.
4. Every new run gets its own `experiments/ic_s3_bt_vN.yaml` (immutable,
   documents exactly what ran) and a new entry appended below with: what
   changed, why, and the result once it finishes.

---

## Run log (append one entry per completed run)

### ic_s3_bt_v3 (2026-07-03) — FINAL (DONE, exit=0, 100/100 iterations)

Full-log breakdown (`tools/end_condition_breakdown.py`, whole run, 5841
terminations): `target altitude below min` 81.80%, `ownship altitude below
min` 16.28%, `ownship destroyed` 1.92%, **`target destroyed` 0.00%**.
Matches the provisional read below almost exactly — the pattern was stable
for the whole run, not a transient. Bundle saved to
`artifacts/models/team01/ic_s3_bt_v3`. Proceeding to v4 (already prepared
below) seeded from this bundle.

### ic_s3_bt_v3 (2026-07-03) — provisional notes (written while still running, kept for context)

Checked at iter 73-83/100 (near the end, trend unlikely to change materially
in the remaining iterations): `training_log.csv`'s win_rate/loss_rate/
timeout_rate/crash_rate are ALL pinned at 0.0 the whole window even as
reward_mean climbs 176→182 — the platform's own classifier apparently has no
bucket for "target altitude below min" at all, so it silently doesn't count
these terminations in any rate column (this column is not usable for judging
this run). Built `tools/end_condition_breakdown.py` to get the real split
from the raw log directly: on the last 20000 lines, `target altitude below
min` = 75.3%, `ownship altitude below min` = 22.1%, `ownship destroyed` =
2.6%, **`target destroyed` = 0.0%**.

Good news: own-crash rate is way down from v1 (100%)/early-v2 (76%) to ~22%
— the aspect-shaping + altitude-floor-bumper reward fix (v2) plus the BT hard
900m floor (v3) both worked as intended on that axis.

Bad news, and the reason for v4: `ep_wez_steps` ~8-11 of a ~240-step episode
and `ep_reward_damage` ~3-4 (of a possible ~30 for a full kill) confirm the
RL is not pressing for a kill — it's camping in the BT's six (which the
aspect-shaping reward already encourages) and letting the BT panic itself
into the ground, which pays the exact same `win_reward` (150) as a genuine
kill. This is the "target altitude below min로 이기는 것" pattern the
autonomous goal explicitly calls out to avoid.

Verdict: BT-floor fix (v3's own change) = success. Terminal-reward equal
payoff (inherited from v2) = the actual blocker on the real goal. → v4 below.

### ic_s3_bt_v4 (2026-07-03) — launched, see YAML for full rationale

Change: `student/my_reward.py` now pays `win_reward=150` only for a genuine
kill (`target_hp <= 0`) and a separate, lower `forced_ground_reward=50` for
"target altitude below min" while the target is still alive on health.
Everything else (BT DLL, hyperparameters, env_config) identical to v3.
Seeded from v3's own final bundle (keep the learned tracking skill, only the
terminal incentive changes). Launched 2026-07-03 04:59, RUNDIR
`artifacts/watch/20260703_045906`. **FINAL (DONE, exit=0, 100/100 iters).**

Recovered cleanly from an initial re-seed-shock crash spike (own-crash
0.07→peaked 0.75 at iter~20→back to 0.000 by iter~85, textbook match for the
project's known re-seed transient) and converged to a fully safe policy:
crash_rate=0.000, loss_rate=0.000 for the last ~15 iterations, reward_mean
stable ~82-85, `ep_wez_steps` up to ~13-15/240 (was ~8-11 in v3),
`ep_reward_damage` up to ~4-4.8/~30 (was ~3-4). **But real kills were STILL
0%**: a converged-window breakdown (last 500 log lines, all "target altitude
below min") showed **100% forced-ground**, matching the whole-run number
(81.14%, `tools/end_condition_breakdown.py`). So halving forced-ground's
payoff (150→50) successfully pushed the RL to stop taking any risk (own-crash
essentially eliminated) but did NOT make it start pressing for kills — it
just found a **zero-risk way to farm the same forced-ground outcome**.

Root-cause dig (via `artifacts/logs/team01/ic_s3_bt_v4/engagement_replays/iter_000090`):
pulled the actual target Tacview trajectory for a representative episode.
Own_hp/tgt_hp stayed 1.0/0.94 the entire episode (ep_min_distance 837m — RL
never closed in at all) while the BT's altitude fell from 7000m to 262m in
under 4 seconds flat, pitch pinned at -75° to -89° (near-vertical) with
erratic oscillating roll the whole way down — a sustained, uninterrupted dive
from essentially the first tick of the episode, not a late defensive
maneuver gone wrong. **The RL wasn't declining to press for a kill out of
caution — there was never a window to press one in.** The BT was already
committed to crashing itself before the RL could do anything.

First hypothesis (wrong, but a reasonable BT-hardening pass regardless):
`Task_RearThreatJink`'s `lowAltitudeBias=-0.45` (intentional dive-to-break at
high altitude) looked like the obvious trigger, since the `offensive_saddle`
spawn (RL locked on at the BT's six, 1100-1450m, aspect 0-30°) satisfies that
task's range/LOS gates almost every episode from step 0. Fixed in
`TacticalTasks.cpp`: removed the intentional dive bias (now 0.0, was -0.45)
and raised recovery margins throughout (`kHardAltitudeFloor` 900→1800,
tree-level `LowAltitudeCheck`/`ClimbRecover` 900/1500→1800/2500 in
`Rule_forTraining.xml`, `RearThreatJink`'s internal clamp 1200/1600→2200/3000).
Rebuilt, deployed (backup: `AIP_BASE_target_pre_rearjink_divebias_<stamp>.dll`).
**Verified this did NOT fix it** — re-ran `scripts/run_eval.py` (20 episodes,
v4 bundle vs the newly-fixed DLL, same saddle geometry): still 100%
"target altitude below min" in ~236-244 steps (~4s) every single episode,
byte-identical pattern to before the C++ change.

**Actual root cause, confirmed empirically:** it's the `offensive_saddle`
spawn geometry itself, not any single BT task's logic. Pulled a fresh
Tacview trace with the new DLL — same instant near-vertical dive from tick 0,
regardless of which task's altitude-floor code was touched. Tested
`range_m` directly (single-episode probes, same v4 bundle + fixed DLL):
1100-1450 (original) / 1600-2000 / 2000-2600 / 2800-3400 — **all** still
crash in ~230-280 steps; **3600-4500 — does not trigger it at all**
(ran the full 900-step episode, `max time out`). An 8-episode batch at
3600-4500 confirmed it: 2/8 max-time-out with **actual mutual damage
exchanged** (own_hp/tgt_hp both ~0.83-0.92, i.e. real gunnery happening for
the first time in this whole S3 line), 2/8 more max-time-out, only 3/8 still
ended in forced-ground but much later in the episode (456-849 of 900 steps,
not an instant 4-second death) and 1/8 ownship crash. Whatever the exact BT
vector-math trigger is (not fully root-caused at the C++ level — plausibly a
degenerate-geometry edge case specific to a near-dead-six, near-point-blank
threat, given `Task_DefensiveBreak`'s `lateralDot` computation is explicitly
near-zero/degenerate for aspect≈0°), it requires the tight saddle geometry to
fire. The C++ hardening from this run is still reasonable to keep (removes an
unforced intentional dive, adds margin) but was **not** the actual fix.

→ v5 (below): widen `offensive_saddle.range_m`, single new variable.

**Checkpoint @ iter 37/150 (2026-07-03):** widened range confirmed working -- own-crash spiked 0.85-0.97 for iters 0-9 (expected re-seed disruption from the range jump), recovered cleanly to ~0.000 by iter 20, now mostly timeout (0.8-1.0) with loss ~0.05-0.2, no wins yet. Healthy, re-armed watcher, no action needed.

### ic_s3_bt_v5 (2026-07-03) — FINAL (DONE, exit=0, 150/150 iterations)

The range widen worked exactly as diagnosed: whole-run breakdown (2924
terminations) — `max time out` 78.56%, `ownship altitude below min` 18.84%
(all from the iter 0-9 re-seed spike, recovered to crash_rate=0.000 by
iter~20 and stayed there), `ownship destroyed` 2.39%, **`target altitude
below min` (forced-ground) down to 0.21%** (was 81-82% in v3/v4). The BT
self-destruct exploit is essentially gone.

**But this exposed the next problem**: for the last 25 iterations
(125-149), `reward_mean` is flat at -180 to -190 with **zero variation**,
`win_rate=0.000` on every single row, `ep_wez_steps` mostly 0.00 (occasional
0.2-0.65), `ep_reward_damage` mostly ~0 (barely any hits landed),
`timeout_rate` 0.875-1.0. `ep_min_distance` sits at a stable 590-830m —
inside WEZ range (152-914m) but the policy isn't converting that into
sustained cone time or damage. Since `draw_reward == loss_reward == -150`
already (the project's existing anti-loiter design), a passive "close to a
comfortable distance, then orbit to a guaranteed timeout" strategy is
exactly as bad on paper as trying and failing — but it's zero-risk, while
actually pressing for a kill risks a worse outcome (getting hit, or crashing
again). PPO found the zero-risk plateau first and reward_mean shows no sign
of climbing out of it in the last third of the run. This is the same class
of "safe-draw/loiter attractor" the project fought earlier in the S2 flat-run
stage (before draw=loss was even applied) — recurring here because the new,
much larger range (3600-4200m vs the 1100-1450m all prior tracking skill was
learned at) needs stronger closure/engagement pressure than the existing
reward provides, not because draw=loss stopped working.

**Constraint check:** confirmed the platform exposes no PPO entropy
coefficient knob at all (`train_rllib.py` has no `--entropy-coeff` flag;
`--target-entropy` is SAC-only) — this lever from the original plan (item 3,
"consider hyperparameter tuning... entropy coefficient") is not available on
this platform, per much earlier project history ("no entropy-coef YAML
knob"). Ruled out, not applicable here.

→ v6 (below): strengthen the continuous closure/engagement incentive
(`pursuit_dense_scale` 0.1→0.2, doubled) and extend runway (150→200
iterations, since escaping a flat plateau may need more time even with a
stronger signal), continuing from v5's bundle.

### ic_s3_bt_v6 (2026-07-03) - STOPPED EARLY (iter 37/200), superseded by v7

User requested a bigger attack reward mid-run. Killed cleanly (process tree + Ray workers verified gone) at iter 37/200, still in the expected post-reseed recovery window (crash 0.85 at iter0 -> ~0.000 by iter30, reward settling back toward the same ~-190 plateau v5 ended at -- too early to tell if pursuit_dense_scale=0.2 alone would have broken out). Not wasted: confirms the recovery pattern is consistent and reproducible across reseeds at this range. Superseded by v7 below.

### ic_s3_bt_v7 (2026-07-03) - launched, user-directed attack-reward boost

Change: damage_dealt_scale 30->60 (doubled), on top of v6's pursuit_dense_scale 0.1->0.2. Seeded from v5 (last fully-converged clean checkpoint), not v6. Rationale: closure pressure alone (v6) only pulls the RL toward the target; it does not make actually landing/sustaining damage once close worth more relative to the safe-draw plateau's guaranteed -150. Doubling the dealt:taken asymmetry (2.5x->5x) directly targets that. Watching for: ep_reward_damage and ep_wez_steps trending up past v5's plateau (~0, ~0), win_rate becoming nonzero. Result: **pending**.

**Checkpoint @ iter 37/200 (2026-07-03), v7:** promising shift -- ep_min_distance dropped steadily from ~2000-2300m (early, still closing from the wide saddle spawn) down to 115-290m by iter 30+ (well inside WEZ range 152-914m, several episodes even below the 152m minimum), vs v5/v6 which plateaued around 590-830m and never got this close. ep_reward_damage now regularly POSITIVE and volatile (1.25, 0.37, 0.74, 1.01, 1.44 mixed with negatives) instead of flat ~0 -- real mutual damage exchange happening, not passive standoff. Own-crash recovered from the usual reseed spike by iter~15. Still win_rate=0.000 every iteration (no target-destroyed kill yet) and timeout still dominates (0.7-1.0), but this is a qualitatively different, more engaged regime than v5/v6 reached. Re-armed watcher (ETA-based, ~3.1h ceiling), healthy, no action needed.

### ic_s3_bt_v7 (2026-07-03) - near-FINAL analysis @ iter 194/200 (finishing now)

Attack-reward boost produced the most ENGAGED behavior of the whole line mid-run (iters ~15-40: ep_min_distance 115-290m, ep_reward_damage repeatedly positive 0.3-1.4 - real mutual gunfire, several episodes inside the WEZ min-range band), then REGRESSED: iters 175-194 back to 570-850m standoff, wez=0.00, dmg slightly negative, timeout ~1.0, win_rate=0.000 throughout. Diagnosis: at close range the BT out-guns the RL (holds its cone better), so closing = taking damage with nothing to show for it; even at dealt:taken 5x the risk-adjusted value of closing stayed negative and PPO retreated to standoff. Chicken-and-egg: gunnery is only learnable close-in, but close-in is net-punishing before gunnery exists.

User asked whether the BT is simply too hard for the RL. Assessment: partially - the BT is beatable in principle (RL reaches gun range fine) but the last skill (holding the 4-deg half-cone on a breaking target while under return fire) has no dense learning signal and negative expected value under the current shaping. Fix the incentives first (v8); if v8 still yields zero kills, THEN nerf the training BT (Rule_forTraining.xml is under our control) as an intermediate curriculum stage (v9 candidate).

### ic_s3_bt_v8 (2026-07-03) - LAUNCHED (RUNDIR artifacts/watch/20260703_125615)

Four changes, one diagnosis (break the close=get-shot=retreat loop): (1) NEW reward.wez_step_bonus 0.5/step while the full WEZ condition holds (implemented in student/my_reward.py, unit-verified: entry step pays 20.5, sustain steps pay +0.5, out-of-cone pays 0) - dense signal for SUSTAINING the gun solution; not loiter-farmable since in-WEZ time deals damage automatically. (2) damage_taken_scale 12->6 - staying in the fight while learning is half as painful. (3) max_engage_time 90->180s - the 3600-4200m spawn ate most of a 90s episode in closure. (4) **user request**: wez.angle_deg 8->16 (doubled again) - angle_deg is the real damage-model cone (platform default is 2.0; 8 was already a deliberately wide training-shaping value). Wider cone = easier to stumble into and learn to hold while tracking skill is this weak. Symmetric (helps BT land hits too) but the BT's tracking is already reliable/rule-based - the RL's cone-hold is the actual bottleneck, so expected to net-help exploration more than it helps the BT. Plan to narrow back toward 2 deg in a later stage once real kills start happening. Seed: v7 bundle_000030 (peak-engagement policy, mindist 115-290m era), NOT v7 final (already collapsed back to standoff). 150 iterations, startup verified healthy. Result: **pending**.

### ic_s3_bt_v9 (2026-07-03) - PREPARED, NOT LAUNCHED (per user instruction)

User corrected v8s approach: widening wez.angle_deg (the real, symmetric kill/damage cone) was the wrong lever. New design: wez.angle_deg reverted to platform default 2.0 (unchanged real kill criteria for both aircraft), and a NEW reward-only wide cone added for RL shaping specifically. Implemented in student/my_reward.py: new `_wez_precision_bonus()` (replaces v8s flat `wez_step_bonus`) -- active within the TRUE WEZ range band but scored continuously across `wez_shaping_cone_deg` (45.0, reward-only) instead of the true 2.0 kill cone, peaking at dead-on aim and ramping to 0 at the wide cones edge. Unit-verified: dead-on=1.5, 45deg-edge=0.0, 10deg-off(outside true cone, inside shaping cone)=0.833 partial credit, out-of-range=0.0. `experiments/ic_s3_bt_v9.yaml` written + dry-run verified, seeded from v7 bundle_000030 (same starting point as v8, since v8s own progress is under the now-superseded angle_deg=16 regime). NOT launched -- awaiting user decision (also v8 is still running as of writing, RUNDIR artifacts/watch/20260703_125615).

**Final design (2026-07-03):** user rejected the initial v9 launch mid-command and revised the precision-bonus shape before relaunch: instead of a 0-to-1.5 ramp down to zero at the cone edge, it now pays `wez_precision_bonus_min`=30 the instant aim is anywhere inside the 45-degree wide cone, rising linearly to `wez_precision_bonus_max`=60 at dead-on (0 outside the cone) -- a floor-plus-ramp, not a ramp-to-zero. Re-verified: ata=0 -> 60.0, ata=11.25deg (midpoint) -> 45.0, ata=22.5deg (cone edge) -> 30.0, ata=22.51deg -> 0.0 (sharp drop just outside the cone, expected/intentional), out-of-range -> 0.0.

Killed the interim v8 (iter 15/150, negligible loss, superseded design) and launched v9 with these final values. RUNDIR: artifacts/watch/20260703_131627. Startup verified healthy.

Self-note: at 30-60 per step, sustained wide-cone time can outweigh the terminal win_reward (150) within just a handful of steps. Watch for a new "hold the wide cone, don't bother finishing" attractor, analogous to the earlier forced-ground attractor -- the signature to watch for is reward_mean climbing steeply while `target destroyed` share (tools/end_condition_breakdown.py) stays at 0%.

**PAUSED (2026-07-03) per user request.** Stopped cleanly at iter 12/150 (process tree + watcher + Ray workers all verified terminated, none left running). Latest saved checkpoint: `artifacts/models/team01/ic_s3_bt_v9/bundle_000010` (iter 10; iters 11-12 since that save are lost, per `lightweight_bundle_frequency: 10`). No native checkpoint was enabled (`save_native_checkpoint: false`, matching every run so far), so resuming means a fresh optimizer state via `init_bundle` from `bundle_000010` -- NOT a true paused-state resume (RLlib has no live pause/suspend; "resume" here means relaunch seeded from the last saved weights). This carries the same "re-seed disruption" transient documented earlier in this log (expect a brief crash/reward dip before recovering) since the optimizer state, not just the policy weights, resets.

To resume: `python scripts\run_experiment.py experiments\ic_s3_bt_v9.yaml` with `runtime.init_bundle` repointed to `artifacts/models/team01/ic_s3_bt_v9/bundle_000010` (or a fresh `ic_s3_bt_v9b.yaml` per the one-YAML-per-run convention), same reward/env config, no new changes -- this is a pause/continue, not a new experimental variable.

### ic_s3_bt_v9b (2026-07-03) - RESUMED per user request

`experiments/ic_s3_bt_v9b.yaml` written: identical reward/env config to v9, only `runtime.init_bundle` repointed to v9's own `bundle_000010` (was v7's `bundle_000030`) -- a pure continuation, no new variable. Launched, RUNDIR `artifacts/watch/20260703_145001`, startup verified healthy. Same re-seed-disruption transient expected as every other bundle-seeded restart in this line (brief crash/reward dip, recovers by ~iter 20-30 historically).

**STOPPED at iter 44/150 (2026-07-03) — the precision-bonus attractor materialized exactly as flagged.** `training_log.csv`: `reward_mean` spiked to 600-970 (iter 25, 29, 33, 35, 39, 40, 42) — far beyond `win_reward`=150 — while `win_rate` stayed 0.000 on every single one of the 45 logged iterations. `ep_min_distance` dropped to 63-150m (below the true WEZ min-range 152.4m in several rows) confirming the RL is closing very aggressively, but `ep_wez_steps` stayed ~0.00-0.29 and `ep_reward_damage` hovered at/below 0 — no real gunnery, just proximity+rough-angle inside the wide 45deg cone paying enormous per-step reward. Full-run `tools/end_condition_breakdown.py` (762 terminations): `ownship altitude below min` 76.51% (own-crash — the ORIGINAL v1-era failure mode, fully back), `max time out` 20.60%, `target altitude below min` 2.49%, **`target destroyed` 0.00%**. The 30-60/step precision bonus is large enough that PPO now accepts crashing itself (a guaranteed -150 + altitude penalties) as a worthwhile gamble for a few steps of proximity reward, undoing the altitude-safety fix from v2/v3 as a side effect. Killed cleanly (process tree + Ray workers verified gone). Root cause: precision-bonus magnitude, not the shape (min/max/linear-interp shape itself is correct and unit-verified) — reported to user for a rebalance decision before any relaunch.
### ic_s3_bt_v10 (2026-07-03) - LAUNCHED (RUNDIR artifacts/watch/20260703_152617)

User redesign of both exploited shaping terms after v9b's collapse. (1) Precision bonus: cone 45->90deg, payoff reshaped from linear 30(edge)->60(dead-on) to EXPONENTIAL 1(edge)->100(dead-on), bonus = 100^(1-|ata|/45). Verified: 0deg->100, 5deg->59.9, 10deg->35.9, 22.5deg->10, 45deg->1, outside->0. Sloppy aim now nearly worthless; payoff concentrated where the true 2deg kill cone (automatic damage) lives. (2) Altitude bumper: reshaped from max-25 polynomial (100m band) to EXPONENTIAL -1@600m -> -1000@300m (300m band), penalty = -1000^((600-alt)/300). Verified: 600m->-1, 450m->-31.6, 350m->-316, 300m->-1000/step. Rationale: v9b proved the old penalty could be outbid by shaping; nothing outbids -1000/step. True kill cone unchanged (wez.angle_deg=2.0). Seed: v9b bundle_000040 (last checkpoint, per user instruction) - the degenerate crash-diving policy, but the -1000 wall gives an immediate dominant gradient to unlearn the dive while keeping its aggressive-closing skill. Flagged caution: per-step rewards now span ~-1000..+100, watch vf_loss/explained_var for value-function instability. 150 iterations. Result: **pending**.

**Checkpoint @ iter 40/150 (2026-07-03), v10:** healthy but noisy recovery from the v9b crash-diver seed + a much larger reward scale. crash_rate started ~0.68-1.0 (iter 0-14, the inherited diving habit meeting the new -1000/step wall) and is trending down through iter 20-42 (0.2-0.5, still noisy, occasional spikes back to 0.6-0.7). ep_min_distance dropped from ~2100-2500m to 500-1300m -- engaging, not standing off. No repeat of the v9b farming pattern (no reward spikes into the hundreds from cone-loitering). reward_mean stays deeply negative (-600 to -4600) but is not comparable across versions anymore -- the reward scale itself changed by ~10x (a single early crash now costs -1000 alone). Caution flagged pre-launch materialized somewhat: explained_var is hovering near 0 (occasionally slightly negative), i.e. the value function is still recalibrating to the new scale; vf_loss is trending down (2.5 -> 1.2-1.6) which is the healthier signal to watch. Not yet bad enough to intervene -- re-armed watcher (ETA-based ~1.7h ceiling), no action taken.

**PAUSED (2026-07-03) — user shutting down the laptop, resume later.** Stopped cleanly at iter 63/150 (process tree + watcher + Ray workers all verified terminated, none left running). Latest saved checkpoint: `artifacts/models/team01/ic_s3_bt_v10/bundle_000060` (iter 60; iters 61-63 since that save are lost, per `lightweight_bundle_frequency: 10`). Status right before the stop: crash_rate still noisy in the 0.45-0.63 range (not yet clearly converged down from the v9b-inherited diving habit, though earlier checkpoints in this run got as low as 0.125-0.2 -- iter 61-63 may just be a noisy patch, not a reversal), ep_min_distance oscillating 1000-1800m, no wins yet, no repeat of the v9b farming exploit.

Same caveat as the earlier v9->v9b pause: no live pause/suspend exists on this platform (`save_native_checkpoint: false`), so resuming means a fresh optimizer state via `init_bundle` from `bundle_000060` -- expect another brief re-seed disruption on top of whatever state the policy was actually in.

To resume: `experiments/ic_s3_bt_v10b.yaml` (or similar), identical reward/env config to v10, `runtime.init_bundle` -> `artifacts/models/team01/ic_s3_bt_v10/bundle_000060`. No new experimental variable -- this is a pause/continue. Result: **paused, awaiting resume instruction**.

### ic_s3_bt_v10b (2026-07-03) - RESUMED (laptop back on)

`experiments/ic_s3_bt_v10b.yaml` written: identical config to v10, only `runtime.init_bundle` repointed to v10's own `bundle_000060` (was v9b's `bundle_000040`) -- pure continuation, no new variable. Launched, RUNDIR `artifacts/watch/20260703_170750`, startup verified healthy. Same re-seed-disruption expected. Watching whether crash_rate resumes its downward trend (was 0.125-0.2 around iter 33-36 before the noisy 0.45-0.63 patch at iter 59-63) or whether that late uptick was a real reversal. Result: **pending**.

**Checkpoint @ iter 43/150 (2026-07-03), v10b:** healthy, clearer trend than pre-pause. crash_rate: 0.72-0.95 (iter 0-9, the usual re-seed shock repeating), declining through iter 10-20 (0.3-0.67), settling to mostly 0.08-0.29 by iter 33-43 (with one iter at 0.000). No repeat of the v9b farming exploit (no reward spikes into the hundreds -- max positive seen is 311.5 at iter 43, well within a plausible real-engagement range). ep_min_distance frequently under 300-500m (down to 99m at times), ep_wez_steps occasionally nonzero (0.06-0.5), ep_reward_damage occasionally positive. No wins yet. vf_loss/explained_var showing n/a for this run (metric-extraction quirk, not investigated -- other signals look healthy so not blocking). Re-armed watcher (ETA-based ~1.6h ceiling), no action needed.

### ic_s3_bt_v10b (2026-07-03) — FINAL (DONE, exit=0, 150/150 iterations)

Full-run breakdown (`tools/end_condition_breakdown.py`, 1836 terminations): `ownship altitude below min` 57.19%, `max time out` 37.75%, `target altitude below min` (forced-ground) 4.90%, `ownship destroyed` 0.16%, **`target destroyed` 0.00%**.

Compared to v3/v4 (forced-ground ~82%, own-crash was the OTHER dominant mode at different points): forced-ground is now solved (82% -> 4.9%). But own-crash never converged the way the mid-run checkpoint (iter 33-43, settling to 0.08-0.29) suggested it would -- the final 20 iterations (130-149) oscillate noisily between 0.167 and 0.708 with no clear downward trend. 200 cumulative iterations (v10's 63 + v10b's 150, across two reseed-disrupted starts) have not produced a single real kill.

One notable data point buried in the noise: iter 147 shows `ep_wez_steps=2.00` and `ep_reward_damage=+3.56` (mindist=91.2m, inside the true WEZ) -- the first iteration in the whole S3 line with meaningfully sustained true-cone time and net-positive damage on average across the batch. Isolated, but proof the exponential precision bonus CAN produce genuine engagement, at least occasionally.

Hypothesis for the non-convergence (flagged pre-launch, now more evidenced): the reward scale itself may be destabilizing PPO's optimization. Terminal/damage terms are O(1-150); the v10 altitude/precision terms span O(1-1000) and O(1-100) respectively -- a >10x range expansion. `vf_loss`/`explained_var` were logged as `n/a` for this whole run (metric-extraction gap, not investigated), so this can't be directly confirmed from the CSV, but the noisy, non-converging crash_rate oscillation is consistent with a value function struggling to track high-variance, high-magnitude per-step rewards rather than a policy that's stuck at a stable bad local optimum (which would look flatter, not noisier).

Reported to user with this read and a recommendation to consider moderating the extreme end of the reward scale (e.g. altitude penalty max 1000 -> something smaller while keeping the exponential shape) OR continuing further given the iter-147 proof-of-concept. Awaiting direction. Result: **200 cumulative iterations in, 0% real kills, forced-ground solved, own-crash reduced but not converged -- next step pending user input**.

### ic_s3_bt_v11 (2026-07-04) - LAUNCHED: value-function scale fix (evidence-based, autonomous decision)

User delegated the v10b-nonconvergence decision ("직접 근거와 함께 판단해서 적용", web search allowed). Investigation:
1. Local cross-run evidence: explained_var mean 0.639 (max 0.967) in v7 whose returns stayed within ~±300, vs mean 0.004 (max 0.252, sometimes negative) in v10 whose returns spanned ±1000-4600. The value function explained nothing for the entire v10 run.
2. Root cause confirmed in local Ray 2.54.0 source (rllib/algorithms/ppo/ppo.py:141): vf_clip_param defaults to 10.0, docstring says "sensitive to the scale of the rewards", and RLlib itself logs a warning to increase it when mean rewards exceed it. With value targets in the thousands clipped to ~10 per update, the critic cannot track returns -> advantages are noise -> the observed noisy non-converging crash_rate. Web search corroborated this is a well-known RLlib failure mode (vf clipping historically "a common cause of user problems").
3. train_rllib.py exposes NO vf-clip flag (grep verified), so instead of modifying platform launch scripts, chose a student-side fix.

Fix: `reward_output_scale: 0.05` (new key in student/my_reward.py) - a uniform 1/20 multiplier applied to every component and the total at the very end of compute_reward. Uniform positive scaling preserves the optimal policy and every designed ratio EXACTLY (the user's exponential precision/altitude curves are untouched; PPO standardizes advantages so the policy gradient is scale-invariant) - only the value-target magnitude shrinks, back into v7's proven-healthy range. Verified numerically: dead-on step 120.4->6.02, altitude@350m -316->-15.8 (safety incl. PBRS -16.27), win 150->7.5, ratios preserved to 4 decimals.

Single new variable vs v10b. Seeded from v10b's final bundle (the incentive structure was right; only the critic was scale-broken). RUNDIR `artifacts/watch/20260704_014333`, startup verified healthy. Success signal to watch: explained_var climbing toward v7-like values (>0.5) within the first ~30 iters, then crash_rate actually converging down instead of oscillating, then wez/dmg/kills. Result: **pending**.

**Checkpoint @ iter 40/150 (2026-07-04), v11 — hypothesis confirmed, best trajectory in the whole S3 line.** explained_var recovered almost immediately: 0.06 (iter0) -> 0.42-0.9+ by iter3-9, sustaining 0.5-0.9 for the rest of the run (matches v7's healthy 0.639 mean, unlike v10's stuck-at-0.004). crash_rate: 0.83-0.97 (expected reseed shock) -> clean convergence to 0.000 by iter17, HOLDS at 0.000 for iters 17-36 (20 straight iterations), only minor blips (0.08-0.21) at 37-40 -- genuine convergence, not noise oscillation like v10. ep_min_distance dropped from ~2000-2500m to a stable 30-70m by iter17+ and stayed there. reward_mean flipped from crash-dominated negative to positive and climbing (27-121 in iters 20-40). ep_wez_steps now regularly nonzero (0.17-0.62). No wins yet (damage still near-breakeven, 0.00-0.07) but this is unambiguously the healthiest, most stable trajectory of the entire line -- the reward_output_scale fix worked exactly as diagnosed. Re-armed watcher (ETA-based ~1.8h ceiling), no action needed, letting it ride.

---

## 2026-07-04 — v13b postmortem: PLATFORM BUG #7 (init_bundle was a silent no-op) + v14 relaunch

**v13b result (codex run, RUNDIR `artifacts/watch/codex_v13b_reduced_precision_rear_gunnery_v1`, 60/60 iters):**
win_rate 0.00 every iteration (one 0.05 blip), timeout -> 1.0, ep_wez_steps ~3, ep_reward_damage ~1.5,
reward_mean climbing 6 -> 66 purely from pursuit/precision stream — looks like farming, BUT the real story:

**Iterations 0-13 were 100% range-discipline LOSSES with fresh-init behavior** (ep_len ~350, min_dist ~640m,
mean_dist ~1720m, final_ata ~87 deg) — the seed bundle_000090, whose frozen NumPy eval shows 314 band-steps
and 45 true-cone steps per episode, was NOT flying. Cross-check: **v12b iter 0 shows the IDENTICAL fresh
signature** (ep_len 377, min_dist 611) despite being "seeded" from v12 bundle_000080 (v12 iters 77-79:
min_dist 58-70m). Every reseed in the project history reset behavior to scratch.

**Root cause — platform bug #7, `src/dogfight/ai/checkpoint_io.py::_apply_policy_weights`:** it applied the
bundle ONLY to `algorithm.env_runner` (the LOCAL env runner, which never samples when num_env_runners=4) and
returned True. The 4 remote samplers kept fresh weights, the learner kept fresh weights, and the first
update broadcast learner(fresh) over everything. `--init-bundle` has therefore been a **complete no-op for
all seeded runs to date**; every "re-seed disruption / crash spike" observed since June was actually
training-from-scratch. Codex's restore autopsy passed because it checked `algorithm.get_module()` — which
returns the LOCAL env runner module (the one object the old code did touch) — never the learner or remote runners.

**Companion bug #7b (save path):** `_extract_policy_weights` read the local env-runner module, which on the
new API stack is an **inference-only** copy -> bundles contained only the 7 actor tensors, critic silently
dropped.

**Fixes applied (BUGFIX-marked, in `src/dogfight/ai/checkpoint_io.py`):**
- load: apply to `algorithm.learner_group.set_state({"learner": {"rl_module": {policy_id: weights}}})` first,
  then `env_runner_group.sync_weights(from_worker_or_learner_group=..., inference_only=True, timeout=120)`,
  keep the old local set + old-stack fallbacks. Actor-only bundles load fine (torch strict=False keeps the
  fresh critic).
- save: prefer `learner_group.get_weights()` -> bundles now carry 14 keys incl. critic + vf. Extra keys are
  ignored by inference-only consumers (verified: RLModule.set_state docstring/behavior), NumPy eval indexes
  by name — unaffected.
- Verified with new `scripts/verify_bundle_restore_fix.py` (extends codex autopsy to learner + all REMOTE
  runners): all_ok=true — learner, 4 remote runners, local runner all match bundle actors; extraction has vf.
  Report: `reports/verify_bundle_restore_fix_20260704.json`.

**Also fixed:** `tools/codex_static_train_monitor.py` crashed with PermissionError (WinError 5) when
`os.replace` hit the HTML file held open by a viewer — that was the "train-monitor failure"; now retries then
falls back to overwrite. (The port-hosted monitors were fine.)

**v14 launched (RUNDIR `artifacts/watch/20260704_210532`, tag team01/ic_s3_v14_seedfix_rear_gunnery_v1):**
byte-identical config to v13b (same reward student.codex_reward_v13b, same seed bundle_000090, lr 3e-5,
clip 0.08, 60 iters) — single variable = the loader fix. Success signal at iter 0-5: band-tracking from the
start (ep_reward_pursuit >> 15, ep_min_distance < 400m, loss_rate << 1.0) instead of v13b's fresh-init
100%-RD-loss opening. If confirmed, all prior "which seed checkpoint is best" analysis (codex ladder) becomes
actionable for real; if kills still fail after genuine seeding, next lever is the precision-stream-vs-kill
payoff ratio (farming stream still totals ~1400 raw/episode vs ~680 one-time for a kill). Result: **pending**.

**v14 RESULT (2026-07-04, DONE exit=0, 60/60, ~37 min): FIX CONFIRMED END-TO-END — first true kill-converting
checkpoint of the rear-gunnery line.** Train: win_rate 0.47 at iter 0 (vs v13b's 0.00/100%-loss opening),
oscillating 0.48-0.81 through iter 59; wez_steps ~23, min_dist ~200-270m, damage ~17 (scaled) ≈ 1.0 hp/episode,
loss+crash ~0. Cross-validation, same bundle_000060:
- `run_eval --target-backend autopilot --experiment-yaml v14` (env-NATIVE target, RLlib inference, default
  ~300s engage time = competition timing): **65% win / 0% loss / 35% draw, 13/20 genuine "target destroyed"**.
- codex NumPy frozen eval (provider-driven target + hard 90s cutoff): 0/10 kills, ~0.37 hp/episode.
  Two compounding causes: (1) 90s cutoff — the policy deals ~0.4 hp per 90s, kills mostly land in 90-300s;
  (2) provider-vs-env-native target path mismatch (same class as the documented BT provider mismatch of
  2026-06-19). So the codex "train metrics not reproducible in frozen eval" mystery = loader bug (#7, now
  fixed) + eval-harness timing/target-path mismatch — NOT metric fabrication.
Champion candidate: `ic_s3_v14_seedfix_rear_gunnery_v1/bundle_000060` (65% deterministic eval vs weave
autopilot at competition timing). Next: (a) push win% higher / draw down (7 timeouts were slow grinds —
consider longer max_engage_time in training or keep 90s pressure), (b) re-run the checkpoint ladder now that
seeding is real, (c) BT opponent stage with true seeding.

---

## 2026-07-04 — v15: exploit-stripped, kill-aligned reward (user directive)

**Diagnosis (user + data-confirmed):** v14 win_rate PEAKED 0.94 @iter22 then declined to 0.67-0.71
@iter30-50 while reward_mean climbed (pursuit slot 154->195) and ep_reward_damage stayed flat ~17.
The reward function was NOT optimizing win_rate — the agent found a non-lethal shaping exploit whose
per-episode payoff (~154-195 logged) dwarfed win_reward (220*0.05=11 logged). Two farmable terms, both
folded into the platform "pursuit" slot:
  1. `rear_cone_reward` (student/my_reward.py `_aspect_shaping`, rear_cone_reward_scale=0.15): pays every
     step the ownship sits in the target's rear cone — collectable by loitering behind, no shot.
  2. wide-90deg `_wez_precision_bonus` (wez_precision_bonus_min/max, wez_shaping_cone_deg=90): pays for
     rough aim inside the WEZ RANGE band without a real hit (true kill cone is 2deg).

**Fix (v15):**
- New reward module `student/codex_reward_v15_wez_only.py`. Zeroed rear_cone_reward_scale,
  wez_precision_bonus_min/max, pursuit_dense_scale, wez_entry_bonus. Added a `bonus_max<=0` early-return
  guard to `_wez_precision_bonus` in my_reward.py (backward-compatible; default 100 unchanged).
- ATTACK reward now = real WEZ damage ONLY (damage_dealt_scale=350 * target_damage, which
  single_agent_env.update_damage accrues exclusively inside the true 2deg WEZ cone) + terminal win (220)
  + fast-kill bonus. Kept un-farmable shaping: PBRS pursuit potential (closure gradient; telescopes to
  boundary terms so dwell-time farming is impossible), PBRS altitude + hard floor penalty (anti-crash),
  front-cone PENALTY (defensive, not a reward). draw/timeout = draw_reward -100.
- Unit-verified (isolated states): farm-attempt state (behind target, in range, roughly aimed, NO damage)
  -> v15 pursuit=0.0000, total≈-0.0003 (step penalty only); vs v14-style same state pursuit=0.147/step.
  Real WEZ hit -> damage=0.35 only. Kill@40s -> terminal=16.44. Win now dominates return.
- Seed = v14 `bundle_000020` (highest-win SAVED checkpoint, win 0.84; iter22's 0.94 wasn't saved). Bundle
  carries the critic (14 keys, post checkpoint_io save fix) so the value fn restores too. 100 iters,
  lr 3e-5 / clip 0.08.

**Launched** RUNDIR `artifacts/watch/20260704_222327`, tag team01/ic_s3_v15_wez_only_v1.
**Success signal:** reward_mean and win_rate now MOVE TOGETHER (no reward-up/win-down divergence);
ep_reward_pursuit collapses toward ~0; win climbs past 0.84 toward ~1.0; timeouts drop. Watch for a brief
re-adaptation transient (critic value targets shift when the reward scale changes) in iters 0-10.
Result: **pending**.

---

## 2026-07-04 — v15 SUCCESS (win 1.00) -> ic_s4 WEAVE CURRICULUM begins

**v15 RESULT: win_rate 1.00 achieved and SUSTAINED** (iters 61-72 nearly all 1.000, timeout 0.00,
crash 0.00, reward_mean ~33 stable). The exploit-strip + kill-alignment fully worked: reward and win
moved together, pursuit farm slot pinned 0.0 the whole run, no collapse. Champion (level target):
`ic_s3_v15_wez_only_v1/bundle_000070`. Training stopped by user at ~iter72 to advance the curriculum.

**New capability added (DogFightEnvWrapper.py):** the weave curriculum is now 3D + anti-forgetting.
- `target_weave.vertical_amplitude_m` + `vertical_period_steps`: oscillates the autopilot `altitude_cmd`
  around its base (up/down), on an INDEPENDENT period from the heading weave, so the target flies a true
  3D wander, not a flat diagonal. (altitude_cmd is Down-positive, base -alt; verified in real env: target
  altitude oscillated 6737-7000m over a smoke run.)
- `target_weave.straight_prob`: fraction of episodes (decided at reset) that fly perfectly straight &
  level, pinning the autopilot commands to base -- prevents forgetting the mastered level-kill skill.
- Existing horizontal `amplitude_deg`/`period_steps` (heading weave) unchanged.

**Ladder (each stage seeds the previous stage's converged bundle; advance when win holds ~>=0.9 on
weaving episodes; reward = exploit-free v15 throughout):**
| stage | heading amp/period | vertical amp(m)/period | straight_prob | intent |
|---|---|---|---|---|
| s4 weave1 (LAUNCHED) | 15deg / 180 | 250 / 140 | 0.25 | gentle 3D |
| s4 weave2 | 35deg / 140 | 500 / 110 | 0.20 | moderate |
| s4 weave3 | 60deg / 100 | 800 / 80  | 0.15 | strong |
| s4 weave4 | 120deg / 70 | 1000 / 60 | 0.10 | max-rate turn (commanded heading rate exceeds turn capability => near-continuous hard turn) |

**Stage 1 launched:** RUNDIR `artifacts/watch/20260704_231628`, tag team01/ic_s4_weave1_gentle_v1,
seed v15 bundle_000070, 100 iters. Watch: brief win dip as it learns to lead the weave, then recovery;
crash ~0. Result: **pending**.

**ic_s4 STAGE 1 (gentle 3D weave) RESULT: solved almost instantly.** Seeded from v15 bundle_000070,
the level-target 100% policy generalized to the gentle 3D weave with near-zero adaptation: win 0.958
@iter0 -> 1.000 sustained by iter16-24 (crash 0, timeout 0). win_rate is over ALL episodes incl. the
25% straight ones, so no forgetting. Stopped at iter24 (converged) and advanced. Stage1 bundle used as
stage2 seed: `ic_s4_weave1_gentle_v1/bundle_000020`.

**STAGE 2 (moderate 3D weave) launched:** RUNDIR `artifacts/watch/20260704_233824`, tag
team01/ic_s4_weave2_moderate_v1. heading +/-35deg/140, altitude +/-500m/110, straight_prob 0.20, 80
iters, seed stage1 bundle_000020. Watch: first real dip expected (bigger lead), crash must stay ~0
despite larger vertical excursions. Result: **pending**.

**STAGE 2 (moderate) RESULT: converged.** Real dip as predicted: win 0.868 @iter0 -> steady climb ->
~0.99-1.00 by iter18-25, crash 0 throughout (even with +/-500m vertical). Stopped iter25, seed for
stage3 = `ic_s4_weave2_moderate_v1/bundle_000020`.

**STAGE 3 (strong 3D weave) launched:** RUNDIR `artifacts/watch/20260704_235956`, tag
team01/ic_s4_weave3_strong_v1. heading +/-60deg/100, altitude +/-800m/80, straight_prob 0.15, 80 iters,
seed stage2 bundle_000020. Watch: bigger dip likely; crash must stay ~0. Result: **pending**.

**STAGE 3 (strong) RESULT: converged.** win 0.860 @iter0 -> noisy climb -> 0.99-1.00 by iter21-28,
crash 0 (even with +/-800m vertical). Only bundle_000010/020 saved before stop @iter28; seed for stage4
= `ic_s4_weave3_strong_v1/bundle_000020` (iter20, win 0.945, converged region).

**STAGE 4 FINAL (max-rate turn) launched:** RUNDIR `artifacts/watch/20260705_002200`, tag
team01/ic_s4_weave4_maxrate_v1. heading +/-120deg/70, altitude +/-1000m/60, straight_prob 0.10, 150
iters (final stage, run to convergence), seed stage3 bundle_000020. The commanded heading rate now
exceeds the target's turn capability => near-continuous max-rate turn (hardest evader this weave model
makes). Pattern so far (iter0 dip deepening 1.0->0.96->0.87->0.86 then ~20-iter recovery to ~1.0, crash
always 0) suggests this converges too, just slower. This bundle becomes the champion vs a hard-
maneuvering autopilot; next real milestone = BT opponent. Result: **pending**.

**STAGE 4 FINAL (max-rate turn) — CURRICULUM COMPLETE.** Surprisingly the EASIEST stage: win 0.990
@iter0 (barely a dip), win 1.000 sustained by iter19-27, crash 0, timeout 0. Insight: a continuous
max-rate turn is PREDICTABLE (constant turn rate) so the agent pulls lead pursuit and sits inside the
turn circle; the intermediate weaves were harder precisely because they REVERSE direction and break the
lead. So the dip ordering was 1.0(s1)->0.87(s2)->0.86(s3)->0.99(s4) -- hardest = mid-strength
reversing weave, not the max-rate turn. Full 3D-weave curriculum solved end to end: the policy now wins
~1.0 vs gentle/moderate/strong 3D weaves AND a max-rate turner, keeps the straight-target skill (10-25%
straight episodes in each stage's 1.0), zero crashes throughout. Champion vs hard-maneuvering autopilot:
`ic_s4_weave4_maxrate_v1/bundle_000020` (win 1.0; later bundles as it runs to 150 for consolidation).
Let stage 4 run to completion for a robust final bundle. NEXT real milestone = BT opponent (held-out
control path, see the finishing-wall memory's train/eval BT mismatch).

---

## 2026-07-05 — STAGE 5 (RANDOM JINK) added, seeded from stage 4

Stage 4 (max-rate turn) consolidated to win 1.0 through iter56 (crash 0), stopped. New harder stage per
user request: randomize the weave's magnitude, direction, AND turn-switch timing so no periodic pattern
is exploitable.

**New wrapper capability (DogFightEnvWrapper._apply_random_jink, gated by target_weave.random_jink):**
the target holds a RANDOM heading-turn rate + RANDOM altitude-climb rate (each random sign) for a RANDOM
number of wrapper-steps, then re-rolls all three. Heading integrates continuously; altitude random-walks
within +/-vertical_dev_max_m of base (bounces off the band edge, no ground/ceiling drift). Verified:
schedule sim (16 segments/900 steps, both signs, alt bounded 5800-8200m) + real-env smoke (4 eps ran
clean, target altitude moved, stage-4 policy already 4/4 kills).

**Stage 5 config:** hdg_rate 2-10deg/step (up to beyond stage-4's max-rate turn), vert_rate 4-20 m/step,
switch every 20-90 steps, altitude +/-1200m, straight_prob 0.10. Reward = exploit-free v15. Seed stage4
bundle_000050 (converged 1.0). 150 iters. RUNDIR `artifacts/watch/20260705_010645`,
tag team01/ic_s5_weave5_random_v1. Success = win holds high vs the unpredictable jinker; crash ~0.
Result: **pending**.
