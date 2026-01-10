//------------------------------------------------------------------------------
// <copyright project="BEmu_cpp" file="src/MarketDataRequest/MarketElementDouble.cpp" company="Jordan Robinson">
//     Copyright (c) 2013 Jordan Robinson. All rights reserved.
//
//     The use of this software is governed by the Microsoft Public License
//     which is included with this distribution.
// </copyright>
//------------------------------------------------------------------------------

#include "MarketDataRequest/MarketElementDouble.h"
#include "Types/DisplayFormats.h"
#include <ostream>

namespace BEmu
{
	namespace MarketDataRequest
	{
		MarketElementDouble::MarketElementDouble(const std::string& name, double value)
		{
			this->_name = name;
			this->_value = value;
		}

		Name MarketElementDouble::name() const
		{
			return Name(this->_name.c_str());
		}

		size_t MarketElementDouble::numValues() const
		{
			return 1;
		}

		size_t MarketElementDouble::numElements() const
		{
			return 0;
		}

		bool MarketElementDouble::isNull() const
		{
			return false;
		}

		bool MarketElementDouble::isArray() const
		{
			return false;
		}

		bool MarketElementDouble::isComplexType() const
		{
			return false;
		}

		double MarketElementDouble::getValueAsFloat64(int index) const
		{
			if(index == 0)
				return this->_value;
			else
				throw elementPtrEx;
		}

		std::ostream& MarketElementDouble::print(std::ostream& stream, int level, int spacesPerLevel) const
		{
			std::string strValue(DisplayFormats::FormatNumberNoSeparators(this->_value, 2));
			this->prettyPrintHelper(stream, level, spacesPerLevel, strValue);
			return stream;
		}

	}
}