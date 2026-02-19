//------------------------------------------------------------------------------
// <copyright project="BEmu_cpp" file="src/ReferenceDataRequest/ReferenceElementObject.cpp" company="Jordan Robinson">
//     Copyright (c) 2013 Jordan Robinson. All rights reserved.
//
//     The use of this software is governed by the Microsoft Public License
//     which is included with this distribution.
// </copyright>
//------------------------------------------------------------------------------

#include "ReferenceDataRequest/ReferenceElementObject.h"
#include "BloombergTypes/Name.h"
#include "Types/IndentType.h"
#include <ostream>

namespace BEmu
{
	namespace ReferenceDataRequest
	{
		ReferenceElementObject::ReferenceElementObject(const std::string& name, const ObjectType& value)
		{
			this->_name = name;			
			this->_value = value;
		}

		ReferenceElementObject::~ReferenceElementObject()
		{
		}

		Name ReferenceElementObject::name() const { return Name(this->_name.c_str()); }
		size_t ReferenceElementObject::numValues() const { return 1; }
		size_t ReferenceElementObject::numElements() const { return 0; }

		bool ReferenceElementObject::isNull() const { return false; }
		bool ReferenceElementObject::isArray() const { return false; }
		bool ReferenceElementObject::isComplexType() const { return false; }

		void ReferenceElementObject::setName(const std::string& name)
		{
			this->_name = name;
		}

		void ReferenceElementObject::setValue(const ObjectType& value)
		{
			this->_value = value;
		}

		const char * ReferenceElementObject::getValueAsString(int index) const
		{
			this->_cachedStringValue = this->_value.ToString();
			return this->_cachedStringValue.c_str();
		}

		std::ostream& ReferenceElementObject::print(std::ostream& stream, int level, int spacesPerLevel) const
		{
			std::string tabs(IndentType::Indent(level, spacesPerLevel));
			stream << tabs << this->_name << " = \"" << this->_value.ToString() << "\"" << std::endl;
			return stream;
		}

	}
}