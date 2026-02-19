//------------------------------------------------------------------------------------------------
// <copyright project="BEmu_cpp" file="headers/IntradayBarRequest/IntradayBarEvent.h" company="Jordan Robinson">
//     Copyright (c) 2013 Jordan Robinson. All rights reserved.
//
//     The use of this software is governed by the Microsoft Public License
//     which is included with this distribution.
// </copyright>
//------------------------------------------------------------------------------------------------

#pragma once

#include <vector>
#include "BloombergTypes/EventPtr.h"

namespace BEmu
{
	class MessagePtr;

	namespace IntradayBarRequest
	{
		class IntradayBarRequest;

		class IntradayBarEvent : public EventPtr
		{
			private:
				std::vector< std::shared_ptr<MessagePtr> > _messages;
				std::vector< std::shared_ptr<MessagePtr> > GenerateMessages() const;
				std::shared_ptr<IntradayBarRequest> _internalP;

			public:
				IntradayBarEvent(const std::shared_ptr<IntradayBarRequest>& request);
				~IntradayBarEvent();

				virtual std::vector< std::shared_ptr<MessagePtr> > getMessages() const;
		};
	}
}