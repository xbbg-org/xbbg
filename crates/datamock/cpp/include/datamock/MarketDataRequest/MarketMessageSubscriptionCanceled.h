//------------------------------------------------------------------------------
// <copyright project="BEmu_cpp" file="headers/MarketDataRequest/MarketMessageSubscriptionCanceled.h" company="Jordan Robinson">
//     Copyright (c) 2013 Jordan Robinson. All rights reserved.
//
//     The use of this software is governed by the Microsoft Public License
//     which is included with this distribution.
// </copyright>
//------------------------------------------------------------------------------

#pragma once

#include "BloombergTypes/MessagePtr.h"
#include "BloombergTypes/Subscription.h"
#include "Types/CanConvertToStringType.h"

namespace BEmu
{
	namespace MarketDataRequest
	{
		class MarketElementSubscriptionCancelReason;

		class MarketMessageSubscriptionCanceled : public MessagePtr, public CanConvertToStringType
		{
			private:
				std::string _topicName;

				std::shared_ptr<MarketElementSubscriptionCancelReason> _reason;

			public:
				MarketMessageSubscriptionCanceled(const Subscription& sub);
				~MarketMessageSubscriptionCanceled();

				virtual size_t numElements() const;
				virtual const char* topicName() const;

				virtual std::shared_ptr<ElementPtr> asElement() const;

				virtual std::ostream& print(std::ostream& stream, int level = 0, int spacesPerLevel = 4) const;
		};
	}
}