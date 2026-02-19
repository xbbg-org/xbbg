//------------------------------------------------------------------------------------------------
// <copyright project="BEmu_cpp" file="src/IntradayBarRequest/IntradayBarRequestElementString.cpp" company="Jordan Robinson">
//     Copyright (c) 2013 Jordan Robinson. All rights reserved.
//
//     The use of this software is governed by the Microsoft Public License
//     which is included with this distribution.
// </copyright>
//------------------------------------------------------------------------------------------------

#include "BloombergTypes/Name.h"
#include "BloombergTypes/ElementPtr.h"
#include "IntradayBarRequest/IntradayBarRequestElementString.h"
#include <ostream>

namespace BEmu
{
	namespace IntradayBarRequest
	{
		IntradayBarRequestElementString::IntradayBarRequestElementString(const std::string& elementName, const std::string& value, bool surroundWithQuotes) : 
			CanConvertToStringType(value, surroundWithQuotes)
		{
			this->_elementName = elementName;
			this->_value = value;
		}

		IntradayBarRequestElementString::~IntradayBarRequestElementString()
		{
		}

		Name IntradayBarRequestElementString::name() const
		{
			Name result(this->_elementName.c_str());
			return result;
		}

		const std::string& IntradayBarRequestElementString::security() const
		{
			return this->_value;
		}

		size_t IntradayBarRequestElementString::numValues() const
		{
			return 1;
		}

		size_t IntradayBarRequestElementString::numElements() const
		{
			return 0;
		}

		bool IntradayBarRequestElementString::isArray() const
		{
			return false;
		}

		bool IntradayBarRequestElementString::isComplexType() const
		{
			return false;
		}

		const char * IntradayBarRequestElementString::getValueAsString(int index) const
		{
			if(index == 0)
				return this->_value.c_str();
			else
				throw elementPtrEx;
		}

		std::ostream& IntradayBarRequestElementString::print(std::ostream& stream, int level, int spacesPerLevel) const
		{
			this->prettyPrintHelper(stream, level, spacesPerLevel, this->ValueAsString());
			return stream;
		}
	}
}