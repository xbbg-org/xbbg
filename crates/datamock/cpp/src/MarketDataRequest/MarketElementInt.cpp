//------------------------------------------------------------------------------
// <copyright project="BEmu_cpp" file="src/MarketDataRequest/MarketElementInt.cpp" company="Jordan Robinson">
//     Copyright (c) 2013 Jordan Robinson. All rights reserved.
//
//     The use of this software is governed by the Microsoft Public License
//     which is included with this distribution.
// </copyright>
//------------------------------------------------------------------------------

#include "MarketDataRequest/MarketElementInt.h"
#include <ostream>

namespace BEmu
{
	namespace MarketDataRequest
	{
		MarketElementInt::MarketElementInt(const std::string& name, int value)
		{
			this->_name = name;
			this->_value = value;
		}

		Name MarketElementInt::name() const
		{
			return Name(this->_name.c_str());
		}

		size_t MarketElementInt::numValues() const
		{
			return 1;
		}

		size_t MarketElementInt::numElements() const
		{
			return 0;
		}

		bool MarketElementInt::isNull() const
		{
			return false;
		}

		bool MarketElementInt::isArray() const
		{
			return false;
		}

		bool MarketElementInt::isComplexType() const
		{
			return false;
		}

		int MarketElementInt::getValueAsInt32(int index) const
		{
			if(index == 0)
				return this->_value;
			else
				throw elementPtrEx;
		}

		long MarketElementInt::getValueAsInt64(int index) const
		{
			if(index == 0)
				return (long)this->_value;
			else
				throw elementPtrEx;
		}

		float MarketElementInt::getValueAsFloat32(int index) const
		{
			if(index == 0)
				return (float)this->_value;
			else
				throw elementPtrEx;
		}

		double MarketElementInt::getValueAsFloat64(int index) const
		{
			if(index == 0)
				return (double)this->_value;
			else
				throw elementPtrEx;
		}

		std::ostream& MarketElementInt::print(std::ostream& stream, int level, int spacesPerLevel) const
		{
			this->prettyPrintHelper(stream, level, spacesPerLevel, this->_value);
			return stream;
		}

	}
}