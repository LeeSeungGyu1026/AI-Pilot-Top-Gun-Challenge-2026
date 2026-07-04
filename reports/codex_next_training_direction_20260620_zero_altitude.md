# Codex Next Training Direction - Zero Ownship Altitude

Created: 2026-06-20T05:57:17Z

## Decision

Do not continue `codex_ic_s5_zero_altitude_guard_v1`, and do not launch another harsh-penalty PPO polish.

The next step should be a short diagnostic evaluation sweep from the frozen H5 candidate, followed by a small potential-based altitude curriculum fine-tune only after the failing scenario/target slices are identified.

## Current Baseline

- Frozen candidate: `AIP_LIB/DogFightEnv/Release_260529/artifacts/models/team01/codex_freeze_ic_s4_mixed_anchor_guard_v1_20260620_0853`
- H5 validation:
  - BT: 27 wins, 3 ownship-altitude losses
  - Autopilot: 19 wins, 1 timeout, 0 ownship-altitude losses
  - Loiter: 25 wins, 1 ownship-altitude loss, 4 timeouts
- H6 result:
  - PPO safety polish from H5 collapsed before validation
  - final crash rate 0.714
  - tail-5 crash rate 0.771
  - win rate 0.0

## Literature-Grounded Rationale

Local literature pack: `reports/codex_rl_literature_20260620/codex_literature_index_20260620.md`

Relevant references:

- Ng et al. reward shaping: avoid non-potential shaping that changes the intended policy optimum.
- SAC / TD3 / DDPG: off-policy continuous control is worth trying, but the prior mixed SAC smoke was too hard from scratch.
- Air-combat HSAC: use staged sparse-to-shaped reward homotopy rather than a single harsh terminal penalty.
- Curriculum RL survey: introduce difficult slices only after easier variants are stable.
- Air-combat self-play / 6-DOF hierarchy: robustness should be built by controlled opponent/geometry progression, not by broad randomization alone.

Interpretation: H6 made altitude loss more expensive, but did not add a learnable recovery path. That matches the reward-shaping warning. The next change should shape recovery and exposure, not punishment magnitude.

## Next Experiment Direction

### H7a: Diagnostic Before Training

Run tag: `codex_ic_s5_h5_altitude_failure_map_v1`

Purpose: identify which H5 target/scenario slices produce ownship-altitude failures.

Plan:

- Evaluate the frozen H5 bundle, not H6.
- Split BT and loiter cases by `legacy_scenario_indices` instead of using the mixed list.
- Run enough episodes per case to expose rare failures, e.g. 25 to 50 per target/scenario pair.
- Gate:
  - Count exact end-condition strings.
  - Find any case with `ownship altitude below min` or `FDM Update Fail`.
  - Do not train until the failing slices are known.

Expected output:

- A codex-named manifest listing failures by target and scenario index.
- A narrowed training distribution for H7b.

### H7b: Small PBRS Altitude Curriculum Fine-Tune

Candidate run tag: `codex_ic_s5_pbrs_altitude_curriculum_v1`

Start from:

- `artifacts/models/team01/codex_freeze_ic_s4_mixed_anchor_guard_v1_20260620_0853`

Recommended YAML direction:

- Keep algorithm as PPO for this repair branch.
- Use `student.my_reward`, not `student.codex_reward_zero_altitude`.
- Do not add large extra terminal penalties.
- Use potential-based altitude shaping:
  - `pbrs_gamma: 1.0`
  - `pbrs_alt_weight`: moderate, around 14 to 18, not 30+
  - `safety_floor_m`: 600 to 700
  - `safety_safe_m`: 1600 to 2000
- Reduce pursuit pressure near the risky floor:
  - lower `pursuit_dense_scale` to around 0.05 to 0.08
  - keep range/ATA PBRS so attack behavior is not erased
- Oversample only the H7a failing scenario slices, plus enough BT anchor cases to avoid forgetting.
- Use very conservative PPO:
  - `lr`: 2e-5 to 5e-5
  - `clip_param`: 0.03 to 0.05
  - `iterations`: 8 to 12 first

Stop criteria:

- If post-iteration 5 crash rate remains above 0.20 with no downward trend, stop.
- If win rate collapses to 0.0 after several completed windows, stop.
- Validate only if tail crash improves materially.

Hard validation gates:

- zero `ownship altitude below min`
- zero `FDM Update Fail`
- BT win >= 0.90
- autopilot win >= 0.90
- loiter win >= 0.70 and draw <= 0.25

## SAC Decision

SAC should not be the immediate incumbent-repair path because the prior from-scratch mixed SAC smoke ended with crash rate 1.0 after iteration 20.

However, SAC should remain the next research branch after H7a/H7b, using an HSAC-style staged curriculum instead of mixed random starts:

- Phase 1: BT or autopilot only, easy/high-altitude geometry, shaped reward.
- Phase 2: add loiter and failing H7a slices.
- Phase 3: reduce shaping and reintroduce mixed BT/loiter.
- Use replay and entropy tuning; do not expect PPO bundle weights to transfer.

Candidate SAC tag after diagnostics: `codex_sac_hsac_curriculum_v1`.

## Final Recommendation

Immediate next action: launch `codex_ic_s5_h5_altitude_failure_map_v1` diagnostic evaluation from frozen H5.

Training action after that: launch `codex_ic_s5_pbrs_altitude_curriculum_v1` only on the identified failing slices, with potential-based altitude shaping and conservative PPO.

Do not run another broad mixed PPO polish and do not relaunch from-scratch mixed SAC as the next main branch.
