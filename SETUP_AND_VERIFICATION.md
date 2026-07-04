# AI Pilot Top Gun Challenge 2026 — 환경 설정 및 검증 보고서

작성: 2026-06-12 (Claude Code 자동 설정)

## 1. 프로젝트 파일 요약

| 위치 | 내용 |
|---|---|
| `1일차 강의 자료/` | 대회 소개 PPT, 교전환경 소개 영상 |
| `2일차 강의 자료/` | 경진대회 매뉴얼(rev7 PPT), RL 매뉴얼(rev8 HTML), student 매뉴얼, 보상 설계 슬라이드, Release 매뉴얼(docx) |
| `AIP_LIB/DogFightEnv/Release/` | **구버전(05-20) RL 환경 — 참고용 보존** |
| `AIP_LIB/DogFightEnv/Release_260529/` | **활성 작업 공간** — 최신 업데이트(05-29) 적용본 |
| `AIP_LIB/AIP_DCS/` | Behavior Tree C++ Visual Studio 프로젝트 (BT 전술 설계용) |
| `AIP_LIB/Windows/` | Unreal 기반 DogFight 뷰어 (로컬 시각화) |
| `Update/` | 업데이트 zip 모음: BattleServer V0.2(최신), AIP_DCS, 강화학습환경 Release_260529(최신), 참고 매뉴얼 |
| `교전 뷰어 사용 메뉴얼.pdf` | 교전 뷰어 사용법 |

## 2. 대회 요구사항 (강의 자료에서 추출)

- **과제**: JSBSim 기반 F-16 1v1 근접 공중전(WVR dogfight)을 수행하는 RL 정책 학습.
  Ray RLlib 2.54.0 (new API stack), PPO 또는 SAC, MLP/LSTM 신경망.
- **관측**: 기본 모드 `classic12/relative14/tactical16(권장 예시)/legacy37` + custom
  (`student/my_observation.py`, `OBSERVATION_SIZE` + `build_observation()` 계약).
- **행동**: `Box([-1,1]^4)` — roll, pitch, rudder/yaw, throttle(내부 [0,1] 변환). action repeat = 6 (학습 `step_ratio`와 일치 필수).
- **보상**: `student/my_reward.py`의 `compute_reward(...) -> (float, dict components)` 계약. components는 `ep_reward_<name>` 지표로 자동 기록.
- **평가**: 최종 지표는 **승률(win_rate)** (체력 기반 승/패/무). 분석 지표로 crash_rate, ep_min_distance, ep_wez_steps, reward_mean을 함께 봄.
- **제출**: lightweight bundle(`artifacts/models/<팀>/<태그>/metadata.json` + `policy_weights.pkl.gz`)을 UDP로 Unreal 대회 서버에 연결(`student/my_submission.py`, 모드 rl/bt/hybrid).
- **제약**: 학생 수정 영역은 `student/*.py`와 `experiments/*.yaml`로 한정. `src/dogfight/` 공통 플랫폼과 DLL/Rule XML/aircraft/engine/scripts 런타임 자산은 수정·이동 금지. 학습/로컬검증/제출에서 관측 mode/module 일치 필수.

## 3. 설치 내역 (재현: `Release_260529\setup_env.ps1`)

| 단계 | 내용 |
|---|---|
| 1 | Miniconda3 (winget, 사용자 영역: `%LOCALAPPDATA%\miniconda3`) + 채널 ToS 동의 |
| 2 | conda env **`aip`** = Python 3.11 (공식 매뉴얼 사양) |
| 3 | PyTorch 2.12.0+**cu126** (RTX 3070 GPU 사용, `torch.cuda.is_available()=True`) |
| 4 | `requirements.txt`: ray[rllib]==2.54.0, gymnasium 1.2.2, numpy 2.2.6, pymap3d, PyYAML, cloudpickle, filelock |
| 5 | **VS 2022 Build Tools(C++ 워크로드)** 설치 후 디버그 CRT 4종(`msvcp140d/vcruntime140d/vcruntime140_1d/ucrtbased.dll`)을 Release 루트로 복사 |

> 5번이 필요한 이유: 제공된 `JSBSimAIPLib.dll`, `AIP_BASE*.dll`이 **Debug 빌드**라
> 디버그 CRT를 임포트하는데, 이는 일반 VC++ 재배포 패키지에 없고 Visual Studio에만
> 포함됩니다. (PE import table 분석으로 확인)

기타 조치: `Update\강화학습환경\Latest\Release_260529.zip`을
`AIP_LIB\DogFightEnv\Release_260529\`로 추출(구버전 보존). 구버전 Release에는
`Rule_forTraining.xml`이 없어 최신본 사용이 필수입니다.

## 4. 검증 결과 (전체 통과)

| # | 항목 | 결과 |
|---|---|---|
| 1 | import smoke: torch(CUDA), ray, gymnasium, JSBSimWrapper(DLL 로드) | ✅ PASS |
| 2 | `py_compile` — 본체/도구/학생 스크립트 13개 | ✅ PASS |
| 3 | YAML dry-run — sac_mlp, ppo_mlp, mixed_initial_sac_mlp | ✅ PASS |
| 4 | 단일 학습 smoke — SAC 2 iterations vs BT 타겟 (`verify/smoke_sac`) | ✅ PASS — bundle·training_log.csv·metrics.jsonl·records 모두 생성, exit 0 |
| 5 | 평가 스크립트 — bundle 로드 후 BT 상대 2 에피소드, 통계 저장 | ✅ PASS (`artifacts/eval/verify_eval/summary.json`) |
| 6 | 병렬 학습 — 2개 프로세스 동시 실행 (lr 0.0003 / 0.001) | ✅ PASS — 둘 다 exit 0, 출력 폴더 분리 (`artifacts/sweeps/verify_parallel/manifest.json`) |

검증용 산출물은 `Release_260529\artifacts\` 아래 `verify*` 이름으로 남아 있으며 삭제해도 무방합니다.

## 5. 추가/수정된 파일 (전부 신규 — 기존 코드는 무수정)

| 파일 | 용도 |
|---|---|
| `Release_260529\scripts\run_parallel.py` | **병렬 스윕 실행기** — base YAML + grid/repeats → 변형 YAML 자동 생성, 동시 실행 제한, run별 로그/manifest |
| `Release_260529\scripts\run_eval.py` | **N회 평가 집계** — 승/패/무율, 종료사유 분포, summary.json + episodes.csv |
| `Release_260529\experiments\sweeps\example_sac_sweep.yaml` | 스윕 정의 예시 (lr × 네트워크 2×2) |
| `Release_260529\experiments\sweeps\verify_parallel_smoke.yaml` | 병렬 검증용 미니 스윕 |
| `Release_260529\experiments\verify_smoke_sac.yaml` | 설치 검증용 2-iteration 실험 |
| `Release_260529\setup_env.ps1` | 환경 전체 재현 스크립트 (Miniconda→aip env→torch→deps→디버그 CRT) |
| `Release_260529\WORKFLOW.md` | 실험 워크플로 통합 가이드 (아래 요약) |

## 6. 사용법 요약 (상세: `Release_260529\WORKFLOW.md`)

```powershell
$py = "$env:LOCALAPPDATA\miniconda3\envs\aip\python.exe"
cd "C:\Users\GYU\Desktop\KAU\AI Pilot Top Gun Challenge 2026\AIP_LIB\DogFightEnv\Release_260529"

# 단일 학습 (조건은 YAML에서 변경: algo.lr, algo.mlp.fcnet_hiddens, runtime.iterations,
#            env_config.reward.*, env.reward_module: student.my_reward 등)
& $py scripts\run_experiment.py experiments\student_sac_mlp.yaml --dry-run
& $py scripts\run_experiment.py experiments\student_sac_mlp.yaml

# 병렬 학습 (스윕 YAML 1개 + 명령 1줄; 이 PC는 max_parallel 2-3 권장)
& $py scripts\run_parallel.py experiments\sweeps\example_sac_sweep.yaml

# 평가 (N회 교전 통계)
& $py scripts\run_eval.py --ownship-bundle-dir artifacts\models\<팀>\<태그> --episodes 20

# 대시보드 (Training 지표 + Replay 궤적)  → http://127.0.0.1:7860
& $py tools\dashboard.py --training-logdir artifacts\dashboard --logdir logs --port 7860
```

결과물: `artifacts\logs|models|checkpoints|dashboard|sweeps|eval\...` (run마다 `<팀>\<태그>` 분리).

**주의**: 병렬 실행 중 `ray stop --force` 금지(모든 Ray 세션 종료됨). 관측 차원을 바꾸면 기존 bundle/checkpoint와 호환되지 않음.
