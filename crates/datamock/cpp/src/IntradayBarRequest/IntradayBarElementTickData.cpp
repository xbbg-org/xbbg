//------------------------------------------------------------------------------------------------
// <copyright project="BEmu_cpp" file="src/IntradayBarRequest/IntradayBarElementTickData.cpp" company="Jordan Robinson">
//     Copyright (c) 2013 Jordan Robinson. All rights reserved.
//
//     The use of this software is governed by the Microsoft Public License
//     which is included with this distribution.
// </copyright>
//------------------------------------------------------------------------------------------------

#include "BloombergTypes/Name.h"
#include "BloombergTypes/Datetime.h"
#include "BloombergTypes/ElementPtr.h"
#include "Types/IndentType.h"
#include "IntradayBarRequest/IntradayBarTickDataType.h"
#include "IntradayBarRequest/IntradayBarElementTickData.h"
#include "IntradayBarRequest/IntradayBarElementDateTime.h"
#include "IntradayBarRequest/IntradayBarElementDouble.h"
#include "IntradayBarRequest/IntradayBarElementLong.h"
#include "IntradayBarRequest/IntradayBarElementInt.h"
#include <cstring>
#include <ostream>

namespace BEmu
{
	namespace IntradayBarRequest
	{
		IntradayBarElementTickData::IntradayBarElementTickData(const IntradayBarTickDataType& arg) :
			_time(new IntradayBarElementDateTime("time", arg.getDatetime())),
			_open(new IntradayBarElementDouble("open", arg.getOpen())),
			_high(new IntradayBarElementDouble("high", arg.getHigh())),
			_low(new IntradayBarElementDouble("low", arg.getLow())),
			_close(new IntradayBarElementDouble("close", arg.getClose())),
			_value(new IntradayBarElementDouble("value", arg.getValue())),
			_volume(new IntradayBarElementLong("volume", arg.getVolume())),
			_numEvents(new IntradayBarElementInt("numEvents", arg.getNumevents()))
		{
		}

		IntradayBarElementTickData::~IntradayBarElementTickData()
		{
		}

		Name IntradayBarElementTickData::name() const
		{
			Name result("barTickData");
			return result;
		}

		size_t IntradayBarElementTickData::numValues() const
		{
			return 0;
		}

		size_t IntradayBarElementTickData::numElements() const
		{
			return 8;
		}

		SchemaElementDefinition IntradayBarElementTickData::elementDefinition() const
		{
			::blpapi_DataType_t dtype = (::blpapi_DataType_t)this->datatype();
			SchemaElementDefinition result(dtype, Name("IntradayBarTickData"));
			return result;
		}

		bool IntradayBarElementTickData::isArray() const
		{
			return false;
		}

		bool IntradayBarElementTickData::isComplexType() const
		{
			return true;
		}

		std::shared_ptr<ElementPtr> IntradayBarElementTickData::getElement(const char* name) const
		{
			if(strncmp(name, "time", 5) == 0)
				return std::dynamic_pointer_cast<ElementPtr>(this->_time);

			else if(strncmp(name, "open", 5) == 0)
				return std::dynamic_pointer_cast<ElementPtr>(this->_open);

			else if(strncmp(name, "high", 5) == 0)
				return std::dynamic_pointer_cast<ElementPtr>(this->_high);

			else if(strncmp(name, "low", 4) == 0)
				return std::dynamic_pointer_cast<ElementPtr>(this->_low);

			else if(strncmp(name, "close", 6) == 0)
				return std::dynamic_pointer_cast<ElementPtr>(this->_close);

			else if(strncmp(name, "value", 6) == 0)
				return std::dynamic_pointer_cast<ElementPtr>(this->_value);

			else if(strncmp(name, "volume", 7) == 0)
				return std::dynamic_pointer_cast<ElementPtr>(this->_volume);

			else if(strncmp(name, "numEvents", 10) == 0)
				return std::dynamic_pointer_cast<ElementPtr>(this->_numEvents);

			else
				throw elementPtrEx;
		}

		bool IntradayBarElementTickData::hasElement(const char* name, bool excludeNullElements) const
		{
			return
				(strncmp(name, "time", 5) == 0) ||
				(strncmp(name, "open", 5) == 0) ||
				(strncmp(name, "high", 5) == 0) ||
				(strncmp(name, "low", 4) == 0) ||
				(strncmp(name, "close", 6) == 0) ||
				(strncmp(name, "value", 6) == 0) ||
				(strncmp(name, "volume", 7) == 0) ||
				(strncmp(name, "numEvents", 10) == 0);
		}

		int IntradayBarElementTickData::getElementAsInt32(const char* name) const
		{
			return this->getElement(name)->getValueAsInt32(0);
		}

		long IntradayBarElementTickData::getElementAsInt64(const char* name) const
		{
			return this->getElement(name)->getValueAsInt64(0);
		}

		Datetime IntradayBarElementTickData::getElementAsDatetime(const char* name) const
		{
			return this->getElement(name)->getValueAsDatetime(0);
		}

		double IntradayBarElementTickData::getElementAsFloat64(const char* name) const
		{
			return this->getElement(name)->getValueAsFloat64(0);
		}

		std::ostream& IntradayBarElementTickData::print(std::ostream& stream, int level, int spacesPerLevel) const
		{
			std::string tabs(IndentType::Indent(level, spacesPerLevel));

			stream << tabs << "barTickData = {" << std::endl;
			this->_time->print(stream, level + 1, spacesPerLevel);
			this->_open->print(stream, level + 1, spacesPerLevel);
			this->_high->print(stream, level + 1, spacesPerLevel);
			this->_low->print(stream, level + 1, spacesPerLevel);
			this->_close->print(stream, level + 1, spacesPerLevel);
			this->_value->print(stream, level + 1, spacesPerLevel);
			this->_volume->print(stream, level + 1, spacesPerLevel);
			this->_numEvents->print(stream, level + 1, spacesPerLevel);
			stream << tabs << '}' << std::endl;

			return stream;
		}
	}
}