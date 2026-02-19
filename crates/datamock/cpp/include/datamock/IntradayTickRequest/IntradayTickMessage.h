//------------------------------------------------------------------------------------------------
// <copyright project="BEmu_cpp" file="headers/IntradayTickRequest/IntradayTickMessage.h" company="Jordan Robinson">
//     Copyright (c) 2013 Jordan Robinson. All rights reserved.
//
//     The use of this software is governed by the Microsoft Public License
//     which is included with this distribution.
// </copyright>
//------------------------------------------------------------------------------------------------

#pragma once

#include <map>
#include "BloombergTypes/MessagePtr.h"

namespace BEmu
{
	class CorrelationId;
	class Service;
	class Datetime;
	class ElementPtr;

	namespace IntradayTickRequest
	{
		class IntradayTickElementDataParent;
		class IntradayTickElementResponseError;
		class IntradayTickElementTuple3;

		class IntradayTickMessage : public MessagePtr
		{
			private:
				std::shared_ptr<IntradayTickElementDataParent> _parent;
				std::shared_ptr<IntradayTickElementResponseError> _responseError;

				bool _isResponseError;

			public:
				IntradayTickMessage(const CorrelationId& corr, const Service& service, std::map<Datetime, IntradayTickElementTuple3>& ticks, bool includeConditionCodes);

				IntradayTickMessage(const CorrelationId& corr, const Service& service);
				~IntradayTickMessage();

				std::shared_ptr<ElementPtr> firstElement() const;

				virtual const char* topicName() const;
				virtual size_t numElements() const;

				virtual std::shared_ptr<ElementPtr> asElement() const;
				
				virtual std::shared_ptr<ElementPtr> getElement(const char* name) const;
				
				virtual bool hasElement(const char* name, bool excludeNullElements = false) const;

				virtual std::ostream& print(std::ostream& stream, int level = 0, int spacesPerLevel = 4) const;
		};
	}
}