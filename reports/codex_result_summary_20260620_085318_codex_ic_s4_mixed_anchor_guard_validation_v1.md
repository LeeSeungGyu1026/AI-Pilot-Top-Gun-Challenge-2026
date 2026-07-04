# Codex Result Summary: codex_ic_s4_mixed_anchor_guard_validation_v1

Created: 2026-06-20T08:53:18+09:00

## Hypothesis

Hypothesis codex-H5-eval: `codex_ic_s4_mixed_anchor_guard_v1` improves robustness while preserving BT behavior.

Validation gates:

- BT win rate >= 0.90
- autopilot win rate >= 0.90 with loss/crash <= 0.05
- loiter win rate >= 0.50 with draw <= 0.40 and loss/crash <= 0.05

## Results

| Case | Episodes | Win | Loss | Draw | Mean reward | Mean steps | End conditions |
|---|---:|---:|---:|---:|---:|---:|---|
| BT | 30 | 0.9000 | 0.1000 | 0.0000 | -32.5850 | 595.97 | `target altitude below min`: 27, `ownship altitude below min`: 3 |
| Autopilot | 20 | 0.9500 | 0.0000 | 0.0500 | -29.9619 | 150.95 | `target altitude below min`: 19, `max time out`: 1 |
| Loiter | 30 | 0.8333 | 0.0333 | 0.1333 | -29.7421 | 426.63 | `target altitude below min`: 25, `ownship altitude below min`: 1, `max time out`: 4 |

## Gate Decision

H5-eval passes the stated gates:

- BT meets the win gate exactly at 0.90.
- Autopilot exceeds the win gate and has no losses/crashes.
- Loiter exceeds the win gate, draw is below 0.40, and loss/crash is below 0.05.

This should be frozen as a PPO stabilization candidate, not treated as a clean champion. The BT slice is right on the minimum threshold and still has a 10 percent ownship-altitude loss rate, so any future branch should validate BT early and avoid aggressive fine-tuning.

## Artifacts

- Validation output: `AIP_LIB/DogFightEnv/Release_260529/artifacts/eval/codex_ic_s4_mixed_anchor_guard_validation_v1`
- Manifest: `AIP_LIB/DogFightEnv/Release_260529/artifacts/eval/codex_ic_s4_mixed_anchor_guard_validation_v1/codex_ladder_manifest.json`
- Summary: `AIP_LIB/DogFightEnv/Release_260529/artifacts/eval/codex_ic_s4_mixed_anchor_guard_validation_v1/codex_ladder_summary.md`
- Source bundle: `AIP_LIB/DogFightEnv/Release_260529/artifacts/models/team01/codex_ic_s4_mixed_anchor_guard_v1`
- Frozen bundle: `AIP_LIB/DogFightEnv/Release_260529/artifacts/models/team01/codex_freeze_ic_s4_mixed_anchor_guard_v1_20260620_0853`

## Recommendation

Stop the current experiment loop because the agreed validation gates passed and the candidate is frozen. Next work should be a cautious confirmatory eval or a separate robustness branch, not further in-place training on this bundle.
