//------------------------------------------------------------------------------
// <copyright project="BEmu_cpp" file="src/HistoricalDataRequest/HistoricElementString.cpp" company="Jordan Robinson">
//     Copyright (c) 2013 Jordan Robinson. All rights reserved.
//
//     The use of this software is governed by the Microsoft Public License
//     which is included with this distribution.
// </copyright>
//------------------------------------------------------------------------------

#include "HistoricalDataRequest/HistoricElementString.h"
#include "BloombergTypes/Name.h"
#include <ostream>

namespace BEmu
{
	namespace HistoricalDataRequest
	{
		HistoricElementString::HistoricElementString(const std::string& name, const std::string& value) : CanConvertToStringType(value)
		{
			this->_name = name;
			this->_value = value;
		}

		HistoricElementString::~HistoricElementString()
		{
		}


		Name HistoricElementString::name() const
		{
			Name result(this->_name.c_str());
			return result;
		}


		const char * HistoricElementString::getValueAsString(int index) const
		{
			if(index == 0)
				return this->_value.c_str();
			else
				throw elementPtrEx;
		}


		std::ostream& HistoricElementString::print(std::ostream& stream, int level, int spacesPerLevel) const
		{
			this->prettyPrintHelper(stream, level, spacesPerLevel, this->_value);
			return stream;
		}

	}
}