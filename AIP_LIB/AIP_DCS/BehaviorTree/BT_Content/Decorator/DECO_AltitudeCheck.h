#pragma once

#include "../../behaviortree_cpp_v3/action_node.h"
#include "../../behaviortree_cpp_v3/bt_factory.h"
#include "../BlackBoard/CPPBlackBoard.h"

using namespace BT;

namespace Action
{
	class DECO_AltitudeCheck : public SyncActionNode
	{
	public:
		DECO_AltitudeCheck(const std::string& name, const NodeConfiguration& config) : SyncActionNode(name, config) {}
		static PortsList providedPorts();
		NodeStatus tick() override;
	};
}
