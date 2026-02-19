//------------------------------------------------------------------------------------------------
// <copyright project="BEmu_cpp" file="src/IntradayTickRequest/IntradayTickMessage.cpp" company="Jordan Robinson">
//     Copyright (c) 2013 Jordan Robinson. All rights reserved.
//
//     The use of this software is governed by the Microsoft Public License
//     which is included with this distribution.
// </copyright>
//------------------------------------------------------------------------------------------------

#include "IntradayTickRequest/IntradayTickMessage.h"
#include "BloombergTypes/Name.h"
#include "BloombergTypes/ElementPtr.h"
#include "BloombergTypes/CorrelationId.h"
#include "BloombergTypes/Service.h"
#include "IntradayTickRequest/IntradayTickElementDataParent.h"
#include "IntradayTickRequest/IntradayTickElementResponseError.h"
#include "IntradayTickRequest/IntradayTickElementTuple3.h"
#include "IntradayTickRequest/IntradayTickElement.h"
#include <cstring>
#include <ostream>

namespace BEmu
{
	namespace IntradayTickRequest
	{
		//makes copies of the arguments
		IntradayTickMessage::IntradayTickMessage(const CorrelationId& corr, const Service& service, std::map<Datetime, IntradayTickElementTuple3>& ticks, bool includeConditionCodes) :
			MessagePtr(Name("IntradayTickResponse"), corr),
			_parent(new IntradayTickElementDataParent(ticks, includeConditionCodes)),
			_responseError()
		{
			this->_isResponseError = false;
		}

		IntradayTickMessage::IntradayTickMessage(const CorrelationId& corr, const Service& service) :
			MessagePtr(Name("IntradayTickResponse"), corr),
			_parent(),
			_responseError(new IntradayTickElementResponseError())
		{
			this->_isResponseError = true;
		}

		IntradayTickMessage::~IntradayTickMessage()
		{
		}

		std::shared_ptr<ElementPtr> IntradayTickMessage::getElement(const char* name) const
		{
			if(this->_isResponseError && strncmp(name, "responseError", 14) == 0)
				return std::dynamic_pointer_cast<ElementPtr>(this->_responseError);

			else if(!this->_isResponseError && strncmp(name, "tickData", 9) == 0)
				return std::dynamic_pointer_cast<ElementPtr>(this->_parent);

			else
				throw messageEx;
		}

		bool IntradayTickMessage::hasElement(const char* name, bool excludeNullElements) const
		{
			return
				(this->_isResponseError && strncmp(name, "responseError", 14) == 0) ||
				(!this->_isResponseError && strncmp(name, "tickData", 9) == 0);
		}

		std::shared_ptr<ElementPtr> IntradayTickMessage::firstElement() const
		{
			if(this->_isResponseError)
				return std::dynamic_pointer_cast<ElementPtr>(this->_responseError);
			else
				return std::dynamic_pointer_cast<ElementPtr>(this->_parent);
		}

		const char* IntradayTickMessage::topicName() const
		{
			return "";
		}

		size_t IntradayTickMessage::numElements() const
		{
			return 1;
		}

		std::shared_ptr<ElementPtr> IntradayTickMessage::asElement() const
		{
			std::shared_ptr<IntradayTickElement> elm(new IntradayTickElement(*this));
			return std::dynamic_pointer_cast<ElementPtr>(elm);
		}

		std::ostream& IntradayTickMessage::print(std::ostream& stream, int level, int spacesPerLevel) const
		{
			stream << "IntradayTickResponse = {" << std::endl;
			
			if(this->_isResponseError)
				this->_responseError->print(stream, level + 1, spacesPerLevel);
			else
				this->_parent->print(stream, level + 1, spacesPerLevel);

			stream << '}' << std::endl;
			return stream;
		}

	}
}