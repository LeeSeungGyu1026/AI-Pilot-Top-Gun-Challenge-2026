# Tailchase Experiment Pipeline

목표는 `run_experiment.py` 기준으로 SAC + `tactical16`을 학습하는 것이다.
상대 기체는 `Rule_Straight.xml` BT로 직진하고, 우리 기체는 뒤에서 추격해 최종적으로 상대 체력을 0으로 만든다.

## 기본 위치

```cmd
cd C:\Users\biobe\desktop\aip\AI-Pilot-Top-Gun-Challenge-2026\AIP_LIB\DogFightEnv\Release_260529
```

항상 conda `aip` 환경의 Python을 직접 지정한다.

```cmd
C:\Users\biobe\miniconda3\envs\aip\python.exe
```

`train_rllib.py`는 기본 SAC config에서 `num_gpus=1`을 사용한다. 실행 전 CUDA 확인은 아래처럼 한다.

```cmd
C:\Users\biobe\miniconda3\envs\aip\python.exe -c "import torch; print(torch.__version__, torch.cuda.is_available(), torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'no cuda')"
```

## Stage Reward Files

이번 라인은 stage별 reward module을 분리한다.

| Stage | Reward module | 목적 |
| --- | --- | --- |
| Stage 1 | `student.my_reward_stage1_survival` | 추락 방지, 고도/속도/자세 안정 |
| Stage 2 | `student.my_reward_stage2_pursuit` | 안정적으로 뒤에서 추격, 거리/각도 유지 |
| Stage 3 | `student.my_reward_stage3_kill` | 추격 상태에서 WEZ 유지, 피해 누적, 상대 체력 0 |

기존 `student.my_reward_table1` 계산식은 그대로 쓰고, stage별 기본 가중치만 wrapper module에서 바꾼다.
새 YAML들은 `env_config.reward` 덮어쓰기를 거의 쓰지 않으므로 reward module 기본값이 실제로 적용된다.

## Stage 1: Survival

```cmd
C:\Users\biobe\miniconda3\envs\aip\python.exe scripts\run_experiment.py --dry-run experiments\tailchase_s1_survival_reward_sac_v1.yaml
C:\Users\biobe\miniconda3\envs\aip\python.exe scripts\run_experiment.py experiments\tailchase_s1_survival_reward_sac_v1.yaml
```

분석:

```cmd
C:\Users\biobe\miniconda3\envs\aip\python.exe scripts\analyze_tailchase_run.py tailchase_s1_survival_reward_sac_v1 --report artifacts\reports\team01\tailchase_s1_survival_reward_sac_v1\analysis.md
```

통과 기준:

- 최근 구간 `crash_rate <= 0.05`
- 고도 패널티가 낮고, `ownship altitude below min` 종료가 거의 없어야 함
- 추격 성능은 아직 필수 아님

## Stage 2: Pursuit

Stage 1 결과를 이어받는다.

```cmd
C:\Users\biobe\miniconda3\envs\aip\python.exe scripts\run_experiment.py --dry-run experiments\tailchase_s2_pursuit_reward_sac_v1.yaml
C:\Users\biobe\miniconda3\envs\aip\python.exe scripts\run_experiment.py experiments\tailchase_s2_pursuit_reward_sac_v1.yaml
```

분석:

```cmd
C:\Users\biobe\miniconda3\envs\aip\python.exe scripts\analyze_tailchase_run.py tailchase_s2_pursuit_reward_sac_v1 --report artifacts\reports\team01\tailchase_s2_pursuit_reward_sac_v1\analysis.md
```

통과 기준:

- Stage 1의 생존 안정성을 유지
- `final_ata_deg` 감소
- `ep_wez_steps` 또는 aim 관련 보상이 꾸준히 증가
- 너무 가까이 붙어서 빙글빙글 도는 패턴이 줄어야 함

## Stage 3: Kill

Stage 2 결과를 이어받는다.

```cmd
C:\Users\biobe\miniconda3\envs\aip\python.exe scripts\run_experiment.py --dry-run experiments\tailchase_s3_kill_reward_sac_v1.yaml
C:\Users\biobe\miniconda3\envs\aip\python.exe scripts\run_experiment.py experiments\tailchase_s3_kill_reward_sac_v1.yaml
```

분석:

```cmd
C:\Users\biobe\miniconda3\envs\aip\python.exe scripts\analyze_tailchase_run.py tailchase_s3_kill_reward_sac_v1 --report artifacts\reports\team01\tailchase_s3_kill_reward_sac_v1\analysis.md
```

통과 기준:

- `target_health`가 실제로 감소
- `target destroyed` 또는 상대 체력 0 승리가 발생
- 고도 붕괴 없이 WEZ 유지 시간이 증가
- 빙글빙글 도는 행동이 줄고 뒤에서 안정적으로 사격 각을 유지

## Replay / Eval

학습 후 quick eval:

```cmd
C:\Users\biobe\miniconda3\envs\aip\python.exe scripts\run_eval.py --bundle artifacts\models\team01\tailchase_s3_kill_reward_sac_v1\bundle_000140 --experiment-yaml experiments\tailchase_s3_kill_reward_sac_v1.yaml --episodes 5 --target-backend bt_env
```

대시보드 리플레이:

```cmd
C:\Users\biobe\miniconda3\envs\aip\python.exe scripts\run_dashboard.py --logdir artifacts\dashboard
```

또는 `artifacts\logs\team01\<tag>\engagement_replays`가 있는 경우 해당 로그 폴더를 대시보드에서 선택한다.

## 조정 원칙

Stage 1 실패:

- 추락하면 `my_reward_stage1_survival.py`의 altitude/safety 계열을 더 강하게 한다.
- 너무 둔하면 `action_abs_limit`을 조금 넓히되 pitch/roll부터 조심스럽게 조정한다.

Stage 2 실패:

- 뒤를 못 잡으면 `track_angle_scale`, `relative_position_scale`, `official_wez_aim_half_angle_deg`를 조정한다.
- 너무 가까워져 회전하면 `too_close_scale`을 올리고 `own_speed_mps` 또는 `range_assist.target_m`을 늘린다.

Stage 3 실패:

- WEZ 안에 있는데 체력을 못 깎으면 `damage_scale`, `wez_hold_bonus`, `official_wez_aim_scale`, `precision_aim_scale`을 올린다.
- 공격하다 추락하면 Stage 2로 돌아가거나 Stage 3의 safety/altitude 계열을 올린다.
