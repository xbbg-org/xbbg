//------------------------------------------------------------------------------------------------
// <copyright project="BEmu_cpp" file="src/IntradayTickRequest/IntradayTickRequestElementString.cpp" company="Jordan Robinson">
//     Copyright (c) 2013 Jordan Robinson. All rights reserved.
//
//     The use of this software is governed by the Microsoft Public License
//     which is included with this distribution.
// </copyright>
//------------------------------------------------------------------------------------------------

#include "IntradayTickRequest/IntradayTickRequestElementString.h"
#include "BloombergTypes/Name.h"
#include "BloombergTypes/Element.h"
#include "Types/IndentType.h"
#include <ostream>

namespace BEmu
{
	namespace IntradayTickRequest
	{
		IntradayTickRequestElementString::IntradayTickRequestElementString(const std::string& elementName, const std::string& value)
		{
			this->_elementName = elementName;
			this->_value = value;
		}

		IntradayTickRequestElementString::IntradayTickRequestElementString(const std::string& elementName, int value)
		{
			this->_elementName = elementName;

			this->_ss << value;
			this->_value = this->_ss.str();
		}

		IntradayTickRequestElementString::IntradayTickRequestElementString(const std::string& elementName, const Datetime& value)
		{
			this->_elementName = elementName;

			this->_ss << value;
			this->_value = this->_ss.str();
		}

		IntradayTickRequestElementString::~IntradayTickRequestElementString()
		{
		}

		const std::string& IntradayTickRequestElementString::security() const
		{
			return this->_value;
		}

		Name IntradayTickRequestElementString::name() const
		{
			Name result(this->_elementName.c_str());
			return result;
		}

		std::ostream& IntradayTickRequestElementString::print(std::ostream& stream, int level, int spacesPerLevel) const
		{
			std::string tabs = IndentType::Indent(level, spacesPerLevel);
			stream << tabs << this->_elementName << " = \"" << this->_value << "\"" << std::endl;
			return stream;
		}

	}
}