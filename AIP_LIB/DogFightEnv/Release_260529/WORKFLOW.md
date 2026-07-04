# DogFightEnv 실험 워크플로 가이드 (Release_260529 작업본)

이 폴더가 **활성 작업 공간**입니다 (`Update\강화학습환경\Latest\Release_260529.zip`에서 추출,
구버전 `AIP_LIB\DogFightEnv\Release\`는 참고용으로 보존). 플랫폼 자체 사용법은 [README.md](README.md)
참조. 이 문서는 환경 설정 + 추가된 실험 자동화 도구만 다룹니다.

## 0. 환경 설정 (1회)

```powershell
powershell -ExecutionPolicy Bypass -File setup_env.ps1        # CUDA GPU 버전 (기본)
powershell -ExecutionPolicy Bypass -File setup_env.ps1 -Cpu   # CPU 전용
```

설치 내용: Miniconda(사용자 영역) → conda env `aip` (Python 3.11) → CUDA PyTorch → `requirements.txt`.

이후 모든 명령은 **이 폴더(Release 루트)에서**, `aip` 환경의 python으로 실행합니다:

```powershell
$py = "$env:LOCALAPPDATA\miniconda3\envs\aip\python.exe"
cd "C:\Users\GYU\Desktop\KAU\AI Pilot Top Gun Challenge 2026\AIP_LIB\DogFightEnv\Release_260529"
```

(또는 Anaconda Prompt에서 `conda activate aip` 후 `python` 사용)

## 1. 단일 학습 실행

```powershell
& $py scripts\run_experiment.py experiments\student_sac_mlp.yaml --dry-run   # 명령 확인
& $py scripts\run_experiment.py experiments\student_sac_mlp.yaml             # 실행
```

새 실험은 `experiments\student_sac_mlp.yaml`을 복사해 팀 파일로 만들고 수정합니다.

## 2. RL 조건 바꾸기 — 전부 YAML에서

| 바꿀 것 | YAML 위치 |
|---|---|
| 알고리즘 (SAC/PPO) | `algo.name` |
| 학습률, gamma, batch 등 | `algo.lr`, `algo.gamma`, `algo.train_batch_size`, … |
| 신경망 구조 (MLP) | `algo.mlp.fcnet_hiddens: [256, 256]` |
| 신경망 구조 (LSTM) | `algo.lstm.*` (SAC는 RLLibLstm 패치 필요), 자유 구조는 `algo.network` |
| 학습 길이 | `runtime.iterations` |
| 보상 가중치 (기본 보상) | `env_config.reward.*` |
| 보상 함수 (직접 설계) | `student\my_reward.py` 작성 후 `env.reward_module: student.my_reward` |
| 관측 설계 | `student\my_observation.py` + `env.observation_mode: custom` + `env.observation_module` |
| 상대 (BT/loiter/autopilot) | `env.target_mode`, `env_config.target_*` |
| 환경 워커 수 | `runtime.num_env_runners` |
| 체크포인트/번들 저장 주기 | `runtime.save_*`, `runtime.*_frequency` |

## 3. 병렬 학습 (추가된 도구: `scripts\run_parallel.py`)

스윕 정의 1개 파일 + 명령 1줄:

```powershell
& $py scripts\run_parallel.py experiments\sweeps\example_sac_sweep.yaml --dry-run
& $py scripts\run_parallel.py experiments\sweeps\example_sac_sweep.yaml
```

스윕 YAML ([예시](experiments/sweeps/example_sac_sweep.yaml)):

```yaml
name: sac_lr_net_sweep
base: experiments/student_sac_mlp.yaml   # 기준 실험
max_parallel: 2                          # 동시 실행 개수 (이 PC는 2-3 권장)
repeats: 1                               # 같은 조건 반복(시드 효과)
overrides:                               # 모든 run 공통 변경
  runtime.iterations: 50
grid:                                    # 조합 전개 (cartesian product)
  algo.lr: [3.0e-4, 1.0e-3]
  algo.mlp.fcnet_hiddens: [[256, 256], [512, 512]]
```

- run마다 `output.tag`가 자동 부여되어 **출력이 절대 겹치지 않습니다**.
- 생성된 정확한 설정: `experiments\generated\<sweep>\<tag>.yaml`
- 각 run 콘솔 로그: `artifacts\sweeps\<sweep>\<tag>.log`
- 진행/결과 현황: `artifacts\sweeps\<sweep>\manifest.json`
- **콘솔은 조용한 게 정상입니다** — run 출력은 로그 파일로 가고, 약 60초마다
  `[progress] <tag>: iter=[..]` 한 줄씩 에코됩니다. 멈춘 것이 아닙니다.
- Ctrl+C로 중단하면 실행 중인 run과 Ray 워커 전체 트리가 종료됩니다(taskkill /T).
  중단 직후 수 분간 Ray 정리 프로세스가 남아 있을 수 있습니다.
- **주의**: 스윕 실행 중 `ray stop --force` 금지 (모든 run의 Ray 세션이 죽음).

## 4. 평가 (추가된 도구: `scripts\run_eval.py`)

학습된 bundle을 BT 상대로 N회 교전시켜 승/패/무 통계 산출:

```powershell
& $py scripts\run_eval.py --ownship-bundle-dir artifacts\models\<team>\<tag> --episodes 20 --eval-name <tag>_vs_bt
```

결과: `artifacts\eval\<eval-name>\summary.json` (승률, 종료사유 분포, 평균 보상) + `episodes.csv`.
custom 관측 정책은 학습 때와 동일하게 `--observation-mode custom --observation-module student.my_observation` 지정.

단일 교전 상세 확인(원본 도구): `run_local_dogfight.py --save-log` → 대시보드 Replay 탭.

## 5. 결과물 위치

```
artifacts/
├── logs/<team>/<tag>/training_log.csv      # 학습 지표 (+ policy_probe, engagement_replays)
├── models/<team>/<tag>/                    # 제출용 bundle (metadata.json + policy_weights.pkl.gz)
├── checkpoints/<team>/<tag>/               # native checkpoint (학습 재개용)
├── dashboard/<team>_<tag>/metrics.jsonl    # 대시보드 데이터
├── sweeps/<sweep>/                         # 병렬 스윕 로그 + manifest
└── eval/<eval-name>/                       # 평가 통계
```

대시보드 (Training 탭 = 학습 지표, Replay 탭 = 3D 교전 궤적) — 권장 명령:

```powershell
& $py tools\dashboard.py --training-logdir artifacts\dashboard --logdir artifacts\logs --port 7860
```
→ http://127.0.0.1:7860

`--logdir`는 **재귀 탐색**하므로 `artifacts\logs`를 주면 모든 run의
`engagement_replays`가 Replay 탭 드롭다운에 한꺼번에 잡힙니다.
README의 예시처럼 `--logdir logs`를 쓰면 안 됩니다 (이 폴더는 존재하지 않음 →
"No Blue/Red CSV log pairs found" + 파란 빈 화면).

Replay가 생기는 조건: 해당 run의 YAML에서 `engagement_log.enabled: true`
(reward_shaping 스윕은 비용 절약을 위해 꺼져 있음 — Training 탭으로 판단).
`run_local_dogfight.py --save-log`로 만든 CSV도 그 폴더를 `--logdir`에 주면 보입니다.

## 5+. 실험 플레이북 (전략 자문 반영, 2026-06-12)

구현된 전략 (자세한 근거는 각 파일 주석):

| 파일 | 내용 |
|---|---|
| `student\my_observation.py` | **tgc26** 26차원 관측: sin/cos 각도(±180° 불연속 제거), log-range, 접근율·상승률·LOS rate(위치 유한차분), 예측 요격점 lead 오차, 비에너지, WEZ 플래그 |
| `student\my_reward.py` | **PBRS**(potential-based, γΦ′−Φ — WEZ 배회로 파밍 불가) + 피해 비대칭(가함 30 ≫ 받음 12) + 고도 램프(900m부터, 회피 여유) + 승 150/패 −150/무 −20 |
| `experiments\team_ppo_mlp.yaml` | 고정 PPO 설정: γ0.997, λ0.95, tanh [256,256], VF 분리, batch 8192, mixed initial geometry. **주 1차엔 이 설정을 잠그고 보상/관측만 변경** |
| `experiments\sweeps\reward_shaping_sweep.yaml` | 주1 진단 스윕: PBRS 가중치 × 피해 비대칭 (30 iter 단기, 패자 빠르게 제거) |
| `student\my_curriculum.py` | 기본 15단계 유지 + stage0 crash 게이트 5%로 강화 + two-circle 구간 shaping 점감(2.0→0.5) + full_dogfight에 mixed geometry 상시 적용 |
| `scripts\run_eval.py` | 평가 사다리: `--target-backend fixed/loiter/autopilot/bt/rl` |

주차별 우선순위 (보상·관측 ≫ 커리큘럼 > 하이퍼파라미터 > 구조):
1. **주1**: PPO 설정 고정, 보상 변형 스윕(단기) + 관측 확정. crash rate가 첫 관문 — 0 근처 전까지 다른 지표 무의미. **관측을 나중에 바꾸면 모든 체크포인트 무효.**
2. **주2**: 최고 보상 1-2개를 커리큘럼 전체 통과시켜 BT 단계까지. 남는 슬롯으로 단일축 하이퍼 점검(γ 또는 lr)만.
3. **주3+**: 최강 라인 강화 + replay에서 드러난 약점 보강(예: 수세 시작 게임 패배 → 해당 geometry 비중↑). 마지막 며칠은 **새 아이디어 금지** — 평가 사다리 win rate로 제출 체크포인트 선정 (학습 reward와 win rate는 수시로 따로 놂).

평가 사다리 (체크포인트마다):

```powershell
& $py scripts\run_eval.py --ownship-bundle-dir <bundle> --episodes 20 --target-backend bt --observation-mode custom --observation-module student.my_observation --eval-name <tag>_vs_bt
& $py scripts\run_eval.py --ownship-bundle-dir <bundle> --episodes 10 --target-backend autopilot --observation-mode custom --observation-module student.my_observation --eval-name <tag>_vs_ap
& $py scripts\run_eval.py --ownship-bundle-dir <bundle> --episodes 10 --target-backend loiter --observation-mode custom --observation-module student.my_observation --eval-name <tag>_vs_loiter
# (이후) 과거 자가 체크포인트 상대: --target-backend rl --target-bundle-dir <old bundle>
```

진단 시그널 (대시보드):
- `ep_reward_pbrs`가 `ep_reward_terminal`보다 커지면 shaping 과다 → 가중치 축소
- `ep_reward_damage_taken`만 줄고 damage_dealt 정체 → 회피 붕괴 → 비대칭 강화
- draw 비율 상승 추세 → 시간 끌기 학습 여부 확인 (`draw_reward` 조정)
- replay가 전부 똑같은 기동이면 조기 수렴(시저스 함정) — 단, **entropy 계수는 YAML로 노출 안 됨**(플랫폼 한계, 필요 시 주최측 문의)

알려진 한계: 보상 함수에 action이 전달되지 않아 action-smoothness 페널티 불가. 학습 중 RL 상대(self-play)는 플랫폼 미지원 — 추후 BT Rule XML 변형 또는 주최측 문의로 해결.

### 자문 2라운드 반영 (2026-06-12 저녁)

1차 스윕 결과: crash rate 전 변형 0% 달성, 그러나 **WEZ 진입 0회** (1.2–1.6 km 배회 + 시간 끌기).
원인: PBRS는 에피소드 합이 ±3으로 유계(telescoping) → 탐색 견인력 부족. 대응:

- `student\my_reward.py`: **dense pursuit** 항 추가 (`pursuit_dense_scale`, 유계 비퍼텐셜 ATA×range,
  커리큘럼이 후반에 0으로 anneal). 컴포넌트명을 플랫폼 텔레메트리 고정 키(pursuit/damage/safety/survival)로
  변경 — 대시보드에서 pursuit↑ + damage 정체 = 파밍 시그널 감시.
- `student\my_observation.py`: `in_wez` 피처를 **항상 진짜 2° 콘 기준**으로 고정 (WEZ 확대 커리큘럼이
  피처 의미를 흔들지 않도록).
- `student\my_curriculum.py`: **WEZ 폭 스케줄** 8°→5°→3°→2° (stage advancement이 metric-gated이므로
  자동으로 숙달 후 좁아짐; 마지막 head-on 3단계 + full_dogfight는 진짜 2° 콘). dense anneal 동시 진행.
  주의: `wez.angle_deg`는 보상이 아니라 **실제 데미지 모델**이며 **양측 대칭** 적용 (BT 총도 넓어짐).
- `experiments\team_curriculum.yaml` + `experiments\sweeps\curriculum_dense_sweep.yaml`:
  dense cap 0.2 vs 0.1 두 arm 비교 (48시간 플랜). **커리큘럼은 YAML env_config를 무시**하므로
  변형은 `curriculum.stages_module`로 구분 (보상 기본값 = MY_REWARD_CONFIG + stage overrides).
- 평가는 항상 진짜 2° 콘: `run_eval.py`는 env 기본 WEZ 사용 → 자동으로 2°.

**커리큘럼 런 모니터링** (플랫폼 제약: `train_curriculum.py`는 대시보드 metrics.jsonl을 쓰지 않음 →
Training 탭에 안 보임. 다음으로 확인):

```powershell
# 실시간 진행 (run_parallel 콘솔 heartbeat 또는 arm별 로그)
Get-Content artifacts\sweeps\curr_dense\<tag>.log -Wait -Tail 3
# 단계/지표 이력
Import-Csv artifacts\curriculum\team01\<tag>\training_log.csv | Select-Object -Last 5
# 교전 궤적 (Replay 탭): 커리큘럼 replay는 artifacts\curriculum 아래에 저장됨
& $py tools\dashboard.py --default-tab replay --logdir artifacts\curriculum --training-logdir artifacts\dashboard --port 7860
```

**플랫폼 버그 수정 (2026-06-12, train_curriculum.py `_extract_custom_metrics`)**: Ray 2.54 new API는
custom metric을 bare 이름(`crash` 등)으로 보고하는데 원본 코드는 `crash_mean`만 찾아서 **모든 stage
advancement 지표가 영구 n/a** → 게이트가 절대 발동하지 않고 stage마다 max_iterations를 전부 소모.
train_rllib와 동일한 fallback 조회로 수정 (주석에 BUGFIX 표기). 주최측 보고 가치 있음.

**승패 채점 정렬 (2026-06-13, 중요)**: 대회 규정상 **상대를 지면으로 몰아넣으면 승리**다.
그러나 플랫폼의 `_classify_outcome`는 `end_condition == "target altitude below min"`을
**무승부(-150)**로 채점한다 → 에이전트의 최선 행동(상대를 격추→추락)이 -150으로 처벌받음.
수정(학생 코드만, 플랫폼 미수정):
- `student/my_reward.py`: 지면 격추(`target altitude below min` + 아군 생존) → `win_reward(+150)`.
- `scripts/run_eval.py` `classify()`: 동일 규정 반영(지면 격추=win, 아군 추락=loss).
- **주의**: 학습 로그의 `win_rate`(플랫폼 `_classify_outcome` 기반)는 여전히 지면 격추를 무승부로
  세므로 **과소 집계**된다. 진행/게이팅 판단은 `run_eval.py`(보정된) win-rate + `ep_reward_mean`
  + `ep_reward_damage`로 한다. 학습 로그 win_rate를 회귀로 오해하지 말 것.

**IC 커리큘럼 (초기조건 단계, 자문 2026-06-13)**: saddle(근접 후방) → 분리거리 확대 →
aspect 확대 → 표적 속도↑ → 기동 표적 → 중립 헤드온 → 대회 초기조건(BT, ~1400m). 콘은 5°로
넓게 유지하다가 **마지막에만** 2°로 좁힌다. 각 단계는 `runtime.init_bundle`로 이전 단계 정책을
시드하고, `run_eval`(보정) win-rate가 ~0.7+면 다음 단계로. saddle 스폰은 `DogFightEnvWrapper`의
`offensive_saddle`(env_config) — `range_m`/`aspect_deg` 밴드를 단계별로 넓힌다.
S2: `experiments/ic_s2_widen.yaml` (600-1200m, 0-30° aspect, autopilot 표적).

**미스터리 종료조건 해결**: 1차 스윕의 미분류 종료 대부분은 `target altitude below min` (에피소드당 최다)
— **loiter 표적(시나리오 5–7, 뱅크 40–70°)이 스스로 지면 추락** → draw 처리. 학습 노이즈이며,
서버 채점에서 상대 추락이 어떻게 처리되는지 주최측 확인 가치 있음.

## 6. 제출

`student\my_submission.py`에서 `TEAM_NAME`, `SERVER_IP`, `BUNDLE_DIR`, `OBSERVATION_MODE/MODULE` 설정 후:

```powershell
& $py student\my_submission.py
```

관측 mode/module과 `ACTION_REPEAT`(기본 6, 학습 `step_ratio`와 동일)가 학습 설정과 일치해야 합니다.
