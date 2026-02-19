//------------------------------------------------------------------------------------------------
// <copyright project="BEmu_cpp" file="src/IntradayBarRequest/IntradayBarElementInt.cpp" company="Jordan Robinson">
//     Copyright (c) 2013 Jordan Robinson. All rights reserved.
//
//     The use of this software is governed by the Microsoft Public License
//     which is included with this distribution.
// </copyright>
//------------------------------------------------------------------------------------------------

#include "IntradayBarRequest/IntradayBarElementInt.h"
#include "BloombergTypes/Name.h"
#include "BloombergTypes/ElementPtr.h"
#include <ostream>

namespace BEmu
{
	namespace IntradayBarRequest
	{
		IntradayBarElementInt::IntradayBarElementInt(const std::string& name, int value)
		{
			this->_name = name;
			this->_value = value;
		}

		IntradayBarElementInt::~IntradayBarElementInt()
		{
		}

		Name IntradayBarElementInt::name() const
		{
			Name result(this->_name.c_str());
			return result;
		}

		size_t IntradayBarElementInt::numValues() const
		{
			return 1;
		}

		size_t IntradayBarElementInt::numElements() const
		{
			return 0;
		}

		bool IntradayBarElementInt::isArray() const
		{
			return false;
		}

		bool IntradayBarElementInt::isComplexType() const
		{
			return false;
		}

		int IntradayBarElementInt::getValueAsInt32(int index) const
		{
			if(index == 0)
				return this->_value;
			else
				throw elementPtrEx;
		}

		std::ostream& IntradayBarElementInt::print(std::ostream& stream, int level, int spacesPerLevel) const
		{
			this->prettyPrintHelper(stream, level, spacesPerLevel, this->_value);
			return stream;
		}
	}
}