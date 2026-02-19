//------------------------------------------------------------------------------------------------
// <copyright project="BEmu_cpp" file="src/IntradayBarRequest/IntradayBarRequestElementStringArray.cpp" company="Jordan Robinson">
//     Copyright (c) 2013 Jordan Robinson. All rights reserved.
//
//     The use of this software is governed by the Microsoft Public License
//     which is included with this distribution.
// </copyright>
//------------------------------------------------------------------------------------------------

#include "BloombergTypes/Name.h"
#include "BloombergTypes/ElementPtr.h"
#include "Types/IndentType.h"
#include "IntradayBarRequest/IntradayBarRequestElementStringArray.h"
#include <ostream>

namespace BEmu
{
	namespace IntradayBarRequest
	{
		IntradayBarRequestElementStringArray::IntradayBarRequestElementStringArray(const std::string& elementName)
		{
			this->_name = elementName;
		}

		IntradayBarRequestElementStringArray::~IntradayBarRequestElementStringArray()
		{
			this->_values.clear();
		}

		Name IntradayBarRequestElementStringArray::name() const
		{
			Name result(this->_name.c_str());
			return result;
		}

		size_t IntradayBarRequestElementStringArray::numValues() const
		{
			return this->_values.size();
		}

		size_t IntradayBarRequestElementStringArray::numElements() const
		{
			return 0;
		}

		bool IntradayBarRequestElementStringArray::isArray() const
		{
			return true;
		}

		bool IntradayBarRequestElementStringArray::isComplexType() const
		{
			return false;
		}

		std::vector<std::string> IntradayBarRequestElementStringArray::values() const
		{
			return this->_values;
		}

		void IntradayBarRequestElementStringArray::addValue(const std::string& value)
		{
			if(this->isEventTypeAllowed(value))
				this->_values.push_back(value);
			else
				throw elementPtrEx; //Yes the actual Bloomberg API really does throw an exception here
		}

		bool IntradayBarRequestElementStringArray::isEventTypeAllowed(const std::string& value)
		{
			return 
				(value.compare("TRADE") == 0) ||
				(value.compare("BID") == 0) ||
				(value.compare("ASK") == 0) ||
				(value.compare("BID_BEST") == 0) ||
				(value.compare("ASK_BEST") == 0) ||
				(value.compare("BEST_BID") == 0) ||
				(value.compare("BEST_ASK") == 0) ||
				(value.compare("BID_YIELD") == 0) ||
				(value.compare("ASK_YIELD") == 0) ||
				(value.compare("MID_PRICE") == 0) ||
				(value.compare("AT_TRADE") == 0) ||
				(value.compare("SETTLE") == 0);
		}

		std::ostream& IntradayBarRequestElementStringArray::print(std::ostream& stream, int level, int spacesPerLevel) const
		{
			std::string tabs(IndentType::Indent(level, spacesPerLevel));

			stream << tabs << this->_name << "[] = {" << std::endl;

			int index = 0, lastIndex = this->_values.size() - 1;
			for(std::vector<std::string>::const_iterator iter = this->_values.begin(); iter != this->_values.end(); ++iter)
			{
				std::string value = *iter;

				stream << value;

				if(index < lastIndex)
					stream << ", ";
			}

			stream << tabs << '}' << std::endl;

			return stream;
		}
	}
}