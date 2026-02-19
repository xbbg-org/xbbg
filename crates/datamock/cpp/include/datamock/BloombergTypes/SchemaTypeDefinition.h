//------------------------------------------------------------------------------------------------
// <copyright project="BEmu_cpp" file="headers/BloombergTypes/SchemaTypeDefinition.h" company="Jordan Robinson">
//     Copyright (c) 2013 Jordan Robinson. All rights reserved.
//
//     The use of this software is governed by the Microsoft Public License
//     which is included with this distribution.
// </copyright>
//------------------------------------------------------------------------------------------------

#pragma once

#include "bemu_headers.h"
#include "BloombergTypes/Name.h"
#include "BloombergTypes/ConstantList.h"
#include "BloombergTypes/SchemaElementDefinition.h"

namespace BEmu
{
	class SchemaTypeDefinition
	{
		public:
			DLL_EXPORT ~SchemaTypeDefinition();

			DLL_EXPORT void setUserData(void *userData);
			DLL_EXPORT int datatype() const;
			DLL_EXPORT Name name() const;
			DLL_EXPORT const char *description() const;
			DLL_EXPORT int status() const;
			DLL_EXPORT size_t numElementDefinitions() const;
			DLL_EXPORT bool isComplexType() const;
			DLL_EXPORT bool isSimpleType() const;
			DLL_EXPORT bool isEnumerationType() const;
			DLL_EXPORT bool hasElementDefinition(const Name& name) const;
			DLL_EXPORT bool hasElementDefinition(const char *name) const;
			DLL_EXPORT SchemaElementDefinition getElementDefinition(const Name& name) const;
			DLL_EXPORT SchemaElementDefinition getElementDefinition(const char *nameString) const;
			DLL_EXPORT SchemaElementDefinition getElementDefinition(size_t index) const;
			DLL_EXPORT const ConstantList enumeration() const;
			DLL_EXPORT void *userData() const;
			DLL_EXPORT std::ostream& print(std::ostream& stream, int level = 0, int spacesPerLevel = 4) const;
	};

	DLL_EXPORT std::ostream& operator<<(std::ostream& stream, const SchemaTypeDefinition& typeDef);
}