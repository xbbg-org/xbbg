//------------------------------------------------------------------------------------------------
// <copyright project="BEmu_cpp" file="headers/BloombergTypes/SubscriptionList.h" company="Jordan Robinson">
//     Copyright (c) 2013 Jordan Robinson. All rights reserved.
//
//     The use of this software is governed by the Microsoft Public License
//     which is included with this distribution.
// </copyright>
//------------------------------------------------------------------------------------------------

#pragma once

#include "bemu_headers.h"
#include "BloombergTypes/CorrelationId.h"
#include "BloombergTypes/Subscription.h"
#include <vector>

namespace BEmu
{
	class SubscriptionList
	{
		private:
			std::vector<Subscription> _subs;

		public:
			DLL_EXPORT SubscriptionList();
			DLL_EXPORT ~SubscriptionList();
			
			DLL_EXPORT SubscriptionList(const SubscriptionList& original);
			DLL_EXPORT SubscriptionList& operator=(const SubscriptionList& rhs);
			
			DLL_EXPORT int add(const char* topic, const char* fields, const char* options, const CorrelationId& correlationId);
			DLL_EXPORT int add(const char* topic, const std::vector<std::string>& fields, const std::vector<std::string>& options, const CorrelationId& correlationId);
			DLL_EXPORT int append(const SubscriptionList& other);
			DLL_EXPORT void clear();

			DLL_EXPORT size_t size() const;
			DLL_EXPORT CorrelationId correlationIdAt(size_t index) const;
			DLL_EXPORT const char* topicStringAt(size_t index) const;

			void add(const Subscription& sub);
			Subscription remove(const CorrelationId& corr);

			std::vector<Subscription> list() const;
	};
}