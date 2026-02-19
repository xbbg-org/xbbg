//------------------------------------------------------------------------------
// <copyright project="BEmu_cpp" file="src/MarketDataRequest/MarketElementSubscriptionCanceled.cpp" company="Jordan Robinson">
//     Copyright (c) 2013 Jordan Robinson. All rights reserved.
//
//     The use of this software is governed by the Microsoft Public License
//     which is included with this distribution.
// </copyright>
//------------------------------------------------------------------------------

#include "MarketDataRequest/MarketElementSubscriptionCanceled.h"
#include "MarketDataRequest/MarketMessageSubscriptionCanceled.h"
#include "MarketDataRequest/MarketElementSubscriptionCancelReason.h"

#include "Types/IndentType.h"
#include <ostream>

namespace BEmu
{
	namespace MarketDataRequest
	{
		MarketElementSubscriptionCanceled::MarketElementSubscriptionCanceled(const MarketMessageSubscriptionCanceled& arg) :
			_reason(std::dynamic_pointer_cast<MarketElementSubscriptionCancelReason>(arg.getElement("reason")))
		{
		}

		Name MarketElementSubscriptionCanceled::name() const
		{
			return Name("SubscriptionTerminated");
		}

		size_t MarketElementSubscriptionCanceled::numValues() const
		{
			return 1;
		}

		size_t MarketElementSubscriptionCanceled::numElements() const
		{
			return 1;
		}

		bool MarketElementSubscriptionCanceled::isNull() const
		{
			return false;
		}

		bool MarketElementSubscriptionCanceled::isArray() const
		{
			return false;
		}

		bool MarketElementSubscriptionCanceled::isComplexType() const
		{
			return true;
		}

		std::ostream& MarketElementSubscriptionCanceled::print(std::ostream& stream, int level, int spacesPerLevel) const
		{
			std::string tabs(IndentType::Indent(level, spacesPerLevel));

			stream << tabs << "SubscriptionTerminated = {" << std::endl;
			this->_reason->print(stream, level + 1, spacesPerLevel);
			stream << tabs << '}' << std::endl;

			return stream;
		}
	}
}