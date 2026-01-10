//------------------------------------------------------------------------------
// <copyright project="BEmu_cpp" file="src/HistoricalDataRequest/HistoricMessage.cpp" company="Jordan Robinson">
//     Copyright (c) 2013 Jordan Robinson. All rights reserved.
//
//     The use of this software is governed by the Microsoft Public License
//     which is included with this distribution.
// </copyright>
//------------------------------------------------------------------------------

#include "HistoricalDataRequest/HistoricMessage.h"
#include "HistoricalDataRequest/HistoricElementSecurityData.h"
#include "BloombergTypes/ElementPtr.h"
#include "BloombergTypes/Name.h"
#include <cstring>
#include <ostream>

namespace BEmu
{
	namespace HistoricalDataRequest
	{
		HistoricMessage::HistoricMessage(
					const CorrelationId& corr, 
					const std::string& securityName, 
					const std::vector<std::string>& badFields, 
					const std::map<Datetime, std::map<std::string, ObjectType>>& fieldData, 
					int sequenceNumber) : 
			MessagePtr(Name("HistoricalDataResponse"), corr),
			_security(new HistoricElementSecurityData(securityName, badFields, fieldData, sequenceNumber))
		{
		}

		HistoricMessage::~HistoricMessage()
		{
		}

		std::shared_ptr<ElementPtr> HistoricMessage::getElement(const char* name) const
		{
			if(strncmp(name, "securityData", 13) == 0)
				return std::dynamic_pointer_cast<ElementPtr>(this->_security);

			else
				throw messageEx;
		}

		bool HistoricMessage::hasElement(const char* name, bool excludeNullElements) const
		{
			return strncmp(name, "securityData", 13) == 0;
		}

		std::ostream& HistoricMessage::print(std::ostream& stream, int level, int spacesPerLevel) const
		{
			stream << "HistoricalDataResponse (choice) = {" << std::endl;
			this->_security->print(stream, 1, spacesPerLevel);
			stream << '}' << std::endl;

			return stream;
		}

	}
}