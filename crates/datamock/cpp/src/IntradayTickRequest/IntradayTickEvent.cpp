//------------------------------------------------------------------------------------------------
// <copyright project="BEmu_cpp" file="src/IntradayTickRequest/IntradayTickEvent.cpp" company="Jordan Robinson">
//     Copyright (c) 2013 Jordan Robinson. All rights reserved.
//
//     The use of this software is governed by the Microsoft Public License
//     which is included with this distribution.
// </copyright>
//------------------------------------------------------------------------------------------------

#include "BloombergTypes/Name.h"
#include "BloombergTypes/ElementPtr.h"
#include "IntradayTickRequest/IntradayTickEvent.h"
#include "IntradayTickRequest/IntradayTickRequest.h"
#include "IntradayTickRequest/IntradayTickMessage.h"
#include "IntradayTickRequest/IntradayTickElementTuple3.h"
#include "BloombergTypes/RequestPtr.h"
#include "BloombergTypes/MessagePtr.h"
#include "BloombergTypes/Datetime.h"
#include "Types/Rules.h"
#include "Types/RandomDataGenerator.h"
#include <map>

namespace BEmu
{
	namespace IntradayTickRequest
	{
		IntradayTickEvent::IntradayTickEvent(const std::shared_ptr<IntradayTickRequest>& request) :
			EventPtr(std::dynamic_pointer_cast<RequestPtr>(request)),
			_internalP(request)
		{
			this->_messages = this->GenerateMessages();
		}

		IntradayTickEvent::~IntradayTickEvent()
		{
			this->_messages.clear();
		}

		std::vector< std::shared_ptr<MessagePtr> > IntradayTickEvent::getMessages() const
		{
			return this->_messages;
		}

		std::vector< std::shared_ptr<MessagePtr> > IntradayTickEvent::GenerateMessages() const
		{
			std::vector< std::shared_ptr<MessagePtr> > result;

			std::string security = this->_internalP->security();
			bool isResponseError = Rules::IsSecurityError(security);

			if (isResponseError)
            {
				std::shared_ptr<IntradayTickMessage> mspIP(new IntradayTickMessage(this->_internalP->getCorrelationId(), this->_internalP->getService()));
				std::shared_ptr<MessagePtr> msgP(std::dynamic_pointer_cast<MessagePtr>(mspIP));

				result.push_back(msgP);
            }
			else
			{
				std::map<Datetime, IntradayTickElementTuple3> tickData;

				if(this->_internalP->hasStartDate())
				{
					std::vector<Datetime> dates = this->_internalP->getDates();

for(unsigned i = 0; i < dates.size(); i++)
					{
						Datetime dt = dates.at(i);
						Datetime::WeekDayEnum wd = dt.getWeekDay();

						if( (wd != Datetime::Sunday) && (wd != Datetime::Saturday) )
						{
							// Add random milliseconds and microseconds for sub-second precision
							dt.setMilliseconds(RandomDataGenerator::RandomInt(0, 999));
							dt.setMicroseconds(RandomDataGenerator::RandomInt(0, 999));
							
							IntradayTickElementTuple3 t3("TRADE", RandomDataGenerator::RandomDouble(), RandomDataGenerator::IntradayTickTradeSize());
							tickData[dt] = t3;
						}
					}

					std::shared_ptr<IntradayTickMessage> mspIP(new IntradayTickMessage(this->_internalP->getCorrelationId(), this->_internalP->getService(), tickData, this->_internalP->includeConditionCodes()));
					std::shared_ptr<MessagePtr> msgP(std::dynamic_pointer_cast<MessagePtr>(mspIP));

					result.push_back(msgP);
				}
			}
			
			return result;
		}

	}
}