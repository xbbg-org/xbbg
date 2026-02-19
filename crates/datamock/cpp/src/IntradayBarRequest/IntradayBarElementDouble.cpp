//------------------------------------------------------------------------------------------------
// <copyright project="BEmu_cpp" file="src/IntradayBarRequest/IntradayBarElementDouble.cpp" company="Jordan Robinson">
//     Copyright (c) 2013 Jordan Robinson. All rights reserved.
//
//     The use of this software is governed by the Microsoft Public License
//     which is included with this distribution.
// </copyright>
//------------------------------------------------------------------------------------------------

#include "IntradayBarRequest/IntradayBarElementDouble.h"
#include "BloombergTypes/Name.h"
#include "BloombergTypes/ElementPtr.h"
#include <ostream>

namespace BEmu
{
	namespace IntradayBarRequest
	{
		IntradayBarElementDouble::IntradayBarElementDouble(const std::string& name, double value) : CanConvertToStringType(value)
		{
			this->_name = name;
			this->_value = value;
		}

		IntradayBarElementDouble::~IntradayBarElementDouble()
		{
		}

		Name IntradayBarElementDouble::name() const
		{
			Name result(this->_name.c_str());
			return result;
		}

		size_t IntradayBarElementDouble::numValues() const
		{
			return 1;
		}

		size_t IntradayBarElementDouble::numElements() const
		{
			return 0;
		}

		bool IntradayBarElementDouble::isArray() const
		{
			return false;
		}

		bool IntradayBarElementDouble::isComplexType() const
		{
			return false;
		}

		double IntradayBarElementDouble::getValueAsFloat64(int index) const
		{
			if(index == 0)
				return this->_value;
			else
				throw elementPtrEx;
		}

		int IntradayBarElementDouble::getValueAsInt32(int index) const
		{
			if(index == 0)
				return (int)this->_value;
			else
				throw elementPtrEx;
		}

		const char * IntradayBarElementDouble::getValueAsString(int index) const
		{
			if(index == 0)
				return this->ValueAsString().c_str();
			else
				throw elementPtrEx;
		}

		std::ostream& IntradayBarElementDouble::print(std::ostream& stream, int level, int spacesPerLevel) const
		{
			this->prettyPrintHelper(stream, level, spacesPerLevel, this->_value);
			return stream;
		}
	}
}