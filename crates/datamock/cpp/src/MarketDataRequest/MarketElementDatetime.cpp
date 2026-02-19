//------------------------------------------------------------------------------
// <copyright project="BEmu_cpp" file="src/MarketDataRequest/MarketElementDatetime.cpp" company="Jordan Robinson">
//     Copyright (c) 2013 Jordan Robinson. All rights reserved.
//
//     The use of this software is governed by the Microsoft Public License
//     which is included with this distribution.
// </copyright>
//------------------------------------------------------------------------------

#include "MarketDataRequest/MarketElementDatetime.h"
#include "Types/DisplayFormats.h"
#include <ostream>

namespace BEmu
{
	namespace MarketDataRequest
	{
		MarketElementDatetime::MarketElementDatetime(const std::string& name, const Datetime& datetime)
		{
			this->_name = name;
			this->_datetime = datetime;
		}

		Name MarketElementDatetime::name() const
		{
			return Name(this->_name.c_str());
		}

		size_t MarketElementDatetime::numValues() const
		{
			return 1;
		}

		size_t MarketElementDatetime::numElements() const
		{
			return 0;
		}

		bool MarketElementDatetime::isNull() const
		{
			return false;
		}

		Datetime MarketElementDatetime::getValueAsDatetime(int index) const
		{
			if(index == 0)
				return this->_datetime;
			else
				throw elementPtrEx;
		}

		std::ostream& MarketElementDatetime::print(std::ostream& stream, int level, int spacesPerLevel) const
		{
			std::string strDateTime(DisplayFormats::MarketDataRequests_FormatDateZone(this->_datetime));
			this->prettyPrintHelper(stream, level, spacesPerLevel, strDateTime);
			return stream;
		}
		
	}
}