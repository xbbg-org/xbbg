//------------------------------------------------------------------------------------------------
// <copyright project="BEmu_cpp" file="src/IntradayTickRequest/IntradayTickElementDateTime.cpp" company="Jordan Robinson">
//     Copyright (c) 2013 Jordan Robinson. All rights reserved.
//
//     The use of this software is governed by the Microsoft Public License
//     which is included with this distribution.
// </copyright>
//------------------------------------------------------------------------------------------------

#include "IntradayTickRequest/IntradayTickElementDateTime.h"
#include "BloombergTypes/Name.h"
#include "BloombergTypes/ElementPtr.h"
#include "BloombergTypes/Datetime.h"
#include "Types/DisplayFormats.h"
#include <ostream>

namespace BEmu
{
	namespace IntradayTickRequest
	{
		IntradayTickElementDateTime::IntradayTickElementDateTime(const std::string& name, const Datetime& value) : CanConvertToStringType(value)
		{
			this->_name = name;
			this->_value = value;
		}

		IntradayTickElementDateTime::~IntradayTickElementDateTime()
		{
		}

		std::ostream& IntradayTickElementDateTime::print(std::ostream& stream, int level, int spacesPerLevel) const
		{
			std::string strValue(DisplayFormats::IntradayRequests_FormatDatetime(this->_value));
			this->prettyPrintHelper(stream, level, spacesPerLevel, strValue);
			return stream;
		}

		Name IntradayTickElementDateTime::name() const
		{
			return Name("time");
		}

		bool IntradayTickElementDateTime::hasElement(const char* name, bool excludeNullElements) const
		{
			return false;
		}

		Datetime IntradayTickElementDateTime::getValueAsDatetime(int index) const
		{
			return this->_value;
		}

		const char * IntradayTickElementDateTime::getValueAsString(int index) const
		{
			if(index == 0)
				return this->ValueAsString().c_str();
			else
				throw elementPtrEx;
		}


	}
}