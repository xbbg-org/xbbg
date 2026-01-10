//------------------------------------------------------------------------------------------------
// <copyright project="BEmu_cpp" file="headers/BloombergTypes/Subscription.h" company="Jordan Robinson">
//     Copyright (c) 2013 Jordan Robinson. All rights reserved.
//
//     The use of this software is governed by the Microsoft Public License
//     which is included with this distribution.
// </copyright>
//------------------------------------------------------------------------------------------------

#pragma once

#include "BloombergTypes/CorrelationId.h"
#include <vector>

namespace BEmu
{
	class Subscription //Note that the BB API does not expose a Subscription class, hence no DLL_EXPORTs here
	{
		private:
			std::string _security, _fields, _options;
			std::vector<std::string> _fieldList;
			CorrelationId _corr;
			bool _isDefault;

			bool _hasConflationInterval;
			int _conflationInterval;
			void construct(const std::string& topic, const std::string& fields, const std::string& options, const CorrelationId& correlationId);

		public:
			Subscription();
			Subscription(const std::string& topic, const std::string& fields, const std::string& options, const CorrelationId& correlationId);
			Subscription(const std::string& topic, const std::string& fields, const std::string& options, const CorrelationId& correlationId, int conflationInterval);
			Subscription(const char* topic, const std::vector<std::string>& fields, const std::vector<std::string>& options, const CorrelationId& correlationId);
			~Subscription();
			Subscription(const Subscription& arg);
			Subscription& operator=(const Subscription& rhs);
			
			const std::string& security() const;
			const std::string& fields() const;
			std::vector<std::string> fieldList() const;
			const std::string& options() const;
			CorrelationId correlationId() const;

			bool hasConflationInterval() const;
			int conflationInterval() const;
			bool isDefault() const;
	};
}