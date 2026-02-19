//------------------------------------------------------------------------------
// <copyright project="BEmu_cpp" file="src/ReferenceDataRequest/ReferenceElementDouble.cpp" company="Jordan Robinson">
//     Copyright (c) 2013 Jordan Robinson. All rights reserved.
//
//     The use of this software is governed by the Microsoft Public License
//     which is included with this distribution.
// </copyright>
//------------------------------------------------------------------------------

#include "ReferenceDataRequest/ReferenceElementDouble.h"
#include "BloombergTypes/Name.h"
#include <ostream>

namespace BEmu
{
	namespace ReferenceDataRequest
	{
		ReferenceElementDouble::ReferenceElementDouble(const std::string& name, double value)
		{
			this->_name = name;
			this->_value = value;
		}

		Name ReferenceElementDouble::name() const { return Name(this->_name.c_str()); }
		size_t ReferenceElementDouble::numValues() const { return 1; }
		size_t ReferenceElementDouble::numElements() const { return 0; }

		bool ReferenceElementDouble::isNull() const { return false; }
		bool ReferenceElementDouble::isArray() const { return false; }
		bool ReferenceElementDouble::isComplexType() const { return false; }

		double ReferenceElementDouble::getValueAsFloat64(int index) const
		{
			if(index == 0)
				return this->_value;
			else
				throw elementPtrEx;
		}

		int ReferenceElementDouble::getValueAsInt32(int index) const
		{
			if(index == 0)
				return (int)this->_value;
			else
				throw elementPtrEx;
		}

		long ReferenceElementDouble::getValueAsInt64(int index) const
		{
			if(index == 0)
				return (long)this->_value;
			else
				throw elementPtrEx;
		}

		std::ostream& ReferenceElementDouble::print(std::ostream& stream, int level, int spacesPerLevel) const
		{
			this->prettyPrintHelper(stream, level, spacesPerLevel, this->_value);
			return stream;
		}

	}
}