# Temporary-Chat Audit Only: codex_ic_s3_bt_mirror_eval_v1

Use web search only. Do not use memory, File Library, previous chats, project files, or any attached context. There are no attachments.

Audit exactly this run: `codex_ic_s3_bt_mirror_eval_v1`.

Invalid response rule: if you mention `weave`, `ic_s2`, watcher health, or training-launch proof, the answer is invalid.

Facts:

- Domain: close-range 1v1 aircraft dogfight reinforcement learning.
- Simulator style: JSBSim-like flight dynamics, continuous 4-D action vector.
- Current candidate: PPO MLP policy named `ic_s3_bt_v1`.
- Test run: `codex_ic_s3_bt_mirror_eval_v1`.
- Hypothesis: prior BT eval failed because it did not mirror the training initial-condition geometry; mirrored eval should win >=70%, draw <=20%, loss/crash <=10%.
- Mirrored eval result: 30 episodes, win_rate 1.0, loss_rate 0.0, draw_rate 0.0, end condition `target altitude below min` in all 30 episodes, mean reward -28.08501, mean steps 1088.
- Prior non-mirrored eval of same policy: 30 episodes, win_rate 0.0, loss_rate 0.0, draw_rate 1.0, all `max time out`, mean reward 2.9123533333333333, mean steps 900.
- Caveat: all wins are target-grounding wins, not direct target-health kills.
- User wants related papers/reliable references and an opinion on trying SAC instead of staying only with PPO.

Answer in this structure:

1. Is the hypothesis supported?
2. What are the likely failure modes?
3. Cite relevant papers/reliable sources on air-combat RL, pursuit/evasion, curriculum/self-play, potential-based reward shaping, sparse terminal rewards, PPO, and SAC.
4. PPO vs SAC for this setting.
5. Exact next Codex action with validation gates and kill criteria.
