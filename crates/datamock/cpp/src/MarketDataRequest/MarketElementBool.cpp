//------------------------------------------------------------------------------
// <copyright project="BEmu_cpp" file="src/MarketDataRequest/MarketElementBool.cpp" company="Jordan Robinson">
//     Copyright (c) 2013 Jordan Robinson. All rights reserved.
//
//     The use of this software is governed by the Microsoft Public License
//     which is included with this distribution.
// </copyright>
//------------------------------------------------------------------------------

#include "MarketDataRequest/MarketElementBool.h"
#include <ostream>

namespace BEmu
{
	namespace MarketDataRequest
	{
		MarketElementBool::MarketElementBool(const std::string& name, bool value)
		{
			this->_name = name;
			this->_value = value;
		}

		Name MarketElementBool::name() const
		{
			return Name(this->_name.c_str());
		}

		size_t MarketElementBool::numValues() const
		{
			return 1;
		}

		size_t MarketElementBool::numElements() const
		{
			return 0;
		}

		bool MarketElementBool::isNull() const
		{
			return false;
		}

		bool MarketElementBool::isArray() const
		{
			return false;
		}

		bool MarketElementBool::isComplexType() const
		{
			return false;
		}

		bool MarketElementBool::getValueAsBool(int index) const
		{
			if(index == 0)
				return this->_value;
			else
				throw elementPtrEx;
		}

		std::ostream& MarketElementBool::print(std::ostream& stream, int level, int spacesPerLevel) const
		{
			this->prettyPrintHelper(stream, level, spacesPerLevel, this->_value ? "True" : "False");
			return stream;
		}

	}
}