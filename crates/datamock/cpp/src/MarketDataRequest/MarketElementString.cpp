//------------------------------------------------------------------------------
// <copyright project="BEmu_cpp" file="src/MarketDataRequest/MarketElementString.cpp" company="Jordan Robinson">
//     Copyright (c) 2013 Jordan Robinson. All rights reserved.
//
//     The use of this software is governed by the Microsoft Public License
//     which is included with this distribution.
// </copyright>
//------------------------------------------------------------------------------

#include "MarketDataRequest/MarketElementString.h"
#include <ostream>

namespace BEmu
{
	namespace MarketDataRequest
	{
		MarketElementString::MarketElementString(const std::string& name, const std::string& value)
		{
			this->_name = name;
			this->_value = value;
		}

		Name MarketElementString::name() const
		{
			return Name(this->_name.c_str());
		}

		size_t MarketElementString::numValues() const
		{
			return 1;
		}

		size_t MarketElementString::numElements() const
		{
			return 0;
		}

		bool MarketElementString::isNull() const
		{
			return false;
		}

		bool MarketElementString::isArray() const
		{
			return false;
		}

		bool MarketElementString::isComplexType() const
		{
			return false;
		}

		const char * MarketElementString::getValueAsString(int index) const
		{
			if(index == 0)
				return this->_value.c_str();
			else
				throw elementPtrEx;
		}

		std::ostream& MarketElementString::print(std::ostream& stream, int level, int spacesPerLevel) const
		{
			this->prettyPrintHelper(stream, level, spacesPerLevel, this->_value);
			return stream;
		}

	}
}