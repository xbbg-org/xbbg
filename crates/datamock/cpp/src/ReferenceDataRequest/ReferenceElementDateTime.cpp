//------------------------------------------------------------------------------
// <copyright project="BEmu_cpp" file="src/ReferenceDataRequest/ReferenceElementDateTime.cpp" company="Jordan Robinson">
//     Copyright (c) 2013 Jordan Robinson. All rights reserved.
//
//     The use of this software is governed by the Microsoft Public License
//     which is included with this distribution.
// </copyright>
//------------------------------------------------------------------------------

#include "ReferenceDataRequest/ReferenceElementDateTime.h"
#include "BloombergTypes/Name.h"
#include "Types/DisplayFormats.h"
#include <ostream>

namespace BEmu
{
	namespace ReferenceDataRequest
	{
		ReferenceElementDateTime::ReferenceElementDateTime(const std::string& name, const Datetime& value)
		{
			this->_name = name;
			this->_value = value;
		}

		Name ReferenceElementDateTime::name() const { return Name(this->_name.c_str()); }
		size_t ReferenceElementDateTime::numValues() const { return 1; }
		size_t ReferenceElementDateTime::numElements() const { return 0; }

		bool ReferenceElementDateTime::isNull() const { return false; }
		bool ReferenceElementDateTime::isArray() const { return false; }
		bool ReferenceElementDateTime::isComplexType() const { return false; }

		Datetime ReferenceElementDateTime::getValueAsDatetime(int index) const
		{
			if(index == 0)
				return this->_value;

			else
				throw elementPtrEx;
		}

		std::ostream& ReferenceElementDateTime::print(std::ostream& stream, int level, int spacesPerLevel) const
		{
			this->prettyPrintHelper(stream, level, spacesPerLevel, DisplayFormats::FormatDatetimeZone(this->_value));
			return stream;
		}

	}
}