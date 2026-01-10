//------------------------------------------------------------------------------
// <copyright project="BEmu_cpp" file="src/ReferenceDataRequest/ReferenceRequestElementString.cpp" company="Jordan Robinson">
//     Copyright (c) 2013 Jordan Robinson. All rights reserved.
//
//     The use of this software is governed by the Microsoft Public License
//     which is included with this distribution.
// </copyright>
//------------------------------------------------------------------------------

#include "ReferenceDataRequest/ReferenceRequestElementString.h"
#include "Types/IndentType.h"
#include "BloombergTypes/Name.h"
#include <ostream>

namespace BEmu
{
	namespace ReferenceDataRequest
	{
		ReferenceRequestElementString::ReferenceRequestElementString(const std::string& elementName, const std::string& value)
		{
			this->_elementName = elementName;
			this->_value = value;
		}

		ReferenceRequestElementString::~ReferenceRequestElementString()
		{
		}

		Name ReferenceRequestElementString::name() const { return Name(this->_elementName.c_str()); }
		size_t ReferenceRequestElementString::numValues() const { return 1; }
		size_t ReferenceRequestElementString::numElements() const { return 0; }

		std::ostream& ReferenceRequestElementString::print(std::ostream& stream, int level, int spacesPerLevel) const
		{
			std::string tabs(IndentType::Indent(level, spacesPerLevel));
			stream << tabs << this->_elementName << " = " << this->_value << std::endl;
			return stream;
		}

	}
}