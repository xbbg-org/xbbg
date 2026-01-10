//------------------------------------------------------------------------------------------------
// <copyright project="BEmu_cpp" file="src/IntradayTickRequest/IntradayTickElementDataArray.cpp" company="Jordan Robinson">
//     Copyright (c) 2013 Jordan Robinson. All rights reserved.
//
//     The use of this software is governed by the Microsoft Public License
//     which is included with this distribution.
// </copyright>
//------------------------------------------------------------------------------------------------

#include "IntradayTickRequest/IntradayTickElementDataArray.h"
#include "IntradayTickRequest/IntradayTickElementData.h"
#include "IntradayTickRequest/IntradayTickElementTuple3.h"
#include "BloombergTypes/Name.h"
#include "BloombergTypes/ElementPtr.h"
#include "Types/IndentType.h"
#include <map>
#include <vector>
#include <ostream>

namespace BEmu
{
	namespace IntradayTickRequest
	{
		//makes copies of the arguments
		IntradayTickElementDataArray::IntradayTickElementDataArray(const std::map<Datetime, IntradayTickElementTuple3> ticks, bool includeConditionCodes)
		{
			for(std::map<Datetime, IntradayTickElementTuple3 >::const_iterator iter = ticks.begin(); iter != ticks.end(); ++iter)
			{
				IntradayTickElementTuple3 tuple(iter->second.item1(), iter->second.item2(), iter->second.item3());
				std::shared_ptr<IntradayTickElementData> elmFieldDataP(new IntradayTickElementData(iter->first, tuple, includeConditionCodes));

				this->_tickData.push_back(elmFieldDataP);
			}
		}

		IntradayTickElementDataArray::~IntradayTickElementDataArray()
		{
			this->_tickData.clear();
		}

		std::shared_ptr<ElementPtr> IntradayTickElementDataArray::getValueAsElement(int index) const
		{
			return std::dynamic_pointer_cast<ElementPtr>(this->_tickData[index]);
		}

		Name IntradayTickElementDataArray::name() const
		{
			Name result("tickData");
			return result;
		}

		size_t IntradayTickElementDataArray::numValues() const
		{
			return this->_tickData.size();
		}

		SchemaElementDefinition IntradayTickElementDataArray::elementDefinition() const
		{
			::blpapi_DataType_t dtype = (::blpapi_DataType_t)this->datatype();
			SchemaElementDefinition result(dtype, Name("IntradayTickData"));
			return result;
		}

		std::ostream& IntradayTickElementDataArray::print(std::ostream& stream, int level, int spacesPerLevel) const
		{
			std::string tabs = IndentType::Indent(level, spacesPerLevel);

			stream << tabs << "tickData[] = {" << std::endl;
			for(std::vector< std::shared_ptr<IntradayTickElementData> >::const_iterator iter = this->_tickData.begin(); iter != this->_tickData.end(); ++iter)
			{
				std::shared_ptr<IntradayTickElementData> elmFieldData = *iter;
				elmFieldData->print(stream, level + 1, spacesPerLevel);
			}
			stream << tabs << '}' << std::endl;

			return stream;
		}


	}
}