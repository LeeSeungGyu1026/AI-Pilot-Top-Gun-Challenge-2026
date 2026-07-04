#pragma once

#include "../../behaviortree_cpp_v3/action_node.h"
#include "../../behaviortree_cpp_v3/bt_factory.h"
#include "../../../Geometry/Vector3.h"
#include "../BlackBoard/CPPBlackBoard.h"

using namespace BT;

namespace Action
{
	class Task_LeadPursuit : public SyncActionNode
	{
	public:
		Task_LeadPursuit(const std::string& name, const NodeConfiguration& config) : SyncActionNode(name, config) {}
		static PortsList providedPorts();
		NodeStatus tick() override;
	};

	class Task_LagPursuit : public SyncActionNode
	{
	public:
		Task_LagPursuit(const std::string& name, const NodeConfiguration& config) : SyncActionNode(name, config) {}
		static PortsList providedPorts();
		NodeStatus tick() override;
	};

	class Task_Extend : public SyncActionNode
	{
	public:
		Task_Extend(const std::string& name, const NodeConfiguration& config) : SyncActionNode(name, config) {}
		static PortsList providedPorts();
		NodeStatus tick() override;
	};

	class Task_DefensiveBreak : public SyncActionNode
	{
	public:
		Task_DefensiveBreak(const std::string& name, const NodeConfiguration& config) : SyncActionNode(name, config) {}
		static PortsList providedPorts();
		NodeStatus tick() override;
	};

	class Task_RearThreatJink : public SyncActionNode
	{
	public:
		Task_RearThreatJink(const std::string& name, const NodeConfiguration& config) : SyncActionNode(name, config) {}
		static PortsList providedPorts();
		NodeStatus tick() override;
	};

	class Task_Recommit : public SyncActionNode
	{
	public:
		Task_Recommit(const std::string& name, const NodeConfiguration& config) : SyncActionNode(name, config) {}
		static PortsList providedPorts();
		NodeStatus tick() override;
	};

	class Task_LowYoYo : public SyncActionNode
	{
	public:
		Task_LowYoYo(const std::string& name, const NodeConfiguration& config) : SyncActionNode(name, config) {}
		static PortsList providedPorts();
		NodeStatus tick() override;
	};

	class Task_ClimbRecover : public SyncActionNode
	{
	public:
		Task_ClimbRecover(const std::string& name, const NodeConfiguration& config) : SyncActionNode(name, config) {}
		static PortsList providedPorts();
		NodeStatus tick() override;
	};
}
