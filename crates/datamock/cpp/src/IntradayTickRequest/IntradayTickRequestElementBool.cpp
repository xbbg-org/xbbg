//------------------------------------------------------------------------------------------------
// <copyright project="BEmu_cpp" file="src/IntradayTickRequest/IntradayTickRequestElementBool.cpp" company="Jordan Robinson">
//     Copyright (c) 2013 Jordan Robinson. All rights reserved.
//
//     The use of this software is governed by the Microsoft Public License
//     which is included with this distribution.
// </copyright>
//------------------------------------------------------------------------------------------------

#include "IntradayTickRequest/IntradayTickRequestElementBool.h"
#include "IntradayTickRequest/IntradayTickRequestElementString.h"
#include "BloombergTypes/Name.h"
#include "BloombergTypes/Element.h"
#include "Types/IndentType.h"
#include <ostream>

namespace BEmu
{
	namespace IntradayTickRequest
	{
		IntradayTickRequestElementBool::IntradayTickRequestElementBool(const std::string& elementName, bool bvalue)
			: CanConvertToStringType(bvalue, false)
		{
			this->_bvalue = bvalue;
			this->_elementName = elementName;
		}

		IntradayTickRequestElementBool::~IntradayTickRequestElementBool()
		{
		}

		bool IntradayTickRequestElementBool::getBool() const
		{
			return this->_bvalue;
		}

		Name IntradayTickRequestElementBool::name() const
		{
			Name result(this->_elementName.c_str());
			return result;
		}

		std::ostream& IntradayTickRequestElementBool::print(std::ostream& stream, int level, int spacesPerLevel) const
		{
			std::string tabs = IndentType::Indent(level, spacesPerLevel);
			stream << tabs << this->_elementName << " = " << this->ValueAsString() << std::endl;
			return stream;
		}

	}
}