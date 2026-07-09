# Release_260529 커스텀 BT 작업 가이드

이 문서는 `Release_260529` 환경에서 DogFightViewer와 통신하며 Behavior Tree(BT)를 실행하거나, 커스텀 BT XML/DLL을 교체할 때 참고하기 위한 메모입니다.

## 기준 경로

```text
repo root:
C:\Users\biobe\desktop\aip\AI-Pilot-Top-Gun-Challenge-2026

Release_260529:
C:\Users\biobe\desktop\aip\AI-Pilot-Top-Gun-Challenge-2026\AIP_LIB\DogFightEnv\Release_260529

Viewer:
C:\Users\biobe\desktop\aip\AI-Pilot-Top-Gun-Challenge-2026\AIP_LIB\Windows

Rule XML 위치:
C:\Users\biobe\desktop\aip\AI-Pilot-Top-Gun-Challenge-2026\AIP_LIB

BT C++ 소스:
C:\Users\biobe\desktop\aip\AI-Pilot-Top-Gun-Challenge-2026\AIP_LIB\AIP_DCS
```

## 그냥 `python`을 써도 되는 조건

`python` 명령은 현재 터미널이 `aip` conda env를 제대로 잡고 있을 때만 사용한다. 여기서 aip 가상환경은 requirement 다 다운 받은 환경임

확인:

```bat
where python
python -c "import sys; print(sys.executable)"
```

정상 예:

```text
C:\Users\biobe\miniconda3\envs\aip\python.exe
```

다른 Python이 나오면 아래처럼 절대 경로 Python을 쓴다.

```bat
C:\Users\biobe\miniconda3\envs\aip\python.exe
```

## Viewer 실행

먼저 Viewer를 켠다.

```bat
cd C:\Users\biobe\desktop\aip\AI-Pilot-Top-Gun-Challenge-2026\AIP_LIB\Windows
DogFightViewer.exe
```

그 다음 다른 터미널에서 `Release_260529`로 이동한다.

```bat
cd C:\Users\biobe\desktop\aip\AI-Pilot-Top-Gun-Challenge-2026\AIP_LIB\DogFightEnv\Release_260529
```

## 기본 BT 실행

현재 `Rule_default.xml`은 `DECO_AltitudeCheck` 등을 사용하므로 `AIP_BASE.dll`이 아니라 `AIP_BASE_target.dll`을 쓴다.

```bat
python run_unreal_inference.py --mode bt --bt-dll AIP_BASE_target.dll --bt-rule-xml "..\..\Rule_default.xml" --team-name team01 --server-ip 127.0.0.1 --server-port 9999 --packet-monitor --action-repeat 6 --ai-type rule
```

절대 경로 Python으로 실행할 때:

```bat
C:\Users\biobe\miniconda3\envs\aip\python.exe run_unreal_inference.py --mode bt --bt-dll AIP_BASE_target.dll --bt-rule-xml "..\..\Rule_default.xml" --team-name team01 --server-ip 127.0.0.1 --server-port 9999 --packet-monitor --action-repeat 6 --ai-type rule
```

## XML만 바꿔서 커스텀 BT 만들기

기존 DLL에 이미 등록된 노드만 조합하는 경우에는 XML만 바꾸면 된다.

예:

```text
SelectTarget
DirectionVectorUpdate
DistanceUpdate
CheckSight
AngleOffUpdate
AspectAngleUpdate
DECO_DistanceCheck
DECO_LOSCheck
DECO_TargetLOSCheck
DECO_AltitudeCheck
Task_LagPursuit
Task_LeadPursuit
Task_DefensiveBreak
Task_RearThreatJink
Task_Recommit
Task_LowYoYo
Task_ClimbRecover
```

기본 XML을 복사한다.

```bat
copy ..\..\Rule_default.xml ..\..\Rule_myBT.xml
```

`C:\Users\biobe\desktop\aip\AI-Pilot-Top-Gun-Challenge-2026\AIP_LIB\Rule_myBT.xml`을 수정한다.

실행:

```bat
python run_unreal_inference.py --mode bt --bt-dll AIP_BASE_target.dll --bt-rule-xml "..\..\Rule_myBT.xml" --team-name team01 --server-ip 127.0.0.1 --server-port 9999 --packet-monitor --action-repeat 6 --ai-type rule
```

주의: `Rule_forTraining.xml`은 직접 수정하지 않는다. `run_unreal_inference.py`가 실행될 때 `--bt-rule-xml`로 지정한 XML을 `Rule_forTraining.xml`로 복사한다.

## 새 C++ 기능이 필요한 커스텀 BT

XML에 새 노드명, 새 속성, 새 행동 로직을 넣는 경우에는 C++ DLL까지 새로 빌드해야 한다.

예를 들어 아래 XML은 기존 `AIP_BASE_target.dll`로는 실패했다.

```xml
<Task_Empty name="CirclePatternHorizontal" BB="{BB}" Pattern="Circle" Radius="1800" Speed="1.0"/>
```

원인:

```text
AIP_BASE_target.dll에는 Task_Empty는 있었지만 Pattern/Radius/Speed 포트가 컴파일되어 있지 않았다.
```

이럴 때 필요한 절차:

1. C++ 노드 수정 또는 추가
2. `providedPorts()`에 XML 속성 등록
3. `tick()`에 실제 행동 구현
4. `CPPBehaviorTree.cpp`에 노드 등록
5. DLL 빌드
6. 빌드된 DLL을 `Release_260529`에 복사
7. `--bt-dll`로 새 DLL 지정

## C++ 노드 수정 위치

Task:

```text
AIP_LIB\AIP_DCS\BehaviorTree\BT_Content\Task
```

Decorator:

```text
AIP_LIB\AIP_DCS\BehaviorTree\BT_Content\Decorator
```

Service:

```text
AIP_LIB\AIP_DCS\BehaviorTree\BT_Content\Service
```

노드 등록:

```text
AIP_LIB\AIP_DCS\BehaviorTree\CPPBehaviorTree.cpp
```

등록 예:

```cpp
Factory.registerNodeType<Action::Task_Empty>("Task_Empty");
Factory.registerNodeType<Action::DECO_AltitudeCheck>("DECO_AltitudeCheck");
```

포트 등록 예:

```cpp
PortsList Action::Task_Empty::providedPorts()
{
    return {
        InputPort<CPPBlackBoard*>("BB"),
        InputPort<std::string>("Pattern"),
        InputPort<std::string>("Radius"),
        InputPort<std::string>("Speed")
    };
}
```

## DLL 빌드

현재 `Release|x64` 설정은 PropertySheets 상대 경로가 맞지 않아 바로 실패할 수 있다.
우선 확인/실험용은 `Debug|x64` 빌드를 사용한다.

CMD:

```bat
"C:\Program Files\Microsoft Visual Studio\2022\Community\MSBuild\Current\Bin\amd64\MSBuild.exe" "C:\Users\biobe\desktop\aip\AI-Pilot-Top-Gun-Challenge-2026\AIP_LIB\AIP_DCS\AIP_DCS.sln" /t:Build /p:Configuration=Debug /p:Platform=x64
```

PowerShell:

```powershell
& "C:\Program Files\Microsoft Visual Studio\2022\Community\MSBuild\Current\Bin\amd64\MSBuild.exe" "C:\Users\biobe\desktop\aip\AI-Pilot-Top-Gun-Challenge-2026\AIP_LIB\AIP_DCS\AIP_DCS.sln" /t:Build /p:Configuration=Debug /p:Platform=x64
```

빌드 산출물:

```text
C:\Users\biobe\desktop\aip\AI-Pilot-Top-Gun-Challenge-2026\AIP_LIB\bin\debug.x64\AIP_DCS.dll
```

복사:

```bat
copy C:\Users\biobe\desktop\aip\AI-Pilot-Top-Gun-Challenge-2026\AIP_LIB\bin\debug.x64\AIP_DCS.dll C:\Users\biobe\desktop\aip\AI-Pilot-Top-Gun-Challenge-2026\AIP_LIB\DogFightEnv\Release_260529\AIP_BASE_target_myBT.dll
```

새 DLL로 실행:

```bat
python run_unreal_inference.py --mode bt --bt-dll AIP_BASE_target_myBT.dll --bt-rule-xml "..\..\Rule_myBT.xml" --team-name team01 --server-ip 127.0.0.1 --server-port 9999 --packet-monitor --action-repeat 6 --ai-type rule
```

## 현재 만들어 둔 원형 패턴 DLL

`Task_Empty`의 `Pattern/Radius/Speed`를 포함하도록 Debug x64로 빌드한 DLL:

```text
AIP_BASE_target_circle_debug.dll
```

이 DLL은 패턴 데모가 눈에 보이도록 `Task_Empty`에서 직접 조종 override도 낸다.

```text
Pattern="Straight"        -> Roll 0.00 / Pitch 0.00 / Rudder 0.00
Pattern="Circle"          -> Roll 0.55 / Pitch -0.45 / Rudder -0.05
Pattern="CircleVertical"  -> Roll 0.00 / Pitch -0.70 / Rudder 0.00
Pattern="Figure8"         -> 시간에 따라 좌우 Roll 변경
```

`Rule_Circle_Horizontal.xml` 실행:

```bat
python run_unreal_inference.py --mode bt --bt-dll AIP_BASE_target_circle_debug.dll --bt-rule-xml "..\..\Rule_Circle_Horizontal.xml" --team-name team01 --server-ip 127.0.0.1 --server-port 9999 --packet-monitor --action-repeat 6 --ai-type rule
```

다른 커스텀 패턴:

```bat
python run_unreal_inference.py --mode bt --bt-dll AIP_BASE_target_circle_debug.dll --bt-rule-xml "..\..\Rule_Straight.xml" --team-name team01 --server-ip 127.0.0.1 --server-port 9999 --packet-monitor --action-repeat 6 --ai-type rule

python run_unreal_inference.py --mode bt --bt-dll AIP_BASE_target_circle_debug.dll --bt-rule-xml "..\..\Rule_Circle.xml" --team-name team01 --server-ip 127.0.0.1 --server-port 9999 --packet-monitor --action-repeat 6 --ai-type rule

python run_unreal_inference.py --mode bt --bt-dll AIP_BASE_target_circle_debug.dll --bt-rule-xml "..\..\Rule_Figure8.xml" --team-name team01 --server-ip 127.0.0.1 --server-port 9999 --packet-monitor --action-repeat 6 --ai-type rule
```

## 오프라인 BT 생성 테스트

Viewer를 켜기 전에 XML과 DLL 조합이 `CreateBehaviorTree`를 통과하는지 먼저 확인할 수 있다.

PowerShell에서 커스텀 XML 전체 테스트:

```powershell
cd C:\Users\biobe\desktop\aip\AI-Pilot-Top-Gun-Challenge-2026\AIP_LIB\DogFightEnv\Release_260529
$env:PYTHONPATH = (Resolve-Path "src").Path + ";" + (Resolve-Path ".").Path
$rules = @("Rule_Straight.xml", "Rule_Circle_Horizontal.xml", "Rule_Circle.xml", "Rule_Figure8.xml")
foreach ($rule in $rules) {
  python -c "from pathlib import Path; from dogfight.ai.native_bt import AIPilot; from dogfight.ai.bt_rule_manager import activate_rule_xml; root=Path.cwd(); xml=root/'..'/'..'/'$rule'; dll=root/'AIP_BASE_target_circle_debug.dll'; print('TEST $rule');`nwith activate_rule_xml(str(xml), root):`n    bt=AIPilot(str(dll)); bt.CreateBehaviorTree(0,1); print('OK $rule')"
}
```

CMD에서 단일 XML 테스트:

```bat
cd C:\Users\biobe\desktop\aip\AI-Pilot-Top-Gun-Challenge-2026\AIP_LIB\DogFightEnv\Release_260529
set PYTHONPATH=%CD%\src;%CD%
python -c "from pathlib import Path; from dogfight.ai.native_bt import AIPilot; from dogfight.ai.bt_rule_manager import activate_rule_xml; root=Path.cwd(); xml=root/'..'/'..'/'Rule_Circle_Horizontal.xml'; dll=root/'AIP_BASE_target_circle_debug.dll'; print('TEST Rule_Circle_Horizontal.xml'); exec('with activate_rule_xml(str(xml), root):\n    bt=AIPilot(str(dll)); bt.CreateBehaviorTree(0,1); print(\"BT Create OK\")')"
```

성공 예:

```text
Behavior Tree Initialized from ./Rule_forTraining.xml
BT Create OK
```

## 문제별 빠른 판단

`Node not recognized: DECO_AltitudeCheck`

```text
XML에 있는 노드를 DLL이 모른다.
대부분 --bt-dll이 잘못됐거나 DLL이 구버전이다.
Rule_default.xml 기준은 AIP_BASE_target.dll을 쓴다.
```

`CreateBehaviorTree failed ... Windows Error 0xe06d7363`

```text
C++ DLL 내부에서 예외가 난 것이다.
XML 노드명 또는 포트가 DLL과 안 맞을 가능성이 높다.
오프라인 BT 생성 테스트로 XML/DLL 조합을 먼저 확인한다.
```

Packet monitor에서 `RX: no packets yet`

```text
Viewer가 안 켜졌거나 IP/포트가 안 맞는다.
local 실행이면 --server-ip 127.0.0.1 --server-port 9999를 쓴다.
```

`MT_SetPlaneID`만 받고 `PlaneInfo`가 없음

```text
Viewer와 연결은 됐지만 게임/시뮬레이션이 아직 PlaneInfo를 보내지 않는 상태다.
Viewer에서 실제 게임 시작 상태인지 확인한다.
```

## 핵심 규칙

XML만 수정해도 되는 경우:

```text
이미 DLL에 있는 노드와 이미 등록된 속성만 조합할 때
```

DLL 빌드가 필요한 경우:

```text
새 노드명
새 XML 속성
새 행동 로직
새 Decorator 조건
새 Service 계산
```

실행 시 가장 중요한 두 인자:

```bat
--bt-dll <사용할 DLL>
--bt-rule-xml <사용할 XML>
```
