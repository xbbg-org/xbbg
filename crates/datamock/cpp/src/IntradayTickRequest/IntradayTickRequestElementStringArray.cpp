//------------------------------------------------------------------------------------------------
// <copyright project="BEmu_cpp" file="src/IntradayTickRequest/IntradayTickRequestElementStringArray.cpp" company="Jordan Robinson">
//     Copyright (c) 2013 Jordan Robinson. All rights reserved.
//
//     The use of this software is governed by the Microsoft Public License
//     which is included with this distribution.
// </copyright>
//------------------------------------------------------------------------------------------------

#include "IntradayTickRequest/IntradayTickRequestElementStringArray.h"
#include "BloombergTypes/Name.h"
#include "BloombergTypes/Element.h"
#include "Types/IndentType.h"
#include <vector>
#include <ostream>

namespace BEmu
{
	namespace IntradayTickRequest
	{
		IntradayTickRequestElementStringArray::IntradayTickRequestElementStringArray(const std::string& elementName)
		{
			this->_elementName = elementName;
		}

		IntradayTickRequestElementStringArray::~IntradayTickRequestElementStringArray()
		{
			this->_values.clear();
		}

		void IntradayTickRequestElementStringArray::addValue(const std::string& value)
		{
			if(value.compare("TRADE") == 0 ||
				value.compare("BID") == 0 ||
				value.compare("ASK") == 0 ||
				value.compare("BID_BEST") == 0 ||
				value.compare("ASK_BEST") == 0 ||
				value.compare("MID_PRICE") == 0 ||
				value.compare("AT_TRADE") == 0 ||
				value.compare("BEST_BID") == 0 ||
				value.compare("BEST_ASK") == 0)
			{
				this->_values.push_back(value);
			}
			else
			{
				//yes, the BloombergAPI actually throws an exception if the user requests a field that isn't supported.
				throw elementPtrEx;
			}
		}

		std::vector<std::string> IntradayTickRequestElementStringArray::getValues() const
		{
			return this->_values;
		}

		Name IntradayTickRequestElementStringArray::name() const
		{
			Name result(this->_elementName.c_str());
			return result;
		}

		size_t IntradayTickRequestElementStringArray::numElements() const
		{
			return this->_values.size();
		}

		std::ostream& IntradayTickRequestElementStringArray::print(std::ostream& stream, int level, int spacesPerLevel) const
		{
			std::string tabs = IndentType::Indent(level, spacesPerLevel);
			std::string tabsOne = IndentType::Indent(1, spacesPerLevel);

			stream << tabs << this->_elementName << "[] = {" << std::endl;
			stream << tabs << tabsOne;

			unsigned count = 1;
			for(std::vector<std::string>::const_iterator iter = this->_values.begin(); iter != this->_values.end(); ++iter, ++count)
			{
				std::string str = *iter;

				stream << str;
				if(count < this->_values.size())
					stream << ", ";
			}

			stream << std::endl << tabs << '}' << std::endl;
			return stream;
		}

	}
}