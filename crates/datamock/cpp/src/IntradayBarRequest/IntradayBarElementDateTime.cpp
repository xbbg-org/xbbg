//------------------------------------------------------------------------------------------------
// <copyright project="BEmu_cpp" file="src/IntradayBarRequest/IntradayBarElementDateTime.cpp" company="Jordan Robinson">
//     Copyright (c) 2013 Jordan Robinson. All rights reserved.
//
//     The use of this software is governed by the Microsoft Public License
//     which is included with this distribution.
// </copyright>
//------------------------------------------------------------------------------------------------

#include "IntradayBarRequest/IntradayBarElementDateTime.h"
#include "BloombergTypes/Name.h"
#include "BloombergTypes/ElementPtr.h"
#include "Types/DisplayFormats.h"
#include <ostream>

namespace BEmu
{
	namespace IntradayBarRequest
	{
		IntradayBarElementDateTime::IntradayBarElementDateTime(const std::string& name, const Datetime& value) : CanConvertToStringType(value)
		{
			this->_name = name;
			this->_value = value;
		}

		IntradayBarElementDateTime::~IntradayBarElementDateTime()
		{
		}

		Name IntradayBarElementDateTime::name() const
		{
			return Name(this->_name.c_str());
		}

		size_t IntradayBarElementDateTime::numValues() const
		{
			return 1;
		}

		size_t IntradayBarElementDateTime::numElements() const
		{
			return 0;
		}

		bool IntradayBarElementDateTime::isArray() const
		{
			return false;
		}

		bool IntradayBarElementDateTime::isComplexType() const
		{
			return false;
		}

		Datetime IntradayBarElementDateTime::getValueAsDatetime(int index) const
		{
			if(index == 0)
				return this->_value;
			else
				throw elementPtrEx;
		}

		const char * IntradayBarElementDateTime::getValueAsString(int index) const
		{
			if(index == 0)
				return this->ValueAsString().c_str();
			else
				throw elementPtrEx;
		}

		std::ostream& IntradayBarElementDateTime::print(std::ostream& stream, int level, int spacesPerLevel) const
		{
			std::string strvalue(DisplayFormats::IntradayRequests_FormatDatetime(this->_value));
			this->prettyPrintHelper(stream, level, spacesPerLevel, strvalue);
			return stream;
		}
	}
}