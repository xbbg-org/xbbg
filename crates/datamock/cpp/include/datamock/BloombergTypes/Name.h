//------------------------------------------------------------------------------------------------
// <copyright project="BEmu_cpp" file="headers/BloombergTypes/Name.h" company="Jordan Robinson">
//     Copyright (c) 2013 Jordan Robinson. All rights reserved.
//
//     The use of this software is governed by the Microsoft Public License
//     which is included with this distribution.
// </copyright>
//------------------------------------------------------------------------------------------------

#pragma once

#include "bemu_headers.h"
#include <map>

namespace BEmu
{
	class Name
	{
		private:
			std::string _name;
			const char * _cname;
			int _length;
			bool _isNull;
			static std::map<std::string, Name> _globalNameTable;

		public:
			DLL_EXPORT Name();
			DLL_EXPORT explicit Name(const char* nameString);
			DLL_EXPORT Name(const Name& original);
			DLL_EXPORT const char *string() const;
			DLL_EXPORT Name& operator=(const Name &rhs);

			DLL_EXPORT size_t length() const;
			DLL_EXPORT size_t hash() const;

			DLL_EXPORT static Name findName(const char *nameString);
			DLL_EXPORT static bool hasName(const char *nameString);

			static void clearGlobalNameTable();
			bool isNull() const;
	};

	DLL_EXPORT std::ostream& operator<<(std::ostream& stream, const Name& name);
				
	DLL_EXPORT bool operator==(const Name& lhs, const char *rhs);
	DLL_EXPORT bool operator==(const Name& lhs, const Name rhs);
	DLL_EXPORT bool operator!=(const Name& lhs, const char *rhs);
	DLL_EXPORT bool operator!=(const Name& lhs, const Name rhs);

	DLL_EXPORT bool operator==(const char *lhs, const Name& rhs);
	DLL_EXPORT bool operator!=(const char *lhs, const Name& rhs);

	//Note that while the order of these operations are consistent, they are not guaranteed to be lexical (this is the same in the BB API)
	DLL_EXPORT bool operator<(const Name& lhs, const Name& rhs);
	DLL_EXPORT bool operator<=(const Name& lhs, const Name& rhs);
	DLL_EXPORT bool operator>(const Name& lhs, const Name& rhs);
	DLL_EXPORT bool operator>=(const Name& lhs, const Name& rhs);
}