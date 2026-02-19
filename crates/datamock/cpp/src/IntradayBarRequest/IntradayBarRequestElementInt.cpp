//------------------------------------------------------------------------------------------------
// <copyright project="BEmu_cpp" file="src/IntradayBarRequest/IntradayBarRequestElementInt.cpp" company="Jordan Robinson">
//     Copyright (c) 2013 Jordan Robinson. All rights reserved.
//
//     The use of this software is governed by the Microsoft Public License
//     which is included with this distribution.
// </copyright>
//------------------------------------------------------------------------------------------------

#include "BloombergTypes/Name.h"
#include "BloombergTypes/ElementPtr.h"
#include "IntradayBarRequest/IntradayBarRequestElementInt.h"
#include <ostream>

namespace BEmu
{
	namespace IntradayBarRequest
	{
		IntradayBarRequestElementInt::IntradayBarRequestElementInt(const std::string& elementName, int ivalue) : CanConvertToStringType(ivalue, false)
		{
			this->_elementName = elementName;
			this->_ivalue = ivalue;
		}

		IntradayBarRequestElementInt::~IntradayBarRequestElementInt()
		{
		}

		int IntradayBarRequestElementInt::getInt() const
		{
			return this->_ivalue;
		}

		Name IntradayBarRequestElementInt::name() const
		{
			Name result(this->_elementName.c_str());
			return result;
		}

		size_t IntradayBarRequestElementInt::numValues() const
		{
			return 1;
		}

		size_t IntradayBarRequestElementInt::numElements() const
		{
			return 0;
		}

		bool IntradayBarRequestElementInt::isArray() const
		{
			return false;
		}

		bool IntradayBarRequestElementInt::isComplexType() const
		{
			return false;
		}

		const char * IntradayBarRequestElementInt::getValueAsString(int index) const
		{
			return this->ValueAsString().c_str();
		}

		std::ostream& IntradayBarRequestElementInt::print(std::ostream& stream, int level, int spacesPerLevel) const
		{
			this->prettyPrintHelper(stream, level, spacesPerLevel, this->ValueAsString());
			return stream;
		}

	}
}