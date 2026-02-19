//------------------------------------------------------------------------------
// <copyright project="BEmu_cpp" file="src/HistoricalDataRequest/HistoricElementDouble.cpp" company="Jordan Robinson">
//     Copyright (c) 2013 Jordan Robinson. All rights reserved.
//
//     The use of this software is governed by the Microsoft Public License
//     which is included with this distribution.
// </copyright>
//------------------------------------------------------------------------------

#include "HistoricalDataRequest/HistoricElementDouble.h"
#include "BloombergTypes/Name.h"
#include <ostream>

namespace BEmu
{
	namespace HistoricalDataRequest
	{
		HistoricElementDouble::HistoricElementDouble(const std::string& name, double value) : CanConvertToStringType(value)
		{
			this->_name = name;
			this->_value = value;
		}

		HistoricElementDouble::~HistoricElementDouble()
		{
		}

		Name HistoricElementDouble::name() const
		{
			Name result(this->_name.c_str());
			return result;
		}

		int HistoricElementDouble::getValueAsInt32(int index) const
		{
			if(index == 0)
				return (int)this->_value;
			else
				throw elementPtrEx;
		}

		long HistoricElementDouble::getValueAsInt64(int index) const
		{
			if(index == 0)
				return (long)this->_value;
			else
				throw elementPtrEx;
		}

		float HistoricElementDouble::getValueAsFloat32(int index) const
		{
			if(index == 0)
				return (float)this->_value;
			else
				throw elementPtrEx;
		}

		double HistoricElementDouble::getValueAsFloat64(int index) const
		{
			if(index == 0)
				return this->_value;
			else
				throw elementPtrEx;
		}

		const char * HistoricElementDouble::getValueAsString(int index) const
		{
			if(index == 0)
			{
				return this->ValueAsString().c_str();
			}
			else
				throw elementPtrEx;
		}

		std::ostream& HistoricElementDouble::print(std::ostream& stream, int level, int spacesPerLevel) const
		{
			ElementPtr::prettyPrintHelper(stream, level, spacesPerLevel, this->_value);
			return stream;
		}
	}
}