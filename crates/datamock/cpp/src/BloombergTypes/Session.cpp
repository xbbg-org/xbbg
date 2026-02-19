//------------------------------------------------------------------------------------------------
// <copyright project="BEmu_cpp" file="src/BloombergTypes/Session.cpp" company="Jordan Robinson">
//     Copyright (c) 2013 Jordan Robinson. All rights reserved.
//
//     The use of this software is governed by the Microsoft Public License
//     which is included with this distribution.
// </copyright>
//------------------------------------------------------------------------------------------------

#include <cstring>
#include <cstdlib>
#include <ctime>

#include "BloombergTypes/Session.h"
#include "BloombergTypes/Service.h"
#include "BloombergTypes/Event.h"
#include "BloombergTypes/EventPtr.h"
#include "BloombergTypes/RequestPtr.h"
#include "BloombergTypes/EventHandler.h"
#include "Types/BEmuTimer.h"
#include "BloombergTypes/SessionTimerFunction.h"

#include "MarketDataRequest/MarketEvent.h"
#include "BloombergTypes/CorrelationId.h"
#include "BloombergTypes/SubscriptionList.h"

#include "IntradayTickRequest/IntradayTickElement.h"

namespace BEmu
{
	Session::Session(const SessionOptions& options) : //for sync calls (HistRef, Intraday, and Reference)
		_sessionTimerFunction(std::shared_ptr<SessionTimerFunction>()),
		_marketSimulatorTimer(std::shared_ptr<BEmuTimer>())
	{
		srand((unsigned int)time(0));
		this->_sessionState = initialized;

		this->_sessionOptions.setServerHost(options.serverHost());
		this->_sessionOptions.setServerPort(options.serverPort());

		this->_isNull_marketSimulatorTimer = true;
	}

	Session::Session(const SessionOptions& options, EventHandler * eventHandler) //for async calls (MarketDataSubscriptions)
	{
		srand((unsigned int)time(0));
		this->_asyncHandler = eventHandler;
		
		this->_sessionOptions.setServerHost(options.serverHost());
		this->_sessionOptions.setServerPort(options.serverPort());

		this->_sessionTimerFunction = std::shared_ptr<SessionTimerFunction>(new SessionTimerFunction(this, eventHandler));

		this->_marketSimulatorTimer = std::shared_ptr<BEmuTimer>(new BEmuTimer(this->_sessionTimerFunction));
		this->_marketSimulatorTimer->start(0, RunType::neverRun);
		
		this->_isNull_marketSimulatorTimer = false;
	}

	Session::~Session()
	{
		if(!this->_isNull_marketSimulatorTimer)
			this->_marketSimulatorTimer->stop();

		while(!this->_sentRequests.empty())
		{
			std::shared_ptr<RequestPtr> request(this->_sentRequests.front());

			this->_sentRequests.pop();
		}

		//Clear the global name table when a Session is de-allocated.
		//  This prevents a _CRTDBG_MAP_ALLOC memory leak message.
		//  For performance, it doesn't matter if I clear out this table or not,
		//    but I was hunting down memory leaks and removing memory leaks related to this table clears out a lot of messages.
		//Note: The actual BB API appears to never clear out its global name table.
		//  The caller will notice no difference whether or not I call clearGlobalNameTable here.
		Name::clearGlobalNameTable();
	}

	void Session::subscribe(const SubscriptionList& subscriptionList)
	{
		std::vector<Subscription> subs = subscriptionList.list();
		for(std::vector<Subscription>::const_iterator iter = subs.begin(); iter != subs.end(); ++iter)
		{
			Subscription sub = *iter;
			this->_subs.add(sub);
		}

		if (this->_asyncHandler != 0)
        {
			std::shared_ptr<MarketDataRequest::MarketEvent> evtSubStatusP(new MarketDataRequest::MarketEvent(Event::SUBSCRIPTION_STATUS, CorrelationId(), subscriptionList));
			std::shared_ptr<EventPtr> evtP = std::dynamic_pointer_cast<EventPtr>(evtSubStatusP);
			const Event ev(evtP);

			this->_asyncHandler->processEvent(ev, this);
        }
	}

	void Session::unsubscribe(const SubscriptionList& subscriptionList)
	{
		std::vector<Subscription> subs(subscriptionList.list());
		for(std::vector<Subscription>::const_iterator iter = subs.begin(); iter != subs.end(); ++iter)
		{
			Subscription subCurrent = *iter;
			CorrelationId corr = subCurrent.correlationId();
			this->cancel(corr);
		}
	}

	void Session::cancel(const CorrelationId& correlationId)
	{
		//remove subscription from the internal list
		Subscription removed = this->_subs.remove(correlationId);
		
		//send a notification to the user about the removed subscription
		if (this->_asyncHandler != 0 && !removed.isDefault())
		{
			std::shared_ptr<MarketDataRequest::MarketEvent> evtSubStatusP(new MarketDataRequest::MarketEvent(Event::SUBSCRIPTION_STATUS, removed));
			std::shared_ptr<EventPtr> evtP = std::dynamic_pointer_cast<EventPtr>(evtSubStatusP);
			const Event ev(evtP);

			this->_asyncHandler->processEvent(ev, this);
		}
	}

	void Session::cancel(const std::vector<CorrelationId>& correlationIds)
	{
		for(std::vector<CorrelationId>::const_iterator iter = correlationIds.begin(); iter != correlationIds.end(); ++iter)
		{
			CorrelationId corr = *iter;
			this->cancel(corr);
		}
	}

	void Session::cancel(const CorrelationId* correlationIds, size_t numCorrelationIds)
	{
		for(size_t i = 0; i < numCorrelationIds; i++)
		{
			CorrelationId corr = correlationIds[i];
			this->cancel(corr);
		}
	}

	CorrelationId Session::openServiceAsync(const char* uri, const CorrelationId& correlationId)
	{
		(void)uri;
		this->_sessionState = serviceOpened;
		return correlationId;
	}

	SubscriptionList Session::getSubscriptions() const
	{
		return this->_subs;
	}

	bool Session::startAsync()
	{
		this->_sessionState = started;

		if (this->_asyncHandler != 0)
		{
			{
				std::shared_ptr<MarketDataRequest::MarketEvent> evtSessionStatusP(new MarketDataRequest::MarketEvent(Event::SESSION_STATUS, CorrelationId(), SubscriptionList()));
				std::shared_ptr<EventPtr> evtP1 = std::dynamic_pointer_cast<EventPtr>(evtSessionStatusP);
				const Event ev1(evtP1);

				this->_asyncHandler->processEvent(ev1, this);
			}

			{
				std::shared_ptr<MarketDataRequest::MarketEvent> evtServiceStatusP(new MarketDataRequest::MarketEvent(Event::SERVICE_STATUS, CorrelationId(), SubscriptionList()));
				std::shared_ptr<EventPtr> evtP2 = std::dynamic_pointer_cast<EventPtr>(evtServiceStatusP);
				const Event ev2(evtP2);
			
				this->_asyncHandler->processEvent(ev2, this);
			}
        }
		
		return true;
	}

	bool Session::start()
	{
		if(this->_sessionOptions.serverPort() == 8194 && 
			( strncmp(this->_sessionOptions.serverHost(), "localhost", 10) == 0 || strncmp(this->_sessionOptions.serverHost(), "127.0.0.1", 10) == 0 ))
		{
			this->_sessionState = started;
			return true;
		}
		else
		{
			this->_sessionState = connectionFailure;
			return false;
		}
	}

	void Session::stop()
	{
		this->_sessionState = stopped;

		if(!this->_isNull_marketSimulatorTimer)
			this->_marketSimulatorTimer->stopAndWait();
	}

	bool Session::openService(const char* uri)
	{
		if(strncmp("//blp/refdata", uri, 14) == 0)
		{
			this->_sessionState = serviceOpened;
			return true;
		}
		else
			return false;
	}

	Service Session::getService(const char* uri) const
	{
		if(strncmp("//blp/refdata", uri, 14) == 0)
		{
			Service result;
			return result;
		}
		else
		{
			throw sessionEx;
		}
	}

	CorrelationId Session::sendRequest(const Request& request, const CorrelationId& correlationId)
	{
		request.getRequestPtr()->setCorrelationId(correlationId);
		this->_sentRequests.push(request.getRequestPtr());

		return correlationId;
	}

	Event Session::nextEvent(int timeout)
	{
		(void)timeout;
		bool isLastRequest = this->_sentRequests.size() == 1;
		std::shared_ptr<RequestPtr> reqP = this->_sentRequests.front();
		
		this->_sentRequests.pop();

		std::shared_ptr<EventPtr> evtP(EventPtr::EventFactory(reqP, isLastRequest));

		if(isLastRequest)
			evtP->setEventType(Event::RESPONSE);
		else
			evtP->setEventType(Event::PARTIAL_RESPONSE);

		Event result(evtP);
		return result;
	}

}