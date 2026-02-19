//------------------------------------------------------------------------------------------------
// <copyright project="BEmu_cpp" file="src/BloombergTypes/Event.cpp" company="Jordan Robinson">
//     Copyright (c) 2013 Jordan Robinson. All rights reserved.
//
//     The use of this software is governed by the Microsoft Public License
//     which is included with this distribution.
// </copyright>
//------------------------------------------------------------------------------------------------

#include "BloombergTypes/Event.h"
#include "BloombergTypes/EventPtr.h"
#include "BloombergTypes/RequestPtr.h"

namespace BEmu
{
	Event::Event()
		: _ptrP()
	{
	}

	Event::Event(std::shared_ptr<EventPtr> ptr)
		: _ptrP(ptr)
	{
	}

	Event::Event(const Event& arg)
		: _ptrP(arg._ptrP)
	{
	}

	Event::~Event()
	{
	}

	std::shared_ptr<EventPtr> Event::getEventPtr() const
	{
		return this->_ptrP;
	}

	Event& Event::operator=(const Event &rhs)
	{
		if (this != &rhs)
		{
			this->_ptrP = rhs._ptrP;
		}
		return *this;
	}

	Event::EventType Event::eventType() const
	{
		return this->_ptrP->getEventType();
	}
}