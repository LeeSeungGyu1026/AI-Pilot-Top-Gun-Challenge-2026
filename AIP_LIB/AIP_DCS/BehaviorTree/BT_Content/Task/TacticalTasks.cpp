#include "TacticalTasks.h"

#include <algorithm>
#include <cmath>
#include <string>

using namespace BT_Geometry;

namespace
{
	constexpr double kDefaultLookAhead = 4500.0;
	constexpr double kMinVectorLength = 1.0e-3;
	// Hard altitude floor for every commanded waypoint, evasive maneuvers included.
	// The tree-level LowAltitudeCheck/ClimbRecover pair and each task's own low-
	// altitude bias only change what a task WANTS to command; a fast, high-energy
	// defensive dive can still out-run that reactive logic before the aircraft
	// physically arrests its descent. Clamping every commanded Z here at the single
	// chokepoint (SetCommand) guarantees no task can ever aim the aircraft below
	// this floor in the first place, regardless of which maneuver is running.
	// Raised 900->1800 (2026-07-03): 900 gave a real engagement (RearThreatJink
	// under the offensive_saddle spawn) less than a second between crossing the
	// floor and hitting the true 300m termination floor once a fast sink was
	// already underway -- not enough margin regardless of trigger logic. See the
	// paired fix in Task_RearThreatJink::tick() removing that task's intentional
	// dive bias, which is the primary fix; this is defense in depth.
	constexpr double kHardAltitudeFloor = 1800.0;

	Vector3 WorldUp() // 월드 상의 z방향
	{
		return Vector3(0.0, 0.0, 1.0);
	}

	Vector3 SafeDirection(Vector3 value, Vector3 fallback) // 방향 벡터 정상화&정규화 하는 함수
	{
		if (value.length() < kMinVectorLength) // 벡터의 크기가 너무 작으면 폴백
		{
			// 폴백 값은 함수 호출할 때 줌. 비정상 시 대체할 변수 넣음
			value = fallback;
		}

		if (value.length() < kMinVectorLength) // 
		{
			value = Vector3(1.0, 0.0, 0.0);
		}

		value.normalize();
		return value;
	}

	double ReadDouble(const NodeConfiguration& config, const std::string& key, double defaultValue)
	{
		auto it = config.input_ports.find(key);
		if (it == config.input_ports.end())
		{
			return defaultValue;
		}

		try
		{
			return std::stod(it->second);
		}
		catch (...)
		{
			return defaultValue;
		}
	}

	void SetCommand(CPPBlackBoard* BB, const Vector3& VP, float throttle)
	{
		Vector3 clamped = VP;
		clamped.Z = std::max(clamped.Z, kHardAltitudeFloor);
		BB->VP_Cartesian = clamped;
		BB->Throttle = std::max(0.0f, std::min(1.0f, throttle));
	}

	Vector3 TargetDirection(CPPBlackBoard* BB) // 적군까지의 벡터
	{
		Vector3 toTarget = BB->TargetLocaion_Cartesian - BB->MyLocation_Cartesian;
		return SafeDirection(toTarget, BB->MyForwardVector); // 폴백은 내가 바라보고 있는 방향
	}

	Vector3 TargetForward(CPPBlackBoard* BB)
	{
		return SafeDirection(BB->TargetForwardVector, TargetDirection(BB)); // 폴백은 적군방향
	}

	Vector3 OwnForward(CPPBlackBoard* BB)
	{
		return SafeDirection(BB->MyForwardVector, TargetDirection(BB));
	}

	Vector3 OwnRight(CPPBlackBoard* BB)
	{
		return SafeDirection(BB->MyRightVector, Vector3(0.0, 1.0, 0.0));
	}
}

namespace Action
{
	PortsList Task_LeadPursuit::providedPorts()
	{
		return {
			InputPort<CPPBlackBoard*>("BB"),
			InputPort<std::string>("MaxLeadDistance"),
			InputPort<std::string>("VerticalOffset")
		};
	}

	NodeStatus Task_LeadPursuit::tick()
	{
		Optional<CPPBlackBoard*> BBInput = getInput<CPPBlackBoard*>("BB");
		CPPBlackBoard* BB = BBInput.value();

		double maxLead = ReadDouble(config(), "MaxLeadDistance", 2400.0);
		double verticalOffset = ReadDouble(config(), "VerticalOffset", 120.0);
		double distance = std::max(0.0f, BB->Distance);
		double ownSpeed = std::max(120.0f, BB->MySpeed_MS);
		double leadTime = std::max(0.8, std::min(4.0, distance / ownSpeed));

		Vector3 lead = TargetForward(BB) * (BB->TargetSpeed_MS * leadTime);
		if (lead.length() > maxLead)
		{
			lead = SafeDirection(lead, TargetDirection(BB)) * maxLead;
		}

		Vector3 vp = BB->TargetLocaion_Cartesian + lead + WorldUp() * verticalOffset;
		SetCommand(BB, vp, 1.0f);
		return NodeStatus::SUCCESS;
	}

	PortsList Task_LagPursuit::providedPorts()
	{
		return {
			InputPort<CPPBlackBoard*>("BB"),
			InputPort<std::string>("LagDistance"),
			InputPort<std::string>("VerticalOffset")
		};
	}

	NodeStatus Task_LagPursuit::tick()
	{
		Optional<CPPBlackBoard*> BBInput = getInput<CPPBlackBoard*>("BB");
		CPPBlackBoard* BB = BBInput.value();

		double lagDistance = ReadDouble(config(), "LagDistance", 900.0);
		double verticalOffset = ReadDouble(config(), "VerticalOffset", 180.0);
		Vector3 vp = BB->TargetLocaion_Cartesian - TargetForward(BB) * lagDistance + WorldUp() * verticalOffset;

		SetCommand(BB, vp, 0.85f);
		return NodeStatus::SUCCESS;
	}

	PortsList Task_Extend::providedPorts()
	{
		return {
			InputPort<CPPBlackBoard*>("BB"),
			InputPort<std::string>("ExtendDistance"),
			InputPort<std::string>("VerticalOffset")
		};
	}

	NodeStatus Task_Extend::tick()
	{
		Optional<CPPBlackBoard*> BBInput = getInput<CPPBlackBoard*>("BB");
		CPPBlackBoard* BB = BBInput.value();

		double extendDistance = ReadDouble(config(), "ExtendDistance", kDefaultLookAhead);
		double verticalOffset = ReadDouble(config(), "VerticalOffset", 500.0);
		Vector3 away = SafeDirection(BB->MyLocation_Cartesian - BB->TargetLocaion_Cartesian, OwnForward(BB));
		Vector3 extendDirection = SafeDirection(away * 0.70 + OwnForward(BB) * 0.30, away);
		Vector3 vp = BB->MyLocation_Cartesian + extendDirection * extendDistance + WorldUp() * verticalOffset;

		SetCommand(BB, vp, 1.0f);
		return NodeStatus::SUCCESS;
	}

	PortsList Task_DefensiveBreak::providedPorts()
	{
		return {
			InputPort<CPPBlackBoard*>("BB"),
			InputPort<std::string>("BreakDistance"),
			InputPort<std::string>("VerticalOffset")
		};
	}

	NodeStatus Task_DefensiveBreak::tick() // 적군과 거리가 많이 가깝고, LOS가 55도 미만
	// 적이랑 가깝고, 좀 불리한 상황(기하적으로)에서 벗어나소, 기울기 바꾸는 행동
	{
		Optional<CPPBlackBoard*> BBInput = getInput<CPPBlackBoard*>("BB");
		CPPBlackBoard* BB = BBInput.value();

		double breakDistance = ReadDouble(config(), "BreakDistance", 5200.0); // 
		double verticalOffset = ReadDouble(config(), "VerticalOffset", 650.0);
		Vector3 toTarget = BB->TargetLocaion_Cartesian - BB->MyLocation_Cartesian;
		// SafeDirection은 무슨 방향이든 정상적인&정규화된 값 반환
		// 타겟이 위치한 방향 (좌/우 등)
		double lateralDot = SafeDirection(toTarget, OwnForward(BB) * -1.0).dot(OwnRight(BB));
		double side = 0.0;
		if (std::abs(lateralDot) > 0.08)
		{
			side = (lateralDot >= 0.0) ? 1.0 : -1.0; // 여기서 좌/우 갈리는 듯
		}
		else
		{
			side = (std::fmod(std::max(0.0, BB->RunningTime), 6.0) < 3.0) ? 1.0 : -1.0;
		}
		double climbBias = (BB->MyLocation_Cartesian.Z < 1400.0) ? 0.50 : 0.0;
		Vector3 breakDirection = SafeDirection(OwnRight(BB) * side * 1.65 - OwnForward(BB) * 0.10 + WorldUp() * climbBias, OwnRight(BB) * side);
		// vp는 목표 point
		Vector3 vp = BB->MyLocation_Cartesian + breakDirection * breakDistance + WorldUp() * verticalOffset;
		if (BB->MyLocation_Cartesian.Z < 1400.0)
		{
			vp.Z = std::max(vp.Z, 1750.0);
		}
		// 기하적으로 불리한 상황에서, 이 상황을 탈출할 먼 지점 하나(vp)를 목표지점으로 찍음
		SetCommand(BB, vp, 1.0f);
		return NodeStatus::SUCCESS;
	}

	PortsList Task_RearThreatJink::providedPorts()
	{
		return {
			InputPort<CPPBlackBoard*>("BB"),
			InputPort<std::string>("LateralDistance"),
			InputPort<std::string>("ForwardDistance"),
			InputPort<std::string>("VerticalOffset")
		};
	}

	NodeStatus Task_RearThreatJink::tick()
	{
		Optional<CPPBlackBoard*> BBInput = getInput<CPPBlackBoard*>("BB");
		CPPBlackBoard* BB = BBInput.value();

		double lateralDistance = ReadDouble(config(), "LateralDistance", 5200.0);
		double forwardDistance = ReadDouble(config(), "ForwardDistance", 1400.0);
		double verticalOffset = ReadDouble(config(), "VerticalOffset", 850.0);

		Vector3 toThreat = SafeDirection(BB->TargetLocaion_Cartesian - BB->MyLocation_Cartesian, OwnForward(BB) * -1.0);
		Vector3 lateral = SafeDirection(toThreat.cross(WorldUp()), OwnRight(BB));
		double side = (toThreat.dot(OwnRight(BB)) >= 0.0) ? -1.0 : 1.0;
		if (std::abs(toThreat.dot(OwnRight(BB))) < 0.08)
		{
			side = (std::fmod(std::max(0.0, BB->RunningTime), 4.0) < 2.0) ? 1.0 : -1.0;
		}

		// Was -0.45 at high altitude (deliberate dive to break lock). Root-caused
		// 2026-07-03: this task fires almost immediately under the offensive_saddle
		// spawn (RL starts locked on at the BT's six, well inside this task's
		// range/LOS triggers), and the resulting commanded dive was observed to
		// degenerate into a near-vertical (~-80 to -89 deg pitch), erratic-roll,
		// ~2500 m/s "descent" straight through every altitude safeguard (900m
		// SetCommand floor, 1200/1600m internal clamp, 900/1500m tree-level
		// ClimbRecover) in under a second once it started -- a control/FDM
		// degeneracy this task's own logic cannot out-run once triggered, not
		// merely a "recovers too late" issue. Fix at the source: never command an
		// intentional altitude LOSS here, only a lateral/forward break.
		double lowAltitudeBias = (BB->MyLocation_Cartesian.Z < 1400.0) ? 1.0 : 0.0;
		Vector3 vertical = WorldUp() * (verticalOffset * lowAltitudeBias);
		Vector3 unload = OwnForward(BB) * forwardDistance;
		Vector3 breakDirection = SafeDirection(lateral * side * 1.25 - toThreat * 0.35 + WorldUp() * lowAltitudeBias * 0.35, lateral * side);
		Vector3 vp = BB->MyLocation_Cartesian + breakDirection * lateralDistance + unload + vertical;

		// Raised margin (was 1200/1600) -- defense in depth in case some other
		// path still induces a fast sink; more altitude means more time to arrest it.
		if (BB->MyLocation_Cartesian.Z < 2200.0)
		{
			vp.Z = std::max(vp.Z, 3000.0);
		}

		SetCommand(BB, vp, 1.0f);
		return NodeStatus::SUCCESS;
	}

	PortsList Task_Recommit::providedPorts()
	{
		return {
			InputPort<CPPBlackBoard*>("BB"),
			InputPort<std::string>("LeadDistance"),
			InputPort<std::string>("VerticalOffset")
		};
	}

	NodeStatus Task_Recommit::tick()
	{
		Optional<CPPBlackBoard*> BBInput = getInput<CPPBlackBoard*>("BB");
		CPPBlackBoard* BB = BBInput.value();

		double leadDistance = ReadDouble(config(), "LeadDistance", 1600.0);
		double verticalOffset = ReadDouble(config(), "VerticalOffset", 120.0);
		Vector3 toTarget = TargetDirection(BB);
		Vector3 targetFuture = BB->TargetLocaion_Cartesian + TargetForward(BB) * leadDistance;
		Vector3 inside = SafeDirection(toTarget * 0.70 + TargetForward(BB) * 0.30, toTarget);
		Vector3 vp = targetFuture + inside * 600.0 + WorldUp() * verticalOffset;

		SetCommand(BB, vp, 1.0f);
		return NodeStatus::SUCCESS;
	}

	PortsList Task_LowYoYo::providedPorts()
	{
		return {
			InputPort<CPPBlackBoard*>("BB"),
			InputPort<std::string>("DiveOffset"),
			InputPort<std::string>("PullLeadDistance"),
			InputPort<std::string>("MinAltitude")
		};
	}

	NodeStatus Task_LowYoYo::tick()
	{   // 최소 고도까지는 올라오게 보장하고, 적군의 정면방향벡터랑 
		
		Optional<CPPBlackBoard*> BBInput = getInput<CPPBlackBoard*>("BB");
		CPPBlackBoard* BB = BBInput.value();

		double diveOffset = ReadDouble(config(), "DiveOffset", 650.0);
		double pullLeadDistance = ReadDouble(config(), "PullLeadDistance", 1200.0);
		double minAltitude = ReadDouble(config(), "MinAltitude", 1300.0);
		Vector3 toTarget = TargetDirection(BB); // 나->적 벡터
		Vector3 targetLead = BB->TargetLocaion_Cartesian + TargetForward(BB) * pullLeadDistance;
		Vector3 vp = targetLead + toTarget * 900.0 - WorldUp() * diveOffset;
		if (BB->MyLocation_Cartesian.Z < minAltitude + 500.0)
		{
			vp.Z = std::max(vp.Z, minAltitude + 500.0);
		}

		SetCommand(BB, vp, 1.0f); // 적이 가게 될 위치(targetLead)보다 조금 낮게, 적에게 더 가깝게 vp설정
		return NodeStatus::SUCCESS;
	}

	PortsList Task_ClimbRecover::providedPorts()
	{
		return {
			InputPort<CPPBlackBoard*>("BB"),
			InputPort<std::string>("MinAltitude"),
			InputPort<std::string>("ForwardDistance")
		};
	}

	NodeStatus Task_ClimbRecover::tick()
	{
		Optional<CPPBlackBoard*> BBInput = getInput<CPPBlackBoard*>("BB");
		CPPBlackBoard* BB = BBInput.value();

		double minAltitude = ReadDouble(config(), "MinAltitude", 1500.0);
		double forwardDistance = ReadDouble(config(), "ForwardDistance", kDefaultLookAhead);
		Vector3 vp = BB->MyLocation_Cartesian + OwnForward(BB) * forwardDistance;
		vp.Z = std::max(vp.Z + 900.0, minAltitude);

		SetCommand(BB, vp, 1.0f);
		return NodeStatus::SUCCESS;
	}
}
