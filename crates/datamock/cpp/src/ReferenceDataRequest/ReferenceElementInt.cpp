//------------------------------------------------------------------------------
// <copyright project="BEmu_cpp" file="src/ReferenceDataRequest/ReferenceElementInt.cpp" company="Jordan Robinson">
//     Copyright (c) 2013 Jordan Robinson. All rights reserved.
//
//     The use of this software is governed by the Microsoft Public License
//     which is included with this distribution.
// </copyright>
//------------------------------------------------------------------------------

#include "ReferenceDataRequest/ReferenceElementInt.h"
#include "BloombergTypes/Name.h"
#include <ostream>

namespace BEmu
{
	namespace ReferenceDataRequest
	{
		ReferenceElementInt::ReferenceElementInt(const std::string& name, int value)
		{
			this->_name = name;
			this->_value = value;
		}

		Name ReferenceElementInt::name() const { return Name(this->_name.c_str()); }
		size_t ReferenceElementInt::numValues() const { return 1; }
		size_t ReferenceElementInt::numElements() const { return 0; }

		bool ReferenceElementInt::isNull() const { return false; }
		bool ReferenceElementInt::isArray() const { return false; }
		bool ReferenceElementInt::isComplexType() const { return false; }

		int ReferenceElementInt::getValueAsInt32(int index) const
		{
			return this->_value;
		}

		long ReferenceElementInt::getValueAsInt64(int index) const
		{
			return (long)this->_value;
		}

		std::ostream& ReferenceElementInt::print(std::ostream& stream, int level, int spacesPerLevel) const
		{
			this->prettyPrintHelper(stream, level, spacesPerLevel, this->_value);
			return stream;
		}

	}
}