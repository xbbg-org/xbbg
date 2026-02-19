//------------------------------------------------------------------------------------------------
// <copyright project="BEmu_cpp" file="src/IntradayTickRequest/IntradayTickRequestElementTime.cpp" company="Jordan Robinson">
//     Copyright (c) 2013 Jordan Robinson. All rights reserved.
//
//     The use of this software is governed by the Microsoft Public License
//     which is included with this distribution.
// </copyright>
//------------------------------------------------------------------------------------------------

#include "IntradayTickRequest/IntradayTickRequestElementTime.h"
#include "IntradayTickRequest/IntradayTickRequestElementString.h"
#include "BloombergTypes/Name.h"
#include "BloombergTypes/Element.h"
#include "Types/IndentType.h"
#include "Types/DisplayFormats.h"
#include <ostream>

namespace BEmu
{
	namespace IntradayTickRequest
	{
		IntradayTickRequestElementTime::IntradayTickRequestElementTime(const std::string& elementName, const Datetime& date)
			: CanConvertToStringType(DisplayFormats::IntradayRequests_FormatDatetime_SecondsLast(date), false)
		{
			this->_instance = date;
			this->_elementName = elementName;
		}

		IntradayTickRequestElementTime::~IntradayTickRequestElementTime()
		{
		}

		Datetime IntradayTickRequestElementTime::getDate() const
		{
			return this->_instance;
		}

		Name IntradayTickRequestElementTime::name() const
		{
			Name result(this->_elementName.c_str());
			return result;
		}

		std::ostream& IntradayTickRequestElementTime::print(std::ostream& stream, int level, int spacesPerLevel) const
		{
			std::string tabs = IndentType::Indent(level, spacesPerLevel);
			stream << tabs << this->_elementName << " = " << this->ValueAsString() << std::endl;
			return stream;
		}

	}
}