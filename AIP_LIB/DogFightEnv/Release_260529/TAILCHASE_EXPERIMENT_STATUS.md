# Tail-Chase SAC Experiment Status

Last updated: 2026-07-12

## Goal

- Runner: `scripts/run_experiment.py`
- Algorithm: SAC
- Observation: `tactical16`
- Target: straight BT, `Rule_Straight.xml`
- Start geometry: ownship behind target, both facing the same direction
- Objective: ownship chases the target and destroys it without falling

## Current Best Runtime

Use this policy bundle:

```powershell
artifacts\models\team01\tailchase_s3_b050_stabilize_micro_sac_v1\bundle_000005
```

Use this safety/eval config:

```powershell
experiments\eval_tailchase_s3_b050_late_emergency.yaml
```

Why: with fixed offensive-saddle RNG and `--seed 260529`, 30-episode eval kept the same kill count as the normal config while removing all altitude losses.

| Config | Eval | Win | Loss | Draw | End conditions |
| --- | --- | ---: | ---: | ---: | --- |
| Normal b050 stabilize | `tailchase_s3_b050_stabilize_b005_seed260529_fixedrng_eval30` | 40% | 43% | 17% | target destroyed 12, ownship altitude below min 13, timeout 5 |
| Late emergency | `tailchase_s3_b050_stabilize_b005_late_emergency_seed260529_fixedrng_eval30` | 40% | 0% | 60% | target destroyed 12, timeout 18 |
| Safe finish micro b003 | `tailchase_s3_b050_safe_finish_b003_seed260529_fixedrng_eval30` | 40% | 0% | 60% | same as late emergency baseline |
| Safe finish10 b005 | `tailchase_s3_b050_safe_finish10_b005_seed260529_fixedrng_eval30` | 40% | 0% | 60% | same as late emergency baseline |
| Safe finish10 b010 | `tailchase_s3_b050_safe_finish10_b010_seed260529_fixedrng_eval30` | 0% | 0% | 100% | timeout 30 |
| Late emergency 150s probe | `tailchase_s3_b050_late_emergency_150s_seed260529_probe10` | 20% | 0% | 80% | first 10 episodes only; same wins as 100s baseline first 10 |
| Reacquire b004 | `tailchase_s3_b050_reacquire_b004_seed260529_fixedrng_eval30` | 40% | 0% | 60% | same as late emergency baseline |
| Reacquire b008 | `tailchase_s3_b050_reacquire_b008_seed260529_fixedrng_eval30` | 17% | 0% | 83% | target destroyed 5, timeout 25; lower draw health but lost kills |
| Hard saddle b004 | `tailchase_s3_b050_hard_saddle_b004_seed260529_fixedrng_eval30` | 40% | 0% | 60% | same as late emergency baseline |
| Hard saddle b008 | `tailchase_s3_b050_hard_saddle_b008_seed260529_fixedrng_eval30` | 27% | 0% | 73% | target destroyed 8, timeout 22; lower draw health but lost kills |
| Execute b004 | `tailchase_s3_b050_execute_b004_seed260529_fixedrng_eval30` | 40% | 0% | 60% | same as late emergency baseline |
| Execute b008 | `tailchase_s3_b050_execute_b008_seed260529_fixedrng_eval30` | 0% | 0% | 100% | timeout 30; converted all baseline wins into draws |

Earlier unseeded 20-episode checks were noisier:

- normal b050 stabilize: win 50% / loss 10% / draw 40%
- late emergency: win 40% / loss 0% / draw 60%

The fixed-seed comparison is now the preferred benchmark.

## Key Fixes Made

Reward-function details are summarized in:

```powershell
TAILCHASE_REWARD_FUNCTIONS.md
```

`scripts/run_eval.py`

- Added `--seed`.
- Episode `ep` now calls `env.reset(seed=seed + ep)`.
- Summary JSON records the seed.
- Help text is ASCII-safe for the Windows console.

`DogFightEnvWrapper.py`

- Provider-driven RL eval now uses the same RL action postprocess path as training.
- `reset(seed=...)` now also seeds the offensive-saddle RNG, so eval configs compare the same initial states.
- Added optional `emergency_recovery` postprocess.
- Added optional gated emergency fields:
  - `require_nose_down_deg`
  - `require_descent_mps`
  - `vertical_velocity_index`
  - `vertical_velocity_descent_sign`

`src/dogfight/ai/rl_action_provider.py`

- Added `output_action_space="rl"` support so local eval providers can return raw RL actions and let the env apply training-time postprocess.

`scripts/analyze_eval_results.py`

- Summarizes `artifacts/eval/<name>/episodes.csv`.
- Reports outcome rates, end conditions, draw target-health buckets, and fixed-seed episode transitions between two evals.

## Commands

Run the current safe benchmark:

```powershell
cd C:\Users\biobe\desktop\aip\AI-Pilot-Top-Gun-Challenge-2026\AIP_LIB\DogFightEnv\Release_260529
C:\Users\biobe\miniconda3\envs\aip\python.exe scripts\run_eval.py --episodes 30 --seed 260529 --eval-name tailchase_s3_b050_stabilize_b005_late_emergency_seed260529_fixedrng_eval30 --ownship-backend rl --target-backend bt_env --ownship-bundle-dir artifacts\models\team01\tailchase_s3_b050_stabilize_micro_sac_v1\bundle_000005 --experiment-yaml experiments\eval_tailchase_s3_b050_late_emergency.yaml
```

Run the current safe policy in a local dogfight:

```powershell
cd C:\Users\biobe\desktop\aip\AI-Pilot-Top-Gun-Challenge-2026\AIP_LIB\DogFightEnv\Release_260529
C:\Users\biobe\miniconda3\envs\aip\python.exe run_local_dogfight.py --ownship-backend rl --ownship-bundle-dir artifacts\models\team01\tailchase_s3_b050_stabilize_micro_sac_v1\bundle_000005 --target-backend bt_env --bt-rule-xml "..\..\Rule_Straight.xml" --max-engage-time 100 --episode-step-limit 6000 --save-log
```

Run the latest finish micro experiment:

```powershell
cd C:\Users\biobe\desktop\aip\AI-Pilot-Top-Gun-Challenge-2026\AIP_LIB\DogFightEnv\Release_260529
C:\Users\biobe\miniconda3\envs\aip\python.exe scripts\run_experiment.py experiments\tailchase_s3_b050_tightaim_micro_sac_v1.yaml
```

Compare two evals:

```powershell
cd C:\Users\biobe\desktop\aip\AI-Pilot-Top-Gun-Challenge-2026\AIP_LIB\DogFightEnv\Release_260529
C:\Users\biobe\miniconda3\envs\aip\python.exe scripts\analyze_eval_results.py tailchase_s3_b050_stabilize_b005_late_emergency_seed260529_fixedrng_eval30 tailchase_s3_b050_safe_finish10_b010_seed260529_fixedrng_eval30 --compare
```

Training uses `train_rllib.py`, which initializes Ray with `num_gpus=1`. Eval uses RLlib local mode and may warn that local-mode policies are on CPU; that warning is expected for eval.

## Interpretation

Current stage 3 is now safe enough for the straight-BT target under the fixed stress seed: the late emergency guard converts altitude failures into timeouts without reducing the number of kills on the same starts.

Episode transition check for normal -> late emergency on seed `260529`: `win->win 12`, `loss->draw 13`, `draw->draw 5`.

The remaining problem is draw rate. In the safe 30-episode eval, timeout target health often remains around 0.5-0.7, with a few closer cases around 0.28-0.33. That means the policy is not just barely missing kills; many draw episodes need better re-attack/finish behavior.

2026-07-12 continuation results:

- Good artifacts were copied to `artifacts\keepers\tailchase_20260712`.
- `student.my_reward_stage3_reacquire` and hard-saddle training can reduce target health in draws, but both lose deterministic quick kills by iteration 8.
- `student.my_reward_stage3_execute` was worse: `bundle_000008` changed all 12 baseline wins into draws and raised draw target-health mean to about `0.7647`.
- Runtime probes with the safe best:
  - `runtime_close_probe15`: 6 win / 0 loss / 9 draw, same as first-15 baseline.
  - `runtime_tight_aim_probe15`: 6 win / 0 loss / 9 draw, draw-health mean slightly lower (`0.5859` vs `0.5881`).
  - `runtime_agile_close_probe15`: 5 win / 0 loss / 10 draw, not safe; it nearly killed one target (`health ~= 0.0002`) but lost a baseline quick kill.
- `tailchase_s3_b050_tightaim_micro_sac_v1` with LR `7.5e-7` did not regress in the 15-episode tight-aim probe, but also did not improve over the safe best.

## Next Experiment Direction

The 3-iteration finish micro run did not move deterministic behavior. The 10-iteration stronger finish run collapsed into safe timeout behavior, so do not use `tailchase_s3_b050_safe_finish10_sac_v1/bundle_000010`.

The eval analyzer confirms the collapse: finish10 b010 converted all 12 baseline wins into draws, and draw target-health mean worsened from about 0.56 to about 0.78.

Next candidates:

1. Do not continue any branch past iteration 4 without a fixed-seed eval; iteration 8 repeatedly drifts into timeout behavior.
2. Use failure-episode replay/log analysis before adding more reward terms. The likely failure mode is losing WEZ after the first firing window rather than terminal reward magnitude.
3. If training again, prefer the original `student.my_reward_stage3_kill` reward and tune initial scenario/runtime gradually. Strong terminal, low-health, or reacquire shaping has so far reduced kill count.

Do not replace the current best unless a candidate beats:

- fixed-seed 30 ep: win >= 40%
- fixed-seed 30 ep: loss == 0%
- preferably fewer than 18 draws
