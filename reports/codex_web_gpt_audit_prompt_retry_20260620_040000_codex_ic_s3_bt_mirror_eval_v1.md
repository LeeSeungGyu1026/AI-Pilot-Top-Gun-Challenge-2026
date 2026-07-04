# Codex RL Experiment Audit Retry

Use high or maximum reasoning and web search. This is a fresh audit request for exactly one run:

`codex_ic_s3_bt_mirror_eval_v1`

Do not discuss `ic_s2_weave_v2`, `weave_v1`, `weave_v2`, watcher fixes, training-launch proof, or any unrelated previous experiment. If those names appear in your answer, the response is invalid.

## Task

Search for relevant papers and reliable technical references, then critique the result and recommend the next experiment. The user specifically wants insight on whether SAC is worth trying instead of staying only with PPO.

## Project Context

This is a close-range 1v1 aircraft dogfight reinforcement-learning project. The policy controls a fighter with a continuous 4-D action vector. The environment uses custom observations, custom reward shaping, curriculum-style initial conditions, and evaluation against a behavior-tree opponent. The current candidate is a PPO MLP policy.

Important concern: a policy can appear strong in training but fail under mismatched evaluation geometry, so distinguish algorithm limitations from evaluation-distribution mistakes.

## Hypothesis

codex-H1: `ic_s3_bt_v1` is stronger than a previous non-mirrored BT eval suggested, and the previous 0% win / 100% draw result was caused by evaluation geometry mismatch. If evaluated against the BT target while merging the training geometry from `experiments/ic_s3_bt.yaml`, it should reach at least 70% win rate over 30 episodes, with draw rate at or below 20% and loss/crash rate at or below 10%.

## Results For This Run Only

Mirrored BT eval for `codex_ic_s3_bt_mirror_eval_v1`:

- Episodes: 30
- Win rate: 1.0
- Loss rate: 0.0
- Draw rate: 0.0
- End conditions: `target altitude below min`: 30/30
- Mean reward: -28.08501
- Mean steps: 1088.0

Prior non-mirrored BT eval of the same bundle:

- Episodes: 30
- Win rate: 0.0
- Loss rate: 0.0
- Draw rate: 1.0
- End conditions: `max time out`: 30/30
- Mean reward: 2.9123533333333333
- Mean steps: 900.0

## Caveat

The mirrored wins all came from forcing the target below minimum altitude, not direct target-health kill. Locally this is classified as a win if ownship survives. This may be a valid tactic, a scoring loophole, an opponent exploit, or a narrow-curriculum artifact.

## Required Output

1. State whether codex-H1 is supported.
2. Explain the most likely failure modes and what should be validated next.
3. Cite relevant papers or reliable sources on air-combat RL, pursuit/evasion, curriculum/self-play, potential-based reward shaping, sparse terminal rewards, and continuous-control algorithms.
4. Compare PPO vs SAC for this exact setting.
5. Recommend the next Codex action: broader validation, PPO continuation, SAC branch, self-play branch, reward/curriculum change, or stop.
6. If SAC is recommended, provide a concrete next-run YAML plan: seed strategy, algorithm settings, reward/curriculum changes, runtime, validation gates, and kill criteria.
7. Keep the answer concise and specific to `codex_ic_s3_bt_mirror_eval_v1`.
