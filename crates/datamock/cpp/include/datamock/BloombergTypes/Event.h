//------------------------------------------------------------------------------------------------
// <copyright project="BEmu_cpp" file="headers/BloombergTypes/Event.h" company="Jordan Robinson">
//     Copyright (c) 2013 Jordan Robinson. All rights reserved.
//
//     The use of this software is governed by the Microsoft Public License
//     which is included with this distribution.
// </copyright>
//------------------------------------------------------------------------------------------------

#pragma once

#include "bemu_headers.h"
#include <exception>
#include <vector>

namespace BEmu
{
	class Name;
	class EventPtr;
	class MessageIterator;
	class Session;
	class Datetime;
	class RequestPtr;
	class Message;
	
	//See my explanation of the RequetPtr class in Request.h for an explanation of this class
	class Event
	{
		private:
			std::shared_ptr<EventPtr> _ptrP;

		public:
			enum EventType {
			  // The possible types of event
			  ADMIN                 = 1,
				// Admin event
			  SESSION_STATUS        = 2,
				// Status updates for a session.
			  SUBSCRIPTION_STATUS   = 3,
				// Status updates for a subscription.
			  REQUEST_STATUS        = 4,
				// Status updates for a request.
			  RESPONSE              = 5,
				// The final (possibly only) response to a request.
			  PARTIAL_RESPONSE      = 6,
				// A partial response to a request.

				//where's 7?  No love for 7?  7's my lucky number :{

			  SUBSCRIPTION_DATA     = 8,
				// Data updates resulting from a subscription.
			  SERVICE_STATUS        = 9,
				// Status updates for a service.
			  TIMEOUT               = 10,
				// An Event returned from nextEvent() if it timed out.
			  AUTHORIZATION_STATUS  = 11,
				// Status updates for user authorization.
			  RESOLUTION_STATUS     = 12,
				// Status updates for a resolution operation.
			  TOPIC_STATUS          = 13,
				// Status updates about topics for service providers.
			  TOKEN_STATUS          = 14,
				// Status updates for a generate token request.
			  REQUEST               = 15,
				// Request event
			  UNKNOWN               = -1
			};
			
			Event(std::shared_ptr<EventPtr> ptr);

			std::shared_ptr<EventPtr> getEventPtr() const;

			DLL_EXPORT Event();			
			DLL_EXPORT Event(const Event& arg);
			DLL_EXPORT Event& operator=(const Event &rhs);
			DLL_EXPORT ~Event();

			DLL_EXPORT EventType eventType() const;
	};
}