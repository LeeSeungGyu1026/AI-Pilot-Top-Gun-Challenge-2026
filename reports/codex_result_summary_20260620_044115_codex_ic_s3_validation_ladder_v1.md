# Codex Result Summary: codex_ic_s3_validation_ladder_v1

## Classification

Finished. The ladder completed all four Codex-owned validation cases and wrote:

- `AIP_LIB/DogFightEnv/Release_260529/artifacts/eval/codex_ic_s3_validation_ladder_v1/codex_ladder_manifest.json`
- `AIP_LIB/DogFightEnv/Release_260529/artifacts/eval/codex_ic_s3_validation_ladder_v1/codex_ladder_summary.md`

## Hypothesis

codex-H2: validate `ic_s3_bt_v1` robustness before SAC. Support only if mirrored BT long win rate is at least 0.90, no validation slice loss/crash rate exceeds 0.05, non-mirrored BT remains materially worse or diagnostically different, and autopilot/loiter do not collapse.

## Results

| Case | Win | Loss | Draw | Mean reward | Mean steps | End conditions |
|---|---:|---:|---:|---:|---:|---|
| `codex_ic_s3_bt_nomirror_eval_v1` | 1.00 | 0.00 | 0.00 | -86.2950 | 8157.00 | `target altitude below min`: 30 |
| `codex_ic_s3_bt_mirror_long_eval_v1` | 1.00 | 0.00 | 0.00 | -28.2252 | 1088.00 | `target altitude below min`: 50 |
| `codex_ic_s3_autopilot_eval_v1` | 0.85 | 0.10 | 0.05 | 122.7644 | 672.25 | `target destroyed`: 17, `max time out`: 1, `ownship altitude below min`: 2 |
| `codex_ic_s3_loiter_eval_v1` | 0.30 | 0.10 | 0.60 | 57.6950 | 1988.95 | `target destroyed`: 6, `max time out`: 12, `ownship altitude below min`: 2 |

## Gate Decision

codex-H2 is rejected.

The BT gates are excellent: both BT slices are 100% wins. The non-mirrored BT case is no longer a draw failure under the Codex wrapper, but it is much slower than mirrored BT, so geometry still matters operationally.

The autopilot and loiter gates fail. Both have ownship-altitude losses above the 0.05 ceiling, and loiter collapses into 60% timeout draws. This means `ic_s3_bt_v1` is a strong BT-specialist candidate, but not robust enough to freeze as a broad incumbent or to use as the only comparator for SAC.

## Decision

Do not launch SAC immediately. First run a targeted PPO stabilization branch that addresses the observed loiter/autopilot weakness while preserving the BT candidate as a source bundle.

Next run: `codex_ic_s4_loiter_guard_v1`

- Seed from `artifacts/models/team01/ic_s3_bt_v1`.
- Train against loiter target on the same offensive-saddle geometry.
- Keep custom 26-D observation and custom reward.
- Strengthen altitude shaping to reduce ownship-ground failures.
- Increase close-range pursuit pressure modestly to reduce loiter timeout draws.
- Re-evaluate against BT, autopilot, and loiter after the branch.
