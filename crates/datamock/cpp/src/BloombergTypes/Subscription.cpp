//------------------------------------------------------------------------------------------------
// <copyright project="BEmu_cpp" file="src/BloombergTypes/Subscription.cpp" company="Jordan Robinson">
//     Copyright (c) 2013 Jordan Robinson. All rights reserved.
//
//     The use of this software is governed by the Microsoft Public License
//     which is included with this distribution.
// </copyright>
//------------------------------------------------------------------------------------------------

#include "BloombergTypes/Subscription.h"

#include <iostream>
#include <string>
#include <sstream>
#include <algorithm>
#include <iterator>

namespace BEmu
{
	Subscription::Subscription()
	{
		this->_isDefault = true;
	}

	Subscription::Subscription(const std::string& topic, const std::string& fields, const std::string& options, const CorrelationId& correlationId)
	{
		this->_isDefault = false;
		this->construct(topic, fields, options, correlationId);
		this->_hasConflationInterval = false;
	}

	Subscription::Subscription(const std::string& topic, const std::string& fields, const std::string& options, const CorrelationId& correlationId, int conflationInterval)
	{
		this->_isDefault = false;
		this->construct(topic, fields, options, correlationId);
		this->_hasConflationInterval = true;
		this->_conflationInterval = conflationInterval;
	}

	Subscription::Subscription(const char* topic, const std::vector<std::string>& fields, const std::vector<std::string>& options, const CorrelationId& correlationId)
	{
		this->_isDefault = false;
		this->_corr = correlationId;
		this->_security = topic;
		this->_fieldList = std::vector<std::string>(fields);

		std::stringstream ssFields;
		for(size_t i = 0; i < fields.size(); i++)
		{
			ssFields << fields[i];
			if(i < fields.size() - 1)
				ssFields << ",";
		}
		this->_fields = std::string(ssFields.str());

		std::stringstream ssOptions;
		for(size_t i = 0; i < options.size(); i++)
		{
			ssOptions << options[i];
			if(i < options.size())
				ssOptions << ",";
		}
		this->_options = std::string(ssOptions.str());
	}

	void Subscription::construct(const std::string& topic, const std::string& fields, const std::string& options, const CorrelationId& correlationId)
	{
		this->_corr = correlationId;
		this->_fields = fields;
		this->_options = options;
		this->_security = topic;

		int start = 0;
		for(size_t i = 1; i < fields.length(); i++)
		{
			if(fields.at(i) == ',')
			{
				std::string current = fields.substr(start, i - start);
				this->_fieldList.push_back(current);
				
				start = i + 1;
				i = start + 1;
			}
		}

		std::string last = fields.substr(start);
		this->_fieldList.push_back(last);
	}

	Subscription::~Subscription()
	{
	}

	Subscription::Subscription(const Subscription& arg)
	{
		this->_isDefault = arg._isDefault;
		this->_corr = arg._corr;
		this->_fields = arg._fields;
		this->_options = arg._options;
		this->_security = arg._security;

		this->_fieldList = std::vector<std::string>(arg._fieldList.begin(), arg._fieldList.end());
	}

	Subscription& Subscription::operator=(const Subscription& rhs)
	{
		if (this != &rhs)
		{
			this->_isDefault = rhs._isDefault;
			this->_corr = rhs._corr;
			this->_fields = rhs._fields;
			this->_options = rhs._options;
			this->_security = rhs._security;

			this->_fieldList = std::vector<std::string>(rhs._fieldList.begin(), rhs._fieldList.end());
		}
		return *this;
	}

	std::vector<std::string> Subscription::fieldList() const
	{
		return this->_fieldList;
	}

	const std::string& Subscription::security() const
	{
		return this->_security;
	}

	const std::string& Subscription::fields() const
	{
		return this->_fields;
	}

	const std::string& Subscription::options() const
	{
		return this->_options;
	}

	CorrelationId Subscription::correlationId() const
	{
		return this->_corr;
	}

	bool Subscription::hasConflationInterval() const
	{
		return this->_hasConflationInterval;
	}

	int Subscription::conflationInterval() const
	{
		return this->_conflationInterval;
	}

	bool Subscription::isDefault() const
	{
		return this->_isDefault;
	}
}