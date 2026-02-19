//------------------------------------------------------------------------------------------------
// <copyright project="BEmu_cpp" file="headers/Types/IndentType.h" company="Jordan Robinson">
//     Copyright (c) 2013 Jordan Robinson. All rights reserved.
//
//     The use of this software is governed by the Microsoft Public License
//     which is included with this distribution.
// </copyright>
//------------------------------------------------------------------------------------------------

#pragma once

#include "bemu_headers.h"

namespace BEmu
{
	class IndentType
	{
		public:
			static std::string Indent(int count, int spacesPerTab);
	};
}