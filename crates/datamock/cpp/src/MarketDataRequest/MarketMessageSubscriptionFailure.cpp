//------------------------------------------------------------------------------
// <copyright project="BEmu_cpp" file="src/MarketDataRequest/MarketMessageSubscriptionFailure.cpp" company="Jordan Robinson">
//     Copyright (c) 2013 Jordan Robinson. All rights reserved.
//
//     The use of this software is governed by the Microsoft Public License
//     which is included with this distribution.
// </copyright>
//------------------------------------------------------------------------------

#include "MarketDataRequest/MarketMessageSubscriptionFailure.h"
#include "MarketDataRequest/MarketElementReason.h"
#include <ostream>

namespace BEmu
{
	namespace MarketDataRequest
	{
		MarketMessageSubscriptionFailure::MarketMessageSubscriptionFailure(const Subscription& sub) :
			MessagePtr(Name("SubscriptionFailure"), sub.correlationId()),
			_reason(new MarketElementReason(ReasonType::badSecurity))
		{
            this->_correlationId = sub.correlationId();
			this->_topicName = sub.security();
		}

		MarketMessageSubscriptionFailure::~MarketMessageSubscriptionFailure()
		{
		}

		size_t MarketMessageSubscriptionFailure::numElements() const
		{
			return 1;
		}

		const char* MarketMessageSubscriptionFailure::topicName() const
		{
			return this->_topicName.c_str();
		}

		bool MarketMessageSubscriptionFailure::hasElement(const char* name, bool excludeNullElements) const
		{
			return this->_reason->name() == name;
		}

		std::shared_ptr<ElementPtr> MarketMessageSubscriptionFailure::getElement(const char* name) const
		{
			if(this->_reason->name() == name)
				return std::dynamic_pointer_cast<ElementPtr>(this->_reason);

			else
				throw messageEx;
		}

		std::ostream& MarketMessageSubscriptionFailure::print(std::ostream& stream, int level, int spacesPerLevel) const
		{
			stream << "SubscriptionFailure = {" << std::endl;
			this->_reason->print(stream, level + 1, spacesPerLevel);
			stream << "}" << std::endl;

			return stream;
		}
	}
}