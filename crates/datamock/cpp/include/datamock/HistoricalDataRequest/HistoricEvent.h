//------------------------------------------------------------------------------
// <copyright project="BEmu_cpp" file="headers/HistoricalDataRequest/HistoricEvent.h" company="Jordan Robinson">
//     Copyright (c) 2013 Jordan Robinson. All rights reserved.
//
//     The use of this software is governed by the Microsoft Public License
//     which is included with this distribution.
// </copyright>
//------------------------------------------------------------------------------

#pragma once

#include "BloombergTypes/EventPtr.h"
#include <vector>

namespace BEmu
{
	class MessagePtr;

	namespace HistoricalDataRequest
	{
		class HistoricRequest;

		class HistoricEvent : public EventPtr
		{
			private:
				std::vector< std::shared_ptr<MessagePtr> > _messages;
				std::vector< std::shared_ptr<MessagePtr> > GenerateMessages() const;
				std::shared_ptr<HistoricRequest> _internalP;

			public:
				HistoricEvent(std::shared_ptr<HistoricRequest> request);
				~HistoricEvent();

				virtual std::vector< std::shared_ptr<MessagePtr> > getMessages() const;
		};
	}
}