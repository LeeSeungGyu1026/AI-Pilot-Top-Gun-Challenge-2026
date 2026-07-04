# Codex Result Summary: codex_ic_s4_loiter_guard_validation_v1

## Classification

Finished. The validation ladder completed all three Codex-owned cases and wrote:

- `AIP_LIB/DogFightEnv/Release_260529/artifacts/eval/codex_ic_s4_loiter_guard_validation_v1/codex_ladder_manifest.json`
- `AIP_LIB/DogFightEnv/Release_260529/artifacts/eval/codex_ic_s4_loiter_guard_validation_v1/codex_ladder_summary.md`

## Hypothesis

codex-H3-eval: the `codex_ic_s4_loiter_guard_v1` PPO fine-tune improved loiter/autopilot robustness versus `ic_s3_bt_v1` while preserving BT performance.

Support gates:

- BT win rate >= 0.90.
- Autopilot win rate >= 0.90 and loss/crash rate <= 0.05.
- Loiter win rate >= 0.60, draw rate <= 0.30, and loss/crash rate <= 0.05.

## Results

| Case | Win | Loss | Draw | Mean reward | Mean steps | End conditions |
|---|---:|---:|---:|---:|---:|---|
| `codex_ic_s4_loiter_guard_bt_eval_v1` | 0.00 | 1.00 | 0.00 | -28.5154 | 611.43 | `ownship altitude below min`: 30 |
| `codex_ic_s4_loiter_guard_autopilot_eval_v1` | 0.00 | 1.00 | 0.00 | -37.9162 | 2443.45 | `ownship altitude below min`: 20 |
| `codex_ic_s4_loiter_guard_loiter_eval_v1` | 0.00 | 0.00 | 1.00 | 44.7560 | 3000.00 | `max time out`: 30 |

## Gate Decision

codex-H3-eval is rejected.

The loiter-guard fine-tune catastrophically destroyed BT and autopilot performance: both became 100% ownship-altitude losses. It also failed the loiter goal: 100% timeout draws. This branch should not be frozen, used as an incumbent, or used as a SAC baseline.

## Diagnosis

The fine-tune likely overfit to a loiter-specific behavior that avoids finishing while still failing altitude/energy management when target behavior changes. Training logs showed late improvement, but the external validation ladder exposed complete policy collapse. This is exactly why the loop required validation before promotion.

## Decision

Discard `codex_ic_s4_loiter_guard_v1` as a failed branch. Return to the last good source bundle, `artifacts/models/team01/ic_s3_bt_v1`, and launch a SAC smoke branch from scratch rather than weight-initializing from the PPO bundle.

The SAC branch is a hypothesis test, not a replacement incumbent:

- Train SAC on a mixed BT/loiter target distribution from the repo's existing mixed-initial pattern.
- Keep custom 26-D observation and custom reward.
- Use conservative runtime and validation gates.
- Compare against `ic_s3_bt_v1`, not against the failed loiter-guard branch.
