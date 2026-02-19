//------------------------------------------------------------------------------
// <copyright project="BEmu_cpp" file="src/HistoricalDataRequest/HistoricRequestElementString.cpp" company="Jordan Robinson">
//     Copyright (c) 2013 Jordan Robinson. All rights reserved.
//
//     The use of this software is governed by the Microsoft Public License
//     which is included with this distribution.
// </copyright>
//------------------------------------------------------------------------------

#include "HistoricalDataRequest/HistoricRequestElementString.h"
#include "BloombergTypes/Name.h"
#include "Types/IndentType.h"
#include <ostream>

namespace BEmu
{
	namespace HistoricalDataRequest
	{
		HistoricRequestElementString::HistoricRequestElementString(const std::string& elementName, const std::string& value)
		{
			this->_elementName = elementName;
			this->_value = value;
		}

		HistoricRequestElementString::HistoricRequestElementString(const std::string& elementName, int value)
		{
			this->_elementName = elementName;

			this->_ss << value;
			this->_value = this->_ss.str();
		}

		HistoricRequestElementString::~HistoricRequestElementString()
		{
		}


		Name HistoricRequestElementString::name() const
		{
			Name result(this->_elementName.c_str());
			return result;
		}

		size_t HistoricRequestElementString::numValues() const
		{
			return 1;
		}

		size_t HistoricRequestElementString::numElements() const
		{
			return 0;
		}


		std::ostream& HistoricRequestElementString::print(std::ostream& stream, int level, int spacesPerLevel) const
		{
			std::string tabs = IndentType::Indent(level, spacesPerLevel);
			stream << tabs << this->_elementName << " = " << this->_value << std::endl;
			return stream;
		}

	}
}