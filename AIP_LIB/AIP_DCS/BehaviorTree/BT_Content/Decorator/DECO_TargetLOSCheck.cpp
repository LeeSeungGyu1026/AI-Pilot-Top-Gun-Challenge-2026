#include "DECO_TargetLOSCheck.h"

#include <string>

namespace Action
{
	PortsList DECO_TargetLOSCheck::providedPorts()
	{
		return {
			InputPort<CPPBlackBoard*>("BB"),
			InputPort<std::string>("UpDown"),
			InputPort<std::string>("InputLOS")
		};
	}

	NodeStatus DECO_TargetLOSCheck::tick()
	{
		Optional<CPPBlackBoard*> BB = getInput<CPPBlackBoard*>("BB");
		Optional<std::string> UpOrDown = getInput<std::string>("UpDown");
		Optional<std::string> Los = getInput<std::string>("InputLOS");

		float currentLOS = (*BB)->Los_Degree_Target;
		std::string compareMode = UpOrDown.value();
		float inputLOS = std::stof(Los.value());

		if (compareMode == "Greater")
		{
			return (currentLOS >= inputLOS) ? NodeStatus::SUCCESS : NodeStatus::FAILURE;
		}

		if (compareMode == "Less")
		{
			return (currentLOS <= inputLOS) ? NodeStatus::SUCCESS : NodeStatus::FAILURE;
		}

		return NodeStatus::FAILURE;
	}
}
