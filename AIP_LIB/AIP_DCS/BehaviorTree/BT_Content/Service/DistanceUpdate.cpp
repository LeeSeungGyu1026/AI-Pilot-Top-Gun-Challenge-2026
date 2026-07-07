//타겟과의 거리 업데이트 노드

#include "DistanceUpdate.h"

namespace Action
{
	PortsList DistanceUpdate::providedPorts()
	{
		return {
			InputPort<CPPBlackBoard*>("BB")
		};
	}

	NodeStatus DistanceUpdate::tick()
	{
		Optional<CPPBlackBoard*> BB = getInput<CPPBlackBoard*>("BB");

		// My: 내 기체
		// Target: 타겟 기체
		Vector3 MyLocation = (*BB)->MyLocation_Cartesian;
		Vector3 TargetLocation = (*BB)->TargetLocaion_Cartesian;
		// 둘 사이 거리
		float Distance = MyLocation.distance(TargetLocation);
		
		(*BB)->Distance = Distance;

		//std::cout << "DistanceUpdate : " << TargetLocation.X << " " << TargetLocation.Y << " " << TargetLocation.Z << std::endl;
		// BTFunc::AddNodeExcute(&(*BB)->Temp_Text, 
		// 	std::string("Distance Update"));
		// BTFunc::AddNodeExcute(&(*BB)->Temp_Text, 
		// 	std::string("  -Distance :") + std::to_string(Distance) + "m");
		return NodeStatus::SUCCESS;
	}

}