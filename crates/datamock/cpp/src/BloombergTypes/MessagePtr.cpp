//------------------------------------------------------------------------------------------------
// <copyright project="BEmu_cpp" file="src/BloombergTypes/MessagePtr.cpp" company="Jordan Robinson">
//     Copyright (c) 2013 Jordan Robinson. All rights reserved.
//
//     The use of this software is governed by the Microsoft Public License
//     which is included with this distribution.
// </copyright>
//------------------------------------------------------------------------------------------------

#include "BloombergTypes/ElementPtr.h"
#include "BloombergTypes/MessagePtr.h"
#include "BloombergTypes/Datetime.h"
#include "BloombergTypes/Name.h"
#include "BloombergTypes/CorrelationId.h"
#include "Types/IndentType.h"
#include <ostream>

namespace BEmu
{
	MessagePtr::MessagePtr(const Name& messageType, const CorrelationId& corr)
	{
		Name n1(messageType);
		this->_messageType = n1;

		CorrelationId c1(corr);
		this->_correlationId = corr;
	}

	MessagePtr::~MessagePtr()
	{
	}

	CorrelationId MessagePtr::correlationId() const
	{
		return this->_correlationId;
	}

	bool MessagePtr::hasElement(const char* name, bool excludeNullElements) const
	{
		(void)name; (void)excludeNullElements;
		throw messageEx;
	}

	Name MessagePtr::messageType() const
	{
		return this->_messageType;
	}

	std::shared_ptr<ElementPtr> MessagePtr::getElement(const char* name) const
	{
		(void)name;
		throw messageEx;
	}

	std::shared_ptr<ElementPtr> MessagePtr::getElement(const Name& name) const
	{
		return this->getElement(name.string());
	}

	const char* MessagePtr::topicName() const
	{
		throw messageEx;
	}

	size_t MessagePtr::numElements() const
	{
		throw messageEx;
	}

	std::shared_ptr<ElementPtr> MessagePtr::asElement() const
	{
		throw messageEx;
	}

	std::ostream& MessagePtr::print(std::ostream& stream, int level, int spacesPerLevel) const
	{
		(void)stream; (void)level; (void)spacesPerLevel;
		throw messageEx;
	}


	bool MessagePtr::getElementAsBool(const char* name) const
	{
		return this->getElement(name)->getValueAsBool(0);
	}

	int MessagePtr::getElementAsInt32(const char* name) const
	{
		return this->getElement(name)->getValueAsInt32(0);
	}

	long MessagePtr::getElementAsInt64(const char* name) const
	{
		return this->getElement(name)->getValueAsInt64(0);
	}

	float MessagePtr::getElementAsFloat32(const char* name) const
	{
		return this->getElement(name)->getValueAsFloat32(0);
	}

	double MessagePtr::getElementAsFloat64(const char* name) const
	{
		return this->getElement(name)->getValueAsFloat64(0);
	}

	Datetime MessagePtr::getElementAsDatetime(const char* name) const
	{
		return this->getElement(name)->getValueAsDatetime(0);
	}
	
	const char* MessagePtr::getElementAsString(const char* name) const
	{
		return this->getElement(name)->getValueAsString(0);
	}

}