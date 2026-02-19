//------------------------------------------------------------------------------
// <copyright project="BEmu_cpp" file="headers/MarketDataRequest/MarketMessageSubscriptionFailure.h" company="Jordan Robinson">
//     Copyright (c) 2013 Jordan Robinson. All rights reserved.
//
//     The use of this software is governed by the Microsoft Public License
//     which is included with this distribution.
// </copyright>
//------------------------------------------------------------------------------

#pragma once

#include "BloombergTypes/MessagePtr.h"
#include "BloombergTypes/Subscription.h"

namespace BEmu
{
	namespace MarketDataRequest
	{
		class MarketElementReason;

		class MarketMessageSubscriptionFailure : public MessagePtr
		{
			private:
				CorrelationId _correlationId;
				std::string _topicName;

				std::shared_ptr<MarketElementReason> _reason;

			public:
				MarketMessageSubscriptionFailure(const Subscription& sub);
				~MarketMessageSubscriptionFailure();

				virtual size_t numElements() const;
				virtual const char* topicName() const;

				virtual std::shared_ptr<ElementPtr> getElement(const char* name) const;

				virtual bool hasElement(const char* name, bool excludeNullElements = false) const;

				virtual std::ostream& print(std::ostream& stream, int level = 0, int spacesPerLevel = 4) const;
		};
	}
}