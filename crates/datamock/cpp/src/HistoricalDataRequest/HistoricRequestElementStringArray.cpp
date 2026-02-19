//------------------------------------------------------------------------------
// <copyright project="BEmu_cpp" file="src/HistoricalDataRequest/HistoricRequestElementStringArray.cpp" company="Jordan Robinson">
//     Copyright (c) 2013 Jordan Robinson. All rights reserved.
//
//     The use of this software is governed by the Microsoft Public License
//     which is included with this distribution.
// </copyright>
//------------------------------------------------------------------------------

#include "HistoricalDataRequest/HistoricRequestElementStringArray.h"
#include "BloombergTypes/Name.h"
#include "Types/IndentType.h"
#include <ostream>

namespace BEmu
{
	namespace HistoricalDataRequest
	{
		HistoricRequestElementStringArray::HistoricRequestElementStringArray(const std::string& elementName)
		{
			this->_elementName = elementName;
		}

		HistoricRequestElementStringArray::~HistoricRequestElementStringArray()
		{
			this->_values.clear();
		}


		Name HistoricRequestElementStringArray::name() const
		{
			Name result(this->_elementName.c_str());
			return result;
		}

		size_t HistoricRequestElementStringArray::numValues() const
		{
			return this->_values.size();
		}

		size_t HistoricRequestElementStringArray::numElements() const
		{
			return 0;
		}

		
		bool HistoricRequestElementStringArray::isNull() const
		{
			return false;
		}

		bool HistoricRequestElementStringArray::isArray() const
		{
			return true;
		}

		bool HistoricRequestElementStringArray::isComplexType() const
		{
			return false;
		}
		
		std::vector<std::string> HistoricRequestElementStringArray::values() const
		{
			return this->_values;
		}

		void HistoricRequestElementStringArray::appendValue(const char* value)
		{
			this->_values.push_back(value);
		}


		std::ostream& HistoricRequestElementStringArray::print(std::ostream& stream, int level, int spacesPerLevel) const
		{
			std::string tabs(IndentType::Indent(level, spacesPerLevel));

			stream << tabs << this->_elementName << "[] = {" << std::endl;
			stream << tabs << IndentType::Indent(1, spacesPerLevel);

			int size = this->_values.size();
			int count = 0;
			for(std::vector<std::string>::const_iterator iter = this->_values.begin(); iter != this->_values.end(); ++iter)
			{
				std::string str = *iter;

				stream << "\"" << str << "\"";
				if(count < size - 1)
					stream << ", ";

				count++;
			}

			stream << std::endl;			
			stream << tabs << '}' << std::endl;

			return stream;
		}

	}
}