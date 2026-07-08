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
	if (!radiusInput->empty())
	{
		try
		{
			radius = std::stod(radiusInput.value());
		}
		catch (...)
		{
		}
	}
	if (!speedInput->empty())
	{
		try
		{
			speed = std::stod(speedInput.value());
		}
		catch (...)
		{
		}
	}

	Vector3 base = blackboard->MyLocation_Cartesian;
	Vector3 forward = SafeDirection(blackboard->MyForwardVector, Vector3(1.0, 0.0, 0.0));
	Vector3 right = SafeDirection(blackboard->MyRightVector, Vector3(0.0, 1.0, 0.0));
	Vector3 vp = base;
	vp.Z = base.Z;

	if (pattern == "Figure8")
	{
		double t = std::max(0.0, blackboard->RunningTime * speed);
		double phase = t;
		double x = std::sin(phase) * radius;
		double y = std::sin(phase * 2.0) * (radius * 0.45);
		vp = base + right * x + forward * y;
		vp.Z = base.Z;
	}
	else if (pattern == "Circle")
	{
		double t = std::max(0.0, blackboard->RunningTime * speed);
		double theta = t * 0.8;
		vp = base + right * std::cos(theta) * radius + forward * std::sin(theta) * radius;
		vp.Z = base.Z;
	}
	else if (pattern == "CircleVertical")
	{
		double t = std::max(0.0, blackboard->RunningTime * speed);
		double theta = t * 0.8;
		// Vertical circle in plane (forward, up)
		Vector3 up = SafeDirection(blackboard->MyUpVector, Vector3(0.0, 0.0, 1.0));
		vp = base + forward * std::cos(theta) * radius + up * std::sin(theta) * radius;
	}
	else
	{
		vp = base + forward * std::max(1000.0, radius * 2.0);
		vp.Z = base.Z;
	}

	blackboard->VP_Cartesian = vp;
	blackboard->Throttle = 1.0f;

	return NodeStatus::SUCCESS;
}
