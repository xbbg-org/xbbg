//------------------------------------------------------------------------------
// <copyright project="BEmu_cpp" file="headers/MarketDataRequest/MarketEvent.h" company="Jordan Robinson">
//     Copyright (c) 2013 Jordan Robinson. All rights reserved.
//
//     The use of this software is governed by the Microsoft Public License
//     which is included with this distribution.
// </copyright>
//------------------------------------------------------------------------------

#pragma once

#include "BloombergTypes/EventPtr.h"
#include "BloombergTypes/CorrelationId.h"
#include "BloombergTypes/Event.h"
#include "BloombergTypes/Subscription.h"
#include "BloombergTypes/SubscriptionList.h"
#include "Types/ObjectType.h"
#include <vector>
#include <map>

namespace BEmu
{
	class MessagePtr;

	namespace MarketDataRequest
	{
		class MarketEvent : public EventPtr
		{
			private:
				std::vector< std::shared_ptr<MessagePtr> > _messages;

				std::map<std::string, ObjectType> generateFakeMessageData(const Subscription& sub) const;

				virtual std::vector< std::shared_ptr<MessagePtr> > getMessages() const;

			public:
				MarketEvent(Event::EventType evtType, const CorrelationId& corr, const SubscriptionList& subs); //use for subscribing
				MarketEvent(Event::EventType evtType, const Subscription& sub); //use for unsubscribing
				~MarketEvent();
		};
	}
}