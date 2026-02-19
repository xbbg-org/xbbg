//------------------------------------------------------------------------------
// <copyright project="BEmu_cpp" file="src/ReferenceDataRequest/ReferenceRequestElementOverride.cpp" company="Jordan Robinson">
//     Copyright (c) 2013 Jordan Robinson. All rights reserved.
//
//     The use of this software is governed by the Microsoft Public License
//     which is included with this distribution.
// </copyright>
//------------------------------------------------------------------------------

#include "ReferenceDataRequest/ReferenceRequestElementOverride.h"
#include "ReferenceDataRequest/ReferenceElementString.h"
#include "ReferenceDataRequest/ReferenceElementObject.h"

#include "Types/IndentType.h"
#include "BloombergTypes/Name.h"
#include <cstring>
#include <ostream>

namespace BEmu
{
	namespace ReferenceDataRequest
	{
		ReferenceRequestElementOverride::ReferenceRequestElementOverride() :
			_fieldId(new ReferenceElementString("fieldId", "")),
			_value(new ReferenceElementObject("value", ""))
		{
		}

		ReferenceRequestElementOverride::~ReferenceRequestElementOverride()
		{
		}

		Name ReferenceRequestElementOverride::name() const { return Name("overrides"); }
		size_t ReferenceRequestElementOverride::numValues() const { return 1; }
		size_t ReferenceRequestElementOverride::numElements() const { return 2; }

		void ReferenceRequestElementOverride::setElement(const char* name, const char* value)
		{
			if(strncmp(name, "fieldId", 8) == 0)
			{
				this->_fieldId->setName(name);
				this->_fieldId->setValue(value);
			}
			else if(strncmp(name, "value", 6) == 0)
			{
				this->_value->setName(name);
				
				ObjectType obj(value);
				this->_value->setValue(obj);
			}
			else
				throw elementPtrEx;
		}

		void ReferenceRequestElementOverride::setElement(const char* name, int value)
		{
			if(strncmp(name, "value", 6) == 0)
			{
				this->_value->setName(name);
				
				ObjectType obj(value);
				this->_value->setValue(obj);
			}
			else
				throw elementPtrEx;
		}

		std::shared_ptr<ElementPtr> ReferenceRequestElementOverride::getElement(const char* name) const
		{
			if(strncmp(name, "fieldId", 8) == 0)
				return std::dynamic_pointer_cast<ElementPtr>(this->_fieldId);

			else if(strncmp(name, "value", 6) == 0)
				return std::dynamic_pointer_cast<ElementPtr>(this->_value);
			
			else
				throw elementPtrEx;
		}

		std::ostream& ReferenceRequestElementOverride::print(std::ostream& stream, int level, int spacesPerLevel) const
		{
			std::string tabs(IndentType::Indent(level, spacesPerLevel));

			stream << tabs << "overrides = {" << std::endl;
			
			this->_fieldId->print(stream, level + 1, spacesPerLevel);
			this->_value->print(stream, level + 1, spacesPerLevel);

			stream << tabs << '}' << std::endl;

			return stream;
		}
	}
}