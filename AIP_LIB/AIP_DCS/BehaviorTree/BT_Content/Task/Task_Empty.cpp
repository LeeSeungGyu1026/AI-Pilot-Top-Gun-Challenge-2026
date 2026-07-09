#include "Task_Empty.h"

#include <algorithm>
#include <cmath>
#include <string>

namespace
{
	Vector3 SafeDirection(Vector3 value, Vector3 fallback)
	{
		const double minLength = 1.0e-3;
		if (value.length() < minLength)
		{
			value = fallback;
		}
		if (value.length() < minLength)
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

	double ClampDouble(double value, double minValue, double maxValue)
	{
		return std::max(minValue, std::min(maxValue, value));
	}

	double NormalizeDegrees(double degrees)
	{
		while (degrees > 180.0)
		{
			degrees -= 360.0;
		}
		while (degrees < -180.0)
		{
			degrees += 360.0;
		}
		return degrees;
	}

	float BankHoldCommand(double currentRollDeg, double desiredRollDeg)
	{
		const double errorDeg = NormalizeDegrees(desiredRollDeg - currentRollDeg);
		return static_cast<float>(ClampDouble(errorDeg * 0.035, -0.45, 0.45));
	}

	float AltitudeHoldPitch(double currentAltitude, double desiredAltitude, double basePitch)
	{
		const double altitudeError = desiredAltitude - currentAltitude;
		const double correction = ClampDouble(altitudeError / 1400.0, -0.26, 0.42);
		return static_cast<float>(ClampDouble(basePitch - correction, -0.60, 0.18));
	}

	double CircleBankDegrees(double speedMps, double radiusMeters)
	{
		const double gravity = 9.80665;
		const double safeSpeed = std::max(120.0, speedMps);
		const double safeRadius = std::max(900.0, radiusMeters);
		const double bankRadians = std::atan((safeSpeed * safeSpeed) / (gravity * safeRadius));
		return ClampDouble(bankRadians * 180.0 / 3.14159265358979323846, 45.0, 72.0);
	}
}

PortsList Action::Task_Empty::providedPorts()
{
	return {
			InputPort<CPPBlackBoard*>("BB"),
			InputPort<std::string>("Pattern"),
			InputPort<std::string>("Radius"),
			InputPort<std::string>("Speed")
	};
}

NodeStatus Action::Task_Empty::tick()
{
	Optional<CPPBlackBoard*> BB = getInput<CPPBlackBoard*>("BB");
	Optional<std::string> patternInput = getInput<std::string>("Pattern");
	Optional<std::string> radiusInput = getInput<std::string>("Radius");
	Optional<std::string> speedInput = getInput<std::string>("Speed");

	CPPBlackBoard* blackboard = BB.value();
	std::string pattern = patternInput.value_or("Straight");
	double radius = ReadDouble(config(), "Radius", 1800.0);
	double speed = ReadDouble(config(), "Speed", 1.0);
	if (radiusInput && !radiusInput.value().empty())
	{
		try
		{
			radius = std::stod(radiusInput.value());
		}
		catch (...)
		{
		}
	}
	if (speedInput && !speedInput.value().empty())
	{
		try
		{
			speed = std::stod(speedInput.value());
		}
		catch (...)
		{
		}
	}

	radius = std::max(300.0, radius);
	speed = std::max(0.05, speed);

	Vector3 current = blackboard->MyLocation_Cartesian;
	Vector3 forward = SafeDirection(blackboard->MyForwardVector, Vector3(1.0, 0.0, 0.0));
	Vector3 right = SafeDirection(blackboard->MyRightVector, Vector3(0.0, 1.0, 0.0));
	Vector3 up = SafeDirection(blackboard->MyUpVector, Vector3(0.0, 0.0, 1.0));
	const double ownSpeed = std::max(120.0f, blackboard->MySpeed_MS);

	if (!blackboard->PatternAnchorInitialized)
	{
		blackboard->PatternAnchorInitialized = true;
		blackboard->PatternOrigin_Cartesian = current;
		blackboard->PatternForwardVector = forward;
		blackboard->PatternRightVector = right;
		blackboard->PatternUpVector = up;
	}

	Vector3 origin = blackboard->PatternOrigin_Cartesian;
	Vector3 anchorForward = SafeDirection(blackboard->PatternForwardVector, forward);
	Vector3 anchorRight = SafeDirection(blackboard->PatternRightVector, right);
	Vector3 anchorUp = SafeDirection(blackboard->PatternUpVector, up);
	Vector3 vp = current;
	const double t = std::max(0.0, blackboard->RunningTime * speed);
	const double currentRollDeg = blackboard->MyRotation_EDegree.Roll;
	const double patternAltitude = origin.Z;
	float rollCmd = 0.0f;
	float pitchCmd = 0.0f;
	float rudderCmd = 0.0f;
	float throttleCmd = 1.0f;
	bool useDirectPatternControl = true;

	if (pattern == "Figure8")
	{
		double phase = t * 0.65;
		double x = std::sin(phase) * radius;
		double y = std::sin(phase * 2.0) * (radius * 0.45);
		double lead = std::max(900.0, radius * 0.65);
		vp = origin + anchorRight * x + anchorForward * (y + lead);
		vp.Z = origin.Z;
		double desiredBank = std::sin(phase) * 28.0;
		rollCmd = BankHoldCommand(currentRollDeg, desiredBank);
		pitchCmd = AltitudeHoldPitch(current.Z, patternAltitude, -0.06);
		rudderCmd = static_cast<float>(ClampDouble(-std::sin(phase) * 0.08, -0.12, 0.12));
	}
	else if (pattern == "Circle")
	{
		double theta = 0.75 + t * 0.45;
		Vector3 center = origin + anchorRight * radius;
		vp = center + anchorRight * (-std::cos(theta) * radius) + anchorForward * (std::sin(theta) * radius);
		vp.Z = origin.Z;
		const double desiredBank = CircleBankDegrees(ownSpeed, radius);
		rollCmd = BankHoldCommand(currentRollDeg, desiredBank);
		pitchCmd = AltitudeHoldPitch(current.Z, patternAltitude, -0.24);
		rudderCmd = -0.06f;
		throttleCmd = 0.56f;
	}
	else if (pattern == "CircleVertical")
	{
		double theta = 0.65 + t * 0.35;
		Vector3 center = origin + anchorUp * radius;
		vp = center + anchorUp * (-std::cos(theta) * radius) + anchorForward * (std::sin(theta) * radius);
		useDirectPatternControl = false;
		rollCmd = BankHoldCommand(currentRollDeg, 0.0);
		pitchCmd = static_cast<float>(ClampDouble(-std::sin(theta) * 0.28, -0.35, 0.20));
		rudderCmd = 0.0f;
		throttleCmd = 1.0f;
	}
	else
	{
		vp = current + forward * std::max(1500.0, radius * 2.0);
		vp.Z = current.Z;
		rollCmd = BankHoldCommand(currentRollDeg, 0.0);
		pitchCmd = AltitudeHoldPitch(current.Z, patternAltitude, 0.0);
		rudderCmd = 0.0f;
	}

	blackboard->VP_Cartesian = vp;
	blackboard->Throttle = throttleCmd;
	blackboard->ControlOverrideEnabled = useDirectPatternControl;
	blackboard->OverrideRollCMD = rollCmd;
	blackboard->OverridePitchCMD = pitchCmd;
	blackboard->OverrideRudderCMD = rudderCmd;

	return NodeStatus::SUCCESS;
}
