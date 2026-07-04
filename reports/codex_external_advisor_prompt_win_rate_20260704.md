# AI Pilot Top Gun RL 학습 현황 및 win_rate 개선 조언 요청

작성일: 2026-07-04  
작성 목적: 외부 조언자에게 현재 강화학습 상황을 공유하고, 다음 학습 설계에서 `win_rate`를 올리기 위한 구체적 조언을 받기 위함.

## 1. 현재까지의 요약

현재 정책은 공중전에서 위치를 잡거나 추격하는 일부 행동은 학습했지만, 최종적으로 적기를 격추해 `win_rate`를 안정적으로 올리는 단계까지는 도달하지 못했다. 최근 진단에서는 learned opponent뿐 아니라 level/autopilot 형태의 단순 타겟을 상대로도 격추가 잘 발생하지 않았다.

따라서 문제의 핵심은 단순히 상대가 강해서가 아니라, 근거리 rear-aspect 상황에서도 사격 정렬, trigger 타이밍, 탄착 유지, damage 누적을 끝까지 완성하지 못하는 데 있다고 판단했다.

## 2. 최근 실험 상태

- v11은 중단했다.
- v11의 마지막 사용 가능한 체크포인트는 `artifacts/models/team01/ic_s3_bt_v11/bundle_000080`이다.
- v11 종료 직전 `bundle_000080` 이후 로그는 중단 과정에서 `nan`이 섞일 수 있어, v12 초기값으로는 `bundle_000080`만 사용한다.
- v12는 level/autopilot target의 뒤쪽에서 RL 에이전트를 스폰하고, 짧은 교전 안에 타겟을 죽이도록 학습하는 방식으로 설정했다.

## 3. v12 학습 가설

기존 self-play 또는 learned-opponent 중심 학습은 너무 많은 하위 문제를 동시에 요구했다.

v12에서는 과제를 좁힌다.

- 시작 위치: 타겟 후방 550-750m
- aspect: 0-8도 수준의 rear-aspect
- 타겟: level/autopilot
- 목표: 이미 유리한 위치에서 조준을 안정화하고, 사격으로 damage/kill을 만드는 능력 확보
- 기대 효과: win_rate 이전에 `kill_count`, `damage_done`, `gun alignment`, `time_to_kill` 같은 직접 지표 개선

## 4. 현재 우려점

1. 이미 후방에 둔 상태에서도 kill이 안 난다면, 기동 정책보다 무장 사용/조준 보상 설계가 병목일 가능성이 크다.
2. `win_rate`만 보상 또는 평가 지표로 보면 sparse해서 학습 신호가 약하다.
3. damage를 넣는 순간, 조준 cone 유지 시간, trigger discipline, 상대와의 closing speed 제어 같은 중간 지표가 더 필요할 수 있다.
4. 시작 조건을 너무 쉽게 만들면 kill 행동은 배울 수 있지만, 실제 전투 초기 상황으로 일반화되지 않을 수 있다.

## 5. 조언을 구하고 싶은 질문

1. 이 상황에서 `win_rate`를 올리기 위한 다음 curriculum은 어떤 순서가 좋은가?
2. rear-aspect kill 학습에서 reward를 어떻게 쪼개는 것이 좋은가?
3. `damage_done`, `shots_on_target`, `gun_cone_time`, `range_control`, `aspect_control`, `kill_bonus` 사이의 적절한 비중은 어떻게 잡는 것이 좋은가?
4. 현재처럼 level target 뒤에서 시작하는 방식이 적절한가, 아니면 stationary/slow target, wider rear cone, fixed altitude 등 더 쉬운 단계부터 가야 하는가?
5. kill이 나오기 전까지 PPO 설정에서 조정해야 할 항목은 무엇인가? 예: learning rate, entropy, clip range, batch size, rollout length.
6. win_rate 개선을 판단할 때 `win_rate` 외에 어떤 보조 지표를 반드시 같이 추적해야 하는가?
7. v12 이후 다시 learned opponent 또는 self-play로 돌아가는 적절한 승급 조건은 무엇인가?

## 6. 현재 제안하는 다음 학습 방향

우선 v12에서 후방 스폰 kill 능력을 확인한다. 첫 번째 목표는 `win_rate` 자체보다 `damage_done > 0`, `hit/kill 발생`, `time_to_first_damage 감소`를 확인하는 것이다.

v12가 damage를 만들기 시작하면, 다음 단계는 시작 거리와 aspect를 점진적으로 넓히는 curriculum으로 간다.

- 단계 A: 후방 400-700m, aspect 0-5도
- 단계 B: 후방 500-900m, aspect 0-15도
- 단계 C: 약간의 고도/속도 차이를 추가
- 단계 D: level target에서 mild maneuver target으로 변경
- 단계 E: learned opponent 또는 self-play 재도입

외부 조언자에게는 특히 "kill을 못 만드는 병목이 reward 설계인지, action/control 제약인지, observation 부족인지, 초기화 curriculum 문제인지"를 구분하는 방법에 대해 조언을 요청하고 싶다.
