//------------------------------------------------------------------------------------------------
// <copyright project="BEmu_cpp" file="src/IntradayBarRequest/IntradayBarElement.cpp" company="Jordan Robinson">
//     Copyright (c) 2013 Jordan Robinson. All rights reserved.
//
//     The use of this software is governed by the Microsoft Public License
//     which is included with this distribution.
// </copyright>
//------------------------------------------------------------------------------------------------

#include "IntradayBarRequest/IntradayBarElement.h"
#include "BloombergTypes/Name.h"
#include "BloombergTypes/ElementPtr.h"

#include "IntradayBarRequest/IntradayBarMessage.h"
#include <ostream>

namespace BEmu
{
	namespace IntradayBarRequest
	{
		IntradayBarElement::IntradayBarElement(const IntradayBarMessage& msg) :
			_parent(msg.firstElement())
		{
		}

		IntradayBarElement::~IntradayBarElement()
		{
		}

		Name IntradayBarElement::name() const
		{
			Name result("IntradayBarRequest");
			return result;
		}

		std::shared_ptr<ElementPtr> IntradayBarElement::getElement(const char* name) const
		{
			if(this->_parent->name() == name)
				return this->_parent;
			else
				throw elementPtrEx;
		}

		bool IntradayBarElement::hasElement(const char* name, bool excludeNullElements) const
		{
			return this->_parent->name() == name;
		}

		std::ostream& IntradayBarElement::print(std::ostream& stream, int level, int spacesPerLevel) const
		{
			stream << "IntradayBarRequest (choice) = {" << std::endl;
			this->_parent->print(stream, level + 1, spacesPerLevel);
			stream << '}' << std::endl;

			return stream;
		}

	}
}
