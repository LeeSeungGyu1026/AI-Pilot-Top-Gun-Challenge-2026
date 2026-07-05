# ic_s6 BT 커리큘럼 설계 (2026-07-05)

목표: weave/random-jink 오토파일럿을 정복한 챔피언(ic_s5 계열)을 **경기용 BT 상대**로
일반화. 6월의 ic_s3_bt 라인(v1~v11)이 실패한 두 원인을 이번엔 설계로 제거한다:

1. **틱0 자살 다이브**: 풀 BT 뒤 1100~3400m에 스폰하면 BT가 방어 태스크
   (DefensiveBreak/RearThreatJink)의 퇴화 지오메트리로 즉시 수직 다이브 → 4초 내
   지면 충돌. 당시 유일한 해법이 스폰을 3600m+로 밀어내는 것이었고, 그 결과
   500-900m에서 익힌 거너리가 전부 무용지물이 됐다.
   → **이번엔 BT 난이도를 우리가 조절**(Rule_forTraining.xml은 학생 통제 자산).
   방어 태스크를 뺀 BT부터 시작하면 근접 스폰이 다시 안전해진다.
2. **가짜 시딩**: 플랫폼 버그 #7로 6월의 모든 seeded run은 사실상 from-scratch였다.
   지금은 로더가 고쳐졌으므로(2026-07-04) 스테이지 체인이 진짜로 작동한다.

## BT 난이도 사다리 (student/bt_rules/)

| 레벨 | 파일 | 내용 |
|---|---|---|
| L1 | `Rule_BT_L1_pursuit_only.xml` | 방어 태스크 전부 제거. 추격+사격만 (LagPursuit/LeadPursuit/Recommit/ClimbRecover). 950m/LOS<30 안에서는 실탄 위협. 다이브 트리거 원천 제거 → 근접 후방 스폰 안전 |
| L2 | `Rule_BT_L2_gentle_break.xml` | L1 + 수평 DefensiveBreak 1개 (트리거 <1400m·후방·추적중, VerticalOffset 0). 스폰 최소거리 ≥1600m로 두면 틱0에 절대 안 걸림 |
| L3 | `Rule_BT_L3_soft_full.xml` | 스톡 전체 구조 + 완화 파라미터 (트리거 축소, 수직 오프셋 축소, LowYoYo 다이브 완화). 스폰 ≥2200m 권장 |
| L4 | `Rule_BT_L4_stock.xml` | 스톡 원본 백업 (= 현재 워크스페이스 루트 파일) |

활성화 방법: 훈련 경로(target_mode: behavior_tree)는 DLL이 **워크스페이스 루트의
`Rule_forTraining.xml`을 직접 읽는다**. 스테이지 시작 전에 해당 레벨 파일을 루트로
복사. eval은 `run_eval --bt-rule-xml student/bt_rules/<파일>`로 지정 가능(자동
백업/복원됨). 병렬로 서로 다른 BT 레벨의 훈련을 동시에 돌리지 말 것(루트 파일 공유).

## 스테이지 설계 (스폰 지오메트리 포함)

공통: v15 exploit-free 보상(codex_reward_v15_wez_only), 진짜 2° 킬콘, forced_ground=0
(캠핑 방지), range_discipline 유지(스폰 최대거리의 ~1.7배), alt 7000m, 자세는 수평
(roll/pitch 0), 에이전트는 타깃 지향(lock-on) 스폰. `offensive_saddle.aspect_deg`는
꼬리 기준 방위 오프셋이라 **0°=정후방, 90°=측방, 180°=정면 머지**까지 커버 —
헤드온 스폰에 래퍼 수정 불필요.

| 스테이지 | BT | 스폰 거리 | aspect | 시간 | 게이트 (진급 조건) |
|---|---|---|---|---|---|
| **BT1** (`ic_s6_bt1_pursuit_only_v1.yaml`) | L1 | 500–900m (마스터한 새들) | 0–25° | 120s | train win ≥0.8 + held-out eval ≥0.7 |
| **BT2** | L1 | 700–1800m | 0–60° | 120s | 동일 |
| **BT3** | L2 | **1600–2400m** (트리거 밖) | 0–60° | 150s | 동일 + 틱0 다이브 없음 확인 |
| **BT4** | L3 | **2200–3200m** | 0–90° | 180s | 동일 |
| **BT5** | L4 (스톡) | 혼합: 2500–4000m, aspect 0–150° (근접 헤드온 포함) | | 180–300s | 최종: 스톡 BT 상대 eval win — 제출 후보 |

- 왜 뒤에서 스폰으로 시작? 에이전트의 전 기술 스택(추적→WEZ 유지→킬 마무리)이
  500-900m 후방 새들에서 형성됐다. BT 전환의 새 변수는 "상대가 반응하고 쏜다"
  하나로 제한하고, 거리/aspect는 익숙한 값에서 출발해 단계별로 확장한다
  (6월의 실패 = 상대와 거리를 동시에 바꾼 것).
- 마주보기(헤드온)는 BT5에서만: 정면 스폰은 상호 WEZ 위험(2° 대칭 킬콘)이 커서
  거너리가 완성되기 전에 넣으면 v7식 "접근=피격=후퇴" 붕괴를 재발시킨다.
- 스폰 자세: 수평, 타깃 지향, own 300m/s (선회하는 BT 대비 closure 여유).
  BT는 틱0 이후 자기 에너지를 스스로 관리하므로 target_speed는 초기값만 의미.

## 스테이지별 절차 (모든 스테이지 공통)

1. 이전 스테이지 최종 번들로 `init_bundle` 갱신 (진짜 시딩 — 명시적 bundle 경로 사용).
2. 해당 레벨 XML을 루트 `Rule_forTraining.xml`로 복사.
3. **3-iter 프로브** → `tools/end_condition_breakdown.py`로 "target altitude below
   min"(BT 자살)과 own-crash 점검. BT 자살이 지배적이면 중단하고 지오메트리 재조정.
4. 본 훈련 150 iters (lr 3e-5 / clip 0.08 유지; 60 iter 지나도 win<0.3이면 lr 1e-4로
   1회 연장 run).
5. 게이트 eval **두 경로 모두**: 훈련 경로 win_rate + `run_eval --experiment-yaml
   <스테이지 yaml> --target-backend bt --bt-rule-xml <해당 XML>` (BTActionProvider =
   held-out 제어 경로; 2026-06-19 train/eval 미스매치 교훈).
6. 마일스톤마다 오토파일럿 weave eval로 기존 기술 망각 여부 확인 (BT엔
   straight_prob 같은 anti-forgetting 믹스가 없음).

## 보상 관련 주의 (과거 교훈 재적용)

- `damage_taken_scale`은 3.0에서 시작, **킬이 정착된 후에만** 10–20으로 인상
  (v7 교훈: 이르게 올리면 "접근의 기대가치<0" → 후퇴 고착).
- `forced_ground_reward=0` 유지 (v3 교훈: 값을 주면 BT 자살 캠핑 학습).
- 훈련로그 win_rate는 BT 자살을 분류 못 함 — 판단은 항상
  `tools/end_condition_breakdown.py` + run_eval로.
- reward_mean↑ & win_rate↓ 패턴이 보이면 즉시 파밍 항 의심 (v14 교훈).
