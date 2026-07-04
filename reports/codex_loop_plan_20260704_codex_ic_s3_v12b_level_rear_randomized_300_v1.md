# codex v12b level rear randomized 300 plan

## Hypothesis

Continuing from `codex_ic_s3_v12_level_rear_gunnery_v1/bundle_000080` while mildly widening the rear-saddle geometry will improve target-destroyed rate without losing the gunnery contact that v12 finally produced.

## Changes From v12

- Run tag: `codex_ic_s3_v12b_level_rear_randomized_300_v1`
- Iterations: `80 -> 300`
- Init bundle: `artifacts/models/team01/codex_ic_s3_v12_level_rear_gunnery_v1/bundle_000080`
- Rear spawn range: `550-750m -> 500-850m`
- Rear aspect: `0-8deg -> 0-14deg`
- Target weave: disabled -> weak 6 degree sinusoidal heading weave

## Success Signals

- `win_rate` improves above the late-v12 band of roughly `0.08-0.15`.
- `target destroyed` remains frequent in engagement logs.
- `timeout_rate` falls without a matching rise in unsafe losses.
- Periodic bundles are saved every 10 iterations.

## Monitoring

Use train-monitor on `http://127.0.0.1:7865/` with watch dir `artifacts/watch/codex_v12b_level_rear_randomized_300_v1`.
