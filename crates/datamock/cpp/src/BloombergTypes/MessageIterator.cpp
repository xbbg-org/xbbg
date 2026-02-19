//------------------------------------------------------------------------------------------------
// <copyright project="BEmu_cpp" file="src/BloombergTypes/MessageIterator.cpp" company="Jordan Robinson">
//     Copyright (c) 2013 Jordan Robinson. All rights reserved.
//
//     The use of this software is governed by the Microsoft Public License
//     which is included with this distribution.
// </copyright>
//------------------------------------------------------------------------------------------------

#include "BloombergTypes/Message.h"
#include "BloombergTypes/MessagePtr.h"
#include "BloombergTypes/MessageIterator.h"
#include "BloombergTypes/Event.h"
#include "BloombergTypes/EventPtr.h"
#include "BloombergTypes/ElementPtr.h"
#include <stack>

namespace BEmu
{
	MessageIterator::MessageIterator(const Event& evt)
	{
		this->_position = -1;

		std::shared_ptr<EventPtr> evtP(evt.getEventPtr());

		std::vector< std::shared_ptr<MessagePtr> > list = evtP->getMessages();
		
		for(std::vector< std::shared_ptr<MessagePtr> >::const_iterator iter = list.begin(); iter != list.end(); ++iter)
		{
			std::shared_ptr<MessagePtr> msg = *iter;

			this->_listP.push_back(msg);
		}
	}

	MessageIterator::~MessageIterator()
	{
		this->_listP.clear();
	}

	bool MessageIterator::next()
	{
		this->_position++;
		return this->_position < (int)(this->_listP.size());
	}

	bool MessageIterator::isValid() const
	{
		return this->_position >= 0 && this->_position < (int)(this->_listP.size());
	}

	Message MessageIterator::message(bool createClonable) const
	{
		(void)createClonable;
		std::shared_ptr<MessagePtr> messageP = this->_listP.at(this->_position);
		Message msg(messageP);
		return msg;
	}
}