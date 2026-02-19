//------------------------------------------------------------------------------------------------
// <copyright project="BEmu_cpp" file="src/IntradayBarRequest/IntradayBarElementTickDataArray.cpp" company="Jordan Robinson">
//     Copyright (c) 2013 Jordan Robinson. All rights reserved.
//
//     The use of this software is governed by the Microsoft Public License
//     which is included with this distribution.
// </copyright>
//------------------------------------------------------------------------------------------------

#include "BloombergTypes/Name.h"
#include "BloombergTypes/ElementPtr.h"
#include "Types/IndentType.h"
#include "IntradayBarRequest/IntradayBarElementTickData.h"
#include "IntradayBarRequest/IntradayBarTickDataType.h"
#include "IntradayBarRequest/IntradayBarElementTickDataArray.h"
#include <ostream>

namespace BEmu
{
	namespace IntradayBarRequest
	{
		IntradayBarElementTickDataArray::IntradayBarElementTickDataArray(const std::vector< std::shared_ptr<IntradayBarTickDataType> >& bars)
		{
			for(std::vector< std::shared_ptr<IntradayBarTickDataType> >::const_iterator iter = bars.begin(); iter != bars.end(); ++iter)
			{
				std::shared_ptr<IntradayBarTickDataType> tick = *iter;
				std::shared_ptr<IntradayBarElementTickData> elmP(new IntradayBarElementTickData(*tick));

				this->_elements.push_back(elmP);
			}
		}

		IntradayBarElementTickDataArray::~IntradayBarElementTickDataArray()
		{
			this->_elements.clear();
		}

		Name IntradayBarElementTickDataArray::name() const
		{
			Name result("barTickData");
			return result;
		}

		size_t IntradayBarElementTickDataArray::numValues() const
		{
			return this->_elements.size();
		}

		size_t IntradayBarElementTickDataArray::numElements() const
		{
			return 0;
		}

		SchemaElementDefinition IntradayBarElementTickDataArray::elementDefinition() const
		{
			::blpapi_DataType_t dtype = (::blpapi_DataType_t)this->datatype();
			SchemaElementDefinition result(dtype, Name("IntradayBarTickData"));
			return result;
		}

		bool IntradayBarElementTickDataArray::isArray() const
		{
			return true;
		}

		bool IntradayBarElementTickDataArray::isComplexType() const
		{
			return false;
		}

		std::shared_ptr<ElementPtr> IntradayBarElementTickDataArray::getValueAsElement(int index) const
		{
			if(index >= 0 && index < (int)this->_elements.size())
				return this->_elements[index];

			else
				throw elementPtrEx;
		}

		std::ostream& IntradayBarElementTickDataArray::print(std::ostream& stream, int level, int spacesPerLevel) const
		{
			std::string tabs = IndentType::Indent(level, spacesPerLevel);

			stream << tabs << "barTickData[] = {" << std::endl;

			for(std::vector< std::shared_ptr<IntradayBarElementTickData> >::const_iterator iter = this->_elements.begin(); iter != this->_elements.end(); ++iter)
			{
				std::shared_ptr<IntradayBarElementTickData> elm = *iter;
				elm->print(stream, level + 1, spacesPerLevel);
			}

			stream << tabs << '}' << std::endl;

			return stream;
		}
	}
}