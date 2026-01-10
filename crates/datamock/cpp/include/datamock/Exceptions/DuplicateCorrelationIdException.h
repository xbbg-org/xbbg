//------------------------------------------------------------------------------------------------
// <copyright project="BEmu_cpp" file="headers/Exceptions/DuplicateCorrelationIdException.h" company="Jordan Robinson">
//     Copyright (c) 2013 Jordan Robinson. All rights reserved.
//
//     The use of this software is governed by the Microsoft Public License
//     which is included with this distribution.
// </copyright>
//------------------------------------------------------------------------------------------------

#pragma once

#include "bemu_headers.h"
#include "Exceptions/Exception.h"

namespace BEmu
{
	class DuplicateCorrelationIdException : public Exception
	{
		public:
			DuplicateCorrelationIdException(const std::string &description) : Exception(description)
			{
			}
	};
}