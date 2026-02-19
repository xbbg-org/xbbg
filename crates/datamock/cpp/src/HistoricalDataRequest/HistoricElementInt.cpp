//------------------------------------------------------------------------------
// <copyright project="BEmu_cpp" file="src/HistoricalDataRequest/HistoricElementInt.cpp" company="Jordan Robinson">
//     Copyright (c) 2013 Jordan Robinson. All rights reserved.
//
//     The use of this software is governed by the Microsoft Public License
//     which is included with this distribution.
// </copyright>
//------------------------------------------------------------------------------

#include "HistoricalDataRequest/HistoricElementInt.h"

#include "BloombergTypes/Name.h"
#include <ostream>

namespace BEmu
{
	namespace HistoricalDataRequest
	{
		HistoricElementInt::HistoricElementInt(const std::string& name, int value) : CanConvertToStringType(value)
		{
			this->_name = name;
			this->_value = value;
		}

		HistoricElementInt::~HistoricElementInt()
		{
		}


		Name HistoricElementInt::name() const
		{
			Name result(this->_name.c_str());
			return result;
		}

		size_t HistoricElementInt::numValues() const
		{
			return 1;
		}

		size_t HistoricElementInt::numElements() const
		{
			return 0;
		}

		
		bool HistoricElementInt::isArray() const
		{
			return false;
		}

		bool HistoricElementInt::isComplexType() const
		{
			return false;
		}


		int HistoricElementInt::getValueAsInt32(int index) const
		{
			if(index == 0)
				return this->_value;
			else
				throw elementPtrEx;
		}

		long HistoricElementInt::getValueAsInt64(int index) const
		{
			if(index == 0)
				return (long)this->_value;
			else
				throw elementPtrEx;
		}

		float HistoricElementInt::getValueAsFloat32(int index) const
		{
			if(index == 0)
				return (float)this->_value;
			else
				throw elementPtrEx;
		}

		double HistoricElementInt::getValueAsFloat64(int index) const
		{
			if(index == 0)
				return (double)this->_value;
			else
				throw elementPtrEx;
		}

		const char * HistoricElementInt::getValueAsString(int index) const
		{
			if(index == 0)
				return this->ValueAsString().c_str();
			else
				throw elementPtrEx;
		}


		std::ostream& HistoricElementInt::print(std::ostream& stream, int level, int spacesPerLevel) const
		{
			ElementPtr::prettyPrintHelper(stream, level, spacesPerLevel, this->_value);
			return stream;
		}

	}
}