# Codex RL Literature Index - 2026-06-20

Purpose: local reference pack for future Codex-authored training configs in the AI Pilot Top Gun dogfight project. Selection favors highly cited RL foundations, then directly relevant air-combat / pursuit-evasion papers even when citation counts are lower.

Citation counts are approximate OpenAlex `cited_by_count` values checked on 2026-06-20 where the title matched cleanly. PPO is included as a core method even though OpenAlex title search returned inconsistent metadata for that record.

## Local PDFs

| File | Topic | Approx. citations | Why it matters for next configs |
| --- | --- | ---: | --- |
| `codex_ppo_schulman_2017.pdf` | PPO | check manually | Current baseline family; use as stability reference, not as default answer to every failure. |
| `codex_gae_schulman_2015.pdf` | GAE / continuous control | 1750 | Advantage estimation and variance control for PPO-style fine-tunes. |
| `codex_sac_haarnoja_2018_icml.pdf` | SAC maximum entropy | 3499 | Main candidate for off-policy continuous 4-D control and better sample reuse. |
| `codex_sac_algorithms_applications_haarnoja_2018.pdf` | SAC automatic temperature / applications | 1954 | Practical SAC defaults, entropy tuning, seed stability expectations. |
| `codex_td3_fujimoto_2018.pdf` | TD3 | 2369 | Twin critics / delayed policy updates; useful if SAC critic instability appears. |
| `codex_ddpg_lillicrap_2015.pdf` | DDPG continuous control | 6787 | Baseline off-policy actor-critic reference; mostly historical, but useful for action-noise pitfalls. |
| `codex_maddpg_lowe_2017.pdf` | Multi-agent actor-critic | 1015 | Relevant for opponent modeling, nonstationarity, and self-play variants. |
| `codex_her_andrychowicz_2017.pdf` | Sparse reward / hindsight replay | 352 | Useful when terminal win/loss rewards dominate and shaping damages behavior. |
| `codex_reward_shaping_ng_1999.pdf` | Potential-based reward shaping | 1634 | Guardrail for altitude penalties: avoid non-potential shaping that changes the intended optimum. |
| `codex_curriculum_rl_survey_narvekar_2020.pdf` | RL curriculum survey | 228 | Framework for staged BT -> autopilot -> loiter -> mixed validation schedules. |
| `codex_air_combat_hsac_zhu_2021.pdf` | Air combat HSAC / sparse reward / self-play | 0 in OpenAlex | Directly relevant SAC-style air-combat reference; prioritize design ideas over citation count. |
| `codex_air_combat_self_play_stacking_tasbas_2023.pdf` | Noisy air combat self-play / state stacking | 3 | Directly relevant to robustness, observation noise, and frozen-opponent self-play. |
| `codex_air_combat_hierarchical_6dof_chai_2022.pdf` | 6-DOF UCAV hierarchical PPO / fictitious self-play | 74 | Directly relevant to separating macro policy from low-level flight control. |
| `codex_dota2_openai_five_2019.pdf` | Large-scale self-play | 1046 | Reference for long-horizon, imperfect-information, continuous action/state self-play systems. |
| `codex_multi_agent_autocurricula_baker_2019.pdf` | Multi-agent autocurricula | 337 | Reference for opponent pressure schedules that expose weaknesses without immediate collapse. |

## Training-Setup Rule

Before Codex writes the next training YAML, it should consult this pack and cite at least the relevant subset in the new `codex` plan artifact:

1. For SAC branches, cite both SAC PDFs, TD3, DDPG, and the air-combat HSAC paper.
2. For altitude-loss fixes, cite reward shaping, curriculum RL, and the air-combat hierarchical/self-play papers before changing penalties.
3. For validation robustness or opponent scheduling, cite MADDPG, OpenAI Five, autocurricula, and the air-combat self-play papers.
4. Avoid another pure harsh-penalty PPO polish unless the plan explains why the Ng et al. shaping warning does not apply.

## Immediate Design Implications

The failed zero-altitude PPO polish suggests that simply increasing terminal altitude penalties can erase useful pursuit behavior instead of teaching recovery. The next serious branch should be either:

- a small diagnostic validation sweep from the frozen H5 candidate to isolate altitude-loss starting states and trajectories, or
- a SAC/HSAC-inspired branch with replay, entropy, and staged sparse-to-shaped reward homotopy rather than another PPO penalty-only fine-tune.

For the user's hard requirement, validation gates should count end-condition strings directly: zero `ownship altitude below min` and zero `FDM Update Fail` across every BT/autopilot/loiter case before freezing.

## Source URLs

- PPO: https://arxiv.org/abs/1707.06347
- GAE: https://arxiv.org/abs/1506.02438
- SAC ICML: https://arxiv.org/abs/1801.01290
- SAC algorithms/applications: https://arxiv.org/abs/1812.05905
- TD3: https://arxiv.org/abs/1802.09477
- DDPG: https://arxiv.org/abs/1509.02971
- MADDPG: https://arxiv.org/abs/1706.02275
- HER: https://arxiv.org/abs/1707.01495
- Reward shaping: https://www.andrewng.org/publications/policy-invariance-under-reward-transformations-theory-and-application-to-reward-shaping/
- Curriculum RL survey: https://arxiv.org/abs/2003.04960
- Air combat HSAC: https://arxiv.org/abs/2112.01328
- Air combat self-play/state stacking: https://arxiv.org/abs/2303.03068
- Hierarchical 6-DOF air combat: https://arxiv.org/abs/2212.03830
- OpenAI Five: https://arxiv.org/abs/1912.06680
- Multi-agent autocurricula: https://arxiv.org/abs/1909.07528
