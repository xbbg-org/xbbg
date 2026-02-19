//------------------------------------------------------------------------------------------------
// <copyright project="BEmu_cpp" file="src/IntradayBarRequest/IntradayBarRequestElementBool.cpp" company="Jordan Robinson">
//     Copyright (c) 2013 Jordan Robinson. All rights reserved.
//
//     The use of this software is governed by the Microsoft Public License
//     which is included with this distribution.
// </copyright>
//------------------------------------------------------------------------------------------------

#include "BloombergTypes/Name.h"
#include "BloombergTypes/ElementPtr.h"
#include "IntradayBarRequest/IntradayBarRequestElementBool.h"
#include <ostream>

namespace BEmu
{
	namespace IntradayBarRequest
	{
		IntradayBarRequestElementBool::IntradayBarRequestElementBool(const std::string& elementName, bool bvalue) : CanConvertToStringType(bvalue, false)
		{
			this->_elementName = elementName;
			this->_bvalue = bvalue;
		}

		IntradayBarRequestElementBool::~IntradayBarRequestElementBool()
		{
		}

		bool IntradayBarRequestElementBool::getBool() const
		{
			return this->_bvalue;
		}

		Name IntradayBarRequestElementBool::name() const
		{
			Name result(this->_elementName.c_str());
			return result;
		}

		size_t IntradayBarRequestElementBool::numValues() const
		{
			return 1;
		}

		size_t IntradayBarRequestElementBool::numElements() const
		{
			return 0;
		}

		bool IntradayBarRequestElementBool::isArray() const
		{
			return false;
		}

		bool IntradayBarRequestElementBool::isComplexType() const
		{
			return false;
		}

		const char * IntradayBarRequestElementBool::getValueAsString(int index) const
		{
			return this->ValueAsString().c_str();
		}

		std::ostream& IntradayBarRequestElementBool::print(std::ostream& stream, int level, int spacesPerLevel) const
		{
			this->prettyPrintHelper(stream, level, spacesPerLevel, this->ValueAsString());
			return stream;
		}

	}
}