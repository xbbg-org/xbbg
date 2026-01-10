//------------------------------------------------------------------------------------------------
// <copyright project="BEmu_cpp" file="src/Types/Rules.cpp" company="Jordan Robinson">
//     Copyright (c) 2013 Jordan Robinson. All rights reserved.
//
//     The use of this software is governed by the Microsoft Public License
//     which is included with this distribution.
// </copyright>
//------------------------------------------------------------------------------------------------

#include "Types/Rules.h"

namespace BEmu
{
	bool Rules::IsSecurityError(const std::string& security)
	{
		return security[0] == 'Z';
	}

	bool Rules::IsBadField(const std::string& field)
	{
		return field[0] == 'Z';
	}
}