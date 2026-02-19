//------------------------------------------------------------------------------
// <copyright project="BEmu_cpp" file="src/HistoricalDataRequest/HistoricElementDateTime.cpp" company="Jordan Robinson">
//     Copyright (c) 2013 Jordan Robinson. All rights reserved.
//
//     The use of this software is governed by the Microsoft Public License
//     which is included with this distribution.
// </copyright>
//------------------------------------------------------------------------------

#include "HistoricalDataRequest/HistoricElementDateTime.h"
#include "BloombergTypes/Name.h"
#include "Types/DisplayFormats.h"
#include <ostream>

namespace BEmu
{
	namespace HistoricalDataRequest
	{
		HistoricElementDateTime::HistoricElementDateTime(const Datetime& value) : CanConvertToStringType(DisplayFormats::HistoricalOrReferenceRequests_FormatDate(value))
		{
			this->_value = value;
		}

		HistoricElementDateTime::~HistoricElementDateTime()
		{
		}

		Name HistoricElementDateTime::name() const
		{
			return Name("date");
		}
				
		Datetime HistoricElementDateTime::getValueAsDatetime(int index) const
		{
			return this->_value;
		}

		const char * HistoricElementDateTime::getValueAsString(int index) const
		{
			return this->ValueAsString().c_str();
		}

		std::ostream& HistoricElementDateTime::print(std::ostream& stream, int level, int spacesPerLevel) const
		{
			std::string strValue(DisplayFormats::HistoricalOrReferenceRequests_FormatDate(this->_value));
			ElementPtr::prettyPrintHelper(stream, level, spacesPerLevel, strValue);
			return stream;
		}

	}
}