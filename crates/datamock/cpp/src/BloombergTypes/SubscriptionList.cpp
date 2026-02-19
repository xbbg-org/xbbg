//------------------------------------------------------------------------------------------------
// <copyright project="BEmu_cpp" file="src/BloombergTypes/SubscriptionList.cpp" company="Jordan Robinson">
//     Copyright (c) 2013 Jordan Robinson. All rights reserved.
//
//     The use of this software is governed by the Microsoft Public License
//     which is included with this distribution.
// </copyright>
//------------------------------------------------------------------------------------------------

#include "BloombergTypes/SubscriptionList.h"
#include "BloombergTypes/Subscription.h"

namespace BEmu
{
	SubscriptionList::SubscriptionList() :
		_subs()
	{
	}
	
	SubscriptionList::~SubscriptionList()
	{
	}
	
	SubscriptionList::SubscriptionList(const SubscriptionList& original) :
		_subs(original._subs.begin(), original._subs.end())
	{
	}

	int SubscriptionList::add(const char* topic, const char* fields, const char* options, const CorrelationId& correlationId)
	{
		Subscription sub(topic, fields, options, correlationId);
		this->_subs.push_back(sub);
		return 1; //I'm not sure what the add function returns
	}

	int SubscriptionList::add(const char* topic, const std::vector<std::string>& fields, const std::vector<std::string>& options, const CorrelationId& correlationId)
	{
		Subscription sub(topic, fields, options, correlationId);
		this->_subs.push_back(sub);
		return 1; //I'm not sure what the add function returns
	}

	int SubscriptionList::append(const SubscriptionList& other)
	{
		for(size_t i = 0; i < other._subs.size(); i++)
		{
			this->_subs.push_back(other._subs[i]);
		}
		return 1; //I'm not sure what the append function returns
	}

	SubscriptionList& SubscriptionList::operator=(const SubscriptionList& rhs)
	{
		if (this != &rhs)
		{
			this->_subs.clear();
			this->append(rhs);
		}
		return *this;
	}

	CorrelationId SubscriptionList::correlationIdAt(size_t index) const
	{
		return this->_subs[index].correlationId();
	}

	const char* SubscriptionList::topicStringAt(size_t index) const
	{
		return this->_subs[index].security().c_str();
	}

	size_t SubscriptionList::size() const
	{
		return this->_subs.size();
	}

	void SubscriptionList::clear()
	{
		this->_subs.clear();
	}

	void SubscriptionList::add(const Subscription& sub)
	{
		this->_subs.push_back(sub);
	}

	Subscription SubscriptionList::remove(const CorrelationId& corr)
	{
		Subscription removed;
		for(size_t i = 0; i < this->_subs.size(); i++)
		{
			Subscription current(this->_subs[i]);

			if(current.correlationId() == corr) //find the subscription by corrId
			{
				removed = current;
				this->_subs.erase(this->_subs.begin() + i); //remove the subscription
				break;
			}
		}

		return removed;
	}

	std::vector<Subscription> SubscriptionList::list() const
	{
		return this->_subs;
	}
}