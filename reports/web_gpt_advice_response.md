# Web GPT Advice Response

Session: `01KVGHR4SQHXVCPC2E5QX2M148`

Conversation URL: https://chatgpt.com/c/6a35883b-3364-83ee-a92f-8e2f5d8578e7

Note: The previous guest/low-quality response was discarded. This response was requested after Google login. The visible ChatGPT UI showed the logged-in Plus account, model menu entry `GPT-5.5`, and reasoning setting `높음` (`High`). `agbrowse` still warned that its built-in selector could not verify `--model thinking --effort heavy`, because the current ChatGPT UI uses selectors it does not recognize.

## Final Recommendation

Freeze `ic_s3_bt_v1` immediately as Candidate A. Do not keep training it in-place. Its 100% tail-10 BT win rate is strong evidence that the policy can finish from a favorable offensive saddle, but it is not yet evidence of robust dogfighting. The next highest-leverage task is to measure the boundary of competence, then branch from the frozen checkpoint.

Do not change observation or reward now, except for clear bug fixes, NaN clamps, reset bugs, or submission-wrapper parity fixes. Changing the 26-D observation invalidates the current policy; changing reward now risks optimizing away from a known-working finisher. Spend scarce time on validation, controlled distribution broadening, and packaging.

Submission should be chosen by validation score, not training reward. Current best training reward/win rate can be overfit to offensive start, BT idiosyncrasy, range-discipline shaping, and true-vs-training wrapper mismatch.

## Prioritized 24-48h Plan

### P0 - First 2-4 hours: freeze, package, and run gate tests

1. Archive Candidate A.

- Checkpoint: `ic_s3_bt_v1_best_tail10`.
- Save exact YAML, seed, git diff, observation/reward files, curriculum config, wrapper config, and export artifact.
- Record whether action slew limiter and range-discipline logic are training-only or also present in submission.

2. Submission parity smoke test.

Run the same 30-50 seeds through:

- trainer inference path
- exported submission wrapper
- deterministic action mode
- true 2 degree cone only
- no widened runtime cone

Hard fail:

- action scaling mismatch
- obs ordering mismatch
- missing finite-difference reset
- NaN/inf observation
- throttle convention mismatch
- action smoothing mismatch
- win-rate drop greater than 5 points between trainer and submission path

3. Run the validation matrix below on Candidate A.

- Minimum: 20 episodes per cell.
- Preferred: 50 episodes per high-risk cell.
- Treat draw as bad unless explicitly known to score neutrally.

Decision after P0:

- If Candidate A passes anchor + packaging but fails broad generalization, keep it as fallback submission and branch training.
- If Candidate A fails packaging parity, fix wrapper before all training.
- If Candidate A fails even the anchor validation, roll back to `ic_s2_sep1450_v1` or the best `sep1250/sep1450` checkpoint and re-run BT branch with stricter logging.

### P1 - Parallel training branch A: conservative broadening

Run name: `ic_s4_bt_broad_mild_v1`

Goal: preserve finishing skill while expanding initial conditions.

Initial-condition mix:

| Portion | Distribution |
|---:|---|
| 55% | Current offensive saddle: range 1100-1450 m |
| 20% | Wider range: 900-1800 m, still mostly aft-quarter |
| 15% | Heading/aspect offsets: +/-15 to +/-45 deg from saddle |
| 5% | Altitude offsets: target +/-300 m |
| 5% | Speed offsets: agent +/-40-70 m/s relative |

Rules:

- True 2 degree WEZ only.
- No widened runtime cone.
- Keep same observation and reward.
- Keep range discipline, but log how often it activates.
- Keep action slew behavior identical to final wrapper if it will be used in submission.

Stop/keep criteria every 10 iterations:

- Keep training if broad validation improves by at least 10 win-rate points while anchor win remains at least 0.90.
- Stop and checkpoint if broad validation improves and then plateaus for 2 evals.
- Kill branch if anchor BT saddle win is below 0.85 for two evals, crash is above 0.03, or mean time-to-first-WEZ worsens by more than 40% versus Candidate A.

### P2 - Parallel training branch B: target/mode robustness

Run name: `ic_s4_target_mix_v1`

Initial-condition mix:

| Portion | Target behavior |
|---:|---|
| 50% | Organizer BT |
| 20% | Gentle weave |
| 15% | Level target |
| 10% | Diving/climbing BT scenarios |
| 5% | Previous simple/easy target for anti-forgetting |

Geometry:

- Range 1100-1700 m.
- Mostly offensive, but with +/-30 deg aspect/heading noise.
- Altitude offset +/-300 m.
- Speed offset +/-50 m/s.

Stop/keep criteria:

- Keep only if it preserves Candidate A anchor performance while improving target-mode matrix.
- Kill if it learns to chase diving BT into low altitude or if loss/crash rises before win-rate improves.

### P3 - Final 6-12 hours: select model and package

Model-selection score:

```text
S = 100W - 150C - 70L - 30D - 0.02T_WEZ - 20F
```

Where:

- `W` = validation win rate
- `C` = crash rate
- `L` = loss rate
- `D` = draw/stall rate
- `T_WEZ` = median time-to-first-WEZ in seconds
- `F` = FDM blowup / NaN / invalid action rate

Weighted validation cells:

| Category | Weight |
|---|---:|
| Submission parity + true 2 degree cone | hard gate |
| Current BT saddle anchor | 20% |
| Range 900-1800 m | 20% |
| Aspect/heading offsets | 20% |
| Altitude/speed offsets | 15% |
| Target behavior mix | 15% |
| Cold/neutral starts | 10% |

Hard gates for final submission:

- Submission wrapper parity: pass.
- True 2 degree cone only: pass.
- No NaN/inf observation/action: pass.
- Crash rate <= 0.02 on full validation.
- Anchor BT saddle win >= 0.90.
- No single critical cell with crash > 0.05.
- If broad branches fail, submit frozen Candidate A rather than a regressed "more general" model.

## Validation Matrix

| ID | Test | Episodes | Pass rule | Diagnoses |
|---|---:|---:|---|---|
| V0 | Trainer-vs-submission parity on same seeds | 30-50 | Same outcomes within 5 win-rate points; no obs/action mismatch | Export/wrapper bugs |
| V1 | Current anchor: BT, range 1100-1450 m, offensive saddle | 100 | Win >= 0.95 preferred; >= 0.90 acceptable; crash 0-1% | Whether 100% tail-10 was real |
| V2 | True 2 degree cone only, no widened runtime cone | 100 | No performance collapse versus V1 | Hidden dependence on widened WEZ |
| V3 | Range sweep: 900, 1100, 1300, 1450, 1600, 1800 m | 25-50 each | >=0.85 through 1450 m; >=0.60 at 1600-1800 m; crash <0.02 | Range overfit / draw loitering |
| V4 | Aspect offsets: +/-15, +/-30, +/-60 deg from saddle | 25-50 each | Avg win >=0.75; draw <0.20 | Overfit to directly-behind geometry |
| V5 | Heading/crossing offsets: target not perfectly aligned | 25-50 each | No orbiting; time-to-WEZ not >2x anchor | Reacquisition and lead pursuit |
| V6 | Altitude offsets: target -300, -150, 0, +150, +300 m | 25 each | Crash <0.02; no ground chase | Dive-following and vertical safety |
| V7 | Speed offsets: agent -70, -40, 0, +40, +70 m/s | 25 each | No overshoot loop; draw <0.20 | Energy-state robustness |
| V8 | Target modes: level, weave, BT, diving BT, climbing BT | 50 each | Avg win >=0.70; crash <0.03 | BT-specific exploit vs real control |
| V9 | BT scenario index/random seed sweep | 100 total | Worst-quartile win >=0.60 | Scenario-index overfit |
| V10 | Cold/neutral starts: co-altitude, 900-1800 m, not behind | 100 | Crash <0.03; first-WEZ rate >=0.30; win >=0.25 is useful | Whether it can dogfight outside curriculum |
| V11 | Low-altitude stress: start near safety floor + descending target | 50 | No ground chase; recovery within 5-10 s | Fatal dive-following |
| V12 | Long episode stall test | 50 | Draw/stall <0.15; range does not grow beyond safe draw band | Range-discipline reward exploit |

Interpretation:

- Passes V1-V9 but fails V10: submit only if competition starts are reliably offensive/saddle-like; otherwise broaden.
- Passes V1 but fails V3/V4: policy is a finisher, not a dogfighter; branch mild broadening.
- Fails V6/V11: do not submit without safety wrapper or retraining; ground chase is tournament-fatal.
- Fails V0: stop training and fix packaging first.

## Risk Notes

1. Biggest current risk: offensive-start overfit.

`ic_s3_bt_v1` proves finishing from a favorable aft-quarter setup. It does not prove neutral merge competence. The validation priority is therefore range/aspect/altitude perturbation, not more BT wins.

2. Second biggest risk: policy regression from broadening too fast.

Do not jump directly from saddle BT to full cold-start randomization. Use mixture training. Keep at least 50% of the current distribution in early broadening so PPO does not forget the finisher.

3. Range-discipline may be a crutch.

Range discipline solved safe-draw extension, but it may encode a training-specific behavior. Log activations. If activations are frequent during validation, the policy may be relying on the wrapper rather than learning pursuit. If final submission cannot include identical logic, retrain/evaluate without it immediately.

4. Action-slew mismatch is dangerous.

The policy learned under an action slew limiter. If the final submission sends raw unsmoothed actions, the aircraft may oscillate, overshoot, or crash. Either reproduce the same limiter in the submission wrapper or validate that removing it does not hurt.

5. BT exploitation is plausible.

A 1.000 BT win from one offensive distribution may mean the policy found a deterministic BT weakness. Target-mode mix and BT scenario-index sweeps are mandatory before trusting it.

6. Hybrid wrapper: use only as a safety guard, not normal blending.

A full BT/RL blend is likely to harm the learned policy near WEZ because RL has learned a specific pursuit/finishing manifold. The safest wrapper is hysteretic emergency override, not continuous arbitration.

Safe trigger candidates:

| Trigger | Override | Exit condition |
|---|---|---|
| Altitude <700 m and vertical speed <-25 m/s | wings-level climb, full throttle, limit pitch-down/rudder | altitude >900 m and vertical speed >=0 |
| Altitude <500 m regardless of state | hard recovery override | altitude >900 m |
| NaN/inf obs or invalid action | provided BT or conservative level-flight action | valid obs for 1-2 s |
| Bank >100 deg or pitch <-45 deg near ground | stabilize/climb override | bank <60 deg, pitch >-20 deg |
| Range >2200-2500 m and target outside forward hemisphere for >10-15 s | optional BT reacquire for 3-5 s | target back within forward hemisphere or range decreasing |

Do not override when:

- in true WEZ
- range <1000 m and target is forward
- lead-angle error is improving
- the policy is already closing

Only keep the hybrid wrapper if it improves V6/V10/V11 without reducing V1-V4. Otherwise submit pure RL plus minimal action/NaN/safety clamps.

7. Reward/observation changes.

Avoid:

- new observation dimensions
- new lead-angle definitions
- new reward weights
- new terminal bonuses
- new WEZ shaping
- removing PBRS/range-discipline before validating

Allowed:

- finite-difference state reset bug fix
- NaN/inf clipping
- true 2 degree WEZ consistency check
- action scaling/smoothing parity
- deterministic inference setting
- logging-only additions

8. Final submission choice.

Submit in this order of preference:

1. Best broad-validated branch if it passes hard gates and beats Candidate A on weighted validation without anchor regression.
2. Frozen `ic_s3_bt_v1` Candidate A if broad branches regress or validation shows competition starts are likely saddle/offensive.
3. Earlier `ic_s2_sep1450_v1` / `sep1250` champion only if BT branch fails packaging, ground safety, or true-cone validation.

Do not chase a higher training win rate in the final hours. Preserve the known finisher, expose its failure envelope, and submit the checkpoint with the best worst-case validation score.
