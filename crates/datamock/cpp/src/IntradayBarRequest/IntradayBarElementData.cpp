//------------------------------------------------------------------------------------------------
// <copyright project="BEmu_cpp" file="src/IntradayBarRequest/IntradayBarElementData.cpp" company="Jordan Robinson">
//     Copyright (c) 2013 Jordan Robinson. All rights reserved.
//
//     The use of this software is governed by the Microsoft Public License
//     which is included with this distribution.
// </copyright>
//------------------------------------------------------------------------------------------------

#include "BloombergTypes/Name.h"
#include "BloombergTypes/ElementPtr.h"
#include <cstring>
#include <vector>
#include "IntradayBarRequest/IntradayBarElementData.h"
#include "IntradayBarRequest/IntradayBarElementTickDataArray.h"
#include "Types/IndentType.h"
#include <ostream>

namespace BEmu
{
	namespace IntradayBarRequest
	{
		IntradayBarElementData::IntradayBarElementData(const std::vector< std::shared_ptr<IntradayBarTickDataType> >& bars) :
			_array(new IntradayBarElementTickDataArray(bars))
		{
		}

		IntradayBarElementData::~IntradayBarElementData()
		{
		}

		Name IntradayBarElementData::name() const
		{
			Name result("barData");
			return result;
		}

		size_t IntradayBarElementData::numValues() const
		{
			return 1;
		}

		size_t IntradayBarElementData::numElements() const
		{
			return 1;
		}

		SchemaElementDefinition IntradayBarElementData::elementDefinition() const
		{
			::blpapi_DataType_t dtype = (::blpapi_DataType_t)this->datatype();
			SchemaElementDefinition result(dtype, Name("BarData"));
			return result;
		}

		bool IntradayBarElementData::isArray() const
		{
			return false;
		}

		bool IntradayBarElementData::isComplexType() const
		{
			return true;
		}

		std::shared_ptr<ElementPtr> IntradayBarElementData::getElement(const char* name) const
		{
			int length = strlen(name);
			
			if(strncmp(this->_array->name().string(), name, length + 1) == 0)
				return std::dynamic_pointer_cast<ElementPtr>(this->_array);
			else
				throw elementPtrEx;
		}

		std::ostream& IntradayBarElementData::print(std::ostream& stream, int level, int spacesPerLevel) const
		{
			std::string tabs(IndentType::Indent(level, spacesPerLevel));

			stream << tabs << "barData = {" << std::endl;
			this->_array->print(stream, level + 1, spacesPerLevel);
			stream << tabs << '}' << std::endl;

			return stream;
		}

	}
}