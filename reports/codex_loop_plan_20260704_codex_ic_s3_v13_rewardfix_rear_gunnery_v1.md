# codex v13 reward-fix rear-gunnery plan

## Advisor Diagnosis

The v12b collapse is best explained by reward farming. The scaled kill terminal is only about `+11`, while the wide per-step WEZ precision bonus can pay up to `+5` every step. PPO can therefore prefer staying near a kill solution without ending the episode.

## Hypothesis

If the per-step precision farming bonus is removed and kill completion is made more valuable through damage and a bounded fast-kill terminal bonus, then the good v12b `bundle_000110` policy should keep or improve its win rate instead of drifting toward non-kill aim farming.

## v13 Changes

- Seed from `artifacts/models/team01/codex_ic_s3_v12b_level_rear_randomized_300_v1/bundle_000110`.
- Use `student.codex_reward_v13`.
- Remove the wide per-step WEZ precision bonus.
- Add fast-kill terminal bonus: up to `+110 raw`, linearly decayed over `90s`.
- Increase `damage_dealt_scale` from `140` to `350`.
- Increase `pbrs_ata_weight` from `2` to `4`.
- Change draw reward from `-170` to `-100`, keep loss at `-150`.
- Stabilize PPO: `lr 1e-4 -> 5e-5`, `clip 0.12 -> 0.10`.
- Keep v12b geometry fixed for attribution: `500-850m`, `0-14deg`, weak 6deg target weave.

## Success Signals

- Early win rate should recover toward the v12b best region, roughly `0.6+`.
- Reward mean should no longer stay high while win rate collapses.
- Timeout/loss should not dominate after iteration 40.
- Best checkpoint should be selected by rolling win rate, not final iteration.

## Watch Points

- If win rate collapses despite the reward fix, next suspect is PPO instability or insufficient aiming gradient after removing precision bonus.
- If kill rate rises but timeout remains high, consider adding held-out eval and gradually widening aspect to `0-25deg`.
- If loss is dominated by range discipline, inspect end conditions before changing reward again.
