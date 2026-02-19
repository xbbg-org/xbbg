//------------------------------------------------------------------------------------------------
// <copyright project="BEmu_cpp" file="headers/BloombergTypes/SchemaStatus.h" company="Jordan Robinson">
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
	struct SchemaStatus
	{
		enum Value
		{
			ACTIVE = 0,
			DEPRECATED = 1,
			INACTIVE = 2,
			PENDING_DEPRECATION = 3
		};
	};
}