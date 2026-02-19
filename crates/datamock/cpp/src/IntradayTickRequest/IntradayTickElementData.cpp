//------------------------------------------------------------------------------------------------
// <copyright project="BEmu_cpp" file="src/IntradayTickRequest/IntradayTickElementData.cpp" company="Jordan Robinson">
//     Copyright (c) 2013 Jordan Robinson. All rights reserved.
//
//     The use of this software is governed by the Microsoft Public License
//     which is included with this distribution.
// </copyright>
//------------------------------------------------------------------------------------------------

#include "IntradayTickRequest/IntradayTickElementData.h"
#include "IntradayTickRequest/IntradayTickElementTuple3.h"
#include "BloombergTypes/Name.h"
#include "BloombergTypes/ElementPtr.h"
#include "BloombergTypes/Datetime.h"
#include "Types/IndentType.h"
#include "Types/RandomDataGenerator.h"
#include "IntradayTickRequest/IntradayTickElementDateTime.h"
#include "IntradayTickRequest/IntradayTickElementString.h"
#include "IntradayTickRequest/IntradayTickElementDouble.h"
#include "IntradayTickRequest/IntradayTickElementInt.h"
#include <cstring>

#include "IntradayTickRequest/IntradayTickElement.h"
#include <ostream>

namespace BEmu
{
	namespace IntradayTickRequest
	{
		IntradayTickElementData::IntradayTickElementData(const Datetime& datetime, const IntradayTickElementTuple3& arg, bool includeConditionCodes) :
			_time(new IntradayTickElementDateTime("time", datetime)),
			_value(new IntradayTickElementDouble("value", arg.item2())),
			_size(new IntradayTickElementInt("size", arg.item3())),
			_type(new IntradayTickElementString("type", arg.item1()))
		{
			this->_includeConditionCodes = includeConditionCodes;

if(includeConditionCodes)
			{
				// Randomly select a condition code from realistic Bloomberg values
				static const char* codes[] = { "", "T", "N", "R6,IS", "B", "IS", "OC" };
				static const int numCodes = sizeof(codes) / sizeof(codes[0]);
				const char* selectedCode = codes[RandomDataGenerator::RandomInt(0, numCodes - 1)];
				this->_conditionCodes = std::shared_ptr<IntradayTickElementString>(new IntradayTickElementString("conditionCodes", selectedCode));
			}
			else
				this->_conditionCodes = std::shared_ptr<IntradayTickElementString>();
		}

		IntradayTickElementData::~IntradayTickElementData()
		{
		}

		Name IntradayTickElementData::name() const
		{
			Name result("tickData");
			return result;
		}

		SchemaElementDefinition IntradayTickElementData::elementDefinition() const
		{
			::blpapi_DataType_t dtype = (::blpapi_DataType_t)this->datatype();
			SchemaElementDefinition result(dtype, Name("IntradayTickData"));
			return result;
		}

		bool IntradayTickElementData::hasElement(const char* name, bool excludeNullElements) const
		{
			return 
				strncmp("time", name, 5) == 0 ||
				strncmp("type", name, 5) == 0 ||
				strncmp("value", name, 6) == 0 ||
				strncmp("size", name, 5) == 0 ||
				(this->_includeConditionCodes && strncmp("conditionCodes", name, 15) == 0);
		}

		std::shared_ptr<ElementPtr> IntradayTickElementData::getElement(int position) const
		{
			switch(position)
			{
				case 0:
					return std::dynamic_pointer_cast<ElementPtr>(this->_time);
				case 1:
					return std::dynamic_pointer_cast<ElementPtr>(this->_type);
				case 2:
					return std::dynamic_pointer_cast<ElementPtr>(this->_value);
				case 3:
					return std::dynamic_pointer_cast<ElementPtr>(this->_size);
				case 4:
					if(this->_includeConditionCodes)
						return std::dynamic_pointer_cast<ElementPtr>(this->_conditionCodes);
			}

			throw elementPtrEx;
		}

		std::shared_ptr<ElementPtr> IntradayTickElementData::getElement(const char* name) const
		{
			if(strncmp("time", name, 5) == 0)
				return std::dynamic_pointer_cast<ElementPtr>(this->_time);

			else if(strncmp("type", name, 5) == 0)
				return std::dynamic_pointer_cast<ElementPtr>(this->_type);

			else if(strncmp("value", name, 6) == 0)
				return std::dynamic_pointer_cast<ElementPtr>(this->_value);

			else if(strncmp("size", name, 5) == 0)
				return std::dynamic_pointer_cast<ElementPtr>(this->_size);

			else if(this->_includeConditionCodes && strncmp("conditionCodes", name, 15) == 0)
				return std::dynamic_pointer_cast<ElementPtr>(this->_conditionCodes);

			throw elementPtrEx;
		}

		int IntradayTickElementData::getElementAsInt32(const char* name) const
		{
			return this->getElement(name)->getValueAsInt32(0);
		}

		Datetime IntradayTickElementData::getElementAsDatetime(const char* name) const
		{
			return this->getElement(name)->getValueAsDatetime(0);
		}

		const char* IntradayTickElementData::getElementAsString(const char* name) const
		{
			return this->getElement(name)->getValueAsString(0);
		}

		std::ostream& IntradayTickElementData::print(std::ostream& stream, int level, int spacesPerLevel) const
		{
			std::string tabs = IndentType::Indent(level, spacesPerLevel);
			stream << tabs << "tickData = {" << std::endl;
			
			this->_time->print(stream, level + 1, spacesPerLevel);
			this->_type->print(stream, level + 1, spacesPerLevel);
			this->_value->print(stream, level + 1, spacesPerLevel);
			this->_size->print(stream, level + 1, spacesPerLevel);

			if(this->_includeConditionCodes)
				this->_conditionCodes->print(stream, level + 1, spacesPerLevel);

			stream << tabs << '}' << std::endl;
			return stream;
		}

	}
}