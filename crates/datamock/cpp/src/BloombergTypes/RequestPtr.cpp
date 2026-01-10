//------------------------------------------------------------------------------------------------
// <copyright project="BEmu_cpp" file="src/BloombergTypes/RequestPtr.cpp" company="Jordan Robinson">
//     Copyright (c) 2013 Jordan Robinson. All rights reserved.
//
//     The use of this software is governed by the Microsoft Public License
//     which is included with this distribution.
// </copyright>
//------------------------------------------------------------------------------------------------

#include "BloombergTypes/RequestPtr.h"
#include "BloombergTypes/Name.h"
#include "BloombergTypes/Datetime.h"
#include "BloombergTypes/CorrelationId.h"
#include <ostream>

namespace BEmu
{
	RequestPtr::RequestPtr()
	{
		this->_correlationId = CorrelationId();
	}

	RequestPtr::RequestPtr(const RequestPtr &src)
	{
		this->_correlationId = src._correlationId;
		this->_requestType = src._requestType;
	}

	RequestPtr::~RequestPtr()
	{
	}

	CorrelationId RequestPtr::getCorrelationId() const
	{
		return this->_correlationId;
	}

	void RequestPtr::setCorrelationId(const CorrelationId& arg)
	{
		this->_correlationId = arg;
	}

	RequestPtr::RequestTypeEnum RequestPtr::getRequestType() const
	{
		return this->_requestType;
	}

	void RequestPtr::append(const char* name, const char* value)
	{
		(void)name; (void)value;
		throw requestEx;
	}
	void RequestPtr::append(const Name& name, const char* value) { return this->append(name.string(), value); }

	void RequestPtr::set(const char* name, const char* value) { (void)name; (void)value; throw requestEx; }
	void RequestPtr::set(const Name& name, const char* value) { return this->set(name.string(), value); }

	void RequestPtr::set(const char* name, bool value) { (void)name; (void)value; throw requestEx; }
	void RequestPtr::set(const Name& name, bool value) { return this->set(name.string(), value); }

	void RequestPtr::set(const char* name, int value) { (void)name; (void)value; throw requestEx; }
	void RequestPtr::set(const Name& name, int value) { return this->set(name.string(), value); }

	void RequestPtr::set(const char* name, const Datetime& value) { (void)name; (void)value; throw requestEx; }
	void RequestPtr::set(const Name& name, const Datetime& value) { return this->set(name.string(), value); }

	Element RequestPtr::getElement(const char* name) { (void)name; throw requestEx; }
	Element RequestPtr::getElement(const Name& name) { return this->getElement(name.string()); }

	std::ostream& RequestPtr::print(std::ostream& stream, int level, int spacesPerLevel) const
	{
		(void)stream; (void)level; (void)spacesPerLevel;
		throw requestEx;
	}

	std::ostream& operator<<(std::ostream& stream, const RequestPtr &request)
	{
		request.print(stream);
		return stream;
	}

}