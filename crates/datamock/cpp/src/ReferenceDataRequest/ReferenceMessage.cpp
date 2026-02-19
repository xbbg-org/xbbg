//------------------------------------------------------------------------------
// <copyright project="BEmu_cpp" file="src/ReferenceDataRequest/ReferenceMessage.cpp" company="Jordan Robinson">
//     Copyright (c) 2013 Jordan Robinson. All rights reserved.
//
//     The use of this software is governed by the Microsoft Public License
//     which is included with this distribution.
// </copyright>
//------------------------------------------------------------------------------

#include "ReferenceDataRequest/ReferenceMessage.h"
#include "ReferenceDataRequest/ReferenceElementSecurityDataArray.h"
#include "ReferenceDataRequest/ReferenceElement.h"
#include <cstring>
#include <ostream>

namespace BEmu
{
	namespace ReferenceDataRequest
	{
		ReferenceMessage::ReferenceMessage(const CorrelationId& corr, const std::map<std::string, std::map<std::string, ObjectType>>& fieldData) : 
			MessagePtr(Name("ReferenceDataResponse"), corr),
			_securities(new ReferenceElementSecurityDataArray(fieldData))
		{
		}

		ReferenceMessage::~ReferenceMessage()
		{
		}

		const char* ReferenceMessage::topicName() const
		{
			return "";
		}

		std::shared_ptr<ElementPtr> ReferenceMessage::asElement() const
		{
			std::shared_ptr<ReferenceElement> elm(new ReferenceElement(*this));
			return std::dynamic_pointer_cast<ElementPtr>(elm);
		}

		std::shared_ptr<ElementPtr> ReferenceMessage::firstElement() const
		{
			return std::dynamic_pointer_cast<ElementPtr>(this->_securities);
		}

		std::shared_ptr<ElementPtr> ReferenceMessage::getElement(const char* name) const
		{
			if(strncmp(name, "securityData", 13) == 0)
				return std::dynamic_pointer_cast<ElementPtr>(this->_securities);

			else
				throw messageEx;
		}

		std::ostream& ReferenceMessage::print(std::ostream& stream, int level, int spacesPerLevel) const
		{
			stream << "ReferenceDataResponse (choice) = {" << std::endl;
			this->_securities->print(stream, 1, spacesPerLevel);
			stream << '}' << std::endl;

			return stream;
		}


	}
}