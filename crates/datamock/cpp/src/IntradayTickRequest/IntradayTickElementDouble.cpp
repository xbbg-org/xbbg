//------------------------------------------------------------------------------------------------
// <copyright project="BEmu_cpp" file="src/IntradayTickRequest/IntradayTickElementDouble.cpp" company="Jordan Robinson">
//     Copyright (c) 2013 Jordan Robinson. All rights reserved.
//
//     The use of this software is governed by the Microsoft Public License
//     which is included with this distribution.
// </copyright>
//------------------------------------------------------------------------------------------------

#include "IntradayTickRequest/IntradayTickElementDouble.h"
#include "BloombergTypes/Name.h"
#include "BloombergTypes/ElementPtr.h"
#include <ostream>

namespace BEmu
{
	namespace IntradayTickRequest
	{
		IntradayTickElementDouble::IntradayTickElementDouble(const std::string& name, double value) : CanConvertToStringType(value)
		{
			this->_name = name;
			this->_value = value;
		}

		IntradayTickElementDouble::~IntradayTickElementDouble()
		{
		}

		Name IntradayTickElementDouble::name() const
		{
			Name result(this->_name.c_str());
			return result;
		}
		
		bool IntradayTickElementDouble::hasElement(const char* name, bool excludeNullElements) const
		{
			return false;
		}

		std::ostream& IntradayTickElementDouble::print(std::ostream& stream, int level, int spacesPerLevel) const
		{
			this->prettyPrintHelper(stream, level, spacesPerLevel, this->_value);
			return stream;
		}

		int IntradayTickElementDouble::getValueAsInt32(int index) const
		{
			if(index == 0)
				return (int)this->_value;
			else
				throw elementPtrEx;
		}

		long IntradayTickElementDouble::getValueAsInt64(int index) const
		{
			if(index == 0)
				return (long)this->_value;
			else
				throw elementPtrEx;
		}
		
		float IntradayTickElementDouble::getValueAsFloat32(int index) const
		{
			if(index == 0)
				return (float)this->_value;
			else
				throw elementPtrEx;
		}

		double IntradayTickElementDouble::getValueAsFloat64(int index) const
		{
			if(index == 0)
				return this->_value;
			else
				throw elementPtrEx;
		}

		const char * IntradayTickElementDouble::getValueAsString(int index) const
		{
			if(index == 0)
				return this->ValueAsString().c_str();
			else
				throw elementPtrEx;
		}


	}
}