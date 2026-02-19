//------------------------------------------------------------------------------------------------
// <copyright project="BEmu_cpp" file="src/Types/IndentType.cpp" company="Jordan Robinson">
//     Copyright (c) 2013 Jordan Robinson. All rights reserved.
//
//     The use of this software is governed by the Microsoft Public License
//     which is included with this distribution.
// </copyright>
//------------------------------------------------------------------------------------------------

#include "Types/IndentType.h"

namespace BEmu
{
	std::string IndentType::Indent(int count, int spacesPerTab)
	{
		std::string result(count * spacesPerTab, ' ');
		return result;
	}
}