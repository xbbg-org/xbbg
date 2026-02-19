//------------------------------------------------------------------------------------------------
// <copyright project="BEmu_cpp" file="src/IntradayTickRequest/IntradayTickElement.cpp" company="Jordan Robinson">
//     Copyright (c) 2013 Jordan Robinson. All rights reserved.
//
//     The use of this software is governed by the Microsoft Public License
//     which is included with this distribution.
// </copyright>
//------------------------------------------------------------------------------------------------

#include "IntradayTickRequest/IntradayTickElement.h"
#include "BloombergTypes/Name.h"
#include "BloombergTypes/ElementPtr.h"

#include "IntradayTickRequest/IntradayTickMessage.h"
#include <ostream>

namespace BEmu
{
	namespace IntradayTickRequest
	{
		IntradayTickElement::IntradayTickElement(const IntradayTickMessage& msg) :
			_parent(msg.firstElement())
		{
		}

		IntradayTickElement::~IntradayTickElement()
		{
		}

		Name IntradayTickElement::name() const
		{
			Name result("IntradayTickRequest");
			return result;
		}

		std::shared_ptr<ElementPtr> IntradayTickElement::getElement(const char* name) const
		{
			if(this->_parent->name() == name)
				return this->_parent;
			else
				throw elementPtrEx;
		}

		bool IntradayTickElement::hasElement(const char* name, bool excludeNullElements) const
		{
			return this->_parent->name() == name;
		}

		std::ostream& IntradayTickElement::print(std::ostream& stream, int level, int spacesPerLevel) const
		{
			stream << "IntradayTickRequest (choice) = {" << std::endl;
			this->_parent->print(stream, level + 1, spacesPerLevel);
			stream << '}' << std::endl;

			return stream;
		}

	}
}