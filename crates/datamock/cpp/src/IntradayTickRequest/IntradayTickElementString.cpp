//------------------------------------------------------------------------------------------------
// <copyright project="BEmu_cpp" file="src/IntradayTickRequest/IntradayTickElementString.cpp" company="Jordan Robinson">
//     Copyright (c) 2013 Jordan Robinson. All rights reserved.
//
//     The use of this software is governed by the Microsoft Public License
//     which is included with this distribution.
// </copyright>
//------------------------------------------------------------------------------------------------

#include "IntradayTickRequest/IntradayTickElementString.h"
#include "BloombergTypes/Name.h"
#include "BloombergTypes/ElementPtr.h"
#include <ostream>

namespace BEmu
{
	namespace IntradayTickRequest
	{
		IntradayTickElementString::IntradayTickElementString(const std::string& name, const std::string& value) : CanConvertToStringType(value)
		{
			this->_name = name;
			this->_value = value;
		}

		IntradayTickElementString::~IntradayTickElementString()
		{
		}

		Name IntradayTickElementString::name() const
		{
			Name result(this->_name.c_str());
			return result;
		}
		
		bool IntradayTickElementString::hasElement(const char* name, bool excludeNullElements) const
		{
			return false;
		}

		std::ostream& IntradayTickElementString::print(std::ostream& stream, int level, int spacesPerLevel) const
		{
			this->prettyPrintHelper(stream, level, spacesPerLevel, this->_value);
			return stream;
		}

		const char * IntradayTickElementString::getValueAsString(int index) const
		{
			if(index == 0)
			{
				return this->_value.c_str();
			}
			else
				throw elementPtrEx;
		}
	}
}