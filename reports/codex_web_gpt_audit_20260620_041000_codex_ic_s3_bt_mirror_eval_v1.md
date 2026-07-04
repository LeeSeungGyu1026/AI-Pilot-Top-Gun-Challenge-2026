# Codex Audit: codex_ic_s3_bt_mirror_eval_v1

## Provider Audit Status

Three fresh ChatGPT/Web GPT attempts were made through `agbrowse`:

- `reports/codex_web_gpt_audit_prompt_20260620_035555_codex_ic_s3_bt_mirror_eval_v1.md`
- `reports/codex_web_gpt_audit_prompt_retry_20260620_040000_codex_ic_s3_bt_mirror_eval_v1.md`
- `reports/codex_web_gpt_audit_prompt_retry2_20260620_040500_codex_ic_s3_bt_mirror_eval_v1.md`

The first two responses discussed unrelated `weave_v2`/watcher scenarios despite explicit exclusion. The third temporary-chat attempt refused to use the supplied facts. I am discarding those responses as contaminated/low-quality and using a source-backed local audit instead of treating them as valid external advice.

## Verdict

codex-H1 is supported. The prior BT eval was not comparable to training geometry:

- Previous non-mirrored BT eval: 30/30 draws, all `max time out`, win rate 0.0.
- Codex mirrored BT eval: 30/30 wins, all `target altitude below min`, win rate 1.0.

That is too large a delta to interpret as algorithmic change; it is an evaluation-distribution mismatch. `ic_s3_bt_v1` should be kept as a promising PPO candidate on its trained geometry.

## Main Caveat

All wins are target-grounding wins, not direct target-health kills. This may be valid under the local competition-aligned classifier, but it can also be:

- a scoring assumption mismatch if the final server treats target-grounding differently,
- a narrow curriculum artifact,
- an opponent-specific exploit,
- a reward-shaping exploit where the policy forces a terminal outcome without robust gunnery.

The next run should validate this before more training.

## Literature And Technical Notes

- PPO is on-policy and works with continuous actions, but it updates from freshly sampled trajectories and can settle into local optima or curriculum-specific tactics. OpenAI Spinning Up describes PPO as an on-policy method and explains PPO-Clip's conservative update; Ray RLlib also lists PPO as supporting continuous action spaces and multi-agent setups.
- SAC is a strong candidate for a branch because it is off-policy, entropy-regularized, and continuous-control focused. Spinning Up describes SAC as off-policy with entropy regularization; the SAC papers emphasize better sample efficiency and robustness across seeds in continuous-control tasks.
- Lockheed Martin's AlphaDogfight-related paper used hierarchical maximum-entropy RL plus reward shaping, which makes a SAC-style branch especially relevant for this project.
- Air-combat curriculum papers support the current staged initial-condition approach, especially for sparse rewards and maneuver decision learning.
- Self-play air-combat work supports eventually mixing frozen RL opponents to reduce behavior-tree overfit.
- Potential-based reward shaping is theoretically attractive, but only if implemented as true potential deltas; arbitrary WEZ/pursuit terms can change the objective and create exploits.

Useful references:

- PPO: https://arxiv.org/abs/1707.06347
- SAC original: https://arxiv.org/abs/1801.01290
- SAC algorithms/applications: https://arxiv.org/abs/1812.05905
- OpenAI Spinning Up PPO: https://spinningup.openai.com/en/latest/algorithms/ppo.html
- OpenAI Spinning Up SAC: https://spinningup.openai.com/en/latest/algorithms/sac.html
- Ray RLlib algorithms: https://docs.ray.io/en/latest/rllib/rllib-algorithms.html
- Hierarchical RL for air-to-air combat / AlphaDogfight: https://arxiv.org/abs/2105.00990
- Curriculum RL with sparse rewards for air combat: https://arxiv.org/abs/2302.05838
- Automatic curriculum RL for maneuver decision-making: https://arxiv.org/abs/2307.06152
- Self-play and state stacking for noisy air combat: https://arxiv.org/abs/2303.03068
- BVR Gym / JSBSim air combat environment: https://arxiv.org/abs/2403.17533
- Air combat behavior modeling survey: https://arxiv.org/abs/2404.13954
- Potential-based shaping follow-up discussion: https://arxiv.org/abs/2208.09570

## PPO Versus SAC For This Project

PPO is already proven operational in the repo and produced a candidate that wins on mirrored BT geometry. Keep it as the incumbent.

SAC is worth trying, but not as an immediate replacement. Its off-policy replay and entropy objective could help sample efficiency and avoid premature deterministic pursuit behaviors. The risk is that SAC may exploit shaped rewards even more aggressively unless the evaluation gates are external to the training reward.

The right order is:

1. Run a Codex validation ladder for `ic_s3_bt_v1`.
2. If target-grounding wins hold and official scoring assumption is acceptable, freeze `ic_s3_bt_v1` as a PPO incumbent.
3. Launch a SAC smoke/branch from scratch or from a SAC-compatible easier-stage checkpoint. Do not initialize SAC from the PPO bundle unless weight compatibility is proven.

## Next Run Recommendation

Launch `codex_ic_s3_validation_ladder_v1`, not SAC yet.

Validation ladder:

- Repeat non-mirrored BT eval under a Codex name to confirm mismatch.
- Run longer mirrored BT eval to check stability.
- Run autopilot/loiter evals from the same bundle to verify the policy did not only learn one BT exploit.
- Summarize outcomes in one Codex-named manifest.

Gates:

- Mirrored BT win rate >= 0.90 over the longer eval.
- Non-mirrored BT remains materially different, confirming geometry sensitivity.
- No ownship crash/loss rate above 0.05 in any validation slice.
- If all wins remain target-grounding, mark as promising but scoring-sensitive and ask/verify official scoring before final promotion.

If the validation ladder passes, launch a SAC smoke run:

- Copy `experiments/ic_s3_bt.yaml` to `experiments/codex_ic_s3_sac_smoke_v1.yaml`.
- Set `algo.name: sac`.
- Use SAC MLP relu `[256, 256]`, `lr: 3.0e-4`, `gamma: 0.997`, `tau: 0.005`, `target_entropy: auto`, `train_batch_size: 256`, replay capacity at least 50000.
- Remove PPO `init_bundle`; train SAC from scratch or from a SAC-compatible checkpoint only.
- Use 30-50 iterations first.
- Kill if replay buffer/logs fail, NaNs appear, crash/loss exceeds 0.5 after warmup, or no terminal improvement is visible by the first saved bundle.
