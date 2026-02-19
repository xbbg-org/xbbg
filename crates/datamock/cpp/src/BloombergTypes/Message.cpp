//------------------------------------------------------------------------------------------------
// <copyright project="BEmu_cpp" file="src/BloombergTypes/Message.cpp" company="Jordan Robinson">
//     Copyright (c) 2013 Jordan Robinson. All rights reserved.
//
//     The use of this software is governed by the Microsoft Public License
//     which is included with this distribution.
// </copyright>
//------------------------------------------------------------------------------------------------

#include "BloombergTypes/Message.h"
#include "BloombergTypes/MessagePtr.h"
#include "BloombergTypes/Name.h"
#include "BloombergTypes/CorrelationId.h"

#include "BloombergTypes/ElementPtr.h"
#include "BloombergTypes/Element.h"
#include <ostream>

namespace BEmu
{
	Message::Message() : _ptr()
	{
	}

	Message::Message(std::shared_ptr<MessagePtr> ptr)
		: _ptr(ptr)
	{
	}

	Message::Message(const Message& arg)
		: _ptr(arg._ptr)
	{
	}

	Message& Message::operator=(const Message &rhs)
	{
		if (this != &rhs)
		{
			this->_ptr = rhs._ptr;
		}
		return *this;
	}

	CorrelationId Message::correlationId() const
	{
		return this->_ptr->correlationId();
	}

	Name Message::messageType() const
	{
		return this->_ptr->messageType();
	}

	const char* Message::topicName() const
	{
		return this->_ptr->topicName();
	}

	size_t Message::numElements() const
	{
		return this->_ptr->numElements();
	}

	const Element Message::asElement() const
	{
		std::shared_ptr<ElementPtr> elmP(this->_ptr->asElement());
		return Element(elmP);
	}

	const Element Message::getElement(const char* name) const
	{
		std::shared_ptr<ElementPtr> elmP(this->_ptr->getElement(name));
		return Element(elmP);
	}
	const Element Message::getElement(const Name& name) const
	{
		return this->getElement(name.string());
	}

	bool Message::hasElement(const Name& name, bool excludeNullElements) const
	{
		return this->hasElement(name.string(), excludeNullElements);
	}
	bool Message::hasElement(const char* name, bool excludeNullElements) const
	{
		return this->_ptr->hasElement(name, excludeNullElements);
	}

	bool Message::getElementAsBool(const char* name) const
	{
		return this->_ptr->getElementAsBool(name);
	}
	bool Message::getElementAsBool(const Name& name) const
	{
		return this->getElementAsBool(name.string());
	}

	int Message::getElementAsInt32(const char* name) const
	{
		return this->_ptr->getElementAsInt32(name);
	}
	int Message::getElementAsInt32(const Name& name) const
	{
		return this->getElementAsInt32(name.string());
	}

	long Message::getElementAsInt64(const char* name) const
	{
		return this->_ptr->getElementAsInt64(name);
	}
	long Message::getElementAsInt64(const Name& name) const
	{
		return this->getElementAsInt64(name.string());
	}

	float Message::getElementAsFloat32(const char* name) const
	{
		return this->_ptr->getElementAsFloat32(name);
	}
	float Message::getElementAsFloat32(const Name& name) const
	{
		return this->getElementAsFloat32(name.string());
	}

	double Message::getElementAsFloat64(const char* name) const
	{
		return this->_ptr->getElementAsFloat64(name);
	}
	double Message::getElementAsFloat64(const Name& name) const
	{
		return this->getElementAsFloat64(name.string());
	}

	Datetime Message::getElementAsDatetime(const char* name) const
	{
		return this->_ptr->getElementAsDatetime(name);
	}
	Datetime Message::getElementAsDatetime(const Name& name) const
	{
		return this->getElementAsDatetime(name.string());
	}

	const char* Message::getElementAsString(const char* name) const
	{
		return this->_ptr->getElementAsString(name);
	}
	const char* Message::getElementAsString(const Name& name) const
	{
		return this->getElementAsString(name.string());
	}

	std::ostream& Message::print(std::ostream& stream, int level, int spacesPerLevel) const
	{
		return this->_ptr->print(stream, level, spacesPerLevel);
	}

	std::ostream& operator<<(std::ostream& stream, const Message &message)
	{
		return message.print(stream);
	}

}