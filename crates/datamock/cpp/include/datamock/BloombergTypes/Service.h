//------------------------------------------------------------------------------------------------
// <copyright project="BEmu_cpp" file="headers/BloombergTypes/Service.h" company="Jordan Robinson">
//     Copyright (c) 2013 Jordan Robinson. All rights reserved.
//
//     The use of this software is governed by the Microsoft Public License
//     which is included with this distribution.
// </copyright>
//------------------------------------------------------------------------------------------------

#pragma once

#include "bemu_headers.h"
#include "BloombergTypes/Request.h"
#include "BloombergTypes/RequestPtr.h"

namespace BEmu
{
	class Service
	{
		public:
			DLL_EXPORT Service();
			DLL_EXPORT virtual ~Service() = default;
			DLL_EXPORT Service(const Service& arg);
			DLL_EXPORT Service& operator=(const Service &rhs);

			DLL_EXPORT virtual Request createRequest(const char* operation) const;			
			DLL_EXPORT virtual const char* name() const;
	};
}
