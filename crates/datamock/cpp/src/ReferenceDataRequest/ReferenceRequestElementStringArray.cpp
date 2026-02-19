//------------------------------------------------------------------------------
// <copyright project="BEmu_cpp" file="src/ReferenceDataRequest/ReferenceRequestElementStringArray.cpp" company="Jordan Robinson">
//     Copyright (c) 2013 Jordan Robinson. All rights reserved.
//
//     The use of this software is governed by the Microsoft Public License
//     which is included with this distribution.
// </copyright>
//------------------------------------------------------------------------------

#include "ReferenceDataRequest/ReferenceRequestElementStringArray.h"

#include "Types/IndentType.h"
#include "BloombergTypes/Name.h"
#include <ostream>

namespace BEmu
{
	namespace ReferenceDataRequest
	{
		ReferenceRequestElementStringArray::ReferenceRequestElementStringArray(const std::string& elementName)
		{
			this->_elementName = elementName;
		}

		ReferenceRequestElementStringArray::~ReferenceRequestElementStringArray()
		{
			this->_values.clear();
		}

		Name ReferenceRequestElementStringArray::name() const { return Name(this->_elementName.c_str()); }
		size_t ReferenceRequestElementStringArray::numValues() const { return this->_values.size(); }
		size_t ReferenceRequestElementStringArray::numElements() const { return 0; }

		bool ReferenceRequestElementStringArray::isNull() const { return false; }
		bool ReferenceRequestElementStringArray::isArray() const { return true; }
		bool ReferenceRequestElementStringArray::isComplexType() const { return false; }

		void ReferenceRequestElementStringArray::addValue(const std::string& elementName)
		{
			this->_values.push_back(elementName);
		}

		std::vector<std::string> ReferenceRequestElementStringArray::getValues() const
		{
			return this->_values;
		}

		std::ostream& ReferenceRequestElementStringArray::print(std::ostream& stream, int level, int spacesPerLevel) const
		{
			std::string tabs(IndentType::Indent(level, spacesPerLevel));
			std::string tabsOne = IndentType::Indent(1, spacesPerLevel);

			stream << tabs << this->_elementName << "[] = {" << std::endl;

			stream << tabs << tabsOne;
			for(size_t i = 0; i < this->_values.size(); i++)
			{
				stream << "\"" << this->_values[i] << "\"";

				if(i + 1 < this->_values.size())
					stream << ", ";
			}
			stream << std::endl;

			stream << tabs << '}' << std::endl;

			return stream;

		}

	}
}