//------------------------------------------------------------------------------
// <copyright project="BEmu_cpp" file="src/ReferenceDataRequest/ReferenceElement.cpp" company="Jordan Robinson">
//     Copyright (c) 2013 Jordan Robinson. All rights reserved.
//
//     The use of this software is governed by the Microsoft Public License
//     which is included with this distribution.
// </copyright>
//------------------------------------------------------------------------------

#include "ReferenceDataRequest/ReferenceElement.h"
#include "ReferenceDataRequest/ReferenceMessage.h"
#include "ReferenceDataRequest/ReferenceElementSecurityDataArray.h"
#include "BloombergTypes/Name.h"
#include <cstring>
#include <ostream>

namespace BEmu
{
	namespace ReferenceDataRequest
	{
		ReferenceElement::ReferenceElement(const ReferenceMessage& arg) :
			_securities(std::dynamic_pointer_cast<ReferenceElementSecurityDataArray>(arg.firstElement()))
		{
		}

		ReferenceElement::~ReferenceElement()
		{
		}

		Name ReferenceElement::name() const { return Name("securityData"); }
		size_t ReferenceElement::numValues() const { return 1; }
		size_t ReferenceElement::numElements() const { return 1; }

		bool ReferenceElement::isNull() const { return false; }
		bool ReferenceElement::isArray() const { return false; }
		bool ReferenceElement::isComplexType() const { return true; }

		std::shared_ptr<ElementPtr> ReferenceElement::getElement(const char* name) const
		{
			if(strncmp(name, "securityData", 13) == 0)
				return std::dynamic_pointer_cast<ElementPtr>(this->_securities);

			else
				throw elementPtrEx;
		}

		std::ostream& ReferenceElement::print(std::ostream& stream, int level, int spacesPerLevel) const
		{
			stream << "ReferenceDataResponse (choice) = {" << std::endl;
			this->_securities->print(stream, level + 1, spacesPerLevel);
			stream << '}' << std::endl;

			return stream;
		}

	}
}