#include "SelectTarget.h"

namespace Action
{
	PortsList SelectTarget::providedPorts()
	{
		return {
			InputPort<CPPBlackBoard*>("BB")
		};
	}



	NodeStatus SelectTarget::tick()
	{
		Optional<CPPBlackBoard*> BB = getInput<CPPBlackBoard*>("BB");

		//std::cout << "Size : " << (*BB)->Enemy.size() << std::endl;

		// Enemy에는 적기들 0,1,2 뭐 이런식으로 있는듯
		if((*BB)->Enemy.size() > 0)
		{
			(*BB)->ACM = EF;
			// 위치, 자세, 속도
			(*BB)->TargetLocaion_Cartesian = (*BB)->Enemy.at(0).Location;
			(*BB)->TargetRotation_EDegree = (*BB)->Enemy.at(0).Rotation;
			(*BB)->TargetSpeed_MS = (*BB)->Enemy.at(0).Speed;

		}
		else
		{ 
			//std::cout << "Ÿ���� ���� or Ÿ�ٰ��� ����� �ȵ���" << std::endl;
		}
				
		return NodeStatus::SUCCESS;
	}

}