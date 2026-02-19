//------------------------------------------------------------------------------
// <copyright project="BEmu_cpp" file="src/MarketDataRequest/MarketElementServiceStatus.cpp" company="Jordan Robinson">
//     Copyright (c) 2013 Jordan Robinson. All rights reserved.
//
//     The use of this software is governed by the Microsoft Public License
//     which is included with this distribution.
// </copyright>
//------------------------------------------------------------------------------

#include "MarketDataRequest/MarketElementServiceStatus.h"
#include "MarketDataRequest/MarketMessageServiceStatus.h"
#include "MarketDataRequest/MarketElementString.h"
#include <ostream>

namespace BEmu
{
	namespace MarketDataRequest
	{
		MarketElementServiceStatus::MarketElementServiceStatus(const MarketMessageServiceStatus& arg) :
			_serviceName(std::dynamic_pointer_cast<MarketElementString>(arg.firstElement()))
		{
		}

		Name MarketElementServiceStatus::name() const
		{
			return Name("ServiceOpened");
		}

		size_t MarketElementServiceStatus::numValues() const
		{
			return 1;
		}

		size_t MarketElementServiceStatus::numElements() const
		{
			return 1;
		}

		bool MarketElementServiceStatus::isNull() const
		{
			return false;
		}

		bool MarketElementServiceStatus::isArray() const
		{
			return false;
		}

		bool MarketElementServiceStatus::isComplexType() const
		{
			return true;
		}

		std::shared_ptr<ElementPtr> MarketElementServiceStatus::getElement(int position) const
		{
			if(position == 0)
				return std::dynamic_pointer_cast<ElementPtr>(this->_serviceName);
			else
				throw elementPtrEx;
		}

		std::ostream& MarketElementServiceStatus::print(std::ostream& stream, int level, int spacesPerLevel) const
		{
			stream << "ServiceOpened = {" << std::endl;
			this->_serviceName->print(stream, level + 1, spacesPerLevel);
			stream << '}' << std::endl;

			return stream;
		}

	}
}