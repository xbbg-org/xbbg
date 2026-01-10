//------------------------------------------------------------------------------------------------
// <copyright project="BEmu_cpp" file="src/IntradayBarRequest/IntradayBarElementString.cpp" company="Jordan Robinson">
//     Copyright (c) 2013 Jordan Robinson. All rights reserved.
//
//     The use of this software is governed by the Microsoft Public License
//     which is included with this distribution.
// </copyright>
//------------------------------------------------------------------------------------------------

#include "IntradayBarRequest/IntradayBarElementString.h"
#include "BloombergTypes/Name.h"
#include "BloombergTypes/ElementPtr.h"
#include <ostream>

namespace BEmu
{
	namespace IntradayBarRequest
	{
		IntradayBarElementString::IntradayBarElementString(const std::string& name, const std::string& value) : CanConvertToStringType(value)
		{
			this->_name = name;
			this->_value = value;
		}

		IntradayBarElementString::~IntradayBarElementString()
		{
		}

		Name IntradayBarElementString::name() const
		{
			Name result(this->_name.c_str());
			return result;
		}

		size_t IntradayBarElementString::numValues() const
		{
			return 1;
		}

		size_t IntradayBarElementString::numElements() const
		{
			return 0;
		}

		bool IntradayBarElementString::isArray() const
		{
			return false;
		}

		bool IntradayBarElementString::isComplexType() const
		{
			return false;
		}

		const char * IntradayBarElementString::getValueAsString(int index) const
		{
			if(index == 0)
				return this->_value.c_str();
			else
				throw elementPtrEx;
		}

		std::ostream& IntradayBarElementString::print(std::ostream& stream, int level, int spacesPerLevel) const
		{
			this->prettyPrintHelper(stream, level, spacesPerLevel, this->_value);
			return stream;
		}
	}
}