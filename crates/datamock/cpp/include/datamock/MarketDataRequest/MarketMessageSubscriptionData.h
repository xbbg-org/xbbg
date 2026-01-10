//------------------------------------------------------------------------------
// <copyright project="BEmu_cpp" file="headers/MarketDataRequest/MarketMessageSubscriptionData.h" company="Jordan Robinson">
//     Copyright (c) 2013 Jordan Robinson. All rights reserved.
//
//     The use of this software is governed by the Microsoft Public License
//     which is included with this distribution.
// </copyright>
//------------------------------------------------------------------------------

#pragma once

#include "BloombergTypes/MessagePtr.h"
#include "BloombergTypes/Subscription.h"
#include "Types/ObjectType.h"
#include <map>

namespace BEmu
{
	class ElementPtr;

	namespace MarketDataRequest
	{
		class MarketMessageSubscriptionData : public MessagePtr
		{
			private:
				std::map<std::string, std::shared_ptr<ElementPtr> > _fields;

				std::string _security;

			public:
				MarketMessageSubscriptionData(const Subscription& sub, const std::map<std::string, ObjectType>& fields);
				~MarketMessageSubscriptionData();

				virtual const char* topicName() const;
				virtual size_t numElements() const;

				virtual bool hasElement(const char* name, bool excludeNullElements = false) const;

				virtual std::shared_ptr<ElementPtr> getElement(const char* name) const;

				virtual std::ostream& print(std::ostream& stream, int level = 0, int spacesPerLevel = 4) const;
		};
	}
}