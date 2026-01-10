//------------------------------------------------------------------------------------------------
// <copyright project="BEmu_cpp" file="src/IntradayBarRequest/IntradayBarEvent.cpp" company="Jordan Robinson">
//     Copyright (c) 2013 Jordan Robinson. All rights reserved.
//
//     The use of this software is governed by the Microsoft Public License
//     which is included with this distribution.
// </copyright>
//------------------------------------------------------------------------------------------------

#include "IntradayBarRequest/IntradayBarMessage.h"
#include "IntradayBarRequest/IntradayBarEvent.h"
#include "IntradayBarRequest/IntradayBarRequest.h"
#include "BloombergTypes/MessagePtr.h"
#include "Types/Rules.h"
#include "Types/RandomDataGenerator.h"
#include <vector>

namespace BEmu
{
	namespace IntradayBarRequest
	{
		IntradayBarEvent::IntradayBarEvent(const std::shared_ptr<IntradayBarRequest>& request) :
			EventPtr(std::dynamic_pointer_cast<RequestPtr>(request)),
			_internalP(request)
		{
			this->_messages = this->GenerateMessages();
		}

		IntradayBarEvent::~IntradayBarEvent()
		{
			this->_messages.clear();
		}

		std::vector< std::shared_ptr<MessagePtr> > IntradayBarEvent::GenerateMessages() const
		{
			std::vector< std::shared_ptr<MessagePtr> > result;

			std::shared_ptr<IntradayBarRequest> ireq = this->_internalP;

			bool isSecurityError = Rules::IsSecurityError(ireq->security());
			if(isSecurityError)
			{
				std::shared_ptr<IntradayBarMessage> msgIP(new IntradayBarMessage(this->_internalP->getCorrelationId(), this->_internalP->getService(), this->_internalP->security()));
				std::shared_ptr<MessagePtr> msgP(std::dynamic_pointer_cast<MessagePtr>(msgIP));

				result.push_back(msgP);
			}
			else
			{
				std::vector< std::shared_ptr<IntradayBarTickDataType> > barData;

				if(ireq->hasStartDate())
				{
					std::vector<Datetime> datetimes = ireq->getDateTimes();
					for(std::vector<Datetime>::const_iterator iter = datetimes.begin(); iter != datetimes.end(); ++iter)
					{
						Datetime date = *iter;
						std::shared_ptr<IntradayBarTickDataType> bar( RandomDataGenerator::GenerateBarData(date) );						
						
						barData.push_back(bar);
					}
				}
				
				std::shared_ptr<IntradayBarMessage> msgIP(new IntradayBarMessage(this->_internalP->getCorrelationId(), ireq->getService(), barData));
				std::shared_ptr<MessagePtr> msgP(std::dynamic_pointer_cast<MessagePtr>(msgIP));

				result.push_back(msgP);
			}

			return result;
		}

		std::vector< std::shared_ptr<MessagePtr> > IntradayBarEvent::getMessages() const
		{
			return this->_messages;
		}

	}
}