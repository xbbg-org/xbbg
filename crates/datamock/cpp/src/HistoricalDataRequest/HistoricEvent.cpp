//------------------------------------------------------------------------------
// <copyright project="BEmu_cpp" file="src/HistoricalDataRequest/HistoricEvent.cpp" company="Jordan Robinson">
//     Copyright (c) 2013 Jordan Robinson. All rights reserved.
//
//     The use of this software is governed by the Microsoft Public License
//     which is included with this distribution.
// </copyright>
//------------------------------------------------------------------------------

#include "HistoricalDataRequest/HistoricEvent.h"
#include "HistoricalDataRequest/HistoricRequest.h"
#include "HistoricalDataRequest/HistoricMessage.h"
#include "BloombergTypes/Datetime.h"
#include "Types/ObjectType.h"
#include "Types/Rules.h"
#include "Types/RandomDataGenerator.h"

namespace BEmu
{
	namespace HistoricalDataRequest
	{
		HistoricEvent::HistoricEvent(std::shared_ptr<HistoricRequest> request) : 
			EventPtr(std::dynamic_pointer_cast<RequestPtr>(request)),
			_internalP(request)
		{
			this->_messages = this->GenerateMessages();
		}

		HistoricEvent::~HistoricEvent()
		{
			this->_messages.clear();
		}

		std::vector< std::shared_ptr<MessagePtr> > HistoricEvent::getMessages() const
		{
			return this->_messages;
		}

		std::vector< std::shared_ptr<MessagePtr> > HistoricEvent::GenerateMessages() const
		{
			std::vector< std::shared_ptr<MessagePtr> > result;

			std::vector<std::string> badFields;
			std::vector<std::string> rfields(this->_internalP->fields());
			for(std::vector<std::string>::const_iterator iterField = rfields.begin(); iterField != rfields.end(); ++iterField)
			{
				std::string field = *iterField;

				if(Rules::IsBadField(field))
					badFields.push_back(field);
			}

			std::vector<std::string> securities(this->_internalP->securities());
			for(std::vector<std::string>::const_iterator iterSec = securities.begin(); iterSec != securities.end(); ++iterSec)
			{
				std::string sec = *iterSec;

				std::map<Datetime, std::map<std::string, ObjectType>> fieldData;

				if(this->_internalP->hasStartDate())
				{
					Datetime dtStart = this->_internalP->dtStart();
					std::vector<Datetime> dates = this->_internalP->getDates();

					for(std::vector<Datetime>::const_iterator iterDate = dates.begin(); iterDate != dates.end(); ++iterDate)
					{
						Datetime date = *iterDate;
						if(date.getWeekDay() != Datetime::Saturday && date.getWeekDay() != Datetime::Sunday)
						{
							std::map<std::string, ObjectType> fields;
							for(std::vector<std::string>::const_iterator iterField2 = rfields.begin(); iterField2 != rfields.end(); ++iterField2)
							{
								std::string field2 = *iterField2;

								if(!Rules::IsBadField(field2))
									fields[field2] = ObjectType(RandomDataGenerator::RandomDouble());
							}

							fieldData[date] = fields;
						}
					}

					std::shared_ptr<HistoricMessage> msgHP(new HistoricMessage(this->_internalP->getCorrelationId(), sec, badFields, fieldData, result.size()));
					std::shared_ptr<MessagePtr> msg(std::dynamic_pointer_cast<MessagePtr>(msgHP));
					result.push_back(msg);
				}
			}

			return result;
		}

	}
}