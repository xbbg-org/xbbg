//------------------------------------------------------------------------------------------------
// <copyright project="BEmu_cpp" file="headers/BloombergTypes/EventPtr.h" company="Jordan Robinson">
//     Copyright (c) 2013 Jordan Robinson. All rights reserved.
//
//     The use of this software is governed by the Microsoft Public License
//     which is included with this distribution.
// </copyright>
//------------------------------------------------------------------------------------------------

#pragma once

#include "BloombergTypes/Event.h"
#include <exception>
#include <vector>

namespace BEmu
{
	class Name;
	class Session;
	class MessageIterator;
	class Datetime;
	class RequestPtr;
	class MessagePtr;

	class EventPtr
	{
		private: //can I make these private?
			std::shared_ptr<RequestPtr> _requestP;
			Event::EventType _type;

		public:
			EventPtr(std::shared_ptr<RequestPtr> request);

			EventPtr(const EventPtr &src);
			virtual ~EventPtr();
			
			Event::EventType getEventType() const;
			void setEventType(Event::EventType evtType);

			virtual std::vector< std::shared_ptr<MessagePtr> > getMessages() const;
			
			static std::shared_ptr<EventPtr> EventFactory(std::shared_ptr<RequestPtr> request, bool isLastRequest);

			class EventPtrException: public std::exception
			{
				virtual const char* what() const throw()
				{
					return "My exception happened";
				}
			} eventPtrEx;
	};
}