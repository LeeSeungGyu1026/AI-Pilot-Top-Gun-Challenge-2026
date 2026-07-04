# v12 전 진단 실험 결과

작성일: 2026-07-04  
목적: 첨부 답안에서 제안한 v12 전 선행 실험을 완료하고, v12 설계를 데이터로 결정하기 위함.  
중요 제약: 진행 중인 `ic_s3_bt_v11` 학습 프로세스는 건드리지 않았고, v12 학습 실험은 실행하지 않았다.

## 사용한 대상

- 평가 모델: `artifacts/models/team01/ic_s3_bt_v11/bundle_000060`
- 현재 진행 중인 v11 학습은 읽기 전용 로그 확인만 수행
- 평가 스크립트: `scripts/codex_pre_v12_diagnostics.py`
- 평가용 in-band YAML: `experiments/codex_pre_v12_inband_autopilot_eval.yaml`
- 계획 문서: `reports/codex_pre_v12_diagnostic_plan_20260704.md`

## 실행한 진단 실험

| 실험 | 상대 | 초기조건 | episodes | 산출물 |
|---|---|---|---:|---|
| `codex_pre_v12_inband_autopilot_v11_bundle60` | autopilot | 500~700m, aspect 0~10도 | 5 | `artifacts/eval/codex_pre_v12_inband_autopilot_v11_bundle60` |
| `codex_pre_v12_wide_autopilot_v11_bundle60` | autopilot | v11 wide saddle 3600~4200m | 5 | `artifacts/eval/codex_pre_v12_wide_autopilot_v11_bundle60` |
| `codex_pre_v12_bt_v11_bundle60` | BT | v11 wide saddle 3600~4200m | 5 | `artifacts/eval/codex_pre_v12_bt_v11_bundle60` |

## 핵심 결과

### 1. 쉬운 직선 target도 아직 격추하지 못함

`inband_autopilot`은 BT 회피와 장거리 closure를 제거한 sanity gate다. 시작부터 true WEZ range band 근처에 두었지만 결과는 5/5 timeout이었다.

| 지표 | 값 |
|---|---:|
| real_win_rate | 0.0 |
| draw_rate | 1.0 |
| mean_time_in_band_steps | 104.8 |
| mean_time_in_band_ata10_steps | 20.8 |
| mean_true_cone_steps | 4.4 |
| mean_overshoot_rate | 0.0 |
| mean_reward_damage | 1.267 |

해석: range band에는 들어가지만 2도 true cone을 오래 유지하지 못한다. `win_rate` 병목의 1순위는 BT 난이도보다 **gunnery/cone-hold 제어 능력 부족**이다.

### 2. wide-saddle 직선 target에서는 contact 자체가 안 됨

`wide_autopilot`은 v11의 3600~4200m saddle을 그대로 두고 target만 autopilot으로 바꾼 평가다. 결과는 5/5 timeout, band 진입 0이었다.

| 지표 | 값 |
|---|---:|
| real_win_rate | 0.0 |
| draw_rate | 1.0 |
| mean_time_in_band_steps | 0.0 |
| mean_true_cone_steps | 0.0 |
| mean_total_reward | -18.0 |
| mean_reward_components.step | -18.0 |
| mean_reward_components.pursuit | 0.0 |
| mean_reward_components.damage | 0.0 |

해석: 현재 정책은 장거리 wide saddle에서 직선 target에게도 유효하게 closure하지 못한다. v11 학습 중 training log에서 보이는 근접/overshoot는 BT의 기동과 상호작용한 결과일 수 있으며, 순수 추격 능력이 안정적이라고 보기 어렵다.

### 3. BT 상대에서는 range band 진입은 하지만 true cone과 damage가 거의 없음

`bt` 평가는 실제 BT 상대의 진단이다. 5회 중 4회 timeout, 1회 forced-ground였고 real kill은 0회다.

| 지표 | 값 |
|---|---:|
| real_win_rate | 0.0 |
| forced_ground_rate | 0.2 |
| draw_rate | 0.8 |
| mean_time_in_band_steps | 333.2 |
| mean_time_in_band_ata10_steps | 25.0 |
| mean_true_cone_steps | 4.0 |
| mean_overshoot_rate | 0.0164 |
| mean_band_entry_closure_mps | 234.6 |
| mean_action_delta_l1 | 0.0744 |
| mean_reward_damage | 0.0005 |

해석: BT 상대에서는 band 체류 시간이 autopilot보다 길지만, true cone step은 여전히 평균 4 step뿐이고 damage는 사실상 0이다. band-entry closure가 평균 234.6 m/s로 높아, band에 들어올 때 이미 과속 진입하고 cone을 잡기 전에 지나치는 패턴이 강하게 의심된다.

## 첨부 답안의 세 가지 진단에 대한 결론

### A. 직선 수평 target gunnery 평가

완료. 결과는 실패다. 쉬운 target도 죽이지 못했으므로 v12를 BT 대응 curriculum으로 바로 가는 것은 위험하다. 먼저 level/autopilot target에서 kill rate를 만드는 훈련 또는 평가 gate가 필요하다.

### B. end-condition별 reward component 분해

완료. 현재 평가에서는 timeout이 대부분이고, reward는 주로 step penalty와 pursuit shaping에 의해 결정된다. 특히 wide autopilot에서는 pursuit/damage/safety가 0이고 step penalty만 누적되어, 장거리 직선 target contact가 전혀 안 된다. BT에서는 pursuit는 조금 생기지만 damage가 거의 0이다.

### C. band 진입 closure와 action jitter 로깅

완료. BT 평가에서 평균 band-entry closure가 234.6 m/s로 높다. action delta L1은 평균 0.074로 아주 폭발적이지는 않지만, true cone 유지에는 충분히 부드럽다고 단정할 수 없다. 우선순위는 action jitter 자체보다 **closure-rate 제어와 cone-hold drill 부족**으로 보인다.

## v12 전에 확정된 설계 시사점

1. v12는 바로 BT wide saddle을 늘리는 실험이면 안 된다.
2. `level/autopilot sanity gate`를 먼저 통과해야 한다. 최소 기준은 in-band straight target real kill rate가 50% 이상, 목표 기준은 80~90% 이상이다.
3. curriculum에는 반드시 in-band cone-hold drill이 들어가야 한다.
4. wide 3600~4200m 분포 비중은 낮춰야 한다. 현재는 직선 target에서도 band 진입이 0이다.
5. range < 152m penalty보다 먼저 band-entry closure를 낮추는 조건이 필요하다. 예: in-band precision reward를 `abs(closure) < 80~120 m/s`로 gate하거나, closure PBRS/penalty를 추가하는 방향.
6. damage reward가 전체 reward에서 너무 약하다. BT 평가 mean damage reward가 0.0005 수준이라 win과 직접 연결되는 gradient가 거의 없다.
7. action repeat 또는 action smoothing 변경은 trainer/submission parity가 깨질 수 있으므로, v12에서 바로 넣기보다 별도 control diagnostic 또는 wrapper parity plan과 함께 검토해야 한다.

## 권장 다음 결정

v12를 실행하기 전에 사용자가 선택할 수 있는 안전한 방향은 다음 중 하나다.

1. **v12를 level-target gunnery curriculum으로 정의**
   - target mix의 대부분을 level/autopilot과 gentle weave로 두고, BT 비중은 낮게 시작한다.
   - in-band 300~700m, ATA < 15도, closure small 조건을 15~25% 이상 포함한다.

2. **v12 전 추가 micro-eval**
   - `bundle_000070` 또는 v11 final bundle이 생기면 같은 세 진단을 다시 실행한다.
   - 단, 학습 프로세스는 계속 건드리지 않는다.

3. **reward 설계만 먼저 문서화**
   - potential-based range band shaping
   - precision reward에 closure gate 추가
   - damage reward 비중 확대
   - timeout/end-condition별 reward component 리포트를 validation hard gate로 포함

현재 데이터만 보면, 가장 타당한 v12 방향은 `BT winrate를 바로 올리는 실험`이 아니라 **autopilot/level target에서 true cone hold와 damage를 만드는 gunnery curriculum**이다.

## 완료 증거

- `artifacts/eval/codex_pre_v12_inband_autopilot_v11_bundle60/codex_summary.json`
- `artifacts/eval/codex_pre_v12_wide_autopilot_v11_bundle60/codex_summary.json`
- `artifacts/eval/codex_pre_v12_bt_v11_bundle60/codex_summary.json`
- `artifacts/eval/*/codex_episodes_diagnostics.csv`
- `artifacts/eval/*/codex_steps_sample.csv`

비고: v12 학습은 실행하지 않았다.
