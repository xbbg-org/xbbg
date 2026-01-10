//------------------------------------------------------------------------------
// <copyright project="BEmu_cpp" file="src/HistoricalDataRequest/HistoricRequestElementDate.cpp" company="Jordan Robinson">
//     Copyright (c) 2013 Jordan Robinson. All rights reserved.
//
//     The use of this software is governed by the Microsoft Public License
//     which is included with this distribution.
// </copyright>
//------------------------------------------------------------------------------

#include "HistoricalDataRequest/HistoricRequestElementDate.h"
#include "BloombergTypes/Datetime.h"
#include "Types/DisplayFormats.h"

namespace BEmu
{
	namespace HistoricalDataRequest
	{
		HistoricRequestElementDate::HistoricRequestElementDate(const std::string& elementName) : HistoricRequestElementString(elementName, "")
		{
		}

		HistoricRequestElementDate::HistoricRequestElementDate(const std::string& elementName, const Datetime& datetime) 
			: HistoricRequestElementString(elementName, DisplayFormats::ToYYYYMMddNoSeparatorsWithQuotes(datetime))
		{
			this->_instance = datetime;
		}

		HistoricRequestElementDate::~HistoricRequestElementDate()
		{
		}

		Datetime HistoricRequestElementDate::getDatetime() const
		{
			return this->_instance;
		}
	}
}