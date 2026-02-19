//------------------------------------------------------------------------------------------------
// <copyright project="BEmu_cpp" file="headers/BloombergTypes/Session.h" company="Jordan Robinson">
//     Copyright (c) 2013 Jordan Robinson. All rights reserved.
//
//     The use of this software is governed by the Microsoft Public License
//     which is included with this distribution.
// </copyright>
//------------------------------------------------------------------------------------------------

#pragma once

#include "BloombergTypes/SessionOptions.h"
#include "BloombergTypes/CorrelationId.h"
#include "BloombergTypes/SubscriptionList.h"
#include "Types/BEmuTimerFunction.h"
#include <queue>
#include <vector>
#include <exception>

namespace BEmu
{
	class RequestPtr;
	class Service;
	class Request;
	class Event;
	class EventHandler;
	class BEmuTimer;
	class SessionTimerFunction;

	class Session
	{
		private:
			enum SessionStateType { initialized, started, serviceOpened, stopped, connectionFailure };
			SessionStateType _sessionState;
			SessionOptions _sessionOptions;

			std::queue<std::shared_ptr<RequestPtr>> _sentRequests;

			EventHandler * _asyncHandler;
			SubscriptionList _subs;

			std::shared_ptr<SessionTimerFunction> _sessionTimerFunction;
			std::shared_ptr<BEmuTimer> _marketSimulatorTimer;

			bool _isNull_marketSimulatorTimer;

		public:

			class SessionException: public std::exception
			{
				virtual const char* what() const throw()
				{
					return "My exception happened";
				}
			} sessionEx;

			///////////////////// Start Sync
			DLL_EXPORT Session(const SessionOptions& options);
			DLL_EXPORT bool start();
			DLL_EXPORT void stop();
			DLL_EXPORT bool openService(const char* uri);
			DLL_EXPORT Service getService(const char* uri) const;
			DLL_EXPORT CorrelationId sendRequest(const Request& request, const CorrelationId& correlationId = CorrelationId());
			DLL_EXPORT Event nextEvent(int timeout=0);
			///////////////////// End Sync

			///////////////////// Start Async
			DLL_EXPORT Session(const SessionOptions& options, EventHandler * eventHandler);
			DLL_EXPORT bool startAsync();
			SubscriptionList getSubscriptions() const;

			DLL_EXPORT void subscribe(const SubscriptionList& subscriptionList);

			DLL_EXPORT CorrelationId openServiceAsync(const char* uri, const CorrelationId& correlationId = CorrelationId());

			DLL_EXPORT void unsubscribe(const SubscriptionList& subscriptionList);
			DLL_EXPORT void cancel(const CorrelationId& correlationId); //defined in blpapi_abstractsession.h
			DLL_EXPORT void cancel(const std::vector<CorrelationId>& correlationIds); //defined in blpapi_abstractsession.h
			DLL_EXPORT void cancel(const CorrelationId* correlationIds, size_t numCorrelationIds); //defined in blpapi_abstractsession.h
			///////////////////// End Async

			DLL_EXPORT ~Session();
	};
}