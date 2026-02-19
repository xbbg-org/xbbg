//------------------------------------------------------------------------------
// <copyright project="BEmu_cpp" file="src/ReferenceDataRequest/ReferenceElementString.cpp" company="Jordan Robinson">
//     Copyright (c) 2013 Jordan Robinson. All rights reserved.
//
//     The use of this software is governed by the Microsoft Public License
//     which is included with this distribution.
// </copyright>
//------------------------------------------------------------------------------

#include "ReferenceDataRequest/ReferenceElementString.h"
#include "BloombergTypes/Name.h"
#include "Types/IndentType.h"
#include <ostream>

namespace BEmu
{
	namespace ReferenceDataRequest
	{
		ReferenceElementString::ReferenceElementString(const std::string& name, const std::string& value) : CanConvertToStringType(value)
		{
			this->_name = name;
			this->_value = value;
		}

		Name ReferenceElementString::name() const { return Name(this->_name.c_str()); }
		size_t ReferenceElementString::numValues() const { return 1; }
		size_t ReferenceElementString::numElements() const { return 0; }

		bool ReferenceElementString::isNull() const { return false; }
		bool ReferenceElementString::isArray() const { return false; }
		bool ReferenceElementString::isComplexType() const { return false; }

		void ReferenceElementString::setName(const std::string& name)
		{
			this->_name = name;
		}

		void ReferenceElementString::setValue(const std::string& value)
		{
			this->_value = value;
		}

		const char * ReferenceElementString::getValueAsString(int index) const
		{
			if(index == 0)
				return this->ValueAsString().c_str();
			else
				throw elementPtrEx;
		}

		std::ostream& ReferenceElementString::print(std::ostream& stream, int level, int spacesPerLevel) const
		{
			std::string tabs(IndentType::Indent(level, spacesPerLevel));
			stream << tabs << this->_name << " = \"" << this->_value << "\"" << std::endl;
			return stream;
		}

	}
}