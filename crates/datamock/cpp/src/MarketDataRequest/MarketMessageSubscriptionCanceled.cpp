//------------------------------------------------------------------------------
// <copyright project="BEmu_cpp" file="src/MarketDataRequest/MarketMessageSubscriptionCanceled.cpp" company="Jordan Robinson">
//     Copyright (c) 2013 Jordan Robinson. All rights reserved.
//
//     The use of this software is governed by the Microsoft Public License
//     which is included with this distribution.
// </copyright>
//------------------------------------------------------------------------------

#include "MarketDataRequest/MarketMessageSubscriptionCanceled.h"
#include "MarketDataRequest/MarketElementSubscriptionCancelReason.h"
#include "BloombergTypes/Name.h"
#include "BloombergTypes/Subscription.h"
#include <ostream>

namespace BEmu
{
	namespace MarketDataRequest
	{
		MarketMessageSubscriptionCanceled::MarketMessageSubscriptionCanceled(const Subscription& sub) :
			MessagePtr(Name("SubscriptionTerminated"), sub.correlationId()), CanConvertToStringType(sub.security()),
			_reason(new MarketElementSubscriptionCancelReason())
		{
			this->_topicName = sub.security();
		}

		MarketMessageSubscriptionCanceled::~MarketMessageSubscriptionCanceled()
		{
		}

		size_t MarketMessageSubscriptionCanceled::numElements() const
		{
			return 1;
		}

		const char* MarketMessageSubscriptionCanceled::topicName() const
		{
			return this->ValueAsString().c_str();
		}

		std::shared_ptr<ElementPtr> MarketMessageSubscriptionCanceled::asElement() const
		{
			throw messageEx;
		}

		std::ostream& MarketMessageSubscriptionCanceled::print(std::ostream& stream, int level, int spacesPerLevel) const
		{
			stream << "SubscriptionTerminated = {"  << std::endl;
			this->_reason->print(stream, level + 1, spacesPerLevel);
			stream << "}" << std::endl;

			return stream;
		}

	}
}