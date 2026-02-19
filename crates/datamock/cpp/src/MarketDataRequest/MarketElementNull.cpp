//------------------------------------------------------------------------------
// <copyright project="BEmu_cpp" file="src/MarketDataRequest/MarketElementNull.cpp" company="Jordan Robinson">
//     Copyright (c) 2013 Jordan Robinson. All rights reserved.
//
//     The use of this software is governed by the Microsoft Public License
//     which is included with this distribution.
// </copyright>
//------------------------------------------------------------------------------

#include "MarketDataRequest/MarketElementNull.h"
#include <ostream>

namespace BEmu
{
	namespace MarketDataRequest
	{
		MarketElementNull::MarketElementNull(const std::string& name)
		{
			this->_name = name;
		}

		Name MarketElementNull::name() const
		{
			return Name(this->_name.c_str());
		}

		size_t MarketElementNull::numValues() const
		{
			return 0;
		}

		size_t MarketElementNull::numElements() const
		{
			return 0;
		}

		bool MarketElementNull::isNull() const
		{
			return true;
		}

		bool MarketElementNull::isArray() const
		{
			return true;
		}

		bool MarketElementNull::isComplexType() const
		{
			return false;
		}

		std::ostream& MarketElementNull::print(std::ostream& stream, int level, int spacesPerLevel) const
		{
			return stream;
		}

	}
}