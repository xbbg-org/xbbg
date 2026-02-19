//------------------------------------------------------------------------------------------------
// <copyright project="BEmu_cpp" file="src/IntradayBarRequest/IntradayBarRequestElementTime.cpp" company="Jordan Robinson">
//     Copyright (c) 2013 Jordan Robinson. All rights reserved.
//
//     The use of this software is governed by the Microsoft Public License
//     which is included with this distribution.
// </copyright>
//------------------------------------------------------------------------------------------------

#include "BloombergTypes/Name.h"
#include "BloombergTypes/Datetime.h"
#include "BloombergTypes/ElementPtr.h"
#include "IntradayBarRequest/IntradayBarRequestElementTime.h"
#include "Types/DisplayFormats.h"
#include <ostream>

namespace BEmu
{
	namespace IntradayBarRequest
	{
		IntradayBarRequestElementTime::IntradayBarRequestElementTime(const std::string& elementName, const Datetime& dtvalue) : 
			CanConvertToStringType(DisplayFormats::ToYYYYMMDDWithDashes(dtvalue), false)
		{
			this->_elementName = elementName;
			this->_dtvalue = dtvalue;
		}

		IntradayBarRequestElementTime::~IntradayBarRequestElementTime()
		{
		}

		Datetime IntradayBarRequestElementTime::getDatetime() const
		{
			return this->_dtvalue;
		}

		Name IntradayBarRequestElementTime::name() const
		{
			Name result(this->_elementName.c_str());
			return result;
		}

		size_t IntradayBarRequestElementTime::numValues() const
		{
			return 1;
		}

		size_t IntradayBarRequestElementTime::numElements() const
		{
			return 0;
		}

		bool IntradayBarRequestElementTime::isArray() const
		{
			return false;
		}

		bool IntradayBarRequestElementTime::isComplexType() const
		{
			return false;
		}

		const char * IntradayBarRequestElementTime::getValueAsString(int index) const
		{
			return this->ValueAsString().c_str();
		}

		std::ostream& IntradayBarRequestElementTime::print(std::ostream& stream, int level, int spacesPerLevel) const
		{
			this->prettyPrintHelper(stream, level, spacesPerLevel, this->ValueAsString());
			return stream;
		}

	}
}