#include "DECO_AltitudeCheck.h"

#include <string>

namespace Action
{
	PortsList DECO_AltitudeCheck::providedPorts()
	{
		return {
			InputPort<CPPBlackBoard*>("BB"),
			InputPort<std::string>("UpDown"),
			InputPort<std::string>("Altitude")
		};
	}

	NodeStatus DECO_AltitudeCheck::tick()
	{
		Optional<CPPBlackBoard*> BB = getInput<CPPBlackBoard*>("BB");
		Optional<std::string> UpOrDown = getInput<std::string>("UpDown");
		Optional<std::string> Alt = getInput<std::string>("Altitude");

		float currentAltitude = static_cast<float>((*BB)->MyLocation_Cartesian.Z);
		std::string compareMode = UpOrDown.value();
		float inputAltitude = std::stof(Alt.value());

		if (compareMode == "Greater")
		{
			return (currentAltitude >= inputAltitude) ? NodeStatus::SUCCESS : NodeStatus::FAILURE;
		}

		if (compareMode == "Less")
		{
			return (currentAltitude <= inputAltitude) ? NodeStatus::SUCCESS : NodeStatus::FAILURE;
		}

		return NodeStatus::FAILURE;
	}
}
