//------------------------------------------------------------------------------------------------
// <copyright project="BEmu_cpp" file="src/IntradayTickRequest/IntradayTickElementInt.cpp" company="Jordan Robinson">
//     Copyright (c) 2013 Jordan Robinson. All rights reserved.
//
//     The use of this software is governed by the Microsoft Public License
//     which is included with this distribution.
// </copyright>
//------------------------------------------------------------------------------------------------

#include "IntradayTickRequest/IntradayTickElementInt.h"
#include "BloombergTypes/Name.h"
#include "BloombergTypes/ElementPtr.h"
#include <ostream>

namespace BEmu
{
	namespace IntradayTickRequest
	{
		IntradayTickElementInt::IntradayTickElementInt(const std::string& name, int value) : CanConvertToStringType(value)
		{
			this->_name = name;
			this->_value = value;
		}

		IntradayTickElementInt::~IntradayTickElementInt()
		{
		}

		Name IntradayTickElementInt::name() const
		{
			Name result(this->_name.c_str());
			return result;
		}

		size_t IntradayTickElementInt::numValues() const
		{
			return 1;
		}

		size_t IntradayTickElementInt::numElements() const
		{
			return 0;
		}

		bool IntradayTickElementInt::isArray() const
		{
			return false;
		}

		bool IntradayTickElementInt::isComplexType() const
		{
			return false;
		}
		
		bool IntradayTickElementInt::hasElement(const char* name, bool excludeNullElements) const
		{
			return false;
		}

		std::ostream& IntradayTickElementInt::print(std::ostream& stream, int level, int spacesPerLevel) const
		{
			this->prettyPrintHelper(stream, level, spacesPerLevel, this->_value);
			return stream;
		}

		int IntradayTickElementInt::getValueAsInt32(int index) const
		{
			if(index == 0)
				return this->_value;
			else
				throw elementPtrEx;
		}

		long IntradayTickElementInt::getValueAsInt64(int index) const
		{
			if(index == 0)
				return this->_value;
			else
				throw elementPtrEx;
		}
		
		float IntradayTickElementInt::getValueAsFloat32(int index) const
		{
			if(index == 0)
				return (float)this->_value;
			else
				throw elementPtrEx;
		}

		double IntradayTickElementInt::getValueAsFloat64(int index) const
		{
			if(index == 0)
				return this->_value;
			else
				throw elementPtrEx;
		}

		const char * IntradayTickElementInt::getValueAsString(int index) const
		{
			if(index == 0)
				return this->ValueAsString().c_str();
			else
				throw elementPtrEx;
		}
	}
}