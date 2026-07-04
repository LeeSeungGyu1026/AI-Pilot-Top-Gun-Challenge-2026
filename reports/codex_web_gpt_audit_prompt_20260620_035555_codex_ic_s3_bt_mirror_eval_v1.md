# Codex RL Experiment Audit

Please use high or maximum reasoning. Search the web for relevant papers and reliable technical references, then critique the result and recommend the next experiment.

## Project Context

This is a close-range 1v1 aircraft dogfight reinforcement-learning project. The policy controls a fighter with a continuous 4-D action vector. The environment uses custom observations, custom reward shaping, curriculum-style initial conditions, and evaluation against a behavior-tree opponent. The current candidate is a PPO MLP policy.

Important concern: a policy can appear strong in training but fail under mismatched evaluation geometry, so please distinguish algorithm limitations from evaluation-distribution mistakes.

The user specifically wants insight on whether SAC is worth trying instead of staying only with PPO.

## Hypothesis

codex-H1: `ic_s3_bt_v1` is stronger than a previous non-mirrored BT eval suggested, and the previous 0% win / 100% draw result was caused by evaluation geometry mismatch. If evaluated against the BT target while merging the training geometry from `experiments/ic_s3_bt.yaml`, it should reach at least 70% win rate over 30 episodes, with draw rate at or below 20% and loss/crash rate at or below 10%.

## Training Plan

- Source bundle: PPO MLP policy `ic_s3_bt_v1`
- Source stage: behavior-tree opponent, offensive-saddle initial geometry, custom 26-D observation, custom reward, wide WEZ shaping cone, altitude safety shaping, range discipline during training.
- Evaluation command mirrored the training geometry by passing the source experiment YAML into evaluation.
- Episodes: 30

## Results

Mirrored BT eval:

- Win rate: 1.0
- Loss rate: 0.0
- Draw rate: 0.0
- End conditions: `target altitude below min`: 30/30
- Mean reward: -28.08501
- Mean steps: 1088.0

Prior non-mirrored BT eval of the same bundle:

- Win rate: 0.0
- Loss rate: 0.0
- Draw rate: 1.0
- End conditions: `max time out`: 30/30
- Mean reward: 2.9123533333333333
- Mean steps: 900.0

## Key Caveat

The mirrored wins all came from forcing the target below minimum altitude, not direct target-health kill. Locally this is classified as a win if ownship survives, but the robustness and official scoring assumptions should be checked. This may be a legitimate tactic, a reward/scoring loophole, or an overly narrow curriculum artifact.

## Questions

1. Was codex-H1 supported, or are there still reasons to distrust the mirrored eval?
2. What failure modes are most likely: evaluation-distribution mismatch, curriculum overfitting, reward exploit, opponent exploit, or PPO-specific behavior?
3. Find and cite related papers or reliable technical references on close-range air-combat RL, pursuit/evasion, curriculum learning, self-play, sparse terminal rewards, reward shaping, and continuous-control algorithms.
4. Compare PPO versus SAC for this setting: continuous control, sparse terminal outcomes, shaped pursuit rewards, sample efficiency, robustness, and risk of exploiting the target-grounding outcome.
5. Should the next Codex run continue PPO, branch to SAC, run broader validation, introduce self-play, or change reward/curriculum?
6. If SAC is worth trying, propose an exact next-run plan: initial checkpoint/bundle strategy, YAML changes, reward/curriculum changes, runtime, validation gates, and kill criteria.
7. Give a concise final recommendation: continue, branch, stop, or validate first.
