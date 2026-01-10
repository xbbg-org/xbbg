//------------------------------------------------------------------------------------------------
// <copyright project="BEmu_cpp" file="headers/BloombergTypes/SchemaElementDefinition.h" company="Jordan Robinson">
//     Copyright (c) 2013 Jordan Robinson. All rights reserved.
//
//     The use of this software is governed by the Microsoft Public License
//     which is included with this distribution.
// </copyright>
//------------------------------------------------------------------------------------------------

#pragma once

#include "bemu_headers.h"
#include "BloombergTypes/Name.h"
#include "BloombergTypes/Datatypes.h"

namespace BEmu
{
	class SchemaElementDefinition
	{
		private:
			Name _name;
			::blpapi_DataType_t _datatype;

		public:
			SchemaElementDefinition(::blpapi_DataType_t datatype);
			SchemaElementDefinition(::blpapi_DataType_t datatype, Name name);

			SchemaElementDefinition& operator=(const SchemaElementDefinition &rhs);
			SchemaElementDefinition(const SchemaElementDefinition& arg);

			DLL_EXPORT Name name() const;
			DLL_EXPORT std::ostream& print(std::ostream& stream, int level = 0, int spacesPerLevel = 4) const;
	};

	DLL_EXPORT std::ostream& operator<<(std::ostream& stream, const SchemaElementDefinition& element);
}