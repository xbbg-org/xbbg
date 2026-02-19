//------------------------------------------------------------------------------------------------
// <copyright project="BEmu_cpp" file="src/IntradayBarRequest/IntradayBarElementLong.cpp" company="Jordan Robinson">
//     Copyright (c) 2013 Jordan Robinson. All rights reserved.
//
//     The use of this software is governed by the Microsoft Public License
//     which is included with this distribution.
// </copyright>
//------------------------------------------------------------------------------------------------

#include "IntradayBarRequest/IntradayBarElementLong.h"
#include "BloombergTypes/Name.h"
#include "BloombergTypes/ElementPtr.h"
#include <ostream>

namespace BEmu
{
	namespace IntradayBarRequest
	{
		IntradayBarElementLong::IntradayBarElementLong(const std::string& name, long value)
		{
			this->_name = name;
			this->_value = value;
		}

		IntradayBarElementLong::~IntradayBarElementLong()
		{
		}

		Name IntradayBarElementLong::name() const
		{
			Name result(this->_name.c_str());
			return result;
		}

		size_t IntradayBarElementLong::numValues() const
		{
			return 1;
		}

		size_t IntradayBarElementLong::numElements() const
		{
			return 0;
		}

		bool IntradayBarElementLong::isArray() const
		{
			return false;
		}

		bool IntradayBarElementLong::isComplexType() const
		{
			return false;
		}

		long IntradayBarElementLong::getValueAsInt64(int index) const
		{
			if(index == 0)
				return this->_value;
			else
				throw elementPtrEx;
		}

		std::ostream& IntradayBarElementLong::print(std::ostream& stream, int level, int spacesPerLevel) const
		{
			this->prettyPrintHelper(stream, level, spacesPerLevel, this->_value);
			return stream;
		}
	}
}