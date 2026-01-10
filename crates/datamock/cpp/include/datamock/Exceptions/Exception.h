//------------------------------------------------------------------------------------------------
// <copyright project="BEmu_cpp" file="headers/Exceptions/Exception.h" company="Jordan Robinson">
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
	class Exception
	{
		private:
			std::string _description;

		public:
			Exception(const std::string description) : _description(description)
			{
			}

			const std::string& description() const { return this->_description; }
	};
}